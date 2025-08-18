============================================================
🎮 TASK COMMAND & CONTROL CENTER
============================================================

📋 ALL OPEN TASKS:
========================================

1. 🗒️  docker_arch_blueprint_dual_machine_4090_3060_actionable_20250817
   Description: Actionable plan compiled from FINAL Docker Architecture Blueprint (Dual-Machine ...
   Status: in_progress
   Created: 2025-08-17T12:00:00+08:00
   TODO Items (9):
      [✗] 0. PHASE 0: SETUP & PROTOCOL (READ FIRST)

**Explanations:** This plan operationalizes the approved Docker Architecture Blueprint into actionable phases with reproducible builds, GPU/CPU separation, and CI/CD hardening.

**Command Preview:**
```bash
python3 plan_next.py
python3 plain_hier.py <task_id ReplaceAll>
```
**Concluding Step: Phase Completion Protocol**
```bash
python3 todo_manager.py show <task_id ReplaceAll>
python3 todo_manager.py done <task_id ReplaceAll> 0
```
IMPORTANT NOTE:
- Work only from the frozen organizer; no silent version/toolchain changes.
- No direct writes to queue/state files by the agent; JSON is provided for the operator to place.
- GPU baseline: CUDA 12.1; Torch 2.2.2+cu121; TORCH_CUDA_ARCH_LIST="89;86".
- All images are non-root with tini (PID 1); Python 3.11 primary; legacy 3.10 only where specified.
- Tagging: ghcr.io/<org>/<family>:YYYYMMDD-<git_sha>; registry cache enabled; Trivy fails on HIGH/CRITICAL.
- Every HTTP service exposes /health → JSON {status:"ok"} with HTTP 200.
      [✗] 1. PHASE 1: Build & push functional-family base images

**Explanations:** Create and push the canonical image families to GHCR with pinned, reproducible layers and multi-stage builds.

**Command Preview:**
```bash
export DATE=$(date +%Y%m%d) && export GIT_SHA=$(git rev-parse --short HEAD)
# CPU families
docker buildx build --push --platform linux/amd64 \
  -t ghcr.io/<org>/base-python:${DATE}-${GIT_SHA} -f dockerfiles/base-python.Dockerfile .
docker buildx build --push --platform linux/amd64 \
  -t ghcr.io/<org>/family-web:${DATE}-${GIT_SHA} -f dockerfiles/family-web.Dockerfile .
# GPU families (CUDA 12.1)
docker buildx build --push --platform linux/amd64 \
  --build-arg TORCH_CUDA_ARCH_LIST="89;86" \
  -t ghcr.io/<org>/family-torch-cu121:${DATE}-${GIT_SHA} -f dockerfiles/family-torch-cu121.Dockerfile .
docker buildx build --push --platform linux/amd64 \
  -t ghcr.io/<org>/family-vision-cu121:${DATE}-${GIT_SHA} -f dockerfiles/family-vision-cu121.Dockerfile .
docker buildx build --push --platform linux/amd64 \
  -t ghcr.io/<org>/family-llm-cu121:${DATE}-${GIT_SHA} -f dockerfiles/family-llm-cu121.Dockerfile .
# Legacy
docker buildx build --push --platform linux/amd64 \
  -t ghcr.io/<org>/legacy-py310-cpu:${DATE}-${GIT_SHA} -f dockerfiles/legacy-py310-cpu.Dockerfile .
```
**Concluding Step: Phase Completion Protocol**
```bash
python3 todo_manager.py show <task_id ReplaceAll>
python3 todo_manager.py done <task_id ReplaceAll> 1
```
IMPORTANT NOTE:
- Use multi-stage (builder/runtime), Debian slim, tini, non-root UID:GID 10001:10001.
- pip with --require-hashes; apt minimal and cleaned; wheel cache mount.
- Tag scheme and GHCR are mandatory; builds must be reproducible.
      [✗] 2. PHASE 2: Dependency audit for Audio/Vision GPU stacks

**Explanations:** Enumerate required system libs (e.g., ffmpeg, libpulse) and add only to GPU families that need them.

**Command Preview:**
```bash
# Static enumerate Python wheels
pip install pip-audit && pip-audit --strict
# Shared object dependency inspection
python - <<'PY'
import importlib, sys
mods = ["torch","torchaudio","opencv","onnxruntime","sounddevice","pyaudio"]
for m in mods:
    try:
        mod = importlib.import_module(m)
        print(m, getattr(mod, "__file__", "n/a"))
    except Exception as e:
        print("ERR", m, e, file=sys.stderr)
PY
# ldd examples (adjust paths from the printout)
ldd /usr/local/lib/python3.11/site-packages/torchaudio/lib/*.so | sort -u
ldd /usr/local/lib/python3.11/site-packages/cv2/*.so | sort -u
```
**Concluding Step: Phase Completion Protocol**
```bash
python3 todo_manager.py show <task_id ReplaceAll>
python3 todo_manager.py done <task_id ReplaceAll> 2
```
IMPORTANT NOTE:
- Add system libs only to family-torch-cu121 or family-vision-cu121 if required; CPU images stay minimal.
- Keep pinned versions; preserve image size targets (CPU ≈100 MB, GPU ≈3 GB).
      [✗] 3. PHASE 3: CI pipeline — build matrix, cache, Trivy, SBOM

**Explanations:** Extend GitHub Actions to build families across machines, use registry cache, and enforce security gates.

**Command Preview:**
```yaml
name: docker-families
on: [push]
jobs:
  build:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        family: [base-python, family-web, family-torch-cu121, family-vision-cu121, family-llm-cu121, legacy-py310-cpu]
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - run: echo "DATE=$(date +%Y%m%d)" >> $GITHUB_ENV
      - run: echo "GIT_SHA=${GITHUB_SHA::7}" >> $GITHUB_ENV
      - run: |
          docker buildx build --push \
            --cache-to=type=registry,ref=ghcr.io/<org>/cache,mode=max \
            --cache-from=type=registry,ref=ghcr.io/<org>/cache \
            -t ghcr.io/<org>/${{ matrix.family }}:${DATE}-${GIT_SHA} \
            -f dockerfiles/${{ matrix.family }}.Dockerfile .
      - uses: aquasecurity/trivy-action@0.20.0
        with:
          image-ref: ghcr.io/<org>/${{ matrix.family }}:${{ env.DATE }}-${{ env.GIT_SHA }}
          ignore-unfixed: true
          severity: HIGH,CRITICAL
          exit-code: '1'
      - run: syft ghcr.io/<org>/${{ matrix.family }}:${DATE}-${GIT_SHA} -o spdx-json > sbom-${{ matrix.family }}.json
      - uses: actions/upload-artifact@v4
        with: { name: sboms, path: sbom-*.json }
```
**Concluding Step: Phase Completion Protocol**
```bash
python3 todo_manager.py show <task_id ReplaceAll>
python3 todo_manager.py done <task_id ReplaceAll> 3
```
IMPORTANT NOTE:
- Use --cache-to/from type=registry; Trivy must fail build on HIGH/CRITICAL.
- SBOMs are generated and uploaded; tags must match YYYYMMDD-<git_sha>.
      [✗] 4. PHASE 4: Service migration — Core Infra (Phase 1)

**Explanations:** Repoint core infra services (e.g., ServiceRegistry, SystemDigitalTwin, UnifiedSystemAgent, UnifiedObservabilityCenter, CentralErrorBus) to new images.

**Command Preview:**
```yaml
services:
  service_registry:
    image: ghcr.io/<org>/family-web:${DATE}-${GIT_SHA}
    ports: ["7200:7200","8200:8200"]
    healthcheck: { test: ["CMD","curl","-sf","http://localhost:8200/health"], interval: "10s", timeout: "2s", retries: 5 }
    user: "10001:10001"
```
**Concluding Step: Phase Completion Protocol**
```bash
python3 todo_manager.py show <task_id ReplaceAll>
python3 todo_manager.py done <task_id ReplaceAll> 4
```
IMPORTANT NOTE:
- Ensure /health endpoints return 200 with {status:"ok"}.
- Enforce non-root runtime; supervisors pull newly tagged images.
      [✗] 5. PHASE 5: Service migration — GPU services on MainPC (Phase 2)

**Explanations:** Roll out GPU services (e.g., ModelOpsCoordinator, AffectiveProcessingCenter, RealTimeAudioPipeline, TinyLlamaServiceEnhanced) on the 4090 machine.

**Command Preview:**
```yaml
services:
  model_ops_coordinator:
    image: ghcr.io/<org>/family-llm-cu121:${DATE}-${GIT_SHA}
    environment:
      - TORCH_CUDA_ARCH_LIST=89
      - GPU_VISIBLE_DEVICES=0
    deploy: { resources: { reservations: { devices: [{ capabilities: ["gpu"] }] } } }
    healthcheck: { test: ["CMD","curl","-sf","http://localhost:8212/health"], interval: "10s", timeout: "2s", retries: 5 }
```
**Concluding Step: Phase Completion Protocol**
```bash
python3 todo_manager.py show <task_id ReplaceAll>
python3 todo_manager.py done <task_id ReplaceAll> 5
```
IMPORTANT NOTE:
- Use CUDA 12.1 images; set MACHINE=mainpc if baked; arch list 89.
- Verify NVIDIA driver ≥ 535 (Risk R1) prior to rollout.
      [✗] 6. PHASE 6: Service migration — CPU services on PC2 (Phase 3)

**Explanations:** Roll out CPU services on the 3060 machine (e.g., TieredResponder, AsyncProcessor, CacheManager, etc.).

**Command Preview:**
```yaml
services:
  tiered_responder:
    image: ghcr.io/<org>/base-cpu-pydeps:${DATE}-${GIT_SHA}
    user: "10001:10001"
    healthcheck: { test: ["CMD","curl","-sf","http://localhost:8100/health"], interval: "10s", timeout: "2s", retries: 5 }
```
**Concluding Step: Phase Completion Protocol**
```bash
python3 todo_manager.py show <task_id ReplaceAll>
python3 todo_manager.py done <task_id ReplaceAll> 6
```
IMPORTANT NOTE:
- Keep images trimmed and pinned; do not introduce GPU-only deps to CPU families.
- Respect port mappings from §F of the organizer.
      [✗] 7. PHASE 7: Observability integration — SBOM + Git SHA emission at startup

**Explanations:** Each service emits image SBOM and Git SHA to UnifiedObservabilityCenter on startup.

**Command Preview:**
```bash
#!/usr/bin/env bash
set -euo pipefail
SBOM=$(syft packages dir:/ -o spdx-json | gzip -c | base64 -w0)
curl -sS -X POST http://observability:9007/ingest/image \
  -H "Content-Type: application/json" \
  -d "{\"service\":\"$SERVICE_NAME\",\"image\":\"$IMAGE_REF\",\"git_sha\":\"$GIT_SHA\",\"sbom\":\"$SBOM\"}"
exec /usr/bin/tini -- "$@"
```
**Concluding Step: Phase Completion Protocol**
```bash
python3 todo_manager.py show <task_id ReplaceAll>
python3 todo_manager.py done <task_id ReplaceAll> 7
```
IMPORTANT NOTE:
- SBOM format: SPDX JSON; compress+base64 if needed for transport.
- Endpoint must be resilient; failures should not prevent service start.
      [✗] 8. PHASE 8: Rollback procedure — -prev tags and pinning

**Explanations:** Maintain previous images with -prev tag and allow forced pinning via FORCE_IMAGE_TAG.

**Command Preview:**
```bash
# Tag previous image and roll back
docker pull ghcr.io/<org>/family-llm-cu121:${DATE}-${GIT_SHA_PREV}
docker tag ghcr.io/<org>/family-llm-cu121:${DATE}-${GIT_SHA_PREV} ghcr.io/<org>/family-llm-cu121:${DATE}-${GIT_SHA}-prev
docker push ghcr.io/<org>/family-llm-cu121:${DATE}-${GIT_SHA}-prev
# Supervisor pin
export FORCE_IMAGE_TAG=${DATE}-${GIT_SHA}-prev
```
**Concluding Step: Phase Completion Protocol**
```bash
python3 todo_manager.py show <task_id ReplaceAll>
python3 todo_manager.py done <task_id ReplaceAll> 8
```
IMPORTANT NOTE:
- Use -prev tags to keep last-known-good; document the exact tag used.
- If CI security gates block rollout (Trivy), coordinate temporary downgrade to WARN per R4 only if risk-accepted.