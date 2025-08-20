#!/usr/bin/env python3
import os
import sys
import base64
from datetime import datetime

import numpy as np
from fastapi.testclient import TestClient


ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
KYC_DIR = os.path.join(ROOT, "KYC VERIFICATION")
SRC = os.path.join(KYC_DIR, "src")
for p in [ROOT, KYC_DIR, SRC]:
    if p not in sys.path:
        sys.path.insert(0, p)

import importlib.util


def import_app_by_path():
    mod_path = os.path.join(SRC, "api", "app.py")
    spec = importlib.util.spec_from_file_location("kyc_api_app", mod_path)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader, f"Cannot load spec for {mod_path}"
    sys.modules["kyc_api_app"] = mod
    spec.loader.exec_module(mod)
    return mod


def install_stubs(api_mod):

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

    api_mod.get_component = fake_get_component
    api_mod.decode_base64_image = lambda _s: np.zeros((80, 80, 3), dtype=np.uint8)


def to_data_uri(image_path: str) -> str:
    with open(image_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return f"data:image/jpeg;base64,{b64}"


def run_for_image(client: TestClient, image_path: str) -> dict:
    data_uri = to_data_uri(image_path)
    out: dict = {"image": image_path, "steps": []}

    # 1) /validate
    payload_v = {"image_base64": data_uri, "document_type": "PHILIPPINE_ID", "metadata": {"source": "script"}}
    rv = client.post("/validate", json=payload_v)
    out["steps"].append({"endpoint": "/validate", "status": rv.status_code, "ok": rv.status_code == 200})

    # 2) /extract
    payload_x = {"image_base64": data_uri, "extract_face": True, "extract_mrz": True, "extract_barcode": True}
    rx = client.post("/extract", json=payload_x)
    out["steps"].append({"endpoint": "/extract", "status": rx.status_code, "ok": rx.status_code == 200})

    # 3) /complete (single step flow)
    payload_c = {
        "image_base64": data_uri,
        "document_type": "PHILIPPINE_ID",
        "session_id": os.path.basename(image_path).split(".")[0],
        "device_info": {"ua": "runner"},
    }
    rc = client.post("/complete", json=payload_c)
    out["steps"].append({"endpoint": "/complete", "status": rc.status_code, "ok": rc.status_code == 200})
    if rc.status_code == 200:
        out["decision"] = rc.json().get("decision")
    return out


def write_report(results: list, path: str):
    ok = []
    pending = []
    for r in results:
        failed = [s for s in r["steps"] if not s["ok"]]
        if failed:
            pending.append({"image": r["image"], "failed": failed})
        else:
            ok.append({"image": r["image"], "decision": r.get("decision")})

    lines = []
    lines.append(f"# KYC Image Test Report\n")
    lines.append(f"Generated: {datetime.now().isoformat()}\n")
    lines.append("\n## Successful\n")
    if ok:
        for item in ok:
            lines.append(f"- {item['image']}: decision={item.get('decision','n/a')}")
    else:
        lines.append("- None")

    lines.append("\n## Pending/Failed\n")
    if pending:
        for item in pending:
            lines.append(f"- {item['image']}:" )
            for s in item["failed"]:
                lines.append(f"  - {s['endpoint']} → HTTP {s['status']}")
    else:
        lines.append("- None")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main():
    mod = import_app_by_path()
    install_stubs(mod)
    client = TestClient(mod.app)
    images = [
        os.path.join(ROOT, "photo-id", "sample3.jpg"),
        os.path.join(ROOT, "photo-id", "sample4.jpg"),
    ]
    results = [run_for_image(client, p) for p in images if os.path.exists(p)]
    out_path = os.path.join(ROOT, "outputs", "kyc_image_test_report.md")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    write_report(results, out_path)
    print(f"Report written to: {out_path}")
    # Print brief summary
    for r in results:
        failed = [s for s in r["steps"] if not s["ok"]]
        status = "OK" if not failed else "FAILED"
        print(f"{r['image']}: {status}")


if __name__ == "__main__":
    main()


