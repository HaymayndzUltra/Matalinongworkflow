"""
Data Quality & Test Matrices Module
Golden Tests, Integration Tests, and Fairness Regression
Part of KYC Bank-Grade Parity - Phase 14

This module implements comprehensive testing matrices for quality assurance.
"""

import logging
import json
import hashlib
import random
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from enum import Enum
import numpy as np
from abc import ABC, abstractmethod

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Manila timezone
MANILA_TZ = timezone(timedelta(hours=8))


class TestCategory(Enum):
    """Test categories"""
    GOLDEN = "golden"
    INTEGRATION = "integration"
    REGRESSION = "regression"
    PERFORMANCE = "performance"
    FAIRNESS = "fairness"
    SECURITY = "security"
    COMPLIANCE = "compliance"


class DocumentType(Enum):
    """Document types for testing"""
    PHILIPPINE_PASSPORT = "ph_passport"
    PHILIPPINE_LICENSE = "ph_license"
    PHILID = "philid"
    UMID = "umid"
    SSS = "sss"
    PRC = "prc"
    INTERNATIONAL_PASSPORT = "intl_passport"


class TestStatus(Enum):
    """Test execution status"""
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    FLAKY = "flaky"


@dataclass
class TestCase:
    """Individual test case"""
    test_id: str
    category: TestCategory
    name: str
    description: str
    document_type: Optional[DocumentType]
    input_data: Dict[str, Any]
    expected_output: Dict[str, Any]
    tolerance: Optional[float] = None
    deterministic: bool = True
    seed: Optional[int] = None
    tags: List[str] = field(default_factory=list)
    
    def generate_hash(self) -> str:
        """Generate deterministic hash for test case"""
        content = f"{self.test_id}{self.category.value}{json.dumps(self.input_data, sort_keys=True)}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]


@dataclass
class TestResult:
    """Test execution result"""
    test_id: str
    status: TestStatus
    actual_output: Dict[str, Any]
    execution_time_ms: float
    timestamp: datetime
    error_message: Optional[str] = None
    metrics: Dict[str, float] = field(default_factory=dict)
    
    def is_success(self) -> bool:
        """Check if test passed"""
        return self.status == TestStatus.PASSED


@dataclass
class TestMetrics:
    """Test execution metrics"""
    total_tests: int
    passed: int
    failed: int
    skipped: int
    flaky: int
    avg_execution_time_ms: float
    p95_execution_time_ms: float
    success_rate: float
    fpr: Optional[float] = None  # False Positive Rate
    fnr: Optional[float] = None  # False Negative Rate
    tar: Optional[float] = None  # True Accept Rate
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)


class GoldenTestSuite:
    """Golden test suite for each issuer/template"""
    
    def __init__(self):
        """Initialize golden test suite"""
        self.test_cases: Dict[str, TestCase] = {}
        self._load_golden_tests()
        logger.info(f"Golden Test Suite initialized with {len(self.test_cases)} tests")
    
    def _load_golden_tests(self):
        """Load golden test cases"""
        # Philippine Passport tests
        self.test_cases["GOLD-PP-001"] = TestCase(
            test_id="GOLD-PP-001",
            category=TestCategory.GOLDEN,
            name="Valid Philippine Passport",
            description="Test valid Philippine passport with all security features",
            document_type=DocumentType.PHILIPPINE_PASSPORT,
            input_data={
                "document_image": "golden/ph_passport_valid.jpg",
                "mrz": "P<PHLDELACRUZ<<JUAN<SANTOS<<<<<<<<<<<<<<<<<<",
                "face_image": "golden/ph_passport_face.jpg",
                "liveness_check": True
            },
            expected_output={
                "verification_status": "verified",
                "document_authentic": True,
                "face_match_score": 0.95,
                "liveness_score": 0.98,
                "risk_score": 15
            },
            tolerance=0.05,
            tags=["passport", "philippines", "valid"]
        )
        
        self.test_cases["GOLD-PP-002"] = TestCase(
            test_id="GOLD-PP-002",
            category=TestCategory.GOLDEN,
            name="Expired Philippine Passport",
            description="Test expired Philippine passport detection",
            document_type=DocumentType.PHILIPPINE_PASSPORT,
            input_data={
                "document_image": "golden/ph_passport_expired.jpg",
                "expiry_date": "2020-01-15"
            },
            expected_output={
                "verification_status": "rejected",
                "rejection_reason": "document_expired",
                "risk_score": 85
            },
            tags=["passport", "philippines", "expired"]
        )
        
        # PhilID tests
        self.test_cases["GOLD-PID-001"] = TestCase(
            test_id="GOLD-PID-001",
            category=TestCategory.GOLDEN,
            name="Valid PhilID",
            description="Test valid PhilID with QR code",
            document_type=DocumentType.PHILID,
            input_data={
                "document_image": "golden/philid_valid.jpg",
                "qr_code": "PHI1234567890",
                "face_image": "golden/philid_face.jpg"
            },
            expected_output={
                "verification_status": "verified",
                "qr_valid": True,
                "face_match_score": 0.93,
                "risk_score": 10
            },
            tolerance=0.05,
            tags=["philid", "philippines", "valid", "qr"]
        )
        
        # Driver's License tests
        self.test_cases["GOLD-DL-001"] = TestCase(
            test_id="GOLD-DL-001",
            category=TestCategory.GOLDEN,
            name="Valid LTO License",
            description="Test valid LTO driver's license",
            document_type=DocumentType.PHILIPPINE_LICENSE,
            input_data={
                "document_image": "golden/lto_license_valid.jpg",
                "license_number": "N01-12-345678",
                "hologram_check": True
            },
            expected_output={
                "verification_status": "verified",
                "lto_verified": True,
                "hologram_authentic": True,
                "risk_score": 20
            },
            tolerance=0.05,
            tags=["license", "lto", "philippines", "valid"]
        )
        
        # Tampered document test
        self.test_cases["GOLD-TAMP-001"] = TestCase(
            test_id="GOLD-TAMP-001",
            category=TestCategory.GOLDEN,
            name="Tampered Document Detection",
            description="Test detection of digitally altered document",
            document_type=DocumentType.PHILIPPINE_PASSPORT,
            input_data={
                "document_image": "golden/passport_tampered.jpg",
                "tampering_type": "photo_replacement"
            },
            expected_output={
                "verification_status": "rejected",
                "rejection_reason": "document_tampered",
                "tampering_detected": True,
                "risk_score": 95
            },
            tags=["security", "tampered", "fraud"]
        )
    
    def run_test(self, test_id: str) -> TestResult:
        """Run a golden test"""
        if test_id not in self.test_cases:
            return TestResult(
                test_id=test_id,
                status=TestStatus.SKIPPED,
                actual_output={},
                execution_time_ms=0,
                timestamp=datetime.now(MANILA_TZ),
                error_message="Test case not found"
            )
        
        test_case = self.test_cases[test_id]
        start_time = time.time()
        
        # Set random seed for deterministic tests
        if test_case.deterministic and test_case.seed:
            random.seed(test_case.seed)
            np.random.seed(test_case.seed)
        
        try:
            # Simulate test execution
            actual_output = self._execute_test(test_case)
            
            # Compare outputs
            passed = self._compare_outputs(
                test_case.expected_output,
                actual_output,
                test_case.tolerance
            )
            
            status = TestStatus.PASSED if passed else TestStatus.FAILED
            error_message = None if passed else "Output mismatch"
            
        except Exception as e:
            status = TestStatus.FAILED
            actual_output = {}
            error_message = str(e)
        
        execution_time = (time.time() - start_time) * 1000
        
        return TestResult(
            test_id=test_id,
            status=status,
            actual_output=actual_output,
            execution_time_ms=execution_time,
            timestamp=datetime.now(MANILA_TZ),
            error_message=error_message
        )
    
    def _execute_test(self, test_case: TestCase) -> Dict[str, Any]:
        """Execute test (mock implementation)"""
        # In production, would call actual KYC system
        # For demo, return slightly modified expected output
        output = test_case.expected_output.copy()
        
        # Add some variance for numeric values
        for key, value in output.items():
            if isinstance(value, float):
                variance = random.uniform(-0.02, 0.02)
                output[key] = value * (1 + variance)
        
        return output
    
    def _compare_outputs(self, expected: Dict[str, Any], 
                        actual: Dict[str, Any],
                        tolerance: Optional[float]) -> bool:
        """Compare expected and actual outputs"""
        for key, expected_value in expected.items():
            if key not in actual:
                return False
            
            actual_value = actual[key]
            
            if isinstance(expected_value, float) and tolerance:
                if abs(expected_value - actual_value) > tolerance:
                    return False
            elif expected_value != actual_value:
                return False
        
        return True


class PADTestMatrix:
    """PAD/Liveness test matrix"""
    
    def __init__(self):
        """Initialize PAD test matrix"""
        self.test_cases: List[TestCase] = []
        self._generate_pad_tests()
        logger.info(f"PAD Test Matrix initialized with {len(self.test_cases)} tests")
    
    def _generate_pad_tests(self):
        """Generate PAD test cases"""
        attack_types = [
            ("print_attack", "Printed photo attack"),
            ("screen_replay", "Screen replay attack"),
            ("video_replay", "Video replay attack"),
            ("3d_mask", "3D mask attack"),
            ("deepfake", "Deepfake attack")
        ]
        
        # Generate attack tests
        for i, (attack_type, description) in enumerate(attack_types):
            self.test_cases.append(TestCase(
                test_id=f"PAD-ATK-{i+1:03d}",
                category=TestCategory.SECURITY,
                name=f"PAD {attack_type}",
                description=description,
                document_type=None,
                input_data={
                    "image": f"pad/attack_{attack_type}.jpg",
                    "attack_type": attack_type
                },
                expected_output={
                    "is_live": False,
                    "attack_detected": True,
                    "confidence": 0.95
                },
                tolerance=0.1,
                tags=["pad", "attack", attack_type]
            ))
        
        # Generate genuine tests
        for i in range(10):
            self.test_cases.append(TestCase(
                test_id=f"PAD-GEN-{i+1:03d}",
                category=TestCategory.SECURITY,
                name=f"PAD genuine face {i+1}",
                description="Genuine live face",
                document_type=None,
                input_data={
                    "image": f"pad/genuine_{i+1}.jpg",
                    "is_genuine": True
                },
                expected_output={
                    "is_live": True,
                    "attack_detected": False,
                    "confidence": 0.98
                },
                tolerance=0.05,
                tags=["pad", "genuine", "live"]
            ))


class FairnessTestSuite:
    """Fairness and bias testing suite"""
    
    def __init__(self):
        """Initialize fairness test suite"""
        self.demographic_groups = [
            "age_18_25", "age_26_35", "age_36_50", "age_51_plus",
            "gender_male", "gender_female", "gender_other",
            "ethnicity_filipino", "ethnicity_chinese", "ethnicity_other"
        ]
        self.test_results: Dict[str, List[TestResult]] = {
            group: [] for group in self.demographic_groups
        }
        logger.info("Fairness Test Suite initialized")
    
    def run_fairness_tests(self) -> Dict[str, Any]:
        """Run fairness tests across demographics"""
        results = {}
        
        for group in self.demographic_groups:
            # Generate test data for group
            test_data = self._generate_test_data(group)
            
            # Run tests
            group_results = []
            for data in test_data:
                result = self._run_single_test(data)
                group_results.append(result)
                self.test_results[group].append(result)
            
            # Calculate metrics
            results[group] = self._calculate_group_metrics(group_results)
        
        # Calculate fairness metrics
        fairness_metrics = self._calculate_fairness_metrics(results)
        
        return {
            "group_results": results,
            "fairness_metrics": fairness_metrics,
            "timestamp": datetime.now(MANILA_TZ).isoformat()
        }
    
    def _generate_test_data(self, group: str) -> List[Dict[str, Any]]:
        """Generate test data for demographic group"""
        # Mock implementation
        test_data = []
        for i in range(100):  # 100 tests per group
            test_data.append({
                "test_id": f"{group}_{i}",
                "group": group,
                "image": f"fairness/{group}_{i}.jpg",
                "expected_accept": random.random() > 0.1  # 90% should be accepted
            })
        return test_data
    
    def _run_single_test(self, data: Dict[str, Any]) -> TestResult:
        """Run single fairness test"""
        # Mock implementation
        accepted = random.random() > 0.05  # 95% acceptance rate
        
        return TestResult(
            test_id=data["test_id"],
            status=TestStatus.PASSED if accepted == data["expected_accept"] else TestStatus.FAILED,
            actual_output={"accepted": accepted},
            execution_time_ms=random.uniform(10, 50),
            timestamp=datetime.now(MANILA_TZ),
            metrics={
                "confidence": random.uniform(0.85, 0.99),
                "processing_time": random.uniform(100, 500)
            }
        )
    
    def _calculate_group_metrics(self, results: List[TestResult]) -> Dict[str, float]:
        """Calculate metrics for a demographic group"""
        total = len(results)
        passed = sum(1 for r in results if r.is_success())
        
        # Calculate FPR and FNR
        true_positives = sum(1 for r in results 
                           if r.is_success() and r.actual_output.get("accepted"))
        false_positives = sum(1 for r in results 
                            if not r.is_success() and r.actual_output.get("accepted"))
        true_negatives = sum(1 for r in results 
                           if r.is_success() and not r.actual_output.get("accepted"))
        false_negatives = sum(1 for r in results 
                            if not r.is_success() and not r.actual_output.get("accepted"))
        
        fpr = false_positives / (false_positives + true_negatives) if (false_positives + true_negatives) > 0 else 0
        fnr = false_negatives / (false_negatives + true_positives) if (false_negatives + true_positives) > 0 else 0
        
        return {
            "total_tests": total,
            "passed": passed,
            "success_rate": passed / total if total > 0 else 0,
            "fpr": fpr,
            "fnr": fnr,
            "accuracy": (true_positives + true_negatives) / total if total > 0 else 0
        }
    
    def _calculate_fairness_metrics(self, group_results: Dict[str, Dict[str, float]]) -> Dict[str, Any]:
        """Calculate fairness metrics across groups"""
        # Demographic parity
        acceptance_rates = [r["success_rate"] for r in group_results.values()]
        demographic_parity = max(acceptance_rates) - min(acceptance_rates)
        
        # Equal opportunity
        fnr_rates = [r["fnr"] for r in group_results.values()]
        equal_opportunity = max(fnr_rates) - min(fnr_rates)
        
        # Equalized odds
        fpr_rates = [r["fpr"] for r in group_results.values()]
        equalized_odds = max(max(fnr_rates) - min(fnr_rates), 
                           max(fpr_rates) - min(fpr_rates))
        
        return {
            "demographic_parity": demographic_parity,
            "equal_opportunity": equal_opportunity,
            "equalized_odds": equalized_odds,
            "fair": demographic_parity < 0.1 and equal_opportunity < 0.1  # Thresholds
        }


class IntegrationTestRunner:
    """Integration test runner for end-to-end testing"""
    
    def __init__(self):
        """Initialize integration test runner"""
        self.test_scenarios: List[Dict[str, Any]] = []
        self._load_scenarios()
        logger.info(f"Integration Test Runner initialized with {len(self.test_scenarios)} scenarios")
    
    def _load_scenarios(self):
        """Load integration test scenarios"""
        # Scenario 1: Complete KYC flow
        self.test_scenarios.append({
            "id": "INT-001",
            "name": "Complete KYC Flow",
            "steps": [
                {"action": "upload_document", "data": {"type": "passport"}},
                {"action": "perform_liveness", "data": {"method": "passive"}},
                {"action": "verify_nfc", "data": {"enabled": True}},
                {"action": "screen_aml", "data": {"providers": ["aml", "pep"]}},
                {"action": "calculate_risk", "data": {}},
                {"action": "make_decision", "data": {}}
            ],
            "expected_outcome": "approved",
            "max_duration_ms": 20000  # 20 seconds
        })
        
        # Scenario 2: High-risk customer flow
        self.test_scenarios.append({
            "id": "INT-002",
            "name": "High-Risk Customer Flow",
            "steps": [
                {"action": "upload_document", "data": {"type": "passport"}},
                {"action": "perform_liveness", "data": {"method": "active"}},
                {"action": "screen_aml", "data": {"providers": ["aml", "pep", "adverse"]}},
                {"action": "enhanced_due_diligence", "data": {}},
                {"action": "manual_review", "data": {"required": True}},
                {"action": "dual_control", "data": {"required": True}}
            ],
            "expected_outcome": "pending_review",
            "max_duration_ms": 60000  # 60 seconds
        })
    
    def run_scenario(self, scenario_id: str) -> TestResult:
        """Run integration scenario"""
        scenario = next((s for s in self.test_scenarios if s["id"] == scenario_id), None)
        
        if not scenario:
            return TestResult(
                test_id=scenario_id,
                status=TestStatus.SKIPPED,
                actual_output={},
                execution_time_ms=0,
                timestamp=datetime.now(MANILA_TZ),
                error_message="Scenario not found"
            )
        
        start_time = time.time()
        step_results = []
        
        try:
            for step in scenario["steps"]:
                step_result = self._execute_step(step)
                step_results.append(step_result)
                
                if not step_result["success"]:
                    raise Exception(f"Step failed: {step['action']}")
            
            execution_time = (time.time() - start_time) * 1000
            
            # Check if within time limit
            if execution_time > scenario["max_duration_ms"]:
                status = TestStatus.FAILED
                error_message = f"Exceeded time limit: {execution_time:.0f}ms > {scenario['max_duration_ms']}ms"
            else:
                status = TestStatus.PASSED
                error_message = None
            
        except Exception as e:
            status = TestStatus.FAILED
            error_message = str(e)
            execution_time = (time.time() - start_time) * 1000
        
        return TestResult(
            test_id=scenario_id,
            status=status,
            actual_output={"steps": step_results},
            execution_time_ms=execution_time,
            timestamp=datetime.now(MANILA_TZ),
            error_message=error_message
        )
    
    def _execute_step(self, step: Dict[str, Any]) -> Dict[str, Any]:
        """Execute integration test step"""
        # Mock implementation
        time.sleep(random.uniform(0.1, 2.0))  # Simulate processing
        
        return {
            "action": step["action"],
            "success": random.random() > 0.05,  # 95% success rate
            "duration_ms": random.uniform(100, 5000)
        }


class BenchmarkRunner:
    """Performance benchmark runner"""
    
    def __init__(self):
        """Initialize benchmark runner"""
        self.metrics_store = Path("/workspace/KYC VERIFICATION/benchmarks")
        self.metrics_store.mkdir(parents=True, exist_ok=True)
        logger.info("Benchmark Runner initialized")
    
    def run_benchmarks(self) -> Dict[str, Any]:
        """Run performance benchmarks"""
        results = {
            "timestamp": datetime.now(MANILA_TZ).isoformat(),
            "benchmarks": {}
        }
        
        # Document verification benchmark
        doc_results = self._benchmark_document_verification()
        results["benchmarks"]["document_verification"] = doc_results
        
        # Liveness detection benchmark
        pad_results = self._benchmark_pad()
        results["benchmarks"]["liveness_detection"] = pad_results
        
        # Risk scoring benchmark
        risk_results = self._benchmark_risk_scoring()
        results["benchmarks"]["risk_scoring"] = risk_results
        
        # Store results
        self._store_results(results)
        
        return results
    
    def _benchmark_document_verification(self) -> Dict[str, Any]:
        """Benchmark document verification"""
        latencies = []
        
        for _ in range(100):
            start = time.time()
            # Simulate document verification
            time.sleep(random.uniform(0.5, 2.0))
            latencies.append((time.time() - start) * 1000)
        
        return {
            "p50_ms": np.percentile(latencies, 50),
            "p95_ms": np.percentile(latencies, 95),
            "p99_ms": np.percentile(latencies, 99),
            "mean_ms": np.mean(latencies),
            "std_ms": np.std(latencies),
            "samples": len(latencies)
        }
    
    def _benchmark_pad(self) -> Dict[str, Any]:
        """Benchmark PAD/liveness detection"""
        latencies = []
        far_samples = []
        frr_samples = []
        
        for _ in range(100):
            start = time.time()
            # Simulate PAD
            time.sleep(random.uniform(0.2, 0.8))
            latencies.append((time.time() - start) * 1000)
            
            # Simulate FAR/FRR
            far_samples.append(random.uniform(0.005, 0.015))
            frr_samples.append(random.uniform(0.02, 0.04))
        
        return {
            "p50_ms": np.percentile(latencies, 50),
            "p95_ms": np.percentile(latencies, 95),
            "far": np.mean(far_samples),
            "frr": np.mean(frr_samples),
            "tar_at_far1": 0.98 - random.uniform(0, 0.02)
        }
    
    def _benchmark_risk_scoring(self) -> Dict[str, Any]:
        """Benchmark risk scoring"""
        latencies = []
        scores = []
        
        for _ in range(100):
            start = time.time()
            # Simulate risk scoring
            time.sleep(random.uniform(0.1, 0.3))
            latencies.append((time.time() - start) * 1000)
            scores.append(random.uniform(0, 100))
        
        return {
            "p50_ms": np.percentile(latencies, 50),
            "p95_ms": np.percentile(latencies, 95),
            "mean_score": np.mean(scores),
            "std_score": np.std(scores)
        }
    
    def _store_results(self, results: Dict[str, Any]):
        """Store benchmark results"""
        timestamp = datetime.now(MANILA_TZ).strftime("%Y%m%d_%H%M%S")
        filename = self.metrics_store / f"benchmark_{timestamp}.json"
        
        with open(filename, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Benchmark results stored: {filename}")


class TestOrchestrator:
    """Main test orchestrator"""
    
    def __init__(self):
        """Initialize test orchestrator"""
        self.golden_suite = GoldenTestSuite()
        self.pad_matrix = PADTestMatrix()
        self.fairness_suite = FairnessTestSuite()
        self.integration_runner = IntegrationTestRunner()
        self.benchmark_runner = BenchmarkRunner()
        
        logger.info("Test Orchestrator initialized")
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all test suites"""
        results = {
            "timestamp": datetime.now(MANILA_TZ).isoformat(),
            "suites": {}
        }
        
        # Run golden tests
        golden_results = self._run_golden_tests()
        results["suites"]["golden"] = golden_results
        
        # Run PAD tests
        pad_results = self._run_pad_tests()
        results["suites"]["pad"] = pad_results
        
        # Run fairness tests
        fairness_results = self.fairness_suite.run_fairness_tests()
        results["suites"]["fairness"] = fairness_results
        
        # Run integration tests
        integration_results = self._run_integration_tests()
        results["suites"]["integration"] = integration_results
        
        # Run benchmarks
        benchmark_results = self.benchmark_runner.run_benchmarks()
        results["suites"]["benchmarks"] = benchmark_results
        
        # Calculate overall metrics
        results["overall"] = self._calculate_overall_metrics(results["suites"])
        
        return results
    
    def _run_golden_tests(self) -> Dict[str, Any]:
        """Run golden test suite"""
        results = []
        
        for test_id in self.golden_suite.test_cases:
            result = self.golden_suite.run_test(test_id)
            results.append(result)
        
        return self._summarize_results(results)
    
    def _run_pad_tests(self) -> Dict[str, Any]:
        """Run PAD test matrix"""
        results = []
        
        for test_case in self.pad_matrix.test_cases:
            result = self.golden_suite.run_test(test_case.test_id)
            results.append(result)
        
        return self._summarize_results(results)
    
    def _run_integration_tests(self) -> Dict[str, Any]:
        """Run integration tests"""
        results = []
        
        for scenario in self.integration_runner.test_scenarios:
            result = self.integration_runner.run_scenario(scenario["id"])
            results.append(result)
        
        return self._summarize_results(results)
    
    def _summarize_results(self, results: List[TestResult]) -> Dict[str, Any]:
        """Summarize test results"""
        total = len(results)
        passed = sum(1 for r in results if r.status == TestStatus.PASSED)
        failed = sum(1 for r in results if r.status == TestStatus.FAILED)
        skipped = sum(1 for r in results if r.status == TestStatus.SKIPPED)
        
        execution_times = [r.execution_time_ms for r in results]
        
        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "success_rate": passed / total if total > 0 else 0,
            "avg_execution_ms": np.mean(execution_times) if execution_times else 0,
            "p95_execution_ms": np.percentile(execution_times, 95) if execution_times else 0
        }
    
    def _calculate_overall_metrics(self, suites: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate overall test metrics"""
        total_tests = sum(s.get("total", 0) for s in suites.values() if isinstance(s, dict))
        total_passed = sum(s.get("passed", 0) for s in suites.values() if isinstance(s, dict))
        
        return {
            "total_tests": total_tests,
            "total_passed": total_passed,
            "overall_success_rate": total_passed / total_tests if total_tests > 0 else 0,
            "fairness_compliant": suites.get("fairness", {}).get("fairness_metrics", {}).get("fair", False)
        }


if __name__ == "__main__":
    # Demo and testing
    print("=== Data Quality & Test Matrices Demo ===\n")
    
    # Initialize orchestrator
    orchestrator = TestOrchestrator()
    
    # Run golden tests
    print("Running Golden Tests...")
    golden_results = []
    for test_id in ["GOLD-PP-001", "GOLD-PID-001", "GOLD-DL-001"]:
        result = orchestrator.golden_suite.run_test(test_id)
        golden_results.append(result)
        status_icon = "✓" if result.is_success() else "✗"
        print(f"  {status_icon} {test_id}: {result.status.value}")
    
    # Run fairness tests
    print("\nRunning Fairness Tests...")
    fairness = orchestrator.fairness_suite.run_fairness_tests()
    print(f"  Demographic Parity: {fairness['fairness_metrics']['demographic_parity']:.3f}")
    print(f"  Equal Opportunity: {fairness['fairness_metrics']['equal_opportunity']:.3f}")
    print(f"  Fair: {'✓' if fairness['fairness_metrics']['fair'] else '✗'}")
    
    # Run integration test
    print("\nRunning Integration Tests...")
    for scenario in orchestrator.integration_runner.test_scenarios[:2]:
        result = orchestrator.integration_runner.run_scenario(scenario["id"])
        status_icon = "✓" if result.is_success() else "✗"
        print(f"  {status_icon} {scenario['name']}: {result.execution_time_ms:.0f}ms")
    
    # Run benchmarks
    print("\nRunning Benchmarks...")
    benchmarks = orchestrator.benchmark_runner.run_benchmarks()
    for name, metrics in benchmarks["benchmarks"].items():
        print(f"  {name}:")
        print(f"    P50: {metrics['p50_ms']:.1f}ms")
        print(f"    P95: {metrics['p95_ms']:.1f}ms")
    
    # Overall summary
    print("\n=== Test Summary ===")
    all_results = orchestrator.run_all_tests()
    overall = all_results["overall"]
    print(f"Total Tests: {overall['total_tests']}")
    print(f"Success Rate: {overall['overall_success_rate']:.1%}")
    print(f"Fairness Compliant: {'✓' if overall['fairness_compliant'] else '✗'}")
    
    print("\n✓ Data quality and test matrices operational")