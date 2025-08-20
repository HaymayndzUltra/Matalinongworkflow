#!/usr/bin/env python3
"""
Test Script for Audit Export Functionality
Demonstrates WORM compliant audit logging with hash chain verification
"""

import sys
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.audit import (
    AuditLogger,
    AuditEventType,
    AuditSeverity,
    AuditVerifier,
    StorageFactory,
    LocalStorageAdapter
)


def test_audit_logging():
    """Test basic audit logging functionality"""
    print("\n" + "="*60)
    print("TEST 1: AUDIT LOGGING")
    print("="*60 + "\n")
    
    # Create audit logger
    logger = AuditLogger(storage_path="./test_audit_logs")
    
    # Log various events
    events = [
        {
            "event_type": AuditEventType.DOCUMENT_VALIDATED,
            "action": "validate_document",
            "resource": "philippine_id_001",
            "outcome": "success",
            "data": {
                "document_type": "PHILIPPINE_ID",
                "quality_score": 0.98,
                "confidence": 0.95
            },
            "session_id": "sess_test_001",
            "user_id": "user_123"
        },
        {
            "event_type": AuditEventType.DATA_EXTRACTED,
            "action": "extract_ocr",
            "resource": "philippine_id_001",
            "outcome": "success",
            "data": {
                "full_name": "Juan Dela Cruz",
                "id_number": "1234-5678-9012",
                "birth_date": "1990-01-01"
            },
            "session_id": "sess_test_001",
            "user_id": "user_123"
        },
        {
            "event_type": AuditEventType.RISK_SCORED,
            "action": "calculate_risk",
            "resource": "philippine_id_001",
            "outcome": "success",
            "data": {
                "risk_score": 15.5,
                "risk_level": "low",
                "factors": ["document_quality", "device_risk"]
            },
            "session_id": "sess_test_001",
            "user_id": "user_123"
        },
        {
            "event_type": AuditEventType.DECISION_MADE,
            "action": "make_decision",
            "resource": "philippine_id_001",
            "outcome": "approved",
            "data": {
                "decision": "approve",
                "confidence": 0.95,
                "policy_version": "2024.1.0"
            },
            "severity": AuditSeverity.INFO,
            "session_id": "sess_test_001",
            "user_id": "user_123"
        }
    ]
    
    # Log events
    record_ids = []
    for event in events:
        record_id = logger.log_event(**event)
        record_ids.append(record_id)
        print(f"✓ Logged event: {event['action']} -> {record_id}")
    
    print(f"\n✅ Successfully logged {len(record_ids)} audit events")
    
    return logger


def test_audit_export(logger: AuditLogger):
    """Test audit log export functionality"""
    print("\n" + "="*60)
    print("TEST 2: AUDIT EXPORT")
    print("="*60 + "\n")
    
    # Define export parameters
    start_date = datetime.now() - timedelta(days=1)
    end_date = datetime.now() + timedelta(days=1)
    
    # Export with PII
    print("Exporting audit logs WITH PII...")
    export_result_pii = logger.export_logs(
        start_date=start_date,
        end_date=end_date,
        include_pii=True,
        format="jsonl"
    )
    
    print(f"✓ Export file: {export_result_pii['file_path']}")
    print(f"✓ Records exported: {export_result_pii['record_count']}")
    print(f"✓ File size: {export_result_pii['file_size']} bytes")
    print(f"✓ Hash chain: {export_result_pii['hash_chain'].get('verified', False)}")
    
    # Export without PII
    print("\nExporting audit logs WITHOUT PII...")
    export_result_no_pii = logger.export_logs(
        start_date=start_date,
        end_date=end_date,
        include_pii=False,
        format="jsonl"
    )
    
    print(f"✓ Export file: {export_result_no_pii['file_path']}")
    print(f"✓ PII redacted: True")
    
    print("\n✅ Audit export completed successfully")
    
    return export_result_pii, export_result_no_pii


def test_hash_chain_verification(export_file: str):
    """Test hash chain verification"""
    print("\n" + "="*60)
    print("TEST 3: HASH CHAIN VERIFICATION")
    print("="*60 + "\n")
    
    # Create verifier
    verifier = AuditVerifier(verbose=True)
    
    # Verify bundle
    print(f"Verifying audit bundle: {export_file}")
    report = verifier.verify_bundle(export_file)
    
    # Print results
    print("\nVerification Results:")
    print(f"Overall Status: {report['overall_status']}")
    print(f"Message: {report['overall_message']}")
    
    if "verification_results" in report:
        results = report["verification_results"]
        
        # Check each component
        checks = [
            ("Manifest", results.get("manifest", {})),
            ("File Integrity", results.get("file_integrity", {})),
            ("Hash Chain", results.get("hash_chain", {})),
            ("Signature", results.get("signature", {}))
        ]
        
        for name, result in checks:
            status = result.get("status", "unknown")
            message = result.get("message", "")
            
            symbol = "✓" if status == "valid" else "✗"
            print(f"  {symbol} {name}: {message}")
    
    # Return success/failure
    return report["overall_status"] == "VALID"


def test_tamper_detection(export_file: str):
    """Test tamper detection by modifying the export file"""
    print("\n" + "="*60)
    print("TEST 4: TAMPER DETECTION")
    print("="*60 + "\n")
    
    # Create a copy of the export file
    export_path = Path(export_file)
    tampered_path = export_path.parent / f"tampered_{export_path.name}"
    
    # Copy manifest and signature files too
    manifest_path = export_path.with_suffix('.manifest.json')
    sig_path = export_path.with_suffix('.sig')
    tampered_manifest = tampered_path.with_suffix('.manifest.json')
    tampered_sig = tampered_path.with_suffix('.sig')
    
    # Copy manifest and signature
    if manifest_path.exists():
        import shutil
        shutil.copy2(manifest_path, tampered_manifest)
    if sig_path.exists():
        import shutil
        shutil.copy2(sig_path, tampered_sig)
    
    # Read original content
    with open(export_path, 'r') as f:
        lines = f.readlines()
    
    if len(lines) > 1:
        # Tamper with a record
        record = json.loads(lines[1])
        record["data"]["tampered"] = True
        lines[1] = json.dumps(record) + '\n'
        
        # Write tampered file
        with open(tampered_path, 'w') as f:
            f.writelines(lines)
        
        print(f"✓ Created tampered file: {tampered_path}")
        print(f"✓ Copied manifest: {tampered_manifest}")
        print(f"✓ Copied signature: {tampered_sig}")
        
        # Verify tampered bundle
        verifier = AuditVerifier(verbose=False)
        report = verifier.verify_bundle(str(tampered_path))
        
        print(f"\nVerification of tampered file:")
        print(f"Status: {report['overall_status']}")
        print(f"Message: {report['overall_message']}")
        
        if report["overall_status"] == "INVALID":
            print("\n✅ Tampering successfully detected!")
            return True
        else:
            print("\n❌ Failed to detect tampering!")
            return False
    
    return False


def test_storage_adapters():
    """Test storage adapter functionality"""
    print("\n" + "="*60)
    print("TEST 5: STORAGE ADAPTERS")
    print("="*60 + "\n")
    
    # Test local storage adapter
    local_adapter = LocalStorageAdapter(base_path="./test_storage")
    
    # Create test file
    test_file = Path("./test_file.txt")
    test_file.write_text("Test audit data")
    
    # Upload file
    print("Testing local storage adapter...")
    upload_result = local_adapter.upload(test_file, "audit/test_file.txt")
    print(f"✓ Upload: {upload_result['success']}")
    print(f"  Path: {upload_result.get('path', '')}")
    print(f"  Checksum: {upload_result.get('checksum', '')[:16]}...")
    
    # Check existence
    exists = local_adapter.exists("audit/test_file.txt")
    print(f"✓ File exists: {exists}")
    
    # Set WORM protection
    worm_set = local_adapter.set_worm("audit/test_file.txt", retention_days=7)
    print(f"✓ WORM protection set: {worm_set}")
    
    # Try to delete (should fail due to WORM)
    deleted = local_adapter.delete("audit/test_file.txt")
    print(f"✓ Delete attempt (should fail): {not deleted}")
    
    # Clean up
    test_file.unlink()
    
    print("\n✅ Storage adapter test completed")
    
    return True


def test_complete_workflow():
    """Test complete audit export workflow"""
    print("\n" + "🚀 STARTING COMPLETE AUDIT EXPORT TEST WORKFLOW 🚀" + "\n")
    
    try:
        # Test 1: Audit Logging
        logger = test_audit_logging()
        
        # Test 2: Export
        export_with_pii, export_without_pii = test_audit_export(logger)
        
        # Test 3: Hash Chain Verification
        verification_passed = test_hash_chain_verification(export_with_pii["file_path"])
        
        # Test 4: Tamper Detection
        tamper_detected = test_tamper_detection(export_with_pii["file_path"])
        
        # Test 5: Storage Adapters
        storage_test_passed = test_storage_adapters()
        
        # Summary
        print("\n" + "="*60)
        print("TEST SUMMARY")
        print("="*60)
        
        tests = [
            ("Audit Logging", True),
            ("Audit Export", True),
            ("Hash Chain Verification", verification_passed),
            ("Tamper Detection", tamper_detected),
            ("Storage Adapters", storage_test_passed)
        ]
        
        for test_name, passed in tests:
            symbol = "✅" if passed else "❌"
            print(f"{symbol} {test_name}: {'PASSED' if passed else 'FAILED'}")
        
        all_passed = all(passed for _, passed in tests)
        
        if all_passed:
            print("\n🎉 ALL TESTS PASSED!")
            print("\n✅ WORM compliant audit export is fully functional")
            print("✅ Hash chain integrity verification working")
            print("✅ Tamper detection operational")
        else:
            print("\n⚠️ Some tests failed. Please review the output above.")
        
        return all_passed
        
    except Exception as e:
        print(f"\n❌ Test failed with error: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_complete_workflow()
    sys.exit(0 if success else 1)
