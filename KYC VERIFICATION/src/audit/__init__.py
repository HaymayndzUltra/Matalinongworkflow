"""
Audit Module - WORM Compliant Audit Logging with Hash Chains
Provides tamper-evident audit logging and verification
"""

from .audit_logger import (
    AuditLogger,
    AuditRecord,
    AuditEventType,
    AuditSeverity
)

from .storage_adapters import (
    StorageAdapter,
    LocalStorageAdapter,
    S3StorageAdapter,
    GCSStorageAdapter,
    AzureStorageAdapter,
    StorageFactory
)

from .verify_audit import (
    AuditVerifier,
    VerificationStatus,
    VerificationResult
)

__all__ = [
    # Logger
    'AuditLogger',
    'AuditRecord',
    'AuditEventType',
    'AuditSeverity',
    
    # Storage
    'StorageAdapter',
    'LocalStorageAdapter',
    'S3StorageAdapter',
    'GCSStorageAdapter',
    'AzureStorageAdapter',
    'StorageFactory',
    
    # Verification
    'AuditVerifier',
    'VerificationStatus',
    'VerificationResult'
]
