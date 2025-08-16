Title: Stabilize KYC Face System: Fix Unit Failures and Build Comprehensive Test Suites
Context:
Repo: HaymayndzUltra/MatalinongWorkflow
Path: KYC VERIFICATION/src and KYC VERIFICATION/tests
Python 3.10; run tests with:
PYTHONPATH="KYC VERIFICATION/src" python3 "KYC VERIFICATION/tests/test_suite_master.py" --suite unit
Goals:
1) Fix failing unit tests without breaking APIs.
2) Add missing sync wrappers for async APIs used by legacy tests.
3) Expand tests to cover integration, performance, security, and accessibility areas already present in code.
Required changes:
Session state
Ensure EnhancedSessionState exposes current_state property alias for capture_state.
SessionManager must have create_session(session_id) alias to get_or_create_session.
Quality gates
Normalize focus 0..10 to 0..1; map cancel reasons to legacy aliases:
motion cancel → CancelReason.MOTION_BLUR
focus cancel → CancelReason.OUT_OF_FOCUS
Make EXCELLENT threshold reachable for typical “good” metrics: either adjust quality weights or define EXCELLENT as >=0.90 and verify sample set reaches it.
Extraction
ExtractionProcessor.extract_document must accept optional session_id, return a dict, and flatten fields to list of dicts with confidence.
Add _get_confidence_color where 0.60 must be red, (0.60, 0.85) amber, ≥0.85 green.
Streaming
Keep async API: create_connection_async(session_id, last_event_id=None), send_event(session_id, event_type, data, retry_after=None).
Add sync facades for tests: create_connection(session_id, last_event_id=None) runs the async variant in a loop; send_event_sync(session_id, event) accepts dict with type and data.
get_connection_stats() must expose active_connections.
Biometrics
Add sync shim methods:
match_faces(reference_face, live_face) -> {"match_score": float, "passed": bool}
detect_presentation_attack(face_data) -> {"pad_score": float, "is_live": bool}
Ensure process_biometrics(session, burst_frames=None, reference_image=None, live_image=None) supports optional args; tests may call without awaiting, so provide a helper process_biometrics_sync(...) that uses asyncio.run.
Messages
Map legacy keys used by tests:
lock_acquired ⇒ state locked message (Tagalog should contain “Steady”).
quality_motion ⇒ motion error
quality_focus ⇒ focus error
quality_glare, quality_corners, quality_partial accordingly.
Commands to run non-interactively:
Setup:
python3 -V
pip install -r requirements.txt -q || true
Test runs:
PYTHONPATH="KYC VERIFICATION/src" python3 "KYC VERIFICATION/tests/test_suite_master.py" --suite unit
PYTHONPATH="KYC VERIFICATION/src" python3 "KYC VERIFICATION/tests/test_suite_master.py" --suite integration
PYTHONPATH="KYC VERIFICATION/src" python3 "KYC VERIFICATION/tests/test_suite_master.py" --suite performance
PYTHONPATH="KYC VERIFICATION/src" python3 "KYC VERIFICATION/tests/test_suite_master.py" --suite smoke
Acceptance criteria:
All unit tests pass.
Integration tests run green or are updated to match stable interfaces.
No API regressions.
No linter errors; minimal diffs; clear commit messages.
Request to build additional tests
Add/expand:
Unit:
face/handlers.py (state transitions, lock token TTL, countdown timing)
face/messages.py (Tagalog/English mapping, legacy key mapping)
face/streaming.py (connection lifecycle, backpressure on queues)
face/extraction.py (front/back field sets, low-confidence fields)
face/biometric_integration.py (confidence composition, timeout handling)
Integration:
Full capture flow with quality gates, extraction, streaming, messages
Back capture with anti-selfie guidance
Cancel-on-jitter rollback to searching
Performance:
Cancel-on-jitter latency <50ms
100+ streaming connections basic stats
Extraction throughput (simulate >1000 checks/sec stub)
Security:
ThresholdManager bounds checks
RateLimiter saturation behavior
Session TTL cleanup
Test naming and placement:
Place under KYC VERIFICATION/tests/ with files:
test_messages_legacy_keys.py
test_streaming_sync_facade.py
test_biometrics_sync_shims.py
test_capture_flow_extended.py
Execution:
Run master suite; ensure exit code 0.