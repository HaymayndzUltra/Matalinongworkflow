# kyc_requirements_manifest.py
# python3 kyc_requirements_manifest.py

from typing import Dict, List, Any

REQUIREMENTS: Dict[str, List[Dict[str, Any]]] = {
  "identity_capture": [
    {"id": "IC1", "desc": "Web/mobile guided capture; glare/blur/orientation checks; multi-frame burst", "inputs": ["camera frames"], "outputs": ["best_frame", "quality_scores"], "accept": [">95% pass at 1000px width", "orientation auto-correct", "quality scores in [0..1]"]},
    {"id": "IC2", "desc": "Inputs: ID front/back, passport MRZ, selfie video for liveness", "inputs": ["id_front","id_back","passport","selfie_video"], "outputs": ["media_uris"], "accept": ["MIME/type validated", "size/duration limits enforced"]},
  ],
  "evidence_extraction": [
    {"id": "EE1", "desc": "Document classifier (ID/passport/other)", "inputs": ["best_frame"], "outputs": ["doc_type"], "accept": [">=0.9 top1 confidence on test set"]},
    {"id": "EE2", "desc": "OCR/MRZ/Barcode/NFC", "inputs": ["id_front","id_back","passport"], "outputs": ["ocr_text","mrz_fields","barcode_fields","nfc_dump"], "accept": ["ICAO 9303 checksums pass", "PDF417/QR parsed", "NFC where available"]},
    {"id": "EE3", "desc": "Face crops: ID and selfie", "inputs": ["id_front","selfie_video"], "outputs": ["id_face","selfie_faces[]"], "accept": ["face boxes returned", "min size 112x112"]},
  ],
  "authenticity_checks": [
    {"id": "AU1", "desc": "Security features: microprint/guilloché/UV (where feasible)", "inputs": ["id_front"], "outputs": ["feature_scores"], "accept": ["thresholds documented per template"]},
    {"id": "AU2", "desc": "Tamper detection: reprint/screenshot/composite", "inputs": ["id_front"], "outputs": ["tamper_score"], "accept": ["AUC≥0.9 on benchmark; ELA/noise/lighting features"]},
    {"id": "AU3", "desc": "Liveness: passive (texture/rPPG) + active (challenge)", "inputs": ["selfie_video"], "outputs": ["liveness_score","challenge_log"], "accept": ["FNMR≤3%, FMR≤1% on eval"]},
    {"id": "AU4", "desc": "Face match: ID vs selfie, multi-frame consensus", "inputs": ["id_face","selfie_faces[]"], "outputs": ["match_score"], "accept": ["TAR@FAR1% ≥ 98%"]},
  ],
  "sanctions_aml": [
    {"id": "SA1", "desc": "Sanctions/PEP/adverse media; watchlists; IP/geo", "inputs": ["name_dob","ip"], "outputs": ["screening_hits"], "accept": ["vendor API integrated", "hit explainability present"]},
  ],
  "risk_scoring": [
    {"id": "RS1", "desc": "Device fingerprint; proxy/VPN/TOR; geovelocity", "inputs": ["device","ip","events"], "outputs": ["device_risk"], "accept": ["proxy/VPN detection enabled"]},
    {"id": "RS2", "desc": "Doc validity/expiry; field consistency; issuer formats", "inputs": ["ocr_fields","mrz_fields"], "outputs": ["doc_risk"], "accept": ["expiry/format validators implemented"]},
    {"id": "RS3", "desc": "Aggregate score (rules + ML) → approve/review/deny", "inputs": ["signals*"], "outputs": ["risk_score","decision"], "accept": ["calibrated thresholds; ROC/AUC reported"]},
  ],
  "human_review": [
    {"id": "HR1", "desc": "Reviewer console with redaction, dual-control", "inputs": ["case"], "outputs": ["review_actions"], "accept": ["PII redaction toggle", "two-person approval on high risk"]},
  ],
  "compliance_security_privacy": [
    {"id": "CP1", "desc": "DPA/GDPR/CCPA; AML/KYC; NIST 800-63-3 alignment", "inputs": ["policies"], "outputs": ["compliance_matrix"], "accept": ["gaps documented and tracked"]},
    {"id": "CP2", "desc": "Data minimization; encryption at rest; KMS/HSM; WORM audit logs; retention", "inputs": ["data_flows"], "outputs": ["controls"], "accept": ["AES-256 at rest; TLS1.2+; append-only audit; retention policies applied"]},
    {"id": "CP3", "desc": "DPIA/ROPA", "inputs": ["processing_activities"], "outputs": ["DPIA","ROPA"], "accept": ["legal sign-off recorded"]},
  ],
  "operations": [
    {"id": "OP1", "desc": "Observability: metrics, traces, risk distributions, FPR", "inputs": ["events"], "outputs": ["dashboards","alerts"], "accept": ["SLOs defined; oncall alerts wired"]},
    {"id": "OP2", "desc": "AB tests; drift monitoring; periodic re-training; fairness checks", "inputs": ["model_artifacts"], "outputs": ["experiments","drift_reports"], "accept": ["drift alarms; bias audits scheduled"]},
  ]
}

REQUIRED_KEYS = {"id","desc","inputs","outputs","accept"}

def validate_manifest(m: Dict[str, List[Dict[str, Any]]]) -> None:
    missing = []
    for section, items in m.items():
        for it in items:
            miss = REQUIRED_KEYS - set(it.keys())
            if miss:
                missing.append((section, it.get("id"), sorted(miss)))
    if missing:
        raise SystemExit(f"Invalid manifest entries:\n" + "\n".join(str(x) for x in missing))
    print("Manifest OK:", sum(len(v) for v in m.values()), "requirements")

def print_checklist(m: Dict[str, List[Dict[str, Any]]]) -> None:
    for section, items in m.items():
        print(f"\n[{section}]")
        for it in items:
            print(f" - {it['id']}: {it['desc']} (accept: {', '.join(it['accept'])})")

if __name__ == "__main__":
    validate_manifest(REQUIREMENTS)
    print_checklist(REQUIREMENTS)
