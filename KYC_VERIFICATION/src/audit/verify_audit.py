#!/usr/bin/env python3
"""
Audit Bundle Verification Tool
Verifies integrity of exported audit logs with hash chain validation
"""

import json
import hashlib
import argparse
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class VerificationStatus(str, Enum):
    """Verification status levels"""
    VALID = "valid"
    WARNING = "warning"
    INVALID = "invalid"
    ERROR = "error"


@dataclass
class VerificationResult:
    """Verification result details"""
    status: VerificationStatus
    message: str
    details: Optional[Dict[str, Any]] = None


class AuditVerifier:
    """Audit bundle verification tool"""
    
    def __init__(self, verbose: bool = False):
        """Initialize verifier"""
        self.verbose = verbose
        self.results = []
    
    def verify_bundle(self, bundle_path: str) -> Dict[str, Any]:
        """
        Verify complete audit bundle
        
        Args:
            bundle_path: Path to the export file (.jsonl or .json)
            
        Returns:
            Verification report with detailed results
        """
        bundle_file = Path(bundle_path)
        
        # Check file exists
        if not bundle_file.exists():
            return self._error_report("Bundle file not found", bundle_path)
        
        # Verify manifest
        manifest_result = self._verify_manifest(bundle_file)
        if manifest_result.status == VerificationStatus.ERROR:
            return self._error_report("Manifest verification failed", manifest_result.message)
        
        # Load manifest
        manifest_file = bundle_file.with_suffix('.manifest.json')
        with open(manifest_file, 'r') as f:
            manifest = json.load(f)
        
        # Verify file integrity
        file_result = self._verify_file_integrity(bundle_file, manifest)
        
        # Load and verify records
        records = self._load_records(bundle_file)
        
        # Verify hash chain
        chain_result = self._verify_hash_chain(records)
        
        # Verify record integrity
        record_results = self._verify_records(records)
        
        # Verify signature
        signature_result = self._verify_signature(bundle_file, manifest)
        
        # Compile report
        report = self._compile_report(
            bundle_file,
            manifest,
            manifest_result,
            file_result,
            chain_result,
            record_results,
            signature_result
        )
        
        return report
    
    def _verify_manifest(self, bundle_file: Path) -> VerificationResult:
        """Verify manifest file exists and is valid"""
        manifest_file = bundle_file.with_suffix('.manifest.json')
        
        if not manifest_file.exists():
            return VerificationResult(
                VerificationStatus.ERROR,
                "Manifest file not found"
            )
        
        try:
            with open(manifest_file, 'r') as f:
                manifest = json.load(f)
            
            # Check required fields
            required_fields = [
                "export_id", "timestamp", "version",
                "record_count", "file_name", "file_hash",
                "hash_chain"
            ]
            
            missing_fields = [f for f in required_fields if f not in manifest]
            
            if missing_fields:
                return VerificationResult(
                    VerificationStatus.WARNING,
                    f"Missing manifest fields: {missing_fields}"
                )
            
            return VerificationResult(
                VerificationStatus.VALID,
                "Manifest structure valid"
            )
        
        except json.JSONDecodeError as e:
            return VerificationResult(
                VerificationStatus.ERROR,
                f"Invalid manifest JSON: {e}"
            )
    
    def _verify_file_integrity(
        self,
        bundle_file: Path,
        manifest: Dict[str, Any]
    ) -> VerificationResult:
        """Verify file hash matches manifest"""
        
        # Calculate file hash
        sha256 = hashlib.sha256()
        with open(bundle_file, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256.update(chunk)
        
        calculated_hash = sha256.hexdigest()
        expected_hash = manifest.get("file_hash", "")
        
        if calculated_hash != expected_hash:
            return VerificationResult(
                VerificationStatus.INVALID,
                "File hash mismatch - file may have been tampered",
                {
                    "expected": expected_hash,
                    "calculated": calculated_hash
                }
            )
        
        return VerificationResult(
            VerificationStatus.VALID,
            "File integrity verified"
        )
    
    def _load_records(self, bundle_file: Path) -> List[Dict[str, Any]]:
        """Load records from bundle file"""
        records = []
        
        if bundle_file.suffix == '.jsonl':
            with open(bundle_file, 'r') as f:
                for line in f:
                    if line.strip():
                        records.append(json.loads(line))
        
        elif bundle_file.suffix == '.json':
            with open(bundle_file, 'r') as f:
                data = json.load(f)
                if isinstance(data, list):
                    records = data
                else:
                    records = [data]
        
        return records
    
    def _verify_hash_chain(self, records: List[Dict[str, Any]]) -> VerificationResult:
        """Verify hash chain integrity"""
        
        if not records:
            return VerificationResult(
                VerificationStatus.WARNING,
                "No records to verify"
            )
        
        chain_errors = []
        
        # Sort records by sequence number to ensure proper order
        sorted_records = sorted(records, key=lambda r: r.get("sequence_number", 0))
        
        for i, record in enumerate(sorted_records):
            # Verify current hash calculation
            calculated_hash = self._calculate_record_hash(record)
            stored_hash = record.get("current_hash", "")
            
            if calculated_hash != stored_hash:
                chain_errors.append({
                    "record": i,
                    "record_id": record.get("record_id"),
                    "error": "Hash calculation mismatch",
                    "expected": stored_hash,
                    "calculated": calculated_hash
                })
            
            # Verify chain continuity (only for consecutive sequence numbers)
            if i > 0:
                prev_record = sorted_records[i-1]
                # Check if sequence numbers are consecutive
                if record.get("sequence_number") == prev_record.get("sequence_number", 0) + 1:
                    expected_prev = prev_record.get("current_hash", "")
                    actual_prev = record.get("previous_hash", "")
                    
                    if expected_prev != actual_prev:
                        chain_errors.append({
                            "record": i,
                            "record_id": record.get("record_id"),
                            "error": "Chain continuity broken",
                            "expected_previous": expected_prev,
                            "actual_previous": actual_prev
                        })
        
        if chain_errors:
            return VerificationResult(
                VerificationStatus.INVALID,
                f"Hash chain verification failed: {len(chain_errors)} errors",
                {"errors": chain_errors}
            )
        
        return VerificationResult(
            VerificationStatus.VALID,
            f"Hash chain verified for {len(sorted_records)} records"
        )
    
    def _calculate_record_hash(self, record: Dict[str, Any]) -> str:
        """Calculate hash of a record"""
        hash_data = {
            "record_id": record.get("record_id"),
            "timestamp": record.get("timestamp"),
            "event_type": record.get("event_type"),
            "severity": record.get("severity"),
            "session_id": record.get("session_id"),
            "user_id": record.get("user_id"),
            "action": record.get("action"),
            "resource": record.get("resource"),
            "outcome": record.get("outcome"),
            "data": json.dumps(record.get("data", {}), sort_keys=True),
            "sequence_number": record.get("sequence_number"),
            "previous_hash": record.get("previous_hash")
        }
        
        hash_string = json.dumps(hash_data, sort_keys=True)
        return hashlib.sha256(hash_string.encode()).hexdigest()
    
    def _verify_records(self, records: List[Dict[str, Any]]) -> List[VerificationResult]:
        """Verify individual record integrity"""
        results = []
        
        # Check sequence numbers
        sequence_numbers = [r.get("sequence_number", -1) for r in records]
        if sequence_numbers != sorted(sequence_numbers):
            results.append(VerificationResult(
                VerificationStatus.WARNING,
                "Sequence numbers not in order"
            ))
        
        # Check for gaps
        if sequence_numbers:
            expected_seq = list(range(sequence_numbers[0], sequence_numbers[-1] + 1))
            missing = set(expected_seq) - set(sequence_numbers)
            if missing:
                results.append(VerificationResult(
                    VerificationStatus.WARNING,
                    f"Missing sequence numbers: {sorted(missing)}"
                ))
        
        # Check timestamps
        timestamps = []
        for r in records:
            try:
                ts = datetime.fromisoformat(r.get("timestamp", ""))
                timestamps.append(ts)
            except:
                pass
        
        if timestamps and timestamps != sorted(timestamps):
            results.append(VerificationResult(
                VerificationStatus.WARNING,
                "Timestamps not in chronological order"
            ))
        
        # Check WORM references
        worm_refs = [r.get("worm_ref") for r in records if r.get("worm_ref")]
        if len(worm_refs) != len(set(worm_refs)):
            results.append(VerificationResult(
                VerificationStatus.WARNING,
                "Duplicate WORM references found"
            ))
        
        return results
    
    def _verify_signature(
        self,
        bundle_file: Path,
        manifest: Dict[str, Any]
    ) -> VerificationResult:
        """Verify bundle signature"""
        
        sig_file = bundle_file.with_suffix('.sig')
        
        if not sig_file.exists():
            return VerificationResult(
                VerificationStatus.WARNING,
                "Signature file not found"
            )
        
        with open(sig_file, 'r') as f:
            stored_signature = f.read().strip()
        
        # Recalculate signature
        signature_data = {
            "file_hash": manifest.get("file_hash", ""),
            "hash_chain": manifest.get("hash_chain", {}),
            "timestamp": manifest.get("timestamp", "")
        }
        
        signature_string = json.dumps(signature_data, sort_keys=True)
        calculated_signature = hashlib.sha256(signature_string.encode()).hexdigest()
        
        if stored_signature != calculated_signature:
            return VerificationResult(
                VerificationStatus.INVALID,
                "Signature verification failed",
                {
                    "expected": stored_signature,
                    "calculated": calculated_signature
                }
            )
        
        return VerificationResult(
            VerificationStatus.VALID,
            "Signature verified"
        )
    
    def _compile_report(
        self,
        bundle_file: Path,
        manifest: Dict[str, Any],
        manifest_result: VerificationResult,
        file_result: VerificationResult,
        chain_result: VerificationResult,
        record_results: List[VerificationResult],
        signature_result: VerificationResult
    ) -> Dict[str, Any]:
        """Compile verification report"""
        
        # Determine overall status
        all_results = [manifest_result, file_result, chain_result, signature_result] + record_results
        
        if any(r.status == VerificationStatus.INVALID for r in all_results):
            overall_status = "INVALID"
            overall_message = "Bundle verification FAILED - tampering detected"
        elif any(r.status == VerificationStatus.ERROR for r in all_results):
            overall_status = "ERROR"
            overall_message = "Bundle verification could not be completed"
        elif any(r.status == VerificationStatus.WARNING for r in all_results):
            overall_status = "WARNING"
            overall_message = "Bundle verified with warnings"
        else:
            overall_status = "VALID"
            overall_message = "Bundle verification PASSED - integrity confirmed"
        
        report = {
            "bundle_file": str(bundle_file),
            "verification_timestamp": datetime.now().isoformat(),
            "overall_status": overall_status,
            "overall_message": overall_message,
            "manifest": {
                "export_id": manifest.get("export_id"),
                "record_count": manifest.get("record_count"),
                "date_range": manifest.get("date_range"),
                "file_size": manifest.get("file_size")
            },
            "verification_results": {
                "manifest": {
                    "status": manifest_result.status.value,
                    "message": manifest_result.message
                },
                "file_integrity": {
                    "status": file_result.status.value,
                    "message": file_result.message,
                    "details": file_result.details
                },
                "hash_chain": {
                    "status": chain_result.status.value,
                    "message": chain_result.message,
                    "details": chain_result.details
                },
                "signature": {
                    "status": signature_result.status.value,
                    "message": signature_result.message,
                    "details": signature_result.details
                },
                "record_checks": [
                    {
                        "status": r.status.value,
                        "message": r.message
                    }
                    for r in record_results
                ]
            }
        }
        
        return report
    
    def _error_report(self, error: str, details: Any = None) -> Dict[str, Any]:
        """Generate error report"""
        return {
            "overall_status": "ERROR",
            "overall_message": error,
            "details": details,
            "verification_timestamp": datetime.now().isoformat()
        }
    
    def print_report(self, report: Dict[str, Any]):
        """Print verification report in readable format"""
        print("\n" + "="*60)
        print("AUDIT BUNDLE VERIFICATION REPORT")
        print("="*60)
        
        print(f"\nBundle: {report.get('bundle_file', 'Unknown')}")
        print(f"Timestamp: {report.get('verification_timestamp')}")
        
        status = report.get('overall_status')
        message = report.get('overall_message')
        
        # Color coding for terminal
        if status == "VALID":
            print(f"\n✅ {message}")
        elif status == "WARNING":
            print(f"\n⚠️  {message}")
        elif status == "INVALID":
            print(f"\n❌ {message}")
        else:
            print(f"\n⛔ {message}")
        
        if "manifest" in report:
            manifest = report["manifest"]
            print(f"\nExport ID: {manifest.get('export_id')}")
            print(f"Records: {manifest.get('record_count')}")
            if manifest.get('date_range'):
                print(f"Date Range: {manifest['date_range'].get('start')} to {manifest['date_range'].get('end')}")
        
        if "verification_results" in report:
            print("\nVerification Details:")
            results = report["verification_results"]
            
            for check_name, check_result in results.items():
                if isinstance(check_result, dict):
                    status = check_result.get('status', 'unknown')
                    message = check_result.get('message', '')
                    
                    if status == 'valid':
                        symbol = '✓'
                    elif status == 'warning':
                        symbol = '⚠'
                    elif status == 'invalid':
                        symbol = '✗'
                    else:
                        symbol = '?'
                    
                    print(f"  {symbol} {check_name}: {message}")
                    
                    if self.verbose and check_result.get('details'):
                        print(f"    Details: {json.dumps(check_result['details'], indent=6)}")
        
        print("\n" + "="*60)


def main():
    """Command-line interface for verification tool"""
    parser = argparse.ArgumentParser(
        description="Verify integrity of audit export bundles"
    )
    
    parser.add_argument(
        "bundle",
        help="Path to audit bundle file (.jsonl or .json)"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Show detailed verification information"
    )
    
    parser.add_argument(
        "-j", "--json",
        action="store_true",
        help="Output report as JSON"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Save report to file"
    )
    
    args = parser.parse_args()
    
    # Create verifier
    verifier = AuditVerifier(verbose=args.verbose)
    
    # Verify bundle
    print(f"Verifying audit bundle: {args.bundle}")
    report = verifier.verify_bundle(args.bundle)
    
    # Output report
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        verifier.print_report(report)
    
    # Save report if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved to: {args.output}")
    
    # Exit with appropriate code
    status = report.get('overall_status')
    if status == 'VALID':
        sys.exit(0)
    elif status == 'WARNING':
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
