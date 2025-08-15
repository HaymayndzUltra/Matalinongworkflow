"""
WORM Audit Logger for Face Scanning System
Implements Write Once Read Many audit trail with privacy protection

Requirements per AI spec:
- No raw PII/biometric data in logs
- Immutable audit entries
- Policy snapshot on decisions
- Anonymized metrics only
- Configurable retention
"""

import json
import hashlib
import time
import os
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
import threading
import logging
from pathlib import Path
import fcntl
import gzip

logger = logging.getLogger(__name__)


# ============= AUDIT TYPES =============

class AuditEventType(Enum):
    """Types of audit events"""
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    FACE_LOCK = "face_lock"
    PAD_CHECK = "pad_check"
    CHALLENGE_ISSUED = "challenge_issued"
    CHALLENGE_RESULT = "challenge_result"
    BURST_EVAL = "burst_eval"
    DECISION_MADE = "decision_made"
    POLICY_APPLIED = "policy_applied"
    THRESHOLD_OVERRIDE = "threshold_override"
    ERROR_OCCURRED = "error_occurred"
    PRIVACY_VIOLATION = "privacy_violation"


class DecisionType(Enum):
    """Decision types for audit"""
    APPROVE = "approve_face"
    REVIEW = "review_face"
    DENY = "deny_face"


# ============= PRIVACY FILTER =============

class PrivacyFilter:
    """Filters and redacts PII from audit data"""
    
    # Fields that should never be logged
    FORBIDDEN_FIELDS = {
        'image', 'image_base64', 'frame_data', 'raw_image',
        'face_image', 'id_photo', 'selfie', 'photo',
        'biometric_template', 'feature_vector', 'embedding',
        'full_name', 'ssn', 'passport_number', 'license_number',
        'email', 'phone', 'address', 'dob', 'date_of_birth'
    }
    
    # Fields that should be hashed
    HASH_FIELDS = {
        'session_id', 'user_id', 'device_id', 'ip_address',
        'request_id', 'correlation_id', 'trace_id'
    }
    
    @classmethod
    def filter_data(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Filter and redact sensitive data"""
        if not isinstance(data, dict):
            return data
        
        filtered = {}
        
        for key, value in data.items():
            # Skip forbidden fields
            if key.lower() in cls.FORBIDDEN_FIELDS:
                continue
            
            # Hash identifiable fields
            if key.lower() in cls.HASH_FIELDS:
                if value is not None:
                    filtered[key] = cls._hash_value(str(value))
                else:
                    filtered[key] = None
            
            # Recursively filter nested dicts
            elif isinstance(value, dict):
                filtered[key] = cls.filter_data(value)
            
            # Filter lists
            elif isinstance(value, list):
                filtered[key] = [
                    cls.filter_data(item) if isinstance(item, dict) else item
                    for item in value
                ]
            
            # Keep safe values
            else:
                filtered[key] = value
        
        return filtered
    
    @classmethod
    def _hash_value(cls, value: str) -> str:
        """Create consistent hash of value"""
        # Use SHA-256 and take first 16 chars for brevity
        return hashlib.sha256(value.encode()).hexdigest()[:16]
    
    @classmethod
    def validate_no_pii(cls, data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Validate that data contains no PII"""
        violations = []
        
        def check_dict(d: dict, path: str = ""):
            for key, value in d.items():
                current_path = f"{path}.{key}" if path else key
                
                # Check for forbidden fields
                if key.lower() in cls.FORBIDDEN_FIELDS:
                    violations.append(f"Forbidden field: {current_path}")
                
                # Check for potential PII patterns
                if isinstance(value, str):
                    if cls._looks_like_pii(value):
                        violations.append(f"Potential PII at: {current_path}")
                
                # Recurse into nested structures
                elif isinstance(value, dict):
                    check_dict(value, current_path)
                elif isinstance(value, list):
                    for i, item in enumerate(value):
                        if isinstance(item, dict):
                            check_dict(item, f"{current_path}[{i}]")
        
        check_dict(data)
        return len(violations) == 0, violations
    
    @classmethod
    def _looks_like_pii(cls, value: str) -> bool:
        """Check if string looks like PII"""
        # Check for common PII patterns
        import re
        
        # Email pattern
        if re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', value):
            return True
        
        # Phone pattern (various formats)
        if re.match(r'^[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}$', value):
            return True
        
        # SSN pattern
        if re.match(r'^\d{3}-\d{2}-\d{4}$', value):
            return True
        
        # Credit card pattern
        if re.match(r'^\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}$', value):
            return True
        
        # Base64 encoded image (basic check)
        if len(value) > 1000 and value.startswith(('data:image', '/9j/', 'iVBOR')):
            return True
        
        return False


# ============= AUDIT ENTRY =============

@dataclass
class AuditEntry:
    """Immutable audit log entry"""
    timestamp: float
    event_type: AuditEventType
    session_hash: str
    decision: Optional[DecisionType] = None
    confidence: Optional[float] = None
    reasons: List[str] = field(default_factory=list)
    metrics: Dict[str, Any] = field(default_factory=dict)
    policy_snapshot: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_json(self) -> str:
        """Convert to JSON for storage"""
        data = {
            'timestamp': self.timestamp,
            'timestamp_iso': datetime.fromtimestamp(self.timestamp).isoformat(),
            'event_type': self.event_type.value,
            'session_hash': self.session_hash,
            'decision': self.decision.value if self.decision else None,
            'confidence': self.confidence,
            'reasons': self.reasons,
            'metrics': self.metrics,
            'policy_snapshot': self.policy_snapshot,
            'metadata': self.metadata
        }
        
        # Filter out None values
        data = {k: v for k, v in data.items() if v is not None}
        
        return json.dumps(data, separators=(',', ':'), sort_keys=True)
    
    def calculate_checksum(self) -> str:
        """Calculate checksum for integrity verification"""
        return hashlib.sha256(self.to_json().encode()).hexdigest()


# ============= WORM STORAGE =============

class WORMStorage:
    """Write Once Read Many storage backend"""
    
    def __init__(self, base_path: str = "/tmp/face_audit"):
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        
        # Current file handles
        self.current_file = None
        self.current_file_handle = None
        self.current_file_size = 0
        self.max_file_size = 10 * 1024 * 1024  # 10MB per file
        
        # File rotation
        self.file_counter = 0
        self.lock = threading.Lock()
        
        # Initialize current file
        self._rotate_file()
    
    def write(self, entry: AuditEntry) -> bool:
        """Write audit entry (immutable)"""
        try:
            with self.lock:
                # Check if rotation needed
                if self.current_file_size > self.max_file_size:
                    self._rotate_file()
                
                # Format entry with checksum
                entry_data = {
                    'entry': json.loads(entry.to_json()),
                    'checksum': entry.calculate_checksum()
                }
                
                line = json.dumps(entry_data) + '\n'
                line_bytes = line.encode('utf-8')
                
                # Write with exclusive lock (WORM behavior)
                fcntl.flock(self.current_file_handle, fcntl.LOCK_EX)
                try:
                    self.current_file_handle.write(line_bytes)
                    self.current_file_handle.flush()
                    os.fsync(self.current_file_handle.fileno())
                finally:
                    fcntl.flock(self.current_file_handle, fcntl.LOCK_UN)
                
                self.current_file_size += len(line_bytes)
                
                # Set file as read-only after each write (WORM)
                # Note: In production, use proper WORM storage
                
                return True
                
        except Exception as e:
            logger.error(f"Failed to write audit entry: {e}")
            return False
    
    def _rotate_file(self):
        """Rotate to new audit file"""
        # Close current file
        if self.current_file_handle:
            self.current_file_handle.close()
            
            # Compress old file
            self._compress_file(self.current_file)
        
        # Create new file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.file_counter += 1
        filename = f"audit_{timestamp}_{self.file_counter:04d}.jsonl"
        self.current_file = self.base_path / filename
        
        # Open with append mode (create if not exists)
        self.current_file_handle = open(self.current_file, 'ab')
        self.current_file_size = 0
        
        logger.info(f"Rotated to new audit file: {filename}")
    
    def _compress_file(self, filepath: Path):
        """Compress completed audit file"""
        if not filepath or not filepath.exists():
            return
        
        try:
            # Gzip the file
            gz_path = filepath.with_suffix('.jsonl.gz')
            
            with open(filepath, 'rb') as f_in:
                with gzip.open(gz_path, 'wb', compresslevel=9) as f_out:
                    f_out.writelines(f_in)
            
            # Remove original after successful compression
            filepath.unlink()
            
            # Make compressed file read-only
            os.chmod(gz_path, 0o444)
            
            logger.info(f"Compressed audit file: {gz_path.name}")
            
        except Exception as e:
            logger.error(f"Failed to compress audit file: {e}")
    
    def read_range(self, start_time: float, end_time: float) -> List[Dict[str, Any]]:
        """Read audit entries in time range"""
        entries = []
        
        # List all audit files
        files = sorted(self.base_path.glob("audit_*.jsonl*"))
        
        for filepath in files:
            try:
                # Handle compressed files
                if filepath.suffix == '.gz':
                    open_func = gzip.open
                else:
                    open_func = open
                
                with open_func(filepath, 'rt') as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            entry = data['entry']
                            
                            # Check time range
                            if start_time <= entry['timestamp'] <= end_time:
                                # Verify checksum
                                expected = data['checksum']
                                actual = hashlib.sha256(
                                    json.dumps(entry, separators=(',', ':'), sort_keys=True).encode()
                                ).hexdigest()
                                
                                if expected == actual:
                                    entries.append(entry)
                                else:
                                    logger.warning(f"Checksum mismatch in audit entry")
                            
                            # Stop if past end time (files are chronological)
                            elif entry['timestamp'] > end_time:
                                break
                                
            except Exception as e:
                logger.error(f"Error reading audit file {filepath}: {e}")
        
        return entries
    
    def cleanup_old_files(self, retention_days: int = 90):
        """Clean up old audit files"""
        cutoff_time = time.time() - (retention_days * 86400)
        
        for filepath in self.base_path.glob("audit_*.jsonl.gz"):
            try:
                # Check file modification time
                if filepath.stat().st_mtime < cutoff_time:
                    filepath.unlink()
                    logger.info(f"Deleted old audit file: {filepath.name}")
            except Exception as e:
                logger.error(f"Error deleting old audit file: {e}")


# ============= AUDIT LOGGER =============

class AuditLogger:
    """Main audit logging system with privacy protection"""
    
    def __init__(self, storage_path: str = "/tmp/face_audit", enable_privacy: bool = True):
        self.storage = WORMStorage(storage_path)
        self.privacy_filter = PrivacyFilter() if enable_privacy else None
        self.enable_privacy = enable_privacy
        
        # Metrics
        self.audit_count = 0
        self.privacy_violations = 0
        self.write_failures = 0
        
        # Thread safety
        self.lock = threading.Lock()
    
    def log_decision(self,
                    session_id: str,
                    decision: str,
                    confidence: float,
                    reasons: List[str],
                    thresholds: Dict[str, Any],
                    metrics: Optional[Dict[str, Any]] = None):
        """Log a face decision with policy snapshot"""
        
        # Filter sensitive data
        if self.enable_privacy:
            filtered_metrics = self.privacy_filter.filter_data(metrics or {})
            filtered_thresholds = self.privacy_filter.filter_data(thresholds)
        else:
            filtered_metrics = metrics or {}
            filtered_thresholds = thresholds
        
        # Create audit entry
        entry = AuditEntry(
            timestamp=time.time(),
            event_type=AuditEventType.DECISION_MADE,
            session_hash=self._hash_session(session_id),
            decision=DecisionType(decision),
            confidence=confidence,
            reasons=reasons,
            metrics=filtered_metrics,
            policy_snapshot=filtered_thresholds,
            metadata={
                'version': '1.0.0',
                'privacy_filtered': self.enable_privacy
            }
        )
        
        # Write to WORM storage
        success = self.storage.write(entry)
        
        with self.lock:
            self.audit_count += 1
            if not success:
                self.write_failures += 1
        
        return success
    
    def log_event(self,
                 event_type: AuditEventType,
                 session_id: str,
                 data: Optional[Dict[str, Any]] = None):
        """Log a general audit event"""
        
        # Filter sensitive data
        if self.enable_privacy and data:
            # Check for PII
            is_clean, violations = self.privacy_filter.validate_no_pii(data)
            if not is_clean:
                logger.warning(f"PII detected in audit data: {violations}")
                with self.lock:
                    self.privacy_violations += 1
                
                # Filter the data
                filtered_data = self.privacy_filter.filter_data(data)
            else:
                filtered_data = data
        else:
            filtered_data = data or {}
        
        # Create audit entry
        entry = AuditEntry(
            timestamp=time.time(),
            event_type=event_type,
            session_hash=self._hash_session(session_id),
            metrics=filtered_data,
            metadata={
                'version': '1.0.0',
                'privacy_filtered': self.enable_privacy
            }
        )
        
        # Write to WORM storage
        success = self.storage.write(entry)
        
        with self.lock:
            self.audit_count += 1
            if not success:
                self.write_failures += 1
        
        return success
    
    def log_threshold_override(self,
                              session_id: str,
                              threshold_name: str,
                              original_value: Any,
                              override_value: Any,
                              reason: str):
        """Log threshold override event"""
        
        entry = AuditEntry(
            timestamp=time.time(),
            event_type=AuditEventType.THRESHOLD_OVERRIDE,
            session_hash=self._hash_session(session_id),
            metrics={
                'threshold_name': threshold_name,
                'original_value': original_value,
                'override_value': override_value,
                'reason': reason
            },
            metadata={
                'version': '1.0.0',
                'privacy_filtered': False  # No PII in threshold data
            }
        )
        
        success = self.storage.write(entry)
        
        with self.lock:
            self.audit_count += 1
            if not success:
                self.write_failures += 1
        
        return success
    
    def get_session_audit_trail(self, session_id: str, 
                               time_window: float = 3600) -> List[Dict[str, Any]]:
        """Get audit trail for a session"""
        session_hash = self._hash_session(session_id)
        
        # Get entries from last hour by default
        end_time = time.time()
        start_time = end_time - time_window
        
        entries = self.storage.read_range(start_time, end_time)
        
        # Filter by session
        session_entries = [
            entry for entry in entries
            if entry.get('session_hash') == session_hash
        ]
        
        return session_entries
    
    def get_decision_audit(self, 
                          start_time: float,
                          end_time: float) -> Dict[str, Any]:
        """Get decision audit summary"""
        
        entries = self.storage.read_range(start_time, end_time)
        
        # Filter decision events
        decisions = [
            e for e in entries
            if e.get('event_type') == AuditEventType.DECISION_MADE.value
        ]
        
        # Aggregate statistics
        stats = {
            'total_decisions': len(decisions),
            'approve_count': sum(1 for d in decisions if d.get('decision') == DecisionType.APPROVE.value),
            'review_count': sum(1 for d in decisions if d.get('decision') == DecisionType.REVIEW.value),
            'deny_count': sum(1 for d in decisions if d.get('decision') == DecisionType.DENY.value),
            'avg_confidence': sum(d.get('confidence', 0) for d in decisions) / max(1, len(decisions)),
            'unique_sessions': len(set(d.get('session_hash') for d in decisions)),
            'reasons': {}
        }
        
        # Count reasons
        for decision in decisions:
            for reason in decision.get('reasons', []):
                stats['reasons'][reason] = stats['reasons'].get(reason, 0) + 1
        
        return stats
    
    def _hash_session(self, session_id: str) -> str:
        """Hash session ID for privacy"""
        return hashlib.sha256(session_id.encode()).hexdigest()[:16]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get audit system metrics"""
        with self.lock:
            return {
                'audit_count': self.audit_count,
                'privacy_violations': self.privacy_violations,
                'write_failures': self.write_failures,
                'privacy_enabled': self.enable_privacy
            }
    
    def cleanup(self, retention_days: int = 90):
        """Clean up old audit files"""
        self.storage.cleanup_old_files(retention_days)


# ============= GLOBAL INSTANCE =============

_audit_logger = None


def get_audit_logger() -> AuditLogger:
    """Get global audit logger instance"""
    global _audit_logger
    if _audit_logger is None:
        # Use environment variable for storage path
        storage_path = os.environ.get('FACE_AUDIT_PATH', '/tmp/face_audit')
        _audit_logger = AuditLogger(storage_path)
    return _audit_logger


# ============= CONVENIENCE FUNCTIONS =============

def audit_decision(session_id: str,
                  decision: str,
                  confidence: float,
                  reasons: List[str],
                  thresholds: Dict[str, Any],
                  metrics: Optional[Dict[str, Any]] = None):
    """Log a face decision"""
    logger_instance = get_audit_logger()
    return logger_instance.log_decision(
        session_id, decision, confidence, reasons, thresholds, metrics
    )


def audit_event(event_type: AuditEventType,
               session_id: str,
               data: Optional[Dict[str, Any]] = None):
    """Log an audit event"""
    logger_instance = get_audit_logger()
    return logger_instance.log_event(event_type, session_id, data)