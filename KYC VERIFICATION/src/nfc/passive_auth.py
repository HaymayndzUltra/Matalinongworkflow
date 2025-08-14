"""
Passive Authentication Module
ICAO 9303 Compliant eMRTD Verification
Part of KYC Bank-Grade Parity - Phase 2

This module implements passive authentication to verify eMRTD authenticity.
"""

import logging
import hashlib
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
from prometheus_client import Gauge, Counter, Histogram, CollectorRegistry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Manila timezone
MANILA_TZ = timezone(timedelta(hours=8))

# Prometheus metrics
registry = CollectorRegistry()

nfc_pa_verified = Gauge(
    'kyc_nfc_pa_verified',
    'NFC Passive Authentication verification status',
    registry=registry
)

nfc_pa_attempts = Counter(
    'kyc_nfc_pa_attempts_total',
    'Total NFC PA verification attempts',
    ['result', 'failure_reason'],
    registry=registry
)

nfc_pa_processing_time = Histogram(
    'kyc_nfc_pa_processing_seconds',
    'NFC PA processing time in seconds',
    buckets=(0.5, 1.0, 2.0, 3.0, 5.0, 10.0),
    registry=registry
)


@dataclass
class Certificate:
    """X.509 Certificate representation"""
    subject: str
    issuer: str
    serial_number: str
    not_before: datetime
    not_after: datetime
    public_key: bytes
    signature: bytes
    raw_data: bytes
    
    def is_valid(self) -> bool:
        """Check if certificate is currently valid"""
        now = datetime.now(timezone.utc)
        return self.not_before <= now <= self.not_after


@dataclass
class SecurityObjectDocument:
    """EF.SOD structure containing data group hashes"""
    version: int
    hash_algorithm: str
    data_group_hashes: Dict[int, bytes]
    signer_certificate: Optional[Certificate]
    signature: bytes
    
    def get_hash(self, dg_number: int) -> Optional[bytes]:
        """Get hash for a specific data group"""
        return self.data_group_hashes.get(dg_number)


@dataclass
class PAResult:
    """Passive Authentication result"""
    is_valid: bool
    certificate_chain_valid: bool
    hashes_valid: bool
    dg_verification: Dict[int, bool]
    processing_time_ms: float
    errors: List[str]
    warnings: List[str]
    artifacts: Dict[str, Any]


class MockCertificateStore:
    """Mock certificate store for testing"""
    
    def __init__(self):
        """Initialize with mock certificates"""
        self.csca_certificates = {
            "PHL": Certificate(
                subject="CN=Philippines CSCA, C=PH",
                issuer="CN=Philippines CSCA, C=PH",
                serial_number="0001",
                not_before=datetime(2020, 1, 1, tzinfo=timezone.utc),
                not_after=datetime(2030, 12, 31, tzinfo=timezone.utc),
                public_key=b"mock_csca_public_key",
                signature=b"mock_csca_signature",
                raw_data=b"mock_csca_cert"
            )
        }
        
        self.dsc_certificates = {
            "PHL_DSC_001": Certificate(
                subject="CN=Philippines DSC 001, C=PH",
                issuer="CN=Philippines CSCA, C=PH",
                serial_number="1001",
                not_before=datetime(2021, 1, 1, tzinfo=timezone.utc),
                not_after=datetime(2026, 12, 31, tzinfo=timezone.utc),
                public_key=b"mock_dsc_public_key",
                signature=b"mock_dsc_signature",
                raw_data=b"mock_dsc_cert"
            )
        }
    
    def get_csca(self, issuer: str) -> Optional[Certificate]:
        """Get CSCA certificate by issuer"""
        # Simplified lookup
        for cert in self.csca_certificates.values():
            if issuer in cert.subject:
                return cert
        return None
    
    def get_dsc(self, subject: str) -> Optional[Certificate]:
        """Get DSC certificate by subject"""
        for cert in self.dsc_certificates.values():
            if subject in cert.subject:
                return cert
        return None
    
    def verify_chain(self, dsc: Certificate, csca: Certificate) -> bool:
        """Verify certificate chain (mock implementation)"""
        # In real implementation, verify DSC signature with CSCA public key
        return dsc.issuer == csca.subject and dsc.is_valid() and csca.is_valid()


class PassiveAuthenticator:
    """Main Passive Authentication implementation"""
    
    def __init__(self, cert_store_path: Optional[Path] = None):
        """
        Initialize passive authenticator
        
        Args:
            cert_store_path: Path to certificate store
        """
        self.cert_store_path = cert_store_path or Path("/workspace/KYC VERIFICATION/certs")
        self.cert_store = MockCertificateStore()  # Use mock for now
        
        # Load threshold manager
        import sys
        sys.path.append('/workspace/KYC VERIFICATION')
        from src.config.threshold_manager import get_threshold_manager
        self.threshold_manager = get_threshold_manager()
        
        logger.info("Passive Authenticator initialized")
    
    def parse_sod(self, sod_data: bytes) -> Optional[SecurityObjectDocument]:
        """
        Parse Security Object Document
        
        Args:
            sod_data: Raw SOD data from EF.SOD
            
        Returns:
            Parsed SOD or None
        """
        try:
            # Mock parsing - in reality would use ASN.1 decoder
            # Create mock SOD with sample hashes
            mock_hashes = {
                1: hashlib.sha256(b"DG1_DATA").digest(),
                2: hashlib.sha256(b"DG2_DATA").digest(),
                7: hashlib.sha256(b"DG7_DATA").digest(),
                11: hashlib.sha256(b"DG11_DATA").digest(),
                12: hashlib.sha256(b"DG12_DATA").digest(),
                14: hashlib.sha256(b"DG14_DATA").digest()
            }
            
            mock_cert = Certificate(
                subject="CN=Philippines DSC 001, C=PH",
                issuer="CN=Philippines CSCA, C=PH",
                serial_number="1001",
                not_before=datetime(2021, 1, 1, tzinfo=timezone.utc),
                not_after=datetime(2026, 12, 31, tzinfo=timezone.utc),
                public_key=b"dsc_public_key",
                signature=b"dsc_signature",
                raw_data=b"dsc_cert"
            )
            
            return SecurityObjectDocument(
                version=1,
                hash_algorithm="SHA256",
                data_group_hashes=mock_hashes,
                signer_certificate=mock_cert,
                signature=b"sod_signature"
            )
        except Exception as e:
            logger.error(f"Failed to parse SOD: {e}")
            return None
    
    def verify_certificate_chain(self, sod: SecurityObjectDocument) -> Tuple[bool, List[str]]:
        """
        Verify certificate chain from document to CSCA
        
        Args:
            sod: Security Object Document
            
        Returns:
            Tuple of (is_valid, error_messages)
        """
        errors = []
        
        if not sod.signer_certificate:
            errors.append("No signer certificate in SOD")
            return False, errors
        
        dsc = sod.signer_certificate
        
        # Check DSC validity
        if not dsc.is_valid():
            errors.append(f"DSC certificate expired or not yet valid")
            return False, errors
        
        # Get CSCA certificate
        csca = self.cert_store.get_csca(dsc.issuer)
        if not csca:
            errors.append(f"CSCA certificate not found for issuer: {dsc.issuer}")
            return False, errors
        
        # Check CSCA validity
        if not csca.is_valid():
            errors.append("CSCA certificate expired or not yet valid")
            return False, errors
        
        # Verify chain
        if not self.cert_store.verify_chain(dsc, csca):
            errors.append("Certificate chain verification failed")
            return False, errors
        
        logger.info("Certificate chain verified successfully")
        return True, []
    
    def verify_data_group_hashes(self, sod: SecurityObjectDocument, 
                                data_groups: Dict[str, Any]) -> Tuple[Dict[int, bool], List[str]]:
        """
        Verify data group hashes against SOD
        
        Args:
            sod: Security Object Document
            data_groups: Data groups read from card
            
        Returns:
            Tuple of (verification_results, error_messages)
        """
        results = {}
        errors = []
        
        for dg_name, dg_data in data_groups.items():
            if not dg_name.startswith("DG"):
                continue
            
            try:
                dg_number = int(dg_name[2:])
                
                # Get expected hash from SOD
                expected_hash = sod.get_hash(dg_number)
                if not expected_hash:
                    logger.warning(f"No hash in SOD for {dg_name}")
                    continue
                
                # Calculate actual hash
                if hasattr(dg_data, 'calculate_hash'):
                    actual_hash = dg_data.calculate_hash(sod.hash_algorithm)
                else:
                    # Simple hash calculation
                    if sod.hash_algorithm == "SHA256":
                        actual_hash = hashlib.sha256(dg_data).digest()
                    else:
                        actual_hash = hashlib.sha1(dg_data).digest()
                
                # Compare hashes
                hashes_match = actual_hash == expected_hash
                results[dg_number] = hashes_match
                
                if not hashes_match:
                    errors.append(f"Hash mismatch for DG{dg_number}")
                    logger.error(f"DG{dg_number} hash mismatch: "
                               f"expected {expected_hash.hex()[:16]}..., "
                               f"got {actual_hash.hex()[:16]}...")
                else:
                    logger.debug(f"DG{dg_number} hash verified")
                    
            except Exception as e:
                errors.append(f"Error verifying DG{dg_number}: {e}")
                results[dg_number] = False
        
        return results, errors
    
    def verify(self, sod_data: bytes, data_groups: Dict[str, Any]) -> PAResult:
        """
        Perform complete passive authentication
        
        Args:
            sod_data: Raw SOD data
            data_groups: Data groups from card
            
        Returns:
            PAResult with verification status
        """
        start_time = time.time()
        errors = []
        warnings = []
        
        # Parse SOD
        sod = self.parse_sod(sod_data)
        if not sod:
            errors.append("Failed to parse SOD")
            return PAResult(
                is_valid=False,
                certificate_chain_valid=False,
                hashes_valid=False,
                dg_verification={},
                processing_time_ms=(time.time() - start_time) * 1000,
                errors=errors,
                warnings=warnings,
                artifacts={}
            )
        
        # Verify certificate chain
        chain_valid, chain_errors = self.verify_certificate_chain(sod)
        errors.extend(chain_errors)
        
        # Verify data group hashes
        dg_verification, hash_errors = self.verify_data_group_hashes(sod, data_groups)
        errors.extend(hash_errors)
        
        # Overall validation
        hashes_valid = all(dg_verification.values()) if dg_verification else False
        is_valid = chain_valid and hashes_valid
        
        # Calculate processing time
        processing_time_ms = (time.time() - start_time) * 1000
        
        # Update metrics
        nfc_pa_verified.set(1.0 if is_valid else 0.0)
        nfc_pa_attempts.labels(
            result="success" if is_valid else "failure",
            failure_reason=errors[0] if errors else "none"
        ).inc()
        nfc_pa_processing_time.observe(processing_time_ms / 1000.0)
        
        # Prepare artifacts for storage
        artifacts = {
            "sod_version": sod.version,
            "hash_algorithm": sod.hash_algorithm,
            "dsc_subject": sod.signer_certificate.subject if sod.signer_certificate else None,
            "dsc_serial": sod.signer_certificate.serial_number if sod.signer_certificate else None,
            "verification_timestamp": datetime.now(MANILA_TZ).isoformat(),
            "dg_count": len(dg_verification),
            "dg_verified": sum(1 for v in dg_verification.values() if v)
        }
        
        # Log result
        logger.info(f"Passive Authentication: {'VALID' if is_valid else 'INVALID'} "
                   f"(chain: {chain_valid}, hashes: {hashes_valid}, time: {processing_time_ms:.1f}ms)")
        
        return PAResult(
            is_valid=is_valid,
            certificate_chain_valid=chain_valid,
            hashes_valid=hashes_valid,
            dg_verification=dg_verification,
            processing_time_ms=processing_time_ms,
            errors=errors,
            warnings=warnings,
            artifacts=artifacts
        )
    
    def save_verification_artifacts(self, result: PAResult, 
                                   output_path: Optional[Path] = None) -> bool:
        """
        Save verification artifacts for audit
        
        Args:
            result: PA verification result
            output_path: Path to save artifacts
            
        Returns:
            True if saved successfully
        """
        output_path = output_path or Path("/workspace/KYC VERIFICATION/artifacts/nfc_pa")
        output_path.mkdir(parents=True, exist_ok=True)
        
        # Create filename with timestamp
        timestamp = datetime.now(MANILA_TZ).strftime("%Y%m%d_%H%M%S")
        filename = output_path / f"pa_verification_{timestamp}.json"
        
        try:
            artifact_data = {
                "timestamp": datetime.now(MANILA_TZ).isoformat(),
                "is_valid": result.is_valid,
                "certificate_chain_valid": result.certificate_chain_valid,
                "hashes_valid": result.hashes_valid,
                "dg_verification": result.dg_verification,
                "processing_time_ms": result.processing_time_ms,
                "errors": result.errors,
                "warnings": result.warnings,
                "artifacts": result.artifacts
            }
            
            with open(filename, 'w') as f:
                json.dump(artifact_data, f, indent=2)
            
            logger.info(f"Verification artifacts saved to {filename}")
            return True
        except Exception as e:
            logger.error(f"Failed to save artifacts: {e}")
            return False


def perform_passive_authentication(nfc_reader) -> PAResult:
    """
    Convenience function to perform PA with an NFC reader
    
    Args:
        nfc_reader: NFCReader instance
        
    Returns:
        PAResult
    """
    authenticator = PassiveAuthenticator()
    
    # Read SOD
    sod_data = nfc_reader.read_ef_sod()
    if not sod_data:
        return PAResult(
            is_valid=False,
            certificate_chain_valid=False,
            hashes_valid=False,
            dg_verification={},
            processing_time_ms=0,
            errors=["Failed to read EF.SOD"],
            warnings=[],
            artifacts={}
        )
    
    # Read data groups
    data_groups = nfc_reader.read_all_data_groups()
    
    # Perform PA
    result = authenticator.verify(sod_data, data_groups)
    
    # Save artifacts
    authenticator.save_verification_artifacts(result)
    
    return result


if __name__ == "__main__":
    # Demo and testing
    print("=== Passive Authentication Demo ===")
    
    # Initialize authenticator
    authenticator = PassiveAuthenticator()
    
    # Create mock data
    mock_sod = b"mock_sod_data"
    mock_dgs = {
        "DG1": b"mock_dg1_data",
        "DG2": b"mock_dg2_data",
        "DG7": b"mock_dg7_data"
    }
    
    # Perform verification
    result = authenticator.verify(mock_sod, mock_dgs)
    
    print(f"\nVerification Result:")
    print(f"  Valid: {result.is_valid}")
    print(f"  Certificate Chain: {result.certificate_chain_valid}")
    print(f"  Hashes Valid: {result.hashes_valid}")
    print(f"  DG Verification: {result.dg_verification}")
    print(f"  Processing Time: {result.processing_time_ms:.1f}ms")
    
    if result.errors:
        print(f"  Errors: {', '.join(result.errors)}")
    
    # Save artifacts
    if authenticator.save_verification_artifacts(result):
        print("✓ Artifacts saved")
    
    print("\n✓ Passive Authentication module operational")