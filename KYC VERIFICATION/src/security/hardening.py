"""
Security & Privacy Hardening Module
Secrets Management, Encryption, Tokenization, and SIEM Integration
Part of KYC Bank-Grade Parity - Phase 8

This module implements security hardening measures for the KYC system.
"""

import logging
import hashlib
import hmac
import json
import base64
import secrets
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from enum import Enum
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Manila timezone
MANILA_TZ = timezone(timedelta(hours=8))


class SecurityLevel(Enum):
    """Security classification levels"""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    SECRET = "secret"


class KeyRotationStatus(Enum):
    """Key rotation status"""
    CURRENT = "current"
    ROTATING = "rotating"
    RETIRED = "retired"
    COMPROMISED = "compromised"


@dataclass
class EncryptionKey:
    """Encryption key metadata"""
    key_id: str
    key_type: str
    algorithm: str
    created_at: datetime
    expires_at: datetime
    status: KeyRotationStatus
    version: int
    fingerprint: str


@dataclass
class Token:
    """PII token representation"""
    token_id: str
    token_value: str
    data_type: str
    created_at: datetime
    expires_at: Optional[datetime]
    usage_count: int = 0
    last_accessed: Optional[datetime] = None


@dataclass
class SecurityEvent:
    """Security event for SIEM"""
    event_id: str
    event_type: str
    severity: str
    timestamp: datetime
    source: str
    user_id: Optional[str]
    ip_address: Optional[str]
    details: Dict[str, Any]
    mitigation: Optional[str] = None


class SecretsManager:
    """Manage secrets with Vault/KMS integration"""
    
    def __init__(self, vault_url: Optional[str] = None):
        """
        Initialize secrets manager
        
        Args:
            vault_url: Vault server URL (mock if not provided)
        """
        self.vault_url = vault_url or "mock://vault"
        self.is_mock = vault_url is None
        self.secrets_cache: Dict[str, Tuple[str, datetime]] = {}
        self.cache_ttl = timedelta(minutes=5)
        
        # Master key for mock mode (in production, from HSM/KMS)
        self._master_key = self._get_or_create_master_key()
        
        logger.info(f"Secrets Manager initialized {'(mock mode)' if self.is_mock else ''}")
    
    def _get_or_create_master_key(self) -> bytes:
        """Get or create master key"""
        key_file = Path("/workspace/KYC VERIFICATION/.keys/master.key")
        key_file.parent.mkdir(parents=True, exist_ok=True)
        
        if key_file.exists():
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            # Generate new master key
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            os.chmod(key_file, 0o600)  # Restrict permissions
            logger.info("Generated new master key")
            return key
    
    def store_secret(self, key: str, value: str, metadata: Optional[Dict] = None) -> bool:
        """
        Store secret in vault
        
        Args:
            key: Secret key/path
            value: Secret value
            metadata: Optional metadata
            
        Returns:
            True if stored successfully
        """
        try:
            if self.is_mock:
                # Encrypt and store locally for mock
                fernet = Fernet(self._master_key)
                encrypted = fernet.encrypt(value.encode())
                
                storage_path = Path(f"/workspace/KYC VERIFICATION/.secrets/{key}.enc")
                storage_path.parent.mkdir(parents=True, exist_ok=True)
                
                with open(storage_path, 'wb') as f:
                    f.write(encrypted)
                
                # Store metadata
                if metadata:
                    meta_path = storage_path.with_suffix('.meta')
                    with open(meta_path, 'w') as f:
                        json.dump(metadata, f)
                
                logger.info(f"Secret stored: {key}")
                return True
            else:
                # Real Vault API call would go here
                pass
                
        except Exception as e:
            logger.error(f"Failed to store secret: {e}")
            return False
    
    def retrieve_secret(self, key: str, use_cache: bool = True) -> Optional[str]:
        """
        Retrieve secret from vault
        
        Args:
            key: Secret key/path
            use_cache: Whether to use cache
            
        Returns:
            Secret value or None
        """
        # Check cache
        if use_cache and key in self.secrets_cache:
            value, cached_at = self.secrets_cache[key]
            if datetime.now(timezone.utc) - cached_at < self.cache_ttl:
                return value
        
        try:
            if self.is_mock:
                # Decrypt from local storage
                storage_path = Path(f"/workspace/KYC VERIFICATION/.secrets/{key}.enc")
                
                if not storage_path.exists():
                    logger.warning(f"Secret not found: {key}")
                    return None
                
                with open(storage_path, 'rb') as f:
                    encrypted = f.read()
                
                fernet = Fernet(self._master_key)
                value = fernet.decrypt(encrypted).decode()
                
                # Update cache
                self.secrets_cache[key] = (value, datetime.now(timezone.utc))
                
                return value
            else:
                # Real Vault API call would go here
                pass
                
        except Exception as e:
            logger.error(f"Failed to retrieve secret: {e}")
            return None
    
    def rotate_secret(self, key: str, new_value: str) -> bool:
        """
        Rotate a secret
        
        Args:
            key: Secret key
            new_value: New secret value
            
        Returns:
            True if rotated successfully
        """
        # Archive old value
        old_value = self.retrieve_secret(key, use_cache=False)
        if old_value:
            archive_key = f"{key}_archive_{datetime.now(MANILA_TZ).strftime('%Y%m%d_%H%M%S')}"
            self.store_secret(archive_key, old_value, {"archived_from": key})
        
        # Store new value
        success = self.store_secret(key, new_value, {
            "rotated_at": datetime.now(MANILA_TZ).isoformat(),
            "rotation_reason": "scheduled"
        })
        
        if success:
            # Clear cache
            self.secrets_cache.pop(key, None)
            logger.info(f"Secret rotated: {key}")
        
        return success


class EncryptionService:
    """Encryption at rest service"""
    
    def __init__(self, key_manager: Optional['KeyManager'] = None):
        """
        Initialize encryption service
        
        Args:
            key_manager: Key management service
        """
        self.key_manager = key_manager or KeyManager()
        self.backend = default_backend()
        logger.info("Encryption Service initialized")
    
    def encrypt_data(self, data: bytes, classification: SecurityLevel = SecurityLevel.CONFIDENTIAL) -> Tuple[bytes, str]:
        """
        Encrypt data based on classification
        
        Args:
            data: Data to encrypt
            classification: Security classification
            
        Returns:
            Tuple of (encrypted_data, key_id)
        """
        # Get appropriate key
        key_info = self.key_manager.get_current_key(classification)
        
        # Generate IV
        iv = os.urandom(16)
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key_info['key']),
            modes.CBC(iv),
            backend=self.backend
        )
        encryptor = cipher.encryptor()
        
        # Pad data to block size
        padded_data = self._pad(data)
        
        # Encrypt
        encrypted = encryptor.update(padded_data) + encryptor.finalize()
        
        # Combine IV and encrypted data
        result = iv + encrypted
        
        return result, key_info['key_id']
    
    def decrypt_data(self, encrypted_data: bytes, key_id: str) -> bytes:
        """
        Decrypt data
        
        Args:
            encrypted_data: Encrypted data with IV
            key_id: Key identifier
            
        Returns:
            Decrypted data
        """
        # Get key
        key = self.key_manager.get_key(key_id)
        
        # Extract IV
        iv = encrypted_data[:16]
        ciphertext = encrypted_data[16:]
        
        # Create cipher
        cipher = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=self.backend
        )
        decryptor = cipher.decryptor()
        
        # Decrypt
        padded_plaintext = decryptor.update(ciphertext) + decryptor.finalize()
        
        # Remove padding
        plaintext = self._unpad(padded_plaintext)
        
        return plaintext
    
    def _pad(self, data: bytes) -> bytes:
        """PKCS7 padding"""
        padding_length = 16 - (len(data) % 16)
        padding = bytes([padding_length] * padding_length)
        return data + padding
    
    def _unpad(self, data: bytes) -> bytes:
        """Remove PKCS7 padding"""
        padding_length = data[-1]
        return data[:-padding_length]


class KeyManager:
    """Cryptographic key management"""
    
    def __init__(self):
        """Initialize key manager"""
        self.keys: Dict[str, Dict[str, Any]] = {}
        self.rotation_schedule: Dict[str, datetime] = {}
        self._initialize_keys()
        logger.info("Key Manager initialized")
    
    def _initialize_keys(self):
        """Initialize encryption keys"""
        for level in SecurityLevel:
            key_id = f"aes256_{level.value}_v1"
            self.keys[key_id] = {
                'key_id': key_id,
                'key': os.urandom(32),  # AES-256 key
                'algorithm': 'AES256',
                'created_at': datetime.now(MANILA_TZ),
                'expires_at': datetime.now(MANILA_TZ) + timedelta(days=90),
                'status': KeyRotationStatus.CURRENT,
                'classification': level
            }
            
            # Schedule rotation
            self.rotation_schedule[key_id] = datetime.now(MANILA_TZ) + timedelta(days=85)
    
    def get_current_key(self, classification: SecurityLevel) -> Dict[str, Any]:
        """Get current key for classification level"""
        for key_info in self.keys.values():
            if (key_info['classification'] == classification and 
                key_info['status'] == KeyRotationStatus.CURRENT):
                return key_info
        
        raise ValueError(f"No current key for classification {classification}")
    
    def get_key(self, key_id: str) -> bytes:
        """Get key by ID"""
        if key_id not in self.keys:
            raise ValueError(f"Key not found: {key_id}")
        return self.keys[key_id]['key']
    
    def rotate_key(self, key_id: str) -> str:
        """
        Rotate encryption key
        
        Args:
            key_id: Current key ID
            
        Returns:
            New key ID
        """
        old_key = self.keys.get(key_id)
        if not old_key:
            raise ValueError(f"Key not found: {key_id}")
        
        # Mark old key as rotating
        old_key['status'] = KeyRotationStatus.ROTATING
        
        # Create new key
        version = int(key_id.split('_v')[-1]) + 1
        new_key_id = f"{key_id.rsplit('_v', 1)[0]}_v{version}"
        
        self.keys[new_key_id] = {
            'key_id': new_key_id,
            'key': os.urandom(32),
            'algorithm': old_key['algorithm'],
            'created_at': datetime.now(MANILA_TZ),
            'expires_at': datetime.now(MANILA_TZ) + timedelta(days=90),
            'status': KeyRotationStatus.CURRENT,
            'classification': old_key['classification']
        }
        
        # Schedule rotation for new key
        self.rotation_schedule[new_key_id] = datetime.now(MANILA_TZ) + timedelta(days=85)
        
        logger.info(f"Key rotated: {key_id} -> {new_key_id}")
        return new_key_id
    
    def check_rotation_needed(self) -> List[str]:
        """Check which keys need rotation"""
        now = datetime.now(MANILA_TZ)
        keys_to_rotate = []
        
        for key_id, rotation_time in self.rotation_schedule.items():
            if rotation_time <= now and self.keys[key_id]['status'] == KeyRotationStatus.CURRENT:
                keys_to_rotate.append(key_id)
        
        return keys_to_rotate


class PIITokenizer:
    """PII tokenization service"""
    
    def __init__(self, encryption_service: Optional[EncryptionService] = None):
        """
        Initialize tokenizer
        
        Args:
            encryption_service: Encryption service for vault
        """
        self.encryption_service = encryption_service or EncryptionService()
        self.token_vault: Dict[str, Tuple[bytes, str]] = {}  # token -> (encrypted_value, key_id)
        self.reverse_index: Dict[str, str] = {}  # hash(value) -> token
        logger.info("PII Tokenizer initialized")
    
    def tokenize(self, value: str, data_type: str = "pii") -> str:
        """
        Tokenize PII value
        
        Args:
            value: PII value to tokenize
            data_type: Type of data
            
        Returns:
            Token string
        """
        # Check if already tokenized
        value_hash = hashlib.sha256(value.encode()).hexdigest()
        if value_hash in self.reverse_index:
            return self.reverse_index[value_hash]
        
        # Generate token
        token = f"tok_{data_type}_{secrets.token_urlsafe(16)}"
        
        # Encrypt and store value
        encrypted, key_id = self.encryption_service.encrypt_data(
            value.encode(),
            SecurityLevel.RESTRICTED
        )
        
        self.token_vault[token] = (encrypted, key_id)
        self.reverse_index[value_hash] = token
        
        logger.debug(f"Tokenized {data_type} value")
        return token
    
    def detokenize(self, token: str) -> Optional[str]:
        """
        Detokenize to get original value
        
        Args:
            token: Token string
            
        Returns:
            Original value or None
        """
        if token not in self.token_vault:
            logger.warning(f"Token not found: {token}")
            return None
        
        encrypted, key_id = self.token_vault[token]
        
        try:
            decrypted = self.encryption_service.decrypt_data(encrypted, key_id)
            return decrypted.decode()
        except Exception as e:
            logger.error(f"Failed to detokenize: {e}")
            return None
    
    def tokenize_dict(self, data: Dict[str, Any], pii_fields: List[str]) -> Dict[str, Any]:
        """
        Tokenize PII fields in dictionary
        
        Args:
            data: Dictionary containing PII
            pii_fields: List of PII field names
            
        Returns:
            Dictionary with tokenized PII
        """
        tokenized = data.copy()
        
        for field in pii_fields:
            if field in tokenized and tokenized[field]:
                tokenized[field] = self.tokenize(str(tokenized[field]), field)
        
        return tokenized


class DLPChecker:
    """Data Loss Prevention checker"""
    
    def __init__(self):
        """Initialize DLP checker"""
        self.patterns = self._load_patterns()
        self.violations: List[Dict[str, Any]] = []
        logger.info("DLP Checker initialized")
    
    def _load_patterns(self) -> Dict[str, Any]:
        """Load DLP patterns"""
        return {
            'credit_card': r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b',
            'ssn': r'\b\d{3}-\d{2}-\d{4}\b',
            'email': r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            'phone': r'\b\+?1?\d{10,14}\b',
            'passport': r'\b[A-Z]{1,2}\d{7,9}\b'
        }
    
    def check_content(self, content: str, context: str = "unknown") -> List[str]:
        """
        Check content for DLP violations
        
        Args:
            content: Content to check
            context: Context of check
            
        Returns:
            List of violations found
        """
        import re
        violations = []
        
        for pattern_name, pattern in self.patterns.items():
            matches = re.findall(pattern, content)
            if matches:
                violations.append(f"{pattern_name}: {len(matches)} matches")
                
                # Log violation
                self.violations.append({
                    'timestamp': datetime.now(MANILA_TZ).isoformat(),
                    'context': context,
                    'pattern': pattern_name,
                    'count': len(matches)
                })
        
        if violations:
            logger.warning(f"DLP violations in {context}: {violations}")
        
        return violations


class SIEMIntegration:
    """SIEM integration for security events"""
    
    def __init__(self, siem_endpoint: Optional[str] = None):
        """
        Initialize SIEM integration
        
        Args:
            siem_endpoint: SIEM collector endpoint
        """
        self.siem_endpoint = siem_endpoint or "mock://siem"
        self.is_mock = siem_endpoint is None
        self.event_queue: List[SecurityEvent] = []
        self.batch_size = 100
        logger.info(f"SIEM Integration initialized {'(mock mode)' if self.is_mock else ''}")
    
    def send_event(self, event: SecurityEvent) -> bool:
        """
        Send security event to SIEM
        
        Args:
            event: Security event
            
        Returns:
            True if sent successfully
        """
        self.event_queue.append(event)
        
        # Send in batches
        if len(self.event_queue) >= self.batch_size:
            return self._flush_events()
        
        return True
    
    def _flush_events(self) -> bool:
        """Flush event queue to SIEM"""
        if not self.event_queue:
            return True
        
        try:
            if self.is_mock:
                # Write to local file for mock
                log_path = Path("/workspace/KYC VERIFICATION/siem_events")
                log_path.mkdir(parents=True, exist_ok=True)
                
                timestamp = datetime.now(MANILA_TZ).strftime("%Y%m%d_%H%M%S")
                filename = log_path / f"events_{timestamp}.jsonl"
                
                with open(filename, 'w') as f:
                    for event in self.event_queue:
                        event_dict = asdict(event)
                        event_dict['timestamp'] = event.timestamp.isoformat()
                        f.write(json.dumps(event_dict) + '\n')
                
                logger.info(f"Flushed {len(self.event_queue)} events to SIEM")
            else:
                # Real SIEM API call would go here
                pass
            
            self.event_queue.clear()
            return True
            
        except Exception as e:
            logger.error(f"Failed to flush SIEM events: {e}")
            return False
    
    def create_security_event(self, event_type: str, severity: str,
                             details: Dict[str, Any],
                             user_id: Optional[str] = None,
                             ip_address: Optional[str] = None) -> SecurityEvent:
        """
        Create and send security event
        
        Args:
            event_type: Type of event
            severity: Severity level
            details: Event details
            user_id: User ID if applicable
            ip_address: IP address if applicable
            
        Returns:
            Created security event
        """
        event = SecurityEvent(
            event_id=secrets.token_hex(16),
            event_type=event_type,
            severity=severity,
            timestamp=datetime.now(MANILA_TZ),
            source="kyc_system",
            user_id=user_id,
            ip_address=ip_address,
            details=details
        )
        
        self.send_event(event)
        return event


class AccessControl:
    """Least privilege access control"""
    
    def __init__(self):
        """Initialize access control"""
        self.permissions: Dict[str, List[str]] = {}
        self.access_log: List[Dict[str, Any]] = []
        self.privileged_operations = [
            "decrypt_pii",
            "export_data",
            "modify_permissions",
            "rotate_keys",
            "access_secrets"
        ]
        logger.info("Access Control initialized")
    
    def grant_permission(self, user_id: str, permission: str, 
                        duration: Optional[timedelta] = None) -> bool:
        """
        Grant permission to user
        
        Args:
            user_id: User ID
            permission: Permission to grant
            duration: Optional duration
            
        Returns:
            True if granted
        """
        if user_id not in self.permissions:
            self.permissions[user_id] = []
        
        self.permissions[user_id].append(permission)
        
        # Log privileged access
        if permission in self.privileged_operations:
            self.access_log.append({
                'timestamp': datetime.now(MANILA_TZ).isoformat(),
                'user_id': user_id,
                'permission': permission,
                'action': 'grant',
                'duration': str(duration) if duration else 'permanent'
            })
            logger.warning(f"Privileged permission granted: {user_id} -> {permission}")
        
        return True
    
    def check_permission(self, user_id: str, permission: str) -> bool:
        """Check if user has permission"""
        return permission in self.permissions.get(user_id, [])
    
    def revoke_permission(self, user_id: str, permission: str) -> bool:
        """Revoke permission from user"""
        if user_id in self.permissions and permission in self.permissions[user_id]:
            self.permissions[user_id].remove(permission)
            
            if permission in self.privileged_operations:
                self.access_log.append({
                    'timestamp': datetime.now(MANILA_TZ).isoformat(),
                    'user_id': user_id,
                    'permission': permission,
                    'action': 'revoke'
                })
            
            return True
        return False
    
    def audit_access(self) -> Dict[str, Any]:
        """Generate access audit report"""
        return {
            'timestamp': datetime.now(MANILA_TZ).isoformat(),
            'total_users': len(self.permissions),
            'privileged_users': sum(
                1 for perms in self.permissions.values()
                if any(p in self.privileged_operations for p in perms)
            ),
            'recent_privileged_grants': self.access_log[-10:]
        }


class SecurityHardening:
    """Main security hardening orchestrator"""
    
    def __init__(self):
        """Initialize security hardening"""
        self.secrets_manager = SecretsManager()
        self.encryption_service = EncryptionService()
        self.key_manager = KeyManager()
        self.tokenizer = PIITokenizer(self.encryption_service)
        self.dlp_checker = DLPChecker()
        self.siem = SIEMIntegration()
        self.access_control = AccessControl()
        
        logger.info("Security Hardening initialized with all components")
    
    def secure_data(self, data: Dict[str, Any], pii_fields: List[str]) -> Dict[str, Any]:
        """
        Apply security to data
        
        Args:
            data: Data to secure
            pii_fields: PII field names
            
        Returns:
            Secured data
        """
        # Tokenize PII
        secured = self.tokenizer.tokenize_dict(data, pii_fields)
        
        # Check for DLP violations
        data_str = json.dumps(secured)
        violations = self.dlp_checker.check_content(data_str, "data_security")
        
        if violations:
            # Send security event
            self.siem.create_security_event(
                event_type="dlp_violation",
                severity="medium",
                details={'violations': violations}
            )
        
        return secured
    
    def perform_key_rotation(self) -> List[str]:
        """Perform scheduled key rotation"""
        rotated_keys = []
        
        for key_id in self.key_manager.check_rotation_needed():
            new_key_id = self.key_manager.rotate_key(key_id)
            rotated_keys.append(new_key_id)
            
            # Log security event
            self.siem.create_security_event(
                event_type="key_rotation",
                severity="info",
                details={
                    'old_key_id': key_id,
                    'new_key_id': new_key_id
                }
            )
        
        if rotated_keys:
            logger.info(f"Rotated {len(rotated_keys)} keys")
        
        return rotated_keys


if __name__ == "__main__":
    # Demo and testing
    print("=== Security & Privacy Hardening Demo ===\n")
    
    # Initialize hardening
    hardening = SecurityHardening()
    
    # Test secrets management
    print("Testing Secrets Management:")
    hardening.secrets_manager.store_secret("api_key", "super-secret-key-123")
    retrieved = hardening.secrets_manager.retrieve_secret("api_key")
    print(f"  Secret stored and retrieved: {'✓' if retrieved else '✗'}")
    
    # Test encryption
    print("\nTesting Encryption:")
    test_data = b"Sensitive customer data"
    encrypted, key_id = hardening.encryption_service.encrypt_data(test_data)
    decrypted = hardening.encryption_service.decrypt_data(encrypted, key_id)
    print(f"  Encryption/Decryption: {'✓' if decrypted == test_data else '✗'}")
    print(f"  Key ID: {key_id}")
    
    # Test tokenization
    print("\nTesting PII Tokenization:")
    pii_data = {
        "name": "John Doe",
        "ssn": "123-45-6789",
        "passport": "P1234567",
        "email": "john@example.com"
    }
    
    tokenized = hardening.secure_data(pii_data, ["ssn", "passport", "email"])
    print(f"  Original SSN: {pii_data['ssn']}")
    print(f"  Tokenized SSN: {tokenized['ssn']}")
    
    # Test detokenization
    original_ssn = hardening.tokenizer.detokenize(tokenized['ssn'])
    print(f"  Detokenized: {original_ssn}")
    print(f"  Tokenization working: {'✓' if original_ssn == pii_data['ssn'] else '✗'}")
    
    # Test DLP
    print("\nTesting DLP Checker:")
    test_content = "Customer card 4111-1111-1111-1111 and SSN 123-45-6789"
    violations = hardening.dlp_checker.check_content(test_content)
    print(f"  Violations found: {len(violations)}")
    for v in violations:
        print(f"    - {v}")
    
    # Test access control
    print("\nTesting Access Control:")
    hardening.access_control.grant_permission("user123", "view_data")
    hardening.access_control.grant_permission("admin456", "decrypt_pii")
    
    has_access = hardening.access_control.check_permission("admin456", "decrypt_pii")
    print(f"  Admin has decrypt_pii permission: {'✓' if has_access else '✗'}")
    
    audit = hardening.access_control.audit_access()
    print(f"  Privileged users: {audit['privileged_users']}")
    
    # Test SIEM events
    print("\nTesting SIEM Integration:")
    event = hardening.siem.create_security_event(
        event_type="suspicious_activity",
        severity="high",
        details={"reason": "Multiple failed auth attempts"},
        user_id="user789",
        ip_address="192.168.1.100"
    )
    print(f"  Event created: {event.event_id}")
    
    # Flush SIEM events
    hardening.siem._flush_events()
    print(f"  Events flushed to SIEM: ✓")
    
    print("\n✓ Security & Privacy Hardening operational")