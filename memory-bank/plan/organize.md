Scope/constraints
Backendonly face scan implementation. Do not edit `src/web/mobile_kyc.html` (AI‑1 domain).
Create/modify only: `src/api/app.py`, `src/api/contracts.py`, `src/config/threshold_manager.py`, and new `src/face/*` modules. Optional: mount static under `/web` without touching AI‑1 files.
Expose CORS/HTTPS; no raw PII/images in logs unless DEBUG explicitly enabled.

PHASE 0: SETUP & PROTOCOL (READ FIRST)
Explanations: Backendonly endpoints, scoring, telemetry, privacy/audit, thresholds. No UI edits.
DoD: Plan gates pass; docs created (postreview/preanalysis).
IMPORTANT NOTE: Backendonly edits; feature flags allowed; follow gates.

PHASE 1: CONTRACTS & STATIC MOUNT SCAFFOLDING
Explanations: Add Pydantic models for face scan APIs; define contracts; mount `/web` path (no UI changes).
DoD: Contracts compile; OpenAPI exposes new endpoints; `/web` mounted.
IMPORTANT NOTE: No breaking changes to existing endpoints.

PHASE 2: THRESHOLD MANAGER (STRICT FACE GATES)
Explanations: Add thresholds (bbox_fill, centering, pose, Tenengrad@640w, brightness mean/p05/p95, stability ms, PAD min, burst caps, match thresholds).
DoD: Values validated; env overrides documented.
 IMPORTANT NOTE: Explicit names; validation + bounds enforced.

PHASE 3: GEOMETRY & GATING LIBRARY
 Explanations: `src/face/geometry.py` for occupancy, centering, pose, brightness, Tenengrad, stability; reasoned failures.
 DoD: Pure functions with unit tests; deterministic outputs.
 IMPORTANT NOTE: No I/O sideeffects.

PHASE 4: /face/lock/check ENDPOINT
 Explanations: Evaluate lock using geometry + thresholds; require continuous pass ≥900 ms (UI runs 600 ms countdown after lock).
 DoD: Returns {ok, lock, reasons[], thresholds{}}; perf ≤20ms typical.
 IMPORTANT NOTE: No images accepted; rate limit safe.

PHASE 5: PASSIVE PAD PRE‑GATE
 Explanations: `POST /face/pad/pre` using PAD detector; spoof heuristics (moiré, flat textures, uniform glare). Block when score <0.70 or spoof_high.
 DoD: Returns passive_score + spoof flags; respected by UI.
 IMPORTANT NOTE: Images handled transiently; no persistence.

PHASE 6: CHALLENGE SEQUENCER (VALIDATION)
 Explanations: `src/face/challenges.py`; `/face/challenge/script` (pick 2 actions; TTL ≤7s), `/face/challenge/verify` (EAR/MAR/yaw/time checks).
 DoD: Peraction ≤3.5s; cancel on pose/brightness breach.
 IMPORTANT NOTE: Deterministic outcomes with reasons.

PHASE 7: BURST UPLOAD & STORAGE POLICY
 Explanations: `/face/burst/upload` ≤24 frames/≤3.5s; transient storage (RAM/tmpfs); EXIF strip; autodelete post‑eval.
 DoD: Enforced limits; cleanup even on errors.
 IMPORTANT NOTE: No gallery writes; no longterm storage.

PHASE 8: CONSENSUS & BIOMETRICS EVAL
 Explanations: `src/face/consensus.py` filter blur/glare/posefail; top‑k=5; match vs ID photo; median≥0.62; ≥3 frames≥0.58; no top‑k <0.58. `/face/burst/eval`.
 DoD: Returns {match_score, consensus_ok, frames_used, topk_scores[]}.
 IMPORTANT NOTE: FAR target ~1%; thresholds configurable.

PHASE 9: DECISION MAPPING (FACE COMPONENT)
 Explanations: `/face/decision` maps passive score, challenges_passed, consensus_ok, match_score to approve/review/deny with reasons; autodeny on liveness_fail/consensus_fail/spoof_high.
 DoD: Humanreadable reasons + policy_version snapshot.
 IMPORTANT NOTE: No PII in decision logs.

PHASE 10: TELEMETRY & /metrics
 Explanations: `POST /face/telemetry` for FACE_SEARCHING, FACE_LOCK, COUNTDOWN_START/STOP, BURST_START/END, CHALLENGE_ISSUED/PASSED/FAILED, LIVENESS_PASS/FAIL, MATCH_SCORE, CONSENSUS_OK, FACE_DONE. `/metrics` exposes time_to_lock_ms, cancel_rate, challenge_success_rate, median_match_score, passive_pad_fmr/fnmr.
 DoD: Aggregates only; device model if available.
 IMPORTANT NOTE: Respect privacy; no raw images.

PHASE 11: PRIVACY & WORM AUDIT
 Explanations: Enforce privacy (no gallery, EXIF strip, redacted logs). WORM audit snapshot with thresholds used & decision rationale.
 DoD: Audit entries written; retention policy documented.
 IMPORTANT NOTE: Store policy snapshot + metrics only.

PHASE 12: ACCEPTANCE CRITERIA & VALIDATION
 Explanations: Validate targets—Lock p50 ≤1.2s, p95 ≤2.5s; countdown ≥600ms; cancelonjitter <50ms; challenge pass‑rate ≥95% (good light); TAR@FAR1% ≥0.98 (eval set); PAD FMR ≤1%, FNMR ≤3%. Metrics exposed and documented.
 DoD: Report with metrics; threshold proposals if gaps exist.
 IMPORTANT NOTE: Use ThresholdManager for adjustments; no hardcoding in code.
