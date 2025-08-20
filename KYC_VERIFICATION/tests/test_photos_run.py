import os
import sys
import base64
from datetime import datetime

import numpy as np
import pytest
from fastapi.testclient import TestClient


# Ensure import path for KYC project
CURRENT_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir, os.pardir))
KYC_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
SRC_PATH = os.path.join(KYC_ROOT, "src")
for p in [KYC_ROOT, SRC_PATH]:
    if p not in sys.path:
        sys.path.insert(0, p)

from api.app import app  # noqa: E402


def install_component_stubs(monkeypatch):
    import api.app as api_app

    class FakeQualityAnalyzer:
        def analyze_frame(self, image):
            metrics = type(
                "M",
                (),
                {
                    "resolution": (640, 480),
                    "blur_score": 0.1,
                    "glare_score": 0.05,
                    "brightness_score": 0.5,
                    "contrast_score": 0.6,
                    "orientation_angle": 0.0,
                    "document_coverage": 0.8,
                    "edge_clarity": 0.7,
                    "overall_score": 0.98,
                },
            )
            return metrics, []

    class FakeDocumentClassifier:
        def classify(self, image):
            return type("C", (), {"document_type": type("T", (), {"value": "PhilID"}), "confidence": 0.95})

    class FakeAuthenticityChecker:
        def check_authenticity(self, image):
            return {"authentic": True, "confidence": 0.99, "issues": []}

    class FakeRiskScorer:
        def calculate_score(self, document_data, device_info, biometric_data, aml_data):
            return {"risk_score": 12.5, "risk_factors": [], "fraud_indicators": []}

    class FakeDecisionEngine:
        def make_decision(self, risk_score, extracted_data, validation_result, policy_overrides=None):
            return {
                "decision": "approve" if risk_score < 20 else "review",
                "confidence": 0.9,
                "reasons": [],
                "policy_version": "2024.1.0",
                "review_required": False,
                "review_reasons": [],
            }

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
    monkeypatch.setattr(api_app, "decode_base64_image", lambda _s: np.zeros((80, 80, 3), dtype=np.uint8), raising=False)


def _to_data_uri(path: str) -> str:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


@pytest.mark.parametrize(
    "image_path",
    [
        os.path.join(PROJECT_ROOT, "photo-id", "sample.jpg"),
        os.path.join(PROJECT_ROOT, "photo-id", "sample2.jpg"),
        os.path.join(PROJECT_ROOT, "photo-id", "sample3.jpg"),
        os.path.join(PROJECT_ROOT, "photo-id", "sample4.jpg"),
    ],
)
def test_run_photo_id_flow(image_path, monkeypatch):
    # Assert file exists now that user confirmed canonical paths
    assert os.path.exists(image_path), f"Missing test image: {image_path}"

    install_component_stubs(monkeypatch)
    client = TestClient(app)

    data_uri = _to_data_uri(image_path)
    session_id = os.path.splitext(os.path.basename(image_path))[0]

    results = []
    # validate
    rv = client.post("/validate", json={"image_base64": data_uri, "document_type": "PHILIPPINE_ID", "metadata": {"source": "pytest"}})
    results.append(("/validate", rv.status_code))

    # extract
    rx = client.post("/extract", json={"image_base64": data_uri, "extract_face": True, "extract_mrz": True, "extract_barcode": True})
    results.append(("/extract", rx.status_code))

    # complete
    rc = client.post("/complete", json={"image_base64": data_uri, "document_type": "PHILIPPINE_ID", "session_id": session_id, "device_info": {"ua": "pytest"}})
    results.append(("/complete", rc.status_code))

    # Write/append report
    report_path = os.path.join(PROJECT_ROOT, "outputs", "kyc_image_test_report.md")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    ok = all(s == 200 for _, s in results)
    with open(report_path, "a", encoding="utf-8") as f:
        if f.tell() == 0:
            f.write(f"# KYC Image Test Report\nGenerated: {datetime.now().isoformat()}\n\n")
        f.write(f"## {image_path}\n")
        for ep, st in results:
            f.write(f"- {ep}: HTTP {st}\n")
        if ok and rc.status_code == 200:
            f.write(f"- decision: {rc.json().get('decision')}\n")
        f.write("\n")

    # Assert overall ok to surface any failing endpoint
    assert ok, f"Failures in: {[ep for ep, st in results if st != 200]}"
