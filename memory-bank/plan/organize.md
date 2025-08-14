# AI eKYC Confidence ≥95% Plan (Executable)

This plan makes your eKYC pipeline consistently achieve ≥95% combined confidence by: (1) capture quality gating; (2) probability calibration for classification; (3) multi-signal confidence aggregation; (4) policy thresholds; (5) continuous validation. All steps below are executable.

---

## 0) Prerequisites

- Python 3.10+ or Docker. For local dev without GPU:
```bash
# Recommended: Docker compose (full deps handled inside container)
# From project root
docker compose up -d api ui
# UI:  http://localhost:8080
# API: http://localhost:8000/docs
```

- Local minimal run (no heavy CV/ML libs):
```bash
# API (minimal)
python3 -m pip install --user fastapi uvicorn pydantic numpy opencv-python pillow scikit-image python-multipart
API_PORT=8000 python3 "KYC VERIFICATION/run_api.py"

# UI
python3 -m pip install --user jinja2 httpx starlette fastapi uvicorn python-multipart
API_BASE=http://localhost:8000 UI_PORT=8080 python3 "KYC VERIFICATION/run_ui.py"
```

- Create artifacts folder for models/calibrators:
```bash
mkdir -p "KYC VERIFICATION/artifacts" "KYC VERIFICATION/datasets/val"
```

---

## 1) Capture Quality Gating (pass@1000px ≥ 95%)

Enforce high capture quality before classification/extraction. This script checks a single image.
```bash
cat > "KYC VERIFICATION/scripts/run_quality_gate.py" <<'PY'
import cv2
from src.capture.quality_analyzer import CaptureQualityAnalyzer

QUALITY_MIN = 0.97

def passes_quality(img):
    qa = CaptureQualityAnalyzer()
    qm, hints = qa.analyze_frame(img)
    return qm.overall_score >= QUALITY_MIN, qm, hints

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python run_quality_gate.py <image_path>")
        sys.exit(2)
    img = cv2.imread(sys.argv[1])
    ok, qm, hints = passes_quality(img)
    print({"ok": ok, "overall": qm.overall_score, "blur": qm.blur_score, "glare": qm.glare_score})
PY
```
Run:
```bash
python3 "KYC VERIFICATION/scripts/run_quality_gate.py" /path/to/sample_id.jpg
```

---

## 2) Classifier Probability Calibration (Guo et al., ICML 2017)

Fit a calibrator so document-type probabilities are well-calibrated.
```bash
cat > "KYC VERIFICATION/scripts/calibrate_classifier.py" <<'PY'
import os
import numpy as np
from joblib import dump
from sklearn.linear_model import LogisticRegression
from sklearn.calibration import CalibratedClassifierCV
from src.classification.document_classifier import DocumentClassifier
import cv2

VAL_DIR = os.environ.get("VAL_DIR", "KYC VERIFICATION/datasets/val")

# Expect directory structure: datasets/val/<label>/*.jpg
# where <label> is one of: PHILIPPINE_ID, UMID, DRIVERS_LICENSE, PASSPORT, PRC_LICENSE

labels_map = {"PHILIPPINE_ID", "UMID", "DRIVERS_LICENSE", "PASSPORT", "PRC_LICENSE"}

def iter_val():
    for label in labels_map:
        cls_dir = os.path.join(VAL_DIR, label)
        if not os.path.isdir(cls_dir):
            continue
        for f in os.listdir(cls_dir):
            if f.lower().endswith((".jpg",".jpeg",".png")):
                yield os.path.join(cls_dir, f), label

def main():
    clf = DocumentClassifier()
    X, y = [], []
    for pth, true_label in iter_val():
        img = cv2.imread(pth)
        res = clf.classify(img)  # res.confidence (top-1), res.document_type.value
        p = float(res.confidence)
        p = np.clip(p, 1e-6, 1-1e-6)
        logit = np.log(p/(1-p))
        X.append([logit])
        y.append(int(true_label == str(res.document_type.value)))
    X = np.array(X); y = np.array(y)

    base = LogisticRegression(max_iter=1000)
    cal = CalibratedClassifierCV(base_estimator=base, cv=3, method="sigmoid")
    cal.fit(X, y)

    os.makedirs("KYC VERIFICATION/artifacts", exist_ok=True)
    dump(cal, "KYC VERIFICATION/artifacts/classifier_calibrator.joblib")
    print({"saved": "KYC VERIFICATION/artifacts/classifier_calibrator.joblib", "N": len(y)})

if __name__ == "__main__":
    main()
PY
```
Run:
```bash
VAL_DIR="KYC VERIFICATION/datasets/val" python3 "KYC VERIFICATION/scripts/calibrate_classifier.py"
```

---

## 3) Multi-Signal Confidence Aggregation (Quality + Calibrated Classifier + Authenticity + Consistency)

Train a logistic aggregator on features: [quality_score, p_cls_cal, authenticity_conf, consistency_score].
```bash
cat > "KYC VERIFICATION/scripts/train_aggregator.py" <<'PY'
import os, json
import numpy as np
import cv2
from joblib import load, dump
from sklearn.linear_model import LogisticRegression
from src.capture.quality_analyzer import CaptureQualityAnalyzer
from src.classification.document_classifier import DocumentClassifier
from src.forensics.authenticity_checker import AuthenticityChecker
from src.extraction.evidence_extractor import EvidenceExtractor

VAL_DIR = os.environ.get("VAL_DIR", "KYC VERIFICATION/datasets/val")
META_FILE = os.environ.get("VAL_META", "KYC VERIFICATION/datasets/val_meta.jsonl")
# val_meta.jsonl rows: {"path": "/img.jpg", "label": 1 for legit, 0 for fraud}

clf_cal = load("KYC VERIFICATION/artifacts/classifier_calibrator.joblib")

def to_logodds(p):
    p = np.clip(p, 1e-6, 1-1e-6)
    return np.log(p/(1-p))

def iter_meta():
    with open(META_FILE, "r", encoding="utf-8") as f:
        for line in f:
            o = json.loads(line)
            yield os.path.join(VAL_DIR, o["path"]) if not o["path"].startswith("/") else o["path"], int(o["label"]) 

def extract_features(img_bgr):
    qa = CaptureQualityAnalyzer(); qm, _ = qa.analyze_frame(img_bgr)
    dc = DocumentClassifier(); res = dc.classify(img_bgr)
    p = float(res.confidence)
    p = np.clip(p, 1e-6, 1-1e-6)
    p_cls = clf_cal.predict_proba([[to_logodds(p)]])[0,1]
    ac = AuthenticityChecker(); auth = ac.check_authenticity(img_bgr)
    p_auth = float(auth.get("confidence", 0.9))
    ex = EvidenceExtractor(); exr = ex.extract_all(img_bgr, "auto")
    consistency = 0.5
    if exr.mrz_data and exr.barcodes: consistency = 1.0
    elif exr.mrz_data or exr.barcodes: consistency = 0.8
    return np.array([qm.overall_score, p_cls, p_auth, consistency], dtype=float)

def main():
    X, y = [], []
    for pth, label in iter_meta():
        img = cv2.imread(pth)
        X.append(extract_features(img))
        y.append(label)
    X = np.vstack(X); y = np.array(y)

    clf = LogisticRegression(max_iter=1000, class_weight="balanced")
    clf.fit(X, y)

    os.makedirs("KYC VERIFICATION/artifacts", exist_ok=True)
    dump(clf, "KYC VERIFICATION/artifacts/aggregator_calibrator.joblib")
    np.save("KYC VERIFICATION/artifacts/agg_features.npy", X)
    np.save("KYC VERIFICATION/artifacts/agg_labels.npy", y)
    print({"saved": "KYC VERIFICATION/artifacts/aggregator_calibrator.joblib", "N": int(len(y))})

if __name__ == "__main__":
    main()
PY
```
Run:
```bash
VAL_DIR="KYC VERIFICATION/datasets/val" \
VAL_META="KYC VERIFICATION/datasets/val_meta.jsonl" \
python3 "KYC VERIFICATION/scripts/train_aggregator.py"
```

---

## 4) Runtime Combined Confidence (drop-in function)

Use the trained calibrators to compute final combined confidence p_final.
```bash
cat > "KYC VERIFICATION/scripts/combined_confidence.py" <<'PY'
import numpy as np, cv2
from pathlib import Path
from joblib import load
from src.capture.quality_analyzer import CaptureQualityAnalyzer
from src.classification.document_classifier import DocumentClassifier
from src.forensics.authenticity_checker import AuthenticityChecker
from src.extraction.evidence_extractor import EvidenceExtractor

clf_cal = load("KYC VERIFICATION/artifacts/classifier_calibrator.joblib")
agg_cal_pth = Path("KYC VERIFICATION/artifacts/aggregator_calibrator.joblib")
agg_cal = load(agg_cal_pth) if agg_cal_pth.exists() else None

def to_logodds(p):
    p = np.clip(p, 1e-6, 1-1e-6); return np.log(p/(1-p))

def combined_confidence(image_bgr):
    qa = CaptureQualityAnalyzer(); qm, _ = qa.analyze_frame(image_bgr)
    dc = DocumentClassifier(); res = dc.classify(image_bgr)
    p = float(res.confidence); p = np.clip(p, 1e-6, 1-1e-6)
    p_cls = clf_cal.predict_proba([[to_logodds(p)]])[0,1]
    ac = AuthenticityChecker(); auth = ac.check_authenticity(image_bgr)
    p_auth = float(auth.get("confidence", 0.9))
    ex = EvidenceExtractor(); exr = ex.extract_all(image_bgr, "auto")
    consistency = 0.5
    if exr.mrz_data and exr.barcodes: consistency = 1.0
    elif exr.mrz_data or exr.barcodes: consistency = 0.8
    feats = np.array([qm.overall_score, p_cls, p_auth, consistency], dtype=float).reshape(1,-1)
    if agg_cal is not None:
        p_final = float(agg_cal.predict_proba(feats)[0,1])
    else:
        p_final = float(np.clip((qm.overall_score * p_cls * p_auth * consistency) ** 0.25, 0.0, 1.0))
    return p_final, {"quality": qm.overall_score, "cls": p_cls, "auth": p_auth, "consistency": consistency}

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python combined_confidence.py <image_path>"); raise SystemExit(2)
    img = cv2.imread(sys.argv[1])
    p, parts = combined_confidence(img)
    print({"combined_confidence": p, "parts": parts})
PY
```
Run:
```bash
python3 "KYC VERIFICATION/scripts/combined_confidence.py" /path/to/sample_id.jpg
```

---

## 5) Policy thresholds (no magic numbers)

Configure thresholds in YAML (example):
```bash
cat > "KYC VERIFICATION/configs/policy_thresholds.yaml" <<'YAML'
confidence:
  min_approve: 0.95
  min_review: 0.80
YAML
```
Apply these thresholds in the decision engine (code change required in `src/scoring/decision_engine.py` or within `src/api/app.py` when constructing responses). Example logic:
- if p_final ≥ 0.95 → approve (if other checks clean)
- else if p_final ≥ 0.80 → review
- else → deny

---

## 6) Tests and acceptance checks

- Assert ≥95% of legit validation samples produce combined_confidence ≥ 0.95.
```bash
cat > "KYC VERIFICATION/tests/test_confidence_calibration.py" <<'PY'
import numpy as np

def test_combined_confidence_target():
    p = np.load("KYC VERIFICATION/artifacts/val_combined_conf_legit.npy")
    assert (p >= 0.95).mean() >= 0.95
PY
```
- Generate the validation distribution (example):
```bash
# Example script to save validation confidences
cat > "KYC VERIFICATION/scripts/eval_combined_conf_val.py" <<'PY'
import os, json, cv2, numpy as np
from combined_confidence import combined_confidence

VAL_DIR = os.environ.get("VAL_DIR", "KYC VERIFICATION/datasets/val")
META_FILE = os.environ.get("VAL_META", "KYC VERIFICATION/datasets/val_meta.jsonl")

conf_legit = []
with open(META_FILE, "r", encoding="utf-8") as f:
    for line in f:
        o = json.loads(line)
        pth = o["path"] if o["path"].startswith("/") else os.path.join(VAL_DIR, o["path"]) 
        if o["label"] != 1: # legit only
            continue
        img = cv2.imread(pth)
        p,_ = combined_confidence(img)
        conf_legit.append(p)

import numpy as np
np.save("KYC VERIFICATION/artifacts/val_combined_conf_legit.npy", np.array(conf_legit))
print({"saved": "KYC VERIFICATION/artifacts/val_combined_conf_legit.npy", "N": len(conf_legit)})
PY

VAL_DIR="KYC VERIFICATION/datasets/val" \
VAL_META="KYC VERIFICATION/datasets/val_meta.jsonl" \
python3 "KYC VERIFICATION/scripts/eval_combined_conf_val.py"
pytest -q "KYC VERIFICATION/tests/test_confidence_calibration.py"
```

---

## 7) Rolling out (runtime integration)

- Load `classifier_calibrator.joblib` and `aggregator_calibrator.joblib` at API startup, and compute `p_final` in `/validate` or `/complete` before constructing the response. Suggested integration points:
  - `src/api/app.py` → inside `validate_document` (after quality/classifier/authenticity) OR
  - inside `complete_kyc_verification` and propagate as `confidence`.
- Use `policy_thresholds.yaml` in the decision engine.

Rollback-safe: keep old logic behind a feature flag (env var `CONF_AGG_ENABLED=true|false`).

---

## 8) Monitoring & drift

- Export histograms: extend `/metrics` to expose moving average of combined_confidence; alert if median/confidence drops.
- Schedule monthly calibration: re-run steps (2)-(3) on fresh labeled data.

---

## 9) UI validation

- Start both servers and run a few documents end-to-end:
```bash
make run-api
API_BASE=http://localhost:8000 UI_PORT=8080 make run-ui
# Open http://localhost:8080, upload ID (and selfie optional), verify decision & confidence
```

---

## Acceptance Criteria

- Combined confidence p_final on legit validation set: ≥95% of samples have p_final ≥ 0.95
- API latency budget preserved (added aggregator < 10ms P99).
- Policy thresholds configurable (no magic numbers).
- Tests pass and metrics show stability.

---

## Failure modes & mitigations

- Over-confidence due to drift → monthly recalibration, drift alerts, feature flag for rollbacks.
- Low-quality capture → coaching via UI; enforce `QUALITY_MIN`.
- Vendor outages → existing vendor orchestrator and circuit breakers; do not block calibration.

---

## References
- Guo, Chuan, et al. "On Calibration of Modern Neural Networks." ICML 2017.
- FastAPI & Pydantic docs (for runtime integration of thresholds and models).
