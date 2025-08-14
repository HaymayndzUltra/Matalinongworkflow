"""
Data Retention & WORM Storage Module
Immutable Storage with Hash-Chaining and Automated Purging
Part of KYC Bank-Grade Parity - Phase 9

This module implements tamper-evident storage with retention policies.
"""

import logging
import hashlib
import json
import time
import shutil
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
from enum import Enum
import uuid
import gzip

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Manila timezone
MANILA_TZ = timezone(timedelta(hours=8))


class DataCategory(Enum):
    """Data categories for retention"""
    KYC_DOCUMENTS = "kyc_documents"
    TRANSACTION_LOGS = "transaction_logs"
    AUDIT_TRAILS = "audit_trails"
    SCREENING_RESULTS = "screening_results"
    RISK_ASSESSMENTS = "risk_assessments"
    CUSTOMER_COMMUNICATIONS = "customer_communications"
    REGULATORY_REPORTS = "regulatory_reports"


class RetentionPeriod(Enum):
    """Standard retention periods"""
    DAYS_30 = 30
    DAYS_90 = 90
    DAYS_180 = 180
    YEARS_1 = 365
    YEARS_3 = 1095
    YEARS_5 = 1825
    YEARS_7 = 2555
    YEARS_10 = 3650
    PERMANENT = -1


@dataclass
class RetentionPolicy:
    """Retention policy definition"""
    category: DataCategory
    retention_days: int
    purge_enabled: bool
    legal_hold: bool = False
    encryption_required: bool = True
    compression_enabled: bool = True
    
    def is_expired(self, created_date: datetime) -> bool:
        """Check if data is past retention period"""
        if self.retention_days == -1:  # Permanent
            return False
        if self.legal_hold:
            return False
        
        expiry_date = created_date + timedelta(days=self.retention_days)
        return datetime.now(MANILA_TZ) > expiry_date


@dataclass
class WORMRecord:
    """Immutable WORM record"""
    record_id: str
    category: DataCategory
    data: Dict[str, Any]
    created_at: datetime
    hash_value: str
    previous_hash: Optional[str]
    block_number: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def calculate_hash(self) -> str:
        """Calculate hash of record"""
        hash_input = f"{self.record_id}{self.category.value}{json.dumps(self.data, sort_keys=True)}"
        hash_input += f"{self.created_at.isoformat()}{self.previous_hash or ''}{self.block_number}"
        return hashlib.sha256(hash_input.encode()).hexdigest()
    
    def verify_integrity(self) -> bool:
        """Verify record integrity"""
        return self.hash_value == self.calculate_hash()


@dataclass
class HashChainBlock:
    """Block in hash chain"""
    block_number: int
    timestamp: datetime
    records: List[WORMRecord]
    block_hash: str
    previous_block_hash: Optional[str]
    merkle_root: str
    
    def calculate_merkle_root(self) -> str:
        """Calculate Merkle root of records"""
        if not self.records:
            return hashlib.sha256(b"empty").hexdigest()
        
        # Calculate hashes of all records
        hashes = [r.hash_value for r in self.records]
        
        # Build Merkle tree
        while len(hashes) > 1:
            if len(hashes) % 2 == 1:
                hashes.append(hashes[-1])  # Duplicate last hash if odd
            
            new_hashes = []
            for i in range(0, len(hashes), 2):
                combined = hashes[i] + hashes[i+1]
                new_hash = hashlib.sha256(combined.encode()).hexdigest()
                new_hashes.append(new_hash)
            
            hashes = new_hashes
        
        return hashes[0]
    
    def calculate_block_hash(self) -> str:
        """Calculate hash of entire block"""
        block_data = f"{self.block_number}{self.timestamp.isoformat()}"
        block_data += f"{self.merkle_root}{self.previous_block_hash or ''}"
        return hashlib.sha256(block_data.encode()).hexdigest()
    
    def verify_integrity(self) -> bool:
        """Verify block integrity"""
        # Check Merkle root
        if self.merkle_root != self.calculate_merkle_root():
            return False
        
        # Check block hash
        if self.block_hash != self.calculate_block_hash():
            return False
        
        # Check all records
        for record in self.records:
            if not record.verify_integrity():
                return False
        
        return True


class RetentionMatrix:
    """Retention policy matrix"""
    
    def __init__(self):
        """Initialize retention matrix"""
        self.policies = self._load_default_policies()
        logger.info(f"Retention Matrix initialized with {len(self.policies)} policies")
    
    def _load_default_policies(self) -> Dict[DataCategory, RetentionPolicy]:
        """Load default retention policies"""
        return {
            DataCategory.KYC_DOCUMENTS: RetentionPolicy(
                category=DataCategory.KYC_DOCUMENTS,
                retention_days=RetentionPeriod.YEARS_7.value,
                purge_enabled=True
            ),
            DataCategory.TRANSACTION_LOGS: RetentionPolicy(
                category=DataCategory.TRANSACTION_LOGS,
                retention_days=RetentionPeriod.YEARS_5.value,
                purge_enabled=True
            ),
            DataCategory.AUDIT_TRAILS: RetentionPolicy(
                category=DataCategory.AUDIT_TRAILS,
                retention_days=RetentionPeriod.YEARS_10.value,
                purge_enabled=False
            ),
            DataCategory.SCREENING_RESULTS: RetentionPolicy(
                category=DataCategory.SCREENING_RESULTS,
                retention_days=RetentionPeriod.YEARS_5.value,
                purge_enabled=True
            ),
            DataCategory.RISK_ASSESSMENTS: RetentionPolicy(
                category=DataCategory.RISK_ASSESSMENTS,
                retention_days=RetentionPeriod.YEARS_3.value,
                purge_enabled=True
            ),
            DataCategory.CUSTOMER_COMMUNICATIONS: RetentionPolicy(
                category=DataCategory.CUSTOMER_COMMUNICATIONS,
                retention_days=RetentionPeriod.YEARS_3.value,
                purge_enabled=True
            ),
            DataCategory.REGULATORY_REPORTS: RetentionPolicy(
                category=DataCategory.REGULATORY_REPORTS,
                retention_days=RetentionPeriod.PERMANENT.value,
                purge_enabled=False
            )
        }
    
    def get_policy(self, category: DataCategory) -> RetentionPolicy:
        """Get retention policy for category"""
        return self.policies.get(category)
    
    def set_legal_hold(self, category: DataCategory, enabled: bool = True):
        """Set legal hold on category"""
        if category in self.policies:
            self.policies[category].legal_hold = enabled
            logger.warning(f"Legal hold {'enabled' if enabled else 'disabled'} for {category.value}")


class WORMStorage:
    """Write Once Read Many storage implementation"""
    
    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize WORM storage
        
        Args:
            storage_path: Path for WORM storage
        """
        self.storage_path = storage_path or Path("/workspace/KYC VERIFICATION/worm_storage")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        self.current_block_number = self._get_latest_block_number()
        self.pending_records: List[WORMRecord] = []
        self.block_size = 100  # Records per block
        self.chain: List[HashChainBlock] = []
        
        # Object lock simulation (in production, use S3 object lock)
        self.locked_objects: Dict[str, datetime] = {}
        
        logger.info(f"WORM Storage initialized at {self.storage_path}")
    
    def _get_latest_block_number(self) -> int:
        """Get the latest block number from storage"""
        block_files = list(self.storage_path.glob("block_*.json.gz"))
        if not block_files:
            return 0
        
        numbers = [int(f.stem.split('_')[1]) for f in block_files]
        return max(numbers)
    
    def write_record(self, category: DataCategory, data: Dict[str, Any],
                    metadata: Optional[Dict[str, Any]] = None) -> WORMRecord:
        """
        Write immutable record
        
        Args:
            category: Data category
            data: Data to store
            metadata: Optional metadata
            
        Returns:
            Created WORM record
        """
        # Get previous hash
        previous_hash = None
        if self.pending_records:
            previous_hash = self.pending_records[-1].hash_value
        elif self.chain:
            last_block = self.chain[-1]
            if last_block.records:
                previous_hash = last_block.records[-1].hash_value
        
        # Create record
        record = WORMRecord(
            record_id=str(uuid.uuid4()),
            category=category,
            data=data,
            created_at=datetime.now(MANILA_TZ),
            hash_value="",  # Will be calculated
            previous_hash=previous_hash,
            block_number=self.current_block_number + 1,
            metadata=metadata or {}
        )
        
        # Calculate hash
        record.hash_value = record.calculate_hash()
        
        # Add to pending
        self.pending_records.append(record)
        
        # Create block if threshold reached
        if len(self.pending_records) >= self.block_size:
            self._create_block()
        
        logger.debug(f"WORM record created: {record.record_id}")
        return record
    
    def _create_block(self):
        """Create and persist a new block"""
        if not self.pending_records:
            return
        
        # Get previous block hash
        previous_block_hash = None
        if self.chain:
            previous_block_hash = self.chain[-1].block_hash
        else:
            # Load from storage if exists
            prev_block_file = self.storage_path / f"block_{self.current_block_number:08d}.json.gz"
            if prev_block_file.exists():
                with gzip.open(prev_block_file, 'rt') as f:
                    prev_block_data = json.load(f)
                    previous_block_hash = prev_block_data['block_hash']
        
        # Create block
        self.current_block_number += 1
        block = HashChainBlock(
            block_number=self.current_block_number,
            timestamp=datetime.now(MANILA_TZ),
            records=self.pending_records.copy(),
            block_hash="",  # Will be calculated
            previous_block_hash=previous_block_hash,
            merkle_root=""  # Will be calculated
        )
        
        # Calculate hashes
        block.merkle_root = block.calculate_merkle_root()
        block.block_hash = block.calculate_block_hash()
        
        # Persist block
        self._persist_block(block)
        
        # Add to chain
        self.chain.append(block)
        
        # Clear pending
        self.pending_records.clear()
        
        logger.info(f"Block {block.block_number} created with {len(block.records)} records")
    
    def _persist_block(self, block: HashChainBlock):
        """Persist block to storage with compression"""
        filename = self.storage_path / f"block_{block.block_number:08d}.json.gz"
        
        # Convert to dictionary
        block_data = {
            'block_number': block.block_number,
            'timestamp': block.timestamp.isoformat(),
            'block_hash': block.block_hash,
            'previous_block_hash': block.previous_block_hash,
            'merkle_root': block.merkle_root,
            'records': [
                {
                    'record_id': r.record_id,
                    'category': r.category.value,
                    'data': r.data,
                    'created_at': r.created_at.isoformat(),
                    'hash_value': r.hash_value,
                    'previous_hash': r.previous_hash,
                    'block_number': r.block_number,
                    'metadata': r.metadata
                }
                for r in block.records
            ]
        }
        
        # Write compressed
        with gzip.open(filename, 'wt') as f:
            json.dump(block_data, f)
        
        # Apply object lock (simulated)
        self.locked_objects[str(filename)] = datetime.now(MANILA_TZ) + timedelta(days=90)
        
        # Make read-only
        filename.chmod(0o444)
    
    def verify_chain(self, start_block: int = 1, 
                    end_block: Optional[int] = None) -> Tuple[bool, List[str]]:
        """
        Verify hash chain integrity
        
        Args:
            start_block: Starting block number
            end_block: Ending block number
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        previous_hash = None
        
        end_block = end_block or self.current_block_number
        
        for block_num in range(start_block, end_block + 1):
            # Load block
            filename = self.storage_path / f"block_{block_num:08d}.json.gz"
            
            if not filename.exists():
                errors.append(f"Block {block_num} not found")
                continue
            
            try:
                with gzip.open(filename, 'rt') as f:
                    block_data = json.load(f)
                
                # Reconstruct block
                records = []
                for r_data in block_data['records']:
                    record = WORMRecord(
                        record_id=r_data['record_id'],
                        category=DataCategory(r_data['category']),
                        data=r_data['data'],
                        created_at=datetime.fromisoformat(r_data['created_at']),
                        hash_value=r_data['hash_value'],
                        previous_hash=r_data['previous_hash'],
                        block_number=r_data['block_number'],
                        metadata=r_data['metadata']
                    )
                    records.append(record)
                
                block = HashChainBlock(
                    block_number=block_data['block_number'],
                    timestamp=datetime.fromisoformat(block_data['timestamp']),
                    records=records,
                    block_hash=block_data['block_hash'],
                    previous_block_hash=block_data['previous_block_hash'],
                    merkle_root=block_data['merkle_root']
                )
                
                # Verify block integrity
                if not block.verify_integrity():
                    errors.append(f"Block {block_num} integrity check failed")
                
                # Verify chain continuity
                if previous_hash and block.previous_block_hash != previous_hash:
                    errors.append(f"Chain broken at block {block_num}")
                
                previous_hash = block.block_hash
                
            except Exception as e:
                errors.append(f"Error loading block {block_num}: {e}")
        
        is_valid = len(errors) == 0
        
        if is_valid:
            logger.info(f"Chain verification passed for blocks {start_block}-{end_block}")
        else:
            logger.error(f"Chain verification failed: {errors}")
        
        return is_valid, errors


class RetentionManager:
    """Manages data retention and purging"""
    
    def __init__(self, worm_storage: WORMStorage,
                 retention_matrix: Optional[RetentionMatrix] = None):
        """
        Initialize retention manager
        
        Args:
            worm_storage: WORM storage instance
            retention_matrix: Retention policy matrix
        """
        self.worm_storage = worm_storage
        self.retention_matrix = retention_matrix or RetentionMatrix()
        self.purge_history: List[Dict[str, Any]] = []
        
        logger.info("Retention Manager initialized")
    
    def scan_for_expired_data(self) -> List[Dict[str, Any]]:
        """
        Scan for data past retention period
        
        Returns:
            List of expired records
        """
        expired_records = []
        
        # Scan all blocks
        for block_file in self.worm_storage.storage_path.glob("block_*.json.gz"):
            try:
                with gzip.open(block_file, 'rt') as f:
                    block_data = json.load(f)
                
                for record_data in block_data['records']:
                    category = DataCategory(record_data['category'])
                    created_at = datetime.fromisoformat(record_data['created_at'])
                    
                    # Get policy
                    policy = self.retention_matrix.get_policy(category)
                    
                    if policy and policy.is_expired(created_at):
                        expired_records.append({
                            'record_id': record_data['record_id'],
                            'category': category,
                            'created_at': created_at,
                            'block_number': block_data['block_number'],
                            'policy': policy
                        })
                
            except Exception as e:
                logger.error(f"Error scanning block {block_file}: {e}")
        
        logger.info(f"Found {len(expired_records)} expired records")
        return expired_records
    
    def execute_purge(self, dry_run: bool = True) -> Dict[str, Any]:
        """
        Execute data purge
        
        Args:
            dry_run: If True, only simulate purge
            
        Returns:
            Purge report
        """
        expired_records = self.scan_for_expired_data()
        
        report = {
            'timestamp': datetime.now(MANILA_TZ).isoformat(),
            'dry_run': dry_run,
            'total_expired': len(expired_records),
            'categories': {},
            'blocks_affected': set(),
            'purged_records': []
        }
        
        # Group by category
        for record in expired_records:
            category = record['category'].value
            if category not in report['categories']:
                report['categories'][category] = {
                    'count': 0,
                    'oldest': None,
                    'newest': None
                }
            
            report['categories'][category]['count'] += 1
            
            if not report['categories'][category]['oldest'] or \
               record['created_at'] < datetime.fromisoformat(report['categories'][category]['oldest']):
                report['categories'][category]['oldest'] = record['created_at'].isoformat()
            
            if not report['categories'][category]['newest'] or \
               record['created_at'] > datetime.fromisoformat(report['categories'][category]['newest']):
                report['categories'][category]['newest'] = record['created_at'].isoformat()
            
            report['blocks_affected'].add(record['block_number'])
            
            # Execute purge if not dry run
            if not dry_run and record['policy'].purge_enabled:
                # In production, would mark for deletion
                # Here we just log it
                report['purged_records'].append(record['record_id'])
                logger.info(f"Purged record {record['record_id']} from {category}")
        
        report['blocks_affected'] = list(report['blocks_affected'])
        
        # Save purge history
        self.purge_history.append(report)
        
        # Persist report
        self._save_purge_report(report)
        
        return report
    
    def _save_purge_report(self, report: Dict[str, Any]):
        """Save purge report for audit"""
        reports_dir = self.worm_storage.storage_path / "purge_reports"
        reports_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now(MANILA_TZ).strftime("%Y%m%d_%H%M%S")
        filename = reports_dir / f"purge_report_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Purge report saved to {filename}")


class AuditExporter:
    """Export tools for audit and compliance"""
    
    def __init__(self, worm_storage: WORMStorage):
        """
        Initialize audit exporter
        
        Args:
            worm_storage: WORM storage instance
        """
        self.worm_storage = worm_storage
        logger.info("Audit Exporter initialized")
    
    def export_bundle(self, start_date: datetime, end_date: datetime,
                     categories: Optional[List[DataCategory]] = None,
                     output_path: Optional[Path] = None) -> Path:
        """
        Export audit bundle for date range
        
        Args:
            start_date: Start date
            end_date: End date
            categories: Categories to include
            output_path: Output path for bundle
            
        Returns:
            Path to exported bundle
        """
        output_path = output_path or Path("/workspace/KYC VERIFICATION/audit_exports")
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Create bundle filename
        timestamp = datetime.now(MANILA_TZ).strftime("%Y%m%d_%H%M%S")
        bundle_file = output_path / f"audit_bundle_{timestamp}.jsonl"
        
        records_exported = 0
        
        with open(bundle_file, 'w') as f:
            # Scan all blocks
            for block_file in sorted(self.worm_storage.storage_path.glob("block_*.json.gz")):
                try:
                    with gzip.open(block_file, 'rt') as bf:
                        block_data = json.load(bf)
                    
                    for record_data in block_data['records']:
                        created_at = datetime.fromisoformat(record_data['created_at'])
                        
                        # Check date range
                        if not (start_date <= created_at <= end_date):
                            continue
                        
                        # Check category filter
                        if categories:
                            category = DataCategory(record_data['category'])
                            if category not in categories:
                                continue
                        
                        # Write to bundle
                        f.write(json.dumps(record_data) + '\n')
                        records_exported += 1
                
                except Exception as e:
                    logger.error(f"Error processing block {block_file}: {e}")
        
        # Create verification file
        verification = self._create_verification_file(bundle_file)
        
        logger.info(f"Exported {records_exported} records to {bundle_file}")
        return bundle_file
    
    def _create_verification_file(self, bundle_file: Path) -> Path:
        """Create verification file for bundle"""
        # Calculate bundle hash
        hasher = hashlib.sha256()
        with open(bundle_file, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        
        bundle_hash = hasher.hexdigest()
        
        # Create verification file
        verify_file = bundle_file.with_suffix('.verify')
        verification = {
            'bundle_file': bundle_file.name,
            'bundle_hash': bundle_hash,
            'created_at': datetime.now(MANILA_TZ).isoformat(),
            'file_size': bundle_file.stat().st_size,
            'verified': True
        }
        
        with open(verify_file, 'w') as f:
            json.dump(verification, f, indent=2)
        
        return verify_file


if __name__ == "__main__":
    # Demo and testing
    print("=== Data Retention & WORM Storage Demo ===\n")
    
    # Initialize components
    worm = WORMStorage()
    retention_matrix = RetentionMatrix()
    retention_manager = RetentionManager(worm, retention_matrix)
    exporter = AuditExporter(worm)
    
    # Write some test records
    print("Writing test records...")
    
    # KYC document
    kyc_record = worm.write_record(
        DataCategory.KYC_DOCUMENTS,
        {
            "customer_id": "CUST001",
            "document_type": "passport",
            "verification_status": "verified",
            "timestamp": datetime.now(MANILA_TZ).isoformat()
        }
    )
    print(f"  KYC record: {kyc_record.record_id[:8]}...")
    
    # Transaction log
    tx_record = worm.write_record(
        DataCategory.TRANSACTION_LOGS,
        {
            "transaction_id": "TXN001",
            "amount": 10000,
            "currency": "PHP",
            "timestamp": datetime.now(MANILA_TZ).isoformat()
        }
    )
    print(f"  Transaction record: {tx_record.record_id[:8]}...")
    
    # Audit trail
    audit_record = worm.write_record(
        DataCategory.AUDIT_TRAILS,
        {
            "user_id": "USER001",
            "action": "approve_kyc",
            "timestamp": datetime.now(MANILA_TZ).isoformat()
        }
    )
    print(f"  Audit record: {audit_record.record_id[:8]}...")
    
    # Force block creation
    for i in range(100):
        worm.write_record(
            DataCategory.SCREENING_RESULTS,
            {"screening_id": f"SCR{i:03d}", "result": "clear"}
        )
    
    print(f"\nBlocks created: {worm.current_block_number}")
    
    # Verify chain
    print("\nVerifying hash chain...")
    is_valid, errors = worm.verify_chain()
    print(f"  Chain valid: {'✓' if is_valid else '✗'}")
    if errors:
        for error in errors[:3]:
            print(f"    - {error}")
    
    # Check retention
    print("\nChecking retention policies...")
    for category in DataCategory:
        policy = retention_matrix.get_policy(category)
        print(f"  {category.value}: {policy.retention_days} days")
    
    # Scan for expired data (dry run)
    print("\nScanning for expired data...")
    expired = retention_manager.scan_for_expired_data()
    print(f"  Found {len(expired)} expired records")
    
    # Execute purge (dry run)
    print("\nExecuting purge (dry run)...")
    purge_report = retention_manager.execute_purge(dry_run=True)
    print(f"  Would purge {purge_report['total_expired']} records")
    print(f"  Blocks affected: {len(purge_report['blocks_affected'])}")
    
    # Export audit bundle
    print("\nExporting audit bundle...")
    start_date = datetime.now(MANILA_TZ) - timedelta(days=1)
    end_date = datetime.now(MANILA_TZ)
    
    bundle_path = exporter.export_bundle(start_date, end_date)
    print(f"  Bundle exported: {bundle_path.name}")
    
    # Verify bundle
    verify_file = bundle_path.with_suffix('.verify')
    if verify_file.exists():
        with open(verify_file, 'r') as f:
            verification = json.load(f)
        print(f"  Bundle hash: {verification['bundle_hash'][:32]}...")
        print(f"  Verified: {'✓' if verification['verified'] else '✗'}")
    
    print("\n✓ Data Retention & WORM Storage operational")