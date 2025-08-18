============================================================
🎮 TASK COMMAND & CONTROL CENTER
============================================================

📋 ALL OPEN TASKS:
========================================

1. 🗒️  docker_arch_blueprint_dual_machine_4090_3060_actionable_20250817
   Description: Actionable plan compiled from FINAL Docker Architecture Blueprint (Dual-Machine 4090 + 3060) (memory-bank/plan/organize.md).
   Status: in_progress
   Created: 2025-08-17T12:00:00+08:00
   TODO Items (9):
      [✗] 0. PHASE 0: SETUP & PROTOCOL (READ FIRST)

IMPORTANT NOTE:
- Work only from the frozen organizer; no silent version/toolchain changes.
- No direct writes to queue/state files by the agent; JSON is provided for the operator to place.
- GPU baseline: CUDA 12.1; Torch 2.2.2+cu121; TORCH_CUDA_ARCH_LIST="89;86".
- All images are non-root with tini (PID 1); Python 3.11 primary; legacy 3.10 only where specified.
- Tagging: ghcr.io/<org>/<family>:YYYYMMDD-<git_sha>; registry cache enabled; Trivy fails on HIGH/CRITICAL.
- Every HTTP service exposes /health → JSON {status:"ok"} with HTTP 200.

      [✗] 1. PHASE 1: Build & push functional-family base images

IMPORTANT NOTE:
- Use multi-stage (builder/runtime), Debian slim, tini, non-root UID:GID 10001:10001.
- pip with --require-hashes; apt minimal and cleaned; wheel cache mount.
- Tag scheme and GHCR are mandatory; builds must be reproducible.

      [✗] 2. PHASE 2: Dependency audit for Audio/Vision GPU stacks

IMPORTANT NOTE:
- Add system libs only to family-torch-cu121 or family-vision-cu121 if required; CPU images stay minimal.
- Keep pinned versions; preserve image size targets (CPU ≈100 MB, GPU ≈3 GB).

      [✗] 3. PHASE 3: CI pipeline — build matrix, cache, Trivy, SBOM

IMPORTANT NOTE:
- Use --cache-to/from type=registry; Trivy must fail build on HIGH/CRITICAL.
- SBOMs are generated and uploaded; tags must match YYYYMMDD-<git_sha>.

      [✗] 4. PHASE 4: Service migration — Core Infra (Phase 1)

IMPORTANT NOTE:
- Ensure /health endpoints return 200 with {status:"ok"}.
- Enforce non-root runtime; supervisors pull newly tagged images.

      [✗] 5. PHASE 5: Service migration — GPU services on MainPC (Phase 2)

IMPORTANT NOTE:
- Use CUDA 12.1 images; set MACHINE=mainpc if baked; arch list 89.
- Verify NVIDIA driver ≥ 535 (Risk R1) prior to rollout.

      [✗] 6. PHASE 6: Service migration — CPU services on PC2 (Phase 3)

IMPORTANT NOTE:
- Keep images trimmed and pinned; do not introduce GPU-only deps to CPU families.
- Respect port mappings from §F of the organizer.

      [✗] 7. PHASE 7: Observability integration — SBOM + Git SHA emission at startup

IMPORTANT NOTE:
- SBOM format: SPDX JSON; compress+base64 if needed for transport.
- Endpoint must be resilient; failures should not prevent service start.

      [✗] 8. PHASE 8: Rollback procedure — -prev tags and pinning

IMPORTANT NOTE:
- Use -prev tags to keep last-known-good; document the exact tag used.
- If CI security gates block rollout (Trivy), coordinate temporary downgrade to WARN per R4 only if risk-accepted.
