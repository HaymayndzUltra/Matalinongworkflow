Human-Readable Plan Draft for Backend-Only Face Scan Implementation
PHASE 0: SETUP & PROTOCOL (READ FIRST)
Explanations: This phase establishes the foundational understanding and constraints for the backend-only face scan implementation. We will set up the development environment, review all protocol directives, and ensure we understand the scope constraints: backend-only modifications, no edits to src/web/mobile_kyc.html, creation/modification limited to specific modules (src/api/app.py, src/api/contracts.py, src/config/threshold_manager.py, and new src/face/* modules). We'll also review privacy requirements (no raw PII/images in logs unless DEBUG explicitly enabled) and CORS/HTTPS exposure requirements.
Concluding Step: Phase Completion Protocol
python3 todo_manager.py show face_scan_actionable_20250116
python3 todo_manager.py done face_scan_actionable_20250116 0
IMPORTANT NOTE: Backend-only edits are enforced; feature flags are allowed; all phase gates must pass before proceeding to next phase. Documentation must be created for post-review/pre-analysis stages.
PHASE 1: CONTRACTS & STATIC MOUNT SCAFFOLDING
Explanations: In this phase, we add Pydantic models for face scan APIs, define all necessary contracts for the face scanning endpoints, and mount the /web path for static file serving without making any UI changes. This establishes the API structure and ensures OpenAPI documentation properly exposes the new endpoints.
Concluding Step: Phase Completion Protocol
python3 todo_manager.py show face_scan_actionable_20250116
python3 todo_manager.py done face_scan_actionable_20250116 1
IMPORTANT NOTE: No breaking changes to existing endpoints are permitted. All new contracts must compile successfully and OpenAPI must properly expose all new endpoints.
PHASE 2: THRESHOLD MANAGER (STRICT FACE GATES)
Explanations: Implementation of the threshold management system with strict face gates. We'll add comprehensive thresholds including bbox_fill, centering, pose, Tenengrad@640w, brightness (mean/p05/p95), stability milliseconds, PAD minimum, burst caps, and match thresholds. All values must be validated and environment overrides must be properly documented.
Concluding Step: Phase Completion Protocol
python3 todo_manager.py show face_scan_actionable_20250116
python3 todo_manager.py done face_scan_actionable_20250116 2
IMPORTANT NOTE: Explicit names are required for all thresholds; validation and bounds must be strictly enforced with no exceptions.
PHASE 3: GEOMETRY & GATING LIBRARY
Explanations: Create src/face/geometry.py containing pure functions for occupancy calculation, centering evaluation, pose assessment, brightness analysis, Tenengrad sharpness computation, and stability measurements. All functions must provide reasoned failures with deterministic outputs and comprehensive unit tests.
Concluding Step: Phase Completion Protocol
python3 todo_manager.py show face_scan_actionable_20250116
python3 todo_manager.py done face_scan_actionable_20250116 3
IMPORTANT NOTE: No I/O side effects are allowed in any geometry functions. All functions must be pure with deterministic outputs.
PHASE 4: /face/lock/check ENDPOINT
Explanations: Implement the /face/lock/check endpoint that evaluates lock conditions using geometry calculations and thresholds. The endpoint must require continuous pass for at least 900ms (UI runs 600ms countdown after lock). Response format must include {ok, lock, reasons[], thresholds{}} with performance target of ≤20ms typical response time.
Concluding Step: Phase Completion Protocol
python3 todo_manager.py show face_scan_actionable_20250116
python3 todo_manager.py done face_scan_actionable_20250116 4
IMPORTANT NOTE: No images are accepted by this endpoint; implementation must be rate limit safe.
PHASE 5: PASSIVE PAD PRE-GATE
Explanations: Implement POST /face/pad/pre endpoint using PAD (Presentation Attack Detection) detector with spoof heuristics including moiré pattern detection, flat texture analysis, and uniform glare detection. The system must block when score <0.70 or when spoof_high flag is triggered. Returns passive_score and spoof flags that must be respected by the UI.
Concluding Step: Phase Completion Protocol
python3 todo_manager.py show face_scan_actionable_20250116
python3 todo_manager.py done face_scan_actionable_20250116 5
IMPORTANT NOTE: Images must be handled transiently with no persistence; all image data must be cleared from memory after processing.
PHASE 6: CHALLENGE SEQUENCER (VALIDATION)
Explanations: Create src/face/challenges.py and implement /face/challenge/script endpoint (picks 2 actions with TTL ≤7s) and /face/challenge/verify endpoint (performs EAR/MAR/yaw/time checks). Each action must complete within ≤3.5s and system must cancel on pose or brightness breach.
Concluding Step: Phase Completion Protocol
python3 todo_manager.py show face_scan_actionable_20250116
python3 todo_manager.py done face_scan_actionable_20250116 6
IMPORTANT NOTE: Deterministic outcomes with clear reasons are mandatory for all challenge verifications.
PHASE 7: BURST UPLOAD & STORAGE POLICY
Explanations: Implement /face/burst/upload endpoint supporting ≤24 frames within ≤3.5s using transient storage (RAM/tmpfs). Must include EXIF stripping and auto-deletion post-evaluation. Enforced limits must be respected and cleanup must occur even on errors.
Concluding Step: Phase Completion Protocol
python3 todo_manager.py show face_scan_actionable_20250116
python3 todo_manager.py done face_scan_actionable_20250116 7
IMPORTANT NOTE: No gallery writes permitted; no long-term storage allowed; all data must be transient.
PHASE 8: CONSENSUS & BIOMETRICS EVAL
Explanations: Create src/face/consensus.py to filter blur/glare/pose failures, select top-k=5 frames, match against ID photo with median≥0.62, require ≥3 frames≥0.58, and reject if any top-k <0.58. Implement /face/burst/eval endpoint returning {match_score, consensus_ok, frames_used, topk_scores[]}.
Concluding Step: Phase Completion Protocol
python3 todo_manager.py show face_scan_actionable_20250116
python3 todo_manager.py done face_scan_actionable_20250116 8
IMPORTANT NOTE: FAR target ~1% must be maintained; all thresholds must be configurable via ThresholdManager.
PHASE 9: DECISION MAPPING (FACE COMPONENT)
Explanations: Implement /face/decision endpoint that maps passive score, challenges_passed, consensus_ok, and match_score to approve/review/deny decisions with clear reasons. Must auto-deny on liveness_fail, consensus_fail, or spoof_high conditions. Include human-readable reasons and policy_version snapshot in responses.
Concluding Step: Phase Completion Protocol
python3 todo_manager.py show face_scan_actionable_20250116
python3 todo_manager.py done face_scan_actionable_20250116 9
IMPORTANT NOTE: No PII permitted in decision logs; only anonymized metrics and decision reasons.
PHASE 10: TELEMETRY & /metrics
Explanations: Implement POST /face/telemetry for tracking FACE_SEARCHING, FACE_LOCK, COUNTDOWN_START/STOP, BURST_START/END, CHALLENGE_ISSUED/PASSED/FAILED, LIVENESS_PASS/FAIL, MATCH_SCORE, CONSENSUS_OK, and FACE_DONE events. Create /metrics endpoint exposing time_to_lock_ms, cancel_rate, challenge_success_rate, median_match_score, and passive_pad_fmr/fnmr aggregates.
Concluding Step: Phase Completion Protocol
python3 todo_manager.py show face_scan_actionable_20250116
python3 todo_manager.py done face_scan_actionable_20250116 10
IMPORTANT NOTE: Respect privacy requirements; no raw images in telemetry; aggregates only with device model if available.
PHASE 11: PRIVACY & WORM AUDIT
Explanations: Enforce comprehensive privacy measures including no gallery storage, EXIF stripping, and redacted logs. Implement WORM (Write Once Read Many) audit snapshot system capturing thresholds used and decision rationale. Audit entries must be written with documented retention policy.
Concluding Step: Phase Completion Protocol
python3 todo_manager.py show face_scan_actionable_20250116
python3 todo_manager.py done face_scan_actionable_20250116 11
IMPORTANT NOTE: Store policy snapshot and metrics only; no raw biometric data in audit logs.
PHASE 12: ACCEPTANCE CRITERIA & VALIDATION
Explanations: Validate all performance targets: Lock p50 ≤1.2s, p95 ≤2.5s; countdown ≥600ms; cancel-on-jitter <50ms; challenge pass-rate ≥95% (good light); TAR@FAR1% ≥0.98 (eval set); PAD FMR ≤1%, FNMR ≤3%. Generate comprehensive report with metrics and propose threshold adjustments if gaps exist.
Concluding Step: Phase Completion Protocol
python3 todo_manager.py show face_scan_actionable_20250116
python3 todo_manager.py done face_scan_actionable_20250116 12
IMPORTANT NOTE: Use ThresholdManager for all adjustments; no hardcoding of thresholds in code is permitted.
Plan Draft Complete - Ready for Approval
This Human-Readable Plan Draft has been generated from memory-bank/plan/organize.md with all phases properly structured, including:
Phase 0 (Setup & Protocol)
Phases 1-12 covering the complete implementation
Each phase includes Explanations, Concluding Step protocol, and IMPORTANT NOTE
All constraints and requirements from the source document are preserved