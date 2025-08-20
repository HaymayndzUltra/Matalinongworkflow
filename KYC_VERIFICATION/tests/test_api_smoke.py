import os
import sys
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient


# Ensure the KYC VERIFICATION src path is importable
CURRENT_DIR = os.path.dirname(__file__)
KYC_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
SRC_PATH = os.path.join(KYC_ROOT, "src")
for p in [KYC_ROOT, SRC_PATH]:
    if p not in sys.path:
        sys.path.insert(0, p)

from api.app import app  # noqa: E402


def install_component_stubs(monkeypatch):
    """Monkeypatch api.app.get_component to return lightweight stubs.

    Avoids importing heavy optional deps (dlib, face_recognition, tesseract, etc.).
    """
    import api.app as api_app

    class FakeQualityAnalyzer:
        def analyze_frame(self, image):
            metrics = SimpleNamespace(
                resolution=(640, 480),
                blur_score=0.1,
                glare_score=0.05,
                brightness_score=0.5,
                contrast_score=0.6,
                orientation_angle=0.0,
                document_coverage=0.8,
                edge_clarity=0.7,
                overall_score=0.98,
            )
            hints = []  # no issues
            return metrics, hints

    class FakeDocumentClassifier:
        def classify(self, image):
            # .document_type.value is consumed downstream
            return SimpleNamespace(
                document_type=SimpleNamespace(value="PhilID"),
                confidence=0.95,
            )

    class FakeAuthenticityChecker:
        def check_authenticity(self, image):
            return {"authentic": True, "confidence": 0.99, "issues": []}

    class FakeRiskScorer:
        def calculate_score(self, document_data, device_info, biometric_data, aml_data):
            return {
                "risk_score": 10.0,
                "risk_factors": [{"factor": "document_quality", "score": 5.0, "weight": 0.2}],
                "fraud_indicators": [],
            }

    class FakeDecisionEngine:
        def make_decision(self, risk_score, extracted_data, validation_result, policy_overrides=None):
            return {
                "decision": "approve",
                "confidence": 0.95,
                "reasons": ["Low risk score", "All validations passed"],
                "policy_version": "2024.1.0",
                "review_required": False,
                "review_reasons": [],
            }

    class FakeVendorOrchestrator:
        def verify_with_issuer(self, document_type, document_number, personal_info, adapter=None):
            return {
                "verified": True,
                "match_score": 0.9,
                "issuer_response": {
                    "status": "VALID",
                    "issued_date": "2020-01-15",
                    "adapter": adapter or "default_adapter",
                },
            }

    class FakeAMLScreener:
        def screen(self, full_name, birth_date, nationality, additional_info, screening_level):
            return {"hits": [], "screened_lists": ["OFAC", "UN", "EU", "PEP"], "vendor": "internal"}

    stub_map = {
        "quality_analyzer": FakeQualityAnalyzer(),
        "document_classifier": FakeDocumentClassifier(),
        "authenticity_checker": FakeAuthenticityChecker(),
        "risk_scorer": FakeRiskScorer(),
        "decision_engine": FakeDecisionEngine(),
        "vendor_orchestrator": FakeVendorOrchestrator(),
        "aml_screener": FakeAMLScreener(),
        # Extractor placeholders for readiness check only
        "ocr_extractor": object(),
        "mrz_parser": object(),
        "barcode_reader": object(),
        # Avoid heavy biometrics
        "face_matcher": object(),
    }

    def fake_get_component(name: str):
        return stub_map.get(name)

    # Patch component getter
    monkeypatch.setattr(api_app, "get_component", fake_get_component, raising=False)

    # Patch image decoder to bypass OpenCV dependency
    def fake_decode_base64_image(_s: str):
        return np.zeros((50, 50, 3), dtype=np.uint8)

    monkeypatch.setattr(api_app, "decode_base64_image", fake_decode_base64_image, raising=False)


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_root_health_ready(client, monkeypatch):
    install_component_stubs(monkeypatch)

    r = client.get("/")
    assert r.status_code == 200
    data = r.json()
    assert data.get("name")
    assert data.get("version")

    r = client.get("/health")
    assert r.status_code == 200
    assert r.json().get("status") == "healthy"

    r = client.get("/ready")
    assert r.status_code == 200
    ready_payload = r.json()
    assert ready_payload.get("ready") is True
    deps = ready_payload.get("dependencies", {})
    assert deps.get("ml_models") is True
    assert deps.get("extractors") is True
    assert deps.get("risk_engine") is True


def test_validate_document(client, monkeypatch):
    install_component_stubs(monkeypatch)

    payload = {
        "image_base64": "data:image/jpeg;base64,TEST",
        "document_type": "PHILIPPINE_ID",
        "metadata": {"session_id": "sess_123"},
    }
    r = client.post("/validate", json=payload)
    assert r.status_code == 200
    resp = r.json()
    assert resp["valid"] is True
    assert resp["document_type"] in {"PHILIPPINE_ID", "PASSPORT", "DRIVERS_LICENSE", "UMID", "PRC_LICENSE", "UNKNOWN"}


def test_score_and_decide(client, monkeypatch):
    install_component_stubs(monkeypatch)

    # /score
    score_req = {
        "document_data": {
            "ocr_text": {},
            "mrz_data": None,
            "barcode_data": None,
            "face_image": None,
            "face_bbox": None,
            "confidence_scores": {},
        },
        "device_info": {"device_trust_score": 0.9},
        "biometric_data": {"selfie_provided": True},
        "aml_data": None,
    }
    rs = client.post("/score", json=score_req)
    assert rs.status_code == 200
    score = rs.json()
    assert 0 <= score["risk_score"] <= 100
    assert score["risk_level"] in {"low", "medium", "high", "critical"}

    # /decide
    decide_req = {
        "risk_score": score["risk_score"],
        "extracted_data": score_req["document_data"],
        "validation_result": {
            "valid": True,
            "confidence": 0.95,
            "document_type": "PHILIPPINE_ID",
            "quality_score": 0.98,
            "issues": [],
            "suggestions": [],
            "metadata": {},
        },
        "policy_overrides": None,
    }
    rd = client.post("/decide", json=decide_req)
    assert rd.status_code == 200
    decision = rd.json()
    assert decision["decision"] in {"approve", "review", "deny", "pending"}


def test_issuer_and_aml(client, monkeypatch):
    install_component_stubs(monkeypatch)

    issu_req = {
        "document_type": "PHILIPPINE_ID",
        "document_number": "A1234567",
        "personal_info": {"full_name": "Juan Dela Cruz"},
    }
    ri = client.post("/issuer/verify", json=issu_req)
    assert ri.status_code == 200
    assert isinstance(ri.json().get("verified"), bool)

    aml_req = {
        "full_name": "Juan Dela Cruz",
        "birth_date": "1990-01-01",
        "nationality": "PH",
        "additional_info": {},
        "screening_level": "standard",
    }
    ra = client.post("/aml/screen", json=aml_req)
    assert ra.status_code == 200
    aml = ra.json()
    assert isinstance(aml.get("clean"), bool)
    assert aml.get("risk_level") in {"low", "medium", "high", "critical"}


def test_complete_flow_with_stubs(client, monkeypatch):
    install_component_stubs(monkeypatch)

    # Patch extract_data to avoid OCR dependencies
    import api.app as api_app
    from api.contracts import ExtractResponse, ExtractedData, DocumentType

    async def fake_extract_data(request):
        ed = ExtractedData(
            ocr_text={"full_name": "JUAN DELA CRUZ", "birth_date": "1990-01-01", "id_number": "A1234567"},
            mrz_data=None,
            barcode_data=None,
            face_image=None,
            face_bbox=None,
            confidence_scores={},
        )
        return ExtractResponse(success=True, document_type=DocumentType.PHILIPPINE_ID, extracted_data=ed, metadata={})

    monkeypatch.setattr(api_app, "extract_data", fake_extract_data, raising=False)

    comp_req = {
        "image_base64": "data:image/jpeg;base64,TEST",
        "selfie_base64": None,
        "document_type": "PHILIPPINE_ID",
        "personal_info": {"full_name": "JUAN DELA CRUZ", "birth_date": "1990-01-01"},
        "device_info": {"ua": "pytest"},
        "session_id": "sess_test",
    }
    rc = client.post("/complete", json=comp_req)
    assert rc.status_code == 200
    out = rc.json()
    assert out.get("decision") in {"approve", "review", "deny", "pending"}
    # Optional blocks should be present due to our stubbed extraction
    assert out.get("issuer_verification") is not None
    assert out.get("aml_screening") is not None


