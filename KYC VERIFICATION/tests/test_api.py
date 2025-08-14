"""
API Endpoint Tests
Tests for all KYC Verification API endpoints
"""

import pytest
from fastapi.testclient import TestClient
from datetime import datetime
import base64
import json

# Import the FastAPI app
from src.api.app import app

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
    response = client.get("/health")
    assert "access-control-allow-origin" in response.headers


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
