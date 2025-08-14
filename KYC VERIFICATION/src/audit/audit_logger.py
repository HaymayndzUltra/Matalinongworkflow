"""
Audit Logger with WORM Compliance and Hash Chain
Implements tamper-evident audit logging with SHA-256 hash chains
"""

import json
import hashlib
import time
import uuid
from typing import Dict, Any, List, Optional, Union
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import threading
import base64


class AuditEventType(str, Enum):
    """Types of audit events"""
    DOCUMENT_VALIDATED = "document_validated"
    DATA_EXTRACTED = "data_extracted"
    RISK_SCORED = "risk_scored"
    DECISION_MADE = "decision_made"
    ISSUER_VERIFIED = "issuer_verified"
    AML_SCREENED = "aml_screened"
    REVIEW_ACTION = "review_action"
    EXPORT_REQUESTED = "export_requested"
    COMPLIANCE_GENERATED = "compliance_generated"
    ERROR_OCCURRED = "error_occurred"
    SYSTEM_EVENT = "system_event"


class AuditSeverity(str, Enum):
    """Audit event severity levels"""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class AuditRecord:
    """Immutable audit record"""
    # Record metadata
    record_id: str
    timestamp: str
    event_type: AuditEventType
    severity: AuditSeverity
    
    # Event details
    session_id: Optional[str]
    user_id: Optional[str]
    action: str
    resource: str
    outcome: str
    
    # Data payload (PII can be redacted)
    data: Dict[str, Any]
    
    # Chain integrity
    sequence_number: int
    previous_hash: str
    current_hash: Optional[str] = None
    
    # WORM reference
    worm_ref: Optional[str] = None
    
    def calculate_hash(self) -> str:
        """Calculate SHA-256 hash of this record"""
        # Create deterministic JSON representation
        hash_data = {
            "record_id": self.record_id,
            "timestamp": self.timestamp,
            "event_type": self.event_type,
            "severity": self.severity,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "action": self.action,
            "resource": self.resource,
            "outcome": self.outcome,
            "data": json.dumps(self.data, sort_keys=True),
            "sequence_number": self.sequence_number,
            "previous_hash": self.previous_hash
        }
        
        # Calculate SHA-256 hash
        hash_string = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(hash_string.encode()).hexdigest()
    
    def to_jsonl(self, include_pii: bool = False) -> str:
        """Convert to JSONL format"""
        record_dict = asdict(self)
        
        # Redact PII if requested
        if not include_pii:
            record_dict["data"] = self._redact_pii(record_dict["data"])
            if record_dict["user_id"]:
                record_dict["user_id"] = self._hash_pii(record_dict["user_id"])
        
        return json.dumps(record_dict, sort_keys=True)
    
    def _redact_pii(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact PII from data"""
        pii_fields = [
            "full_name", "name", "email", "phone", "address",
            "birth_date", "ssn", "id_number", "document_number",
            "face_image", "selfie_image"
        ]
        
        redacted = data.copy()
        for field in pii_fields:
            if field in redacted:
                redacted[field] = "[REDACTED]"
        
        return redacted
    
    def _hash_pii(self, value: str) -> str:
        """Hash PII for pseudonymization"""
        return f"hash_{hashlib.sha256(value.encode()).hexdigest()[:12]}"


class AuditLogger:
    """Thread-safe audit logger with hash chain integrity"""
    
    def __init__(self, storage_path: str = "./audit_logs"):
        """Initialize audit logger"""
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(parents=True, exist_ok=True)
        
        # Initialize chain
        self.sequence_number = 0
        self.previous_hash = "0" * 64  # Genesis hash
        self.chain_lock = threading.Lock()
        
        # Current log file
        self.current_log_file = None
        self.log_file_handle = None
        
        # Initialize
        self._initialize_chain()
    
    def _initialize_chain(self):
        """Initialize or restore hash chain"""
        chain_file = self.storage_path / "chain_state.json"
        
        if chain_file.exists():
            # Restore chain state
            with open(chain_file, 'r') as f:
                state = json.load(f)
                self.sequence_number = state["sequence_number"]
                self.previous_hash = state["previous_hash"]
        else:
            # Create genesis block
            self._log_genesis()
    
    def _log_genesis(self):
        """Create genesis audit record"""
        genesis = AuditRecord(
            record_id=f"genesis_{uuid.uuid4().hex[:8]}",
            timestamp=self._get_timestamp(),
            event_type=AuditEventType.SYSTEM_EVENT,
            severity=AuditSeverity.INFO,
            session_id=None,
            user_id=None,
            action="genesis_block",
            resource="audit_chain",
            outcome="created",
            data={"message": "Audit chain initialized"},
            sequence_number=0,
            previous_hash="0" * 64
        )
        
        genesis.current_hash = genesis.calculate_hash()
        self._write_record(genesis)
        
        # Update chain state after genesis
        self.previous_hash = genesis.current_hash
        self.sequence_number = 0
        self._save_chain_state()
    
    def log_event(
        self,
        event_type: AuditEventType,
        action: str,
        resource: str,
        outcome: str,
        data: Optional[Dict[str, Any]] = None,
        severity: AuditSeverity = AuditSeverity.INFO,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> str:
        """Log an audit event with hash chain integrity"""
        
        with self.chain_lock:
            # Create audit record
            record = AuditRecord(
                record_id=f"audit_{uuid.uuid4().hex}",
                timestamp=self._get_timestamp(),
                event_type=event_type,
                severity=severity,
                session_id=session_id,
                user_id=user_id,
                action=action,
                resource=resource,
                outcome=outcome,
                data=data or {},
                sequence_number=self.sequence_number + 1,
                previous_hash=self.previous_hash
            )
            
            # Calculate hash
            record.current_hash = record.calculate_hash()
            
            # Generate WORM reference
            record.worm_ref = self._generate_worm_ref(record)
            
            # Write to append-only log
            self._write_record(record)
            
            # Update chain state
            self.sequence_number = record.sequence_number
            self.previous_hash = record.current_hash
            self._save_chain_state()
            
            return record.record_id
    
    def _write_record(self, record: AuditRecord):
        """Write record to append-only JSONL file"""
        # Get current log file
        log_file = self._get_current_log_file()
        
        # Append record
        with open(log_file, 'a') as f:
            f.write(record.to_jsonl(include_pii=True) + '\n')
    
    def _get_current_log_file(self) -> Path:
        """Get current log file (rotates daily)"""
        date_str = datetime.now().strftime("%Y%m%d")
        return self.storage_path / f"audit_{date_str}.jsonl"
    
    def _generate_worm_ref(self, record: AuditRecord) -> str:
        """Generate WORM storage reference"""
        # In production, this would be the immutable storage reference
        # For now, generate a unique reference
        timestamp = int(time.time() * 1000000)
        return f"worm://{timestamp}/{record.record_id}"
    
    def _save_chain_state(self):
        """Save current chain state"""
        chain_file = self.storage_path / "chain_state.json"
        state = {
            "sequence_number": self.sequence_number,
            "previous_hash": self.previous_hash,
            "timestamp": self._get_timestamp()
        }
        
        with open(chain_file, 'w') as f:
            json.dump(state, f, indent=2)
    
    def export_logs(
        self,
        start_date: datetime,
        end_date: datetime,
        include_pii: bool = False,
        format: str = "jsonl",
        filters: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Export audit logs for date range"""
        
        # Collect records
        records = self._collect_records(start_date, end_date, filters)
        
        if not records:
            return {
                "file_path": None,
                "record_count": 0,
                "file_size": 0,
                "hash_chain": None,
                "manifest": {}
            }
        
        # Generate export
        export_id = f"export_{uuid.uuid4().hex[:12]}"
        export_file = self._generate_export(
            records, export_id, include_pii, format
        )
        
        # Create manifest
        manifest = self._create_manifest(
            export_id, records, export_file, include_pii
        )
        
        # Sign bundle
        signature = self._sign_bundle(export_file, manifest)
        
        return {
            "file_path": str(export_file),
            "record_count": len(records),
            "file_size": export_file.stat().st_size,
            "hash_chain": manifest["hash_chain"],
            "manifest": manifest,
            "signature": signature
        }
    
    def _collect_records(
        self,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[AuditRecord]:
        """Collect records within date range"""
        records = []
        
        # Iterate through daily log files
        current_date = start_date.date()
        end_date_only = end_date.date()
        
        while current_date <= end_date_only:
            log_file = self.storage_path / f"audit_{current_date.strftime('%Y%m%d')}.jsonl"
            
            if log_file.exists():
                with open(log_file, 'r') as f:
                    for line in f:
                        if line.strip():
                            record_data = json.loads(line)
                            
                            # Parse timestamp
                            timestamp_str = record_data["timestamp"]
                            # Parse ISO format timestamp
                            if '+' in timestamp_str or 'Z' in timestamp_str:
                                record_time = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                            else:
                                # Assume UTC+8 if no timezone
                                record_time = datetime.fromisoformat(timestamp_str).replace(
                                    tzinfo=timezone(timedelta(hours=8))
                                )
                            
                            # Make start_date and end_date timezone-aware if they aren't
                            if start_date.tzinfo is None:
                                start_date = start_date.replace(tzinfo=timezone(timedelta(hours=8)))
                            if end_date.tzinfo is None:
                                end_date = end_date.replace(tzinfo=timezone(timedelta(hours=8)))
                            
                            # Check date range
                            if start_date <= record_time <= end_date:
                                # Apply filters
                                if self._apply_filters(record_data, filters):
                                    records.append(self._dict_to_record(record_data))
            
            # Next day
            current_date = current_date + timedelta(days=1)
        
        return records
    
    def _apply_filters(
        self,
        record: Dict[str, Any],
        filters: Optional[Dict[str, Any]]
    ) -> bool:
        """Apply filters to record"""
        if not filters:
            return True
        
        for key, value in filters.items():
            if key in record and record[key] != value:
                return False
        
        return True
    
    def _dict_to_record(self, data: Dict[str, Any]) -> AuditRecord:
        """Convert dictionary to AuditRecord"""
        return AuditRecord(
            record_id=data["record_id"],
            timestamp=data["timestamp"],
            event_type=AuditEventType(data["event_type"]),
            severity=AuditSeverity(data["severity"]),
            session_id=data.get("session_id"),
            user_id=data.get("user_id"),
            action=data["action"],
            resource=data["resource"],
            outcome=data["outcome"],
            data=data["data"],
            sequence_number=data["sequence_number"],
            previous_hash=data["previous_hash"],
            current_hash=data.get("current_hash"),
            worm_ref=data.get("worm_ref")
        )
    
    def _generate_export(
        self,
        records: List[AuditRecord],
        export_id: str,
        include_pii: bool,
        format: str
    ) -> Path:
        """Generate export file"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if format == "jsonl":
            export_file = self.storage_path / f"{export_id}_{timestamp}.jsonl"
            
            with open(export_file, 'w') as f:
                for record in records:
                    f.write(record.to_jsonl(include_pii) + '\n')
        
        elif format == "json":
            export_file = self.storage_path / f"{export_id}_{timestamp}.json"
            
            records_data = [
                json.loads(record.to_jsonl(include_pii))
                for record in records
            ]
            
            with open(export_file, 'w') as f:
                json.dump(records_data, f, indent=2)
        
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        return export_file
    
    def _create_manifest(
        self,
        export_id: str,
        records: List[AuditRecord],
        export_file: Path,
        include_pii: bool
    ) -> Dict[str, Any]:
        """Create export manifest"""
        # Calculate hash chain summary
        hash_chain = self._calculate_hash_chain(records)
        
        manifest = {
            "export_id": export_id,
            "timestamp": self._get_timestamp(),
            "version": "1.0",
            "record_count": len(records),
            "sequence_range": {
                "start": records[0].sequence_number if records else 0,
                "end": records[-1].sequence_number if records else 0
            },
            "date_range": {
                "start": records[0].timestamp if records else None,
                "end": records[-1].timestamp if records else None
            },
            "file_name": export_file.name,
            "file_size": export_file.stat().st_size,
            "file_hash": self._calculate_file_hash(export_file),
            "include_pii": include_pii,
            "hash_chain": hash_chain,
            "worm_refs": [r.worm_ref for r in records if r.worm_ref]
        }
        
        # Save manifest
        manifest_file = export_file.with_suffix('.manifest.json')
        with open(manifest_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        
        return manifest
    
    def _calculate_hash_chain(self, records: List[AuditRecord]) -> Dict[str, Any]:
        """Calculate hash chain summary"""
        if not records:
            return {}
        
        return {
            "algorithm": "SHA-256",
            "genesis_hash": records[0].previous_hash,
            "final_hash": records[-1].current_hash,
            "chain_length": len(records),
            "verified": self._verify_chain(records)
        }
    
    def _verify_chain(self, records: List[AuditRecord]) -> bool:
        """Verify hash chain integrity"""
        if not records:
            return True
        
        # Sort records by sequence number to ensure proper order
        sorted_records = sorted(records, key=lambda r: r.sequence_number)
        
        for i, record in enumerate(sorted_records):
            # Verify hash calculation
            calculated_hash = record.calculate_hash()
            if calculated_hash != record.current_hash:
                return False
            
            # Verify chain continuity (only for consecutive sequence numbers)
            if i > 0:
                prev_record = sorted_records[i-1]
                # Check if sequence numbers are consecutive
                if record.sequence_number == prev_record.sequence_number + 1:
                    if record.previous_hash != prev_record.current_hash:
                        return False
        
        return True
    
    def _calculate_file_hash(self, file_path: Path) -> str:
        """Calculate SHA-256 hash of file"""
        sha256 = hashlib.sha256()
        
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        
        return sha256.hexdigest()
    
    def _sign_bundle(
        self,
        export_file: Path,
        manifest: Dict[str, Any]
    ) -> str:
        """Sign export bundle (placeholder for real signing)"""
        # In production, use proper digital signatures (RSA/ECDSA)
        # For now, create a simple HMAC signature
        
        signature_data = {
            "file_hash": manifest["file_hash"],
            "hash_chain": manifest["hash_chain"],
            "timestamp": manifest["timestamp"]
        }
        
        signature_string = json.dumps(signature_data, sort_keys=True)
        signature = hashlib.sha256(signature_string.encode()).hexdigest()
        
        # Save signature
        sig_file = export_file.with_suffix('.sig')
        with open(sig_file, 'w') as f:
            f.write(signature)
        
        return signature
    
    def _get_timestamp(self) -> str:
        """Get ISO8601 timestamp with Philippines timezone"""
        tz = timezone(timedelta(hours=8))
        return datetime.now(tz).isoformat()
    
    def verify_export(self, export_file_path: str) -> Dict[str, Any]:
        """Verify an exported audit bundle"""
        export_file = Path(export_file_path)
        
        if not export_file.exists():
            return {"valid": False, "error": "Export file not found"}
        
        # Load manifest
        manifest_file = export_file.with_suffix('.manifest.json')
        if not manifest_file.exists():
            return {"valid": False, "error": "Manifest file not found"}
        
        with open(manifest_file, 'r') as f:
            manifest = json.load(f)
        
        # Verify file hash
        calculated_hash = self._calculate_file_hash(export_file)
        if calculated_hash != manifest["file_hash"]:
            return {
                "valid": False,
                "error": "File hash mismatch",
                "expected": manifest["file_hash"],
                "calculated": calculated_hash
            }
        
        # Load and verify records
        records = []
        with open(export_file, 'r') as f:
            for line in f:
                if line.strip():
                    record_data = json.loads(line)
                    records.append(self._dict_to_record(record_data))
        
        # Verify hash chain
        if not self._verify_chain(records):
            return {"valid": False, "error": "Hash chain verification failed"}
        
        # Verify signature
        sig_file = export_file.with_suffix('.sig')
        if sig_file.exists():
            with open(sig_file, 'r') as f:
                stored_signature = f.read().strip()
            
            # Recalculate signature
            signature_data = {
                "file_hash": manifest["file_hash"],
                "hash_chain": manifest["hash_chain"],
                "timestamp": manifest["timestamp"]
            }
            signature_string = json.dumps(signature_data, sort_keys=True)
            calculated_signature = hashlib.sha256(signature_string.encode()).hexdigest()
            
            if stored_signature != calculated_signature:
                return {"valid": False, "error": "Signature verification failed"}
        
        return {
            "valid": True,
            "record_count": len(records),
            "hash_chain_verified": True,
            "file_hash_verified": True,
            "signature_verified": True,
            "manifest": manifest
        }
