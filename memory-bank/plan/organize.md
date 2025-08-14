# Human-Readable Plan Draft — eKYC Combined Confidence ≥95%

PHASE 0: SETUP & PROTOCOL (READ FIRST)
- **Explanations:** Use containerized stack for consistency; prepare calibration artifacts; run minimal local stack only if Docker is unavailable. Do not write to queue/state files during ingestion. All thresholds must be config-driven.
- **Concluding Step: Phase Completion Protocol**
```bash
python3 todo_manager.py show <TASK_ID>
python3 todo_manager.py done <TASK_ID> 0
```
- **IMPORTANT NOTE:**
  - [SYNTHESIZED FROM ORGANIZER] Prefer Docker Compose; otherwise install minimal deps only for API/UI.
  - [SYNTHESIZED FROM ORGANIZER] Store artifacts under `KYC VERIFICATION/artifacts/`. No secrets in code; respect PII redaction.
  - [SYNTHESIZED FROM ORGANIZER] Do not write to `memory-bank/queue-system/*.json`. JSON for ingestion will be output only after approval.
  - [SYNTHESIZED FROM ORGANIZER] Timestamps in ISO8601 +08:00; thresholds come from YAML, not magic numbers.

PHASE 1: Establish Capture Quality Gating (pass@1000px ≥ 95%)
- **Explanations:** Enforce `QUALITY_MIN >= 0.97` prior to classification/extraction to ensure data quality. Provide a script to evaluate frames and surface blur/glare to the UI.
- **Concluding Step: Phase Completion Protocol**
```bash
python3 todo_manager.py show <TASK_ID>
python3 todo_manager.py done <TASK_ID> 1
```
- **IMPORTANT NOTE:**
  - [SYNTHESIZED FROM ORGANIZER] Gate must be tunable via config; default 0.97.
  - [SYNTHESIZED FROM ORGANIZER] UI should coach users until quality gate passes.

PHASE 2: Calibrate Classifier Probabilities (Platt/Sigmoid)
- **Explanations:** Fit `CalibratedClassifierCV` on validation set for document-type top-1 probability to fix over/under-confidence. Save `classifier_calibrator.joblib` in artifacts.
- **Concluding Step: Phase Completion Protocol**
```bash
python3 todo_manager.py show <TASK_ID>
python3 todo_manager.py done <TASK_ID> 2
```
- **IMPORTANT NOTE:**
  - [SYNTHESIZED FROM ORGANIZER] Dataset must be clean, issuer-balanced; no leakage from train to validation.

PHASE 3: Train Multi-Signal Aggregator (Quality + Calibrated Class + Authenticity + Consistency)
- **Explanations:** Train a logistic combiner over features `[quality_score, p_cls_cal, authenticity_conf, consistency_score]` using legit/fraud labels from `val_meta.jsonl`. Save `aggregator_calibrator.joblib`.
- **Concluding Step: Phase Completion Protocol**
```bash
python3 todo_manager.py show <TASK_ID>
python3 todo_manager.py done <TASK_ID> 3
```
- **IMPORTANT NOTE:**
  - [SYNTHESIZED FROM ORGANIZER] Consistency uses MRZ/Barcode presence; ensure extractors are deterministic for eval.

PHASE 4: Implement Runtime Combined Confidence
- **Explanations:** Provide a runtime function that loads both calibrators and computes `p_final` with fallback geometric mean when aggregator is absent.
- **Concluding Step: Phase Completion Protocol**
```bash
python3 todo_manager.py show <TASK_ID>
python3 todo_manager.py done <TASK_ID> 4
```
- **IMPORTANT NOTE:**
  - [SYNTHESIZED FROM ORGANIZER] Keep inference latency overhead <10ms P99.

PHASE 5: Apply Policy Thresholds via YAML (No Magic Numbers)
- **Explanations:** Add `configs/policy_thresholds.yaml` with `min_approve: 0.95, min_review: 0.80` and wire into decision engine.
- **Concluding Step: Phase Completion Protocol**
```bash
python3 todo_manager.py show <TASK_ID>
python3 todo_manager.py done <TASK_ID> 5
```
- **IMPORTANT NOTE:**
  - [SYNTHESIZED FROM ORGANIZER] All thresholds tunable; changes must be audit-logged.

PHASE 6: Tests and Acceptance Checks (≥95% legit at ≥0.95)
- **Explanations:** Generate validation confidences for legit subset; assert that at least 95% are ≥0.95. Add a unit test and save the distribution to artifacts.
- **Concluding Step: Phase Completion Protocol**
```bash
python3 todo_manager.py show <TASK_ID>
python3 todo_manager.py done <TASK_ID> 6
```
- **IMPORTANT NOTE:**
  - [SYNTHESIZED FROM ORGANIZER] Seed runs; ensure reproducibility; store metrics with timestamps.

PHASE 7: Integrate and Roll Out (Feature-flagged)
- **Explanations:** Load calibrators at API startup; compute `p_final` in `/validate` or `/complete`. Use env flag `CONF_AGG_ENABLED=true|false` for safe rollback.
- **Concluding Step: Phase Completion Protocol**
```bash
python3 todo_manager.py show <TASK_ID>
python3 todo_manager.py done <TASK_ID> 7
```
- **IMPORTANT NOTE:**
  - [SYNTHESIZED FROM ORGANIZER] Keep current behavior as fallback; do not break contracts.

PHASE 8: Monitoring & Drift
- **Explanations:** Extend `/metrics` to export combined confidence distribution; alert on median/quantile drops. Monthly recalibration on fresh labeled data.
- **Concluding Step: Phase Completion Protocol**
```bash
python3 todo_manager.py show <TASK_ID>
python3 todo_manager.py done <TASK_ID> 8
```
- **IMPORTANT NOTE:**
  - [SYNTHESIZED FROM ORGANIZER] Do not block traffic on drift; just alert and schedule recalibration.

PHASE 9: UI Validation (End-to-End)
- **Explanations:** Run `make run-api` and `make run-ui`; upload samples; verify decisions align with thresholds and present detailed parts (quality, cls, auth, consistency).
- **Concluding Step: Phase Completion Protocol**
```bash
python3 todo_manager.py show <TASK_ID>
python3 todo_manager.py done <TASK_ID> 9
```
- **IMPORTANT NOTE:**
  - [SYNTHESIZED FROM ORGANIZER] PII redaction ON by default in reviewer views.
