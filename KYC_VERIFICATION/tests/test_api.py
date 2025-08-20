"""
API Endpoint Tests
Tests for all KYC Verification API endpoints
"""

import os
import sys
import numpy as np
import pytest
from fastapi.testclient import TestClient
from datetime import datetime
import base64
import json

# Ensure import paths for KYC root and src
CURRENT_DIR = os.path.dirname(__file__)
KYC_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
SRC_PATH = os.path.join(KYC_ROOT, "src")
for p in [KYC_ROOT, SRC_PATH]:
    if p not in sys.path:
        sys.path.insert(0, p)

# Import the FastAPI app
from api.app import app


@pytest.fixture(autouse=True)
def _install_test_stubs(monkeypatch):
    """Install lightweight stubs for heavy components to keep tests deterministic."""
    import api.app as api_app

    class FakeQualityAnalyzer:
        def analyze_frame(self, image):
            metrics = type("M", (), {
                "resolution": (640, 480),
                "blur_score": 0.1,
                "glare_score": 0.05,
                "brightness_score": 0.5,
                "contrast_score": 0.6,
                "orientation_angle": 0.0,
                "document_coverage": 0.8,
                "edge_clarity": 0.7,
                "overall_score": 0.98,
            })
            return metrics, []

    class FakeDocumentClassifier:
        def classify(self, image):
            return type("C", (), {"document_type": type("T", (), {"value": "PhilID"}), "confidence": 0.95})

    class FakeAuthenticityChecker:
        def check_authenticity(self, image):
            return {"authentic": True, "confidence": 0.99, "issues": []}

    class FakeRiskScorer:
        def calculate_score(self, document_data, device_info, biometric_data, aml_data):
            return {"risk_score": 10.0, "risk_factors": [], "fraud_indicators": []}

    class FakeDecisionEngine:
        def make_decision(self, risk_score, extracted_data, validation_result, policy_overrides=None):
            return {"decision": "approve", "confidence": 0.95, "reasons": [], "policy_version": "2024.1.0", "review_required": False, "review_reasons": []}

    class FakeVendorOrchestrator:
        def verify_with_issuer(self, document_type, document_number, personal_info, adapter=None):
            return {"verified": True, "match_score": 0.9, "issuer_response": {"status": "VALID"}}

    class FakeAMLScreener:
        def screen(self, full_name, birth_date, nationality, additional_info, screening_level):
            return {"hits": [], "screened_lists": ["OFAC", "UN", "EU", "PEP"], "vendor": "internal"}

    class FakeComplianceGenerator:
        def generate(self, artifact_type: str, include_data_flows: bool, include_minimization: bool, format: str):
            return {"file_path": f"./artifacts/{artifact_type}.md", "sections": ["purpose", "risks"]}

    class FakeAuditLogger:
        def export_logs(self, start_date, end_date, include_pii, format, filters):
            return {"file_path": "/exports/audit.jsonl", "file_size": 512, "record_count": 1, "hash_chain": "sha256:abc", "manifest": {}}

    stub_map = {
        "quality_analyzer": FakeQualityAnalyzer(),
        "document_classifier": FakeDocumentClassifier(),
        "authenticity_checker": FakeAuthenticityChecker(),
        "risk_scorer": FakeRiskScorer(),
        "decision_engine": FakeDecisionEngine(),
        "vendor_orchestrator": FakeVendorOrchestrator(),
        "aml_screener": FakeAMLScreener(),
        "compliance_generator": FakeComplianceGenerator(),
        "audit_logger": FakeAuditLogger(),
        "ocr_extractor": object(),
        "mrz_parser": object(),
        "barcode_reader": object(),
        "face_matcher": object(),
    }

    def fake_get_component(name: str):
        return stub_map.get(name)

    monkeypatch.setattr(api_app, "get_component", fake_get_component, raising=False)
    monkeypatch.setattr(api_app, "decode_base64_image", lambda _s: np.zeros((50, 50, 3), dtype=np.uint8), raising=False)

# Create test client
client = TestClient(app)


class TestHealthEndpoints:
    """Test health check endpoints"""
    
    def test_root_endpoint(self):
        """Test root endpoint"""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert data["status"] == "operational"
    
    def test_health_endpoint(self):
        """Test /health endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "version" in data
        assert "uptime_seconds" in data
        assert "timestamp" in data
    
    def test_ready_endpoint(self):
        """Test /ready endpoint"""
        response = client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert "ready" in data
        assert "dependencies" in data
        assert isinstance(data["dependencies"], dict)
    
    def test_metrics_endpoint(self):
        """Test /metrics endpoint"""
        response = client.get("/metrics")
        assert response.status_code == 200
        data = response.json()
        assert "metrics" in data
        assert "timestamp" in data
        metrics = data["metrics"]
        assert "requests_total" in metrics
        assert "error_rate" in metrics
        assert "p95_latency_ms" in metrics


class TestValidationEndpoint:
    """Test document validation endpoint"""
    
    def test_validate_with_valid_image(self):
        """Test validation with valid image data"""
        # Create a simple test image (1x1 white pixel)
        test_image = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAP/bAEMAAQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="
        
        payload = {
            "image_base64": test_image,
            "document_type": "PHILIPPINE_ID",
            "metadata": {"test": True}
        }
        
        response = client.post("/validate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "valid" in data
        assert "confidence" in data
        assert "document_type" in data
        assert "quality_score" in data
        assert "issues" in data
        assert "suggestions" in data
    
    def test_validate_missing_image(self):
        """Test validation with missing image"""
        payload = {
            "document_type": "PHILIPPINE_ID"
        }
        
        response = client.post("/validate", json=payload)
        assert response.status_code == 422  # Validation error


class TestExtractionEndpoint:
    """Test data extraction endpoint"""
    
    def test_extract_with_valid_request(self):
        """Test extraction with valid request"""
        test_image = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAP=="
        
        payload = {
            "image_base64": test_image,
            "extract_face": True,
            "extract_mrz": True,
            "extract_barcode": True
        }
        
        response = client.post("/extract", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "success" in data
        assert "document_type" in data
        assert "extracted_data" in data
        assert "metadata" in data
        
        extracted = data["extracted_data"]
        assert "ocr_text" in extracted
        assert "confidence_scores" in extracted


class TestScoringEndpoint:
    """Test risk scoring endpoint"""
    
    def test_score_calculation(self):
        """Test risk score calculation"""
        payload = {
            "document_data": {
                "ocr_text": {"name": "Test User", "id": "123456"},
                "mrz_data": None,
                "barcode_data": None,
                "face_image": None,
                "face_bbox": None,
                "confidence_scores": {"name": 0.95, "id": 0.98}
            },
            "device_info": {
                "ip": "192.168.1.1",
                "device_id": "test_device"
            }
        }
        
        response = client.post("/score", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "risk_score" in data
        assert "risk_level" in data
        assert "risk_factors" in data
        assert "fraud_indicators" in data
        assert 0 <= data["risk_score"] <= 100


class TestDecisionEndpoint:
    """Test decision endpoint"""
    
    def test_decision_making(self):
        """Test decision making"""
        payload = {
            "risk_score": 15.5,
            "extracted_data": {
                "ocr_text": {"name": "Test User"},
                "mrz_data": None,
                "barcode_data": None,
                "face_image": None,
                "face_bbox": None,
                "confidence_scores": {}
            },
            "validation_result": {
                "valid": True,
                "confidence": 0.95,
                "document_type": "PHILIPPINE_ID",
                "quality_score": 0.98,
                "issues": [],
                "suggestions": [],
                "metadata": {}
            }
        }
        
        response = client.post("/decide", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "decision" in data
        assert data["decision"] in ["approve", "review", "deny", "pending"]
        assert "confidence" in data
        assert "reasons" in data
        assert "policy_version" in data


class TestIssuerVerificationEndpoint:
    """Test issuer verification endpoint"""
    
    def test_issuer_verify(self):
        """Test issuer verification"""
        payload = {
            "document_type": "PHILIPPINE_ID",
            "document_number": "1234-5678-9012",
            "personal_info": {
                "full_name": "Juan Dela Cruz",
                "birth_date": "1990-01-01"
            }
        }
        
        response = client.post("/issuer/verify", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "verified" in data
        assert "match_score" in data
        assert "issuer_response" in data
        assert "proof" in data
        assert "metadata" in data


class TestAMLScreeningEndpoint:
    """Test AML screening endpoint"""
    
    def test_aml_screening(self):
        """Test AML/sanctions screening"""
        payload = {
            "full_name": "John Doe",
            "birth_date": "1990-01-01",
            "nationality": "PH",
            "screening_level": "standard"
        }
        
        response = client.post("/aml/screen", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "clean" in data
        assert "hits" in data
        assert "risk_level" in data
        assert "screened_lists" in data
        assert isinstance(data["hits"], list)


class TestAuditExportEndpoint:
    """Test audit export endpoint"""
    
    def test_audit_export(self):
        """Test audit log export"""
        payload = {
            "start_date": "2024-01-01T00:00:00+08:00",
            "end_date": "2024-01-31T23:59:59+08:00",
            "include_pii": False,
            "format": "jsonl"
        }
        
        response = client.post("/audit/export", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "export_id" in data
        assert "file_url" in data
        assert "file_size_bytes" in data
        assert "record_count" in data
        assert "hash_chain" in data
        assert "manifest" in data


class TestComplianceEndpoint:
    """Test compliance generation endpoint"""
    
    def test_compliance_generation(self):
        """Test compliance artifact generation"""
        payload = {
            "artifact_type": "dpia",
            "include_data_flows": True,
            "include_minimization": True,
            "format": "markdown"
        }
        
        response = client.post("/compliance/generate", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "artifact_id" in data
        assert "artifact_type" in data
        assert "file_path" in data
        assert "metadata" in data


class TestCompleteFlowEndpoint:
    """Test complete KYC flow endpoint"""
    
    def test_complete_kyc_flow(self):
        """Test complete KYC verification"""
        test_image = "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAP=="
        
        payload = {
            "image_base64": test_image,
            "document_type": "PHILIPPINE_ID",
            "session_id": "test_session_123",
            "device_info": {
                "ip": "192.168.1.1",
                "device_id": "test_device"
            }
        }
        
        response = client.post("/complete", json=payload)
        assert response.status_code == 200
        data = response.json()
        assert "session_id" in data
        assert "decision" in data
        assert "risk_score" in data
        assert "risk_level" in data
        assert "validation" in data
        assert "extraction" in data
        assert "scoring" in data
        assert "decision_details" in data
        assert "processing_time_ms" in data


class TestOpenAPISpec:
    """Test OpenAPI specification"""
    
    def test_openapi_schema(self):
        """Test OpenAPI schema is accessible"""
        response = client.get("/openapi.json")
        assert response.status_code == 200
        schema = response.json()
        assert "openapi" in schema
        assert "info" in schema
        assert "paths" in schema
        
        # Check all required endpoints are documented
        required_endpoints = [
            "/validate",
            "/extract",
            "/score",
            "/decide",
            "/issuer/verify",
            "/aml/screen",
            "/audit/export",
            "/compliance/generate",
            "/health",
            "/ready",
            "/metrics",
            "/complete"
        ]
        
        for endpoint in required_endpoints:
            assert endpoint in schema["paths"]


def test_cors_headers():
    """Test CORS headers are properly set"""
    response = client.get("/health", headers={"Origin": "http://example.com"})
    # CORS header should be present when Origin is provided
    assert response.headers.get("access-control-allow-origin") in {"*", "http://example.com"}


def test_request_id_header():
    """Test request ID is added to responses"""
    response = client.get("/health")
    assert "x-request-id" in response.headers


def test_process_time_header():
    """Test process time is added to responses"""
    response = client.get("/health")
    assert "x-process-time" in response.headers


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "--tb=short"])
