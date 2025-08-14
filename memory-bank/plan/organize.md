Scope/constraints
New UI for face scan; no changes to backend files.
Create only in KYC VERIFICATION/src/web/ and docs/.
All validation/gating calls go to backend endpoints; UI shows states and guides.
Milestone 1 — Scaffolding
Files to add
src/web/face_scan.html
src/web/css/face_scan.css
src/web/js/face_scan.js
docs/face_scan_contract.md (copy of endpoint payloads used by UI)
DoD
Page loads over HTTPS; shows empty state; includes CSS/JS; no console errors.
Milestone 2 — State machine + transport
Implement states: SEARCHING → FACE_LOCK → COUNTDOWN → BURST_CAPTURE → CHALLENGE → EVAL → DONE|RETRY
Implement event bus/timers; 60–120 ms tick for UI; 5–10 Hz network calls.
DoD
Deterministic transitions; cancellable countdown; retry path from any fail.
Milestone 3 — Camera + device readiness
getUserMedia with facingMode=user; permission UX; orientation lock; reduced‑motion detection.
Video metrics sampler (downsample ROI to 160×100 for light/focus proxies).
DoD
Works on modern mobile browsers (Chrome/Safari); shows helpful error prompts.
Milestone 4 — Face lock UI loop (strict visual feedback)
Visuals: amber ring (SEARCHING), green ring (FACE_LOCK), 600 ms countdown ring, cancel on jitter.
Backend call (poll): POST /face/lock/check
UI sends: {w,h, face_bbox?, pose?, brightness {mean,p05,p95}, focus_proxy, occupancy?, ts}
DoD
No capture unless backend returns lock:true continuously for ≥900 ms + 600 ms countdown visible.
Milestone 5 — Passive PAD pre‑gate
On FACE_LOCK, call POST /face/pad/pre once per lock.
If passive_score < 0.70 or spoof flags present → block and show microcopy (“Ayusin ang ilaw / iwasan ang screen refleksyon”).
DoD
UI never proceeds to challenge when passive PAD fails.
Milestone 6 — Burst capture (client) + upload
Capture ≤24 frames in ≤3.5 s; drop frames on strong motion/blur (client‑side heuristic only).
POST /face/burst/upload chunks; progress arc; haptic tick end.
DoD
Upload completes under 4 s on decent network; shows progress and completion.
Milestone 7 — Challenge sequencer (UI prompts only)
Get script: POST /face/challenge/script → 2 randomized actions, ttl ≤7 s.
Show prompt chips + countdown per action (≤3.5 s); cancel on pose/brightness fail (from lock loop).
Send telemetry per action (lightweight if no landmarks): POST /face/challenge/verify
DoD
Clear prompts; timer visible; fail fast on timeouts/jitter; success marks action chip.
Milestone 8 — Evaluation + decision (face component)
Call POST /face/burst/eval → show match_score, frames_used, consensus chip.
Call POST /face/decision with {passive_score, challenges_passed, consensus_ok, match_score}.
DoD
Result chips: Approve/Review/Deny; human‑readable reasons; retry button.
Milestone 9 — Telemetry + metrics emit (client side)
POST /face/telemetry events:
FACE_SEARCHING, FACE_LOCK, COUNTDOWN_START/STOP, BURST_START/END,
CHALLENGE_ISSUED, CHALLENGE_PASSED/FAILED, LIVENESS_PASS/FAIL,
MATCH_SCORE, CONSENSUS_OK, FACE_DONE
DoD
All critical transitions emit once; payload includes device model if available.
Milestone 10 — UX/microcopy + accessibility
Microcopy (Tagalog‑first) for lock/lighting/steady/challenge/fail.
Reduced‑motion: replace motion with fades; no haptics.
DoD
Screen‑reader labels; font scale safe; high contrast OK.
Milestone 11 — Config/flags + debug panel
Feature flags (read from querystring/localStorage):
?debug=1 → show metrics panel (focus/brightness/pose/occupancy, event log).
?reduced_motion=1 → force fade mode.
DoD
QA can toggle without code changes.
Milestone 12 — QA matrix (runbook embedded in docs)
Scenarios (10 trials each): lighting (diffuse/glare/dim), movement (steady/micro‑shake), occupancy (borderline/full), angles, devices.
Success criteria (visible in docs/face_scan_contract.md):
Lock p50 ≤1.2 s, p95 ≤2.5 s; countdown ≥600 ms; cancel‑on‑jitter <50 ms; challenge pass‑rate ≥95% in good light.
DoD
Checklist completed; issues filed with thresholds to tune.
File map (AI‑1 only)
src/web/face_scan.html: markup (rings, chips, prompts, debug panel)
src/web/css/face_scan.css: tokens, animations, reduce‑motion variants
src/web/js/face_scan.js: state machine, timers, camera, polling, challenge UI, telemetry
docs/face_scan_contract.md: endpoint payloads, timing/thresholds, QA runbook
Hand‑offs/assumptions (to avoid conflicts)
AI‑1 must NOT edit any backend files; uses only documented endpoints.
AI‑2 guarantees endpoints exist and are CORS/HTTPS accessible.
Mount path: backend serves /web/face_scan.html without code changes from AI‑1.
Done.