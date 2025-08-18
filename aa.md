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


---



============================================================
🎮 TASK COMMAND & CONTROL CENTER
============================================================

📋 ALL OPEN TASKS:
========================================

1. 🗒️  docker_arch_blueprint_dual_machine_4090_3060_analysis_20250817
   Description: Pre-execution analysis for FINAL Docker Architecture Blueprint (Dual-Machine 4090 + 3060): detect ownership overlaps, policy conflicts, contract/schema drift, dependency inversions, logic duplication,…
   Status: in_progress
   Created: 2025-08-17T12:00:00+08:00
   TODO Items (9):
      [✗] 0. PHASE 0: SETUP & PROTOCOL ANALYSIS (READ FIRST)


Purpose: Ensure one shared understanding of blueprint→plan mapping, naming/tags, toolchain freezes, and machine scoping before any build or rollout.
Scope: semantic/architectural review only (no builds/tests).

Checks:
• Single source of truth: organizer/blueprint vs this plan—no parallel or conflicting versions.
• Policy alignment: non-root+tini, Python 3.11 primary (3.10 only where stated), CUDA/Torch baselines, health endpoint contract.
• Tagging/registry: one canonical tag pattern (YYYYMMDD-<git_sha>) and GHCR path; no alternates.
• Machine scoping terms: ‘MainPC(4090)’ vs ‘PC2(3060)’ consistently named and referenced.

LOGIC PARITY CHECK:
• Identify duplicate or competing “protocol” definitions (how to build, tag, or gate).
• If criteria/flow/outputs match ≥4/5 across two places → duplicate; if contradictory → conflict.

DECISION GATE: Do not proceed until there is one canonical protocol, one tag scheme, and one health-contract definition.

IMPORTANT NOTE: This is the semantic gate for the entire plan.

      [✗] 1. PHASE 1: Build & push functional-family base images — ANALYSIS


Purpose: Validate the image family taxonomy and policies (builder/runtime split, reproducibility, non-root, version pins) without building.
Scope: taxonomy, ownership, policies; not runtime.

Checks:
• Family taxonomy: each family has a distinct purpose; no overlaps (CPU vs GPU; web vs torch/vision/llm; legacy py310 boundaries clear).
• Ownership: one owner per family for Dockerfile policy; adapters OK, duplicate base logic not OK.
• Reproducibility policy: multi-stage, slim base, hash-pinned deps, consistent toolchain versions.
• GPU/CPU separation: CUDA/Torch only in GPU families; CPU families remain GPU-free.
• Tagging/labels: single tag scheme; image labels/annotations consistent across families.

LOGIC PARITY CHECK:
• Compare base policies across families (inputs, rules, flow, outputs, side-effects like labels/tags).
• Flag duplicates (two families implementing same base pattern) or conflicts (different rules for same concern).

DECISION GATE: Block if any family overlaps in scope, violates CPU/GPU split, or diverges from the canonical reproducibility policy.

      [✗] 2. PHASE 2: Dependency audit for Audio/Vision GPU stacks — ANALYSIS


Purpose: Decide ‘which system libs belong where’ at policy level; prevent leakage of GPU-only deps into CPU images.
Scope: mapping rules and boundaries; not ldd/pip runs.

Checks:
• Dependency mapping policy: single list-of-record for libs per family; no duplicated lists living in multiple places.
• CPU minimalism: assert that CPU families cannot depend on GPU-only libs; any shared libs are justified and version-pinned.
• Size/footprint targets are policy, not best-effort (CPU ~100MB, GPU ~3GB) and acknowledged by owners.
• Upgrade path: one policy for bumping lib versions; no per-team overrides that fork contracts.

LOGIC PARITY CHECK:
• Detect parallel ‘allowed-libs’ policies for the same family; reconcile to one canonical source.

DECISION GATE: Block if dependency ownership is split, lists conflict, or CPU images would inherit GPU-only libs by policy.

      [✗] 3. PHASE 3: CI pipeline — build matrix, cache, Trivy, SBOM — ANALYSIS


Purpose: Verify there is a single CI policy for matrix coverage, cache usage, security gating, and SBOM emission.
Scope: policy/contracts only; not CI execution.

Checks:
• Matrix coverage: all declared families present; no silent exclusions.
• Cache policy: one canonical cache-to/from registry approach; no competing cache paths.
• Security gate: single authority on fail criteria (Trivy HIGH/CRITICAL → fail); no alternate thresholds elsewhere.
• SBOM contract: one format (SPDX JSON), one naming/tag linkage to image refs.
• Tag/date/git linkage: DATE and GIT_SHA expansion consistent in all CI steps.

LOGIC PARITY CHECK:
• Compare CI rules across docs/workflows; flag duplicate/conflicting policies.

DECISION GATE: Block if matrix misses families, cache policy is duplicated/contradictory, or security/SBOM policies diverge.

      [✗] 4. PHASE 4: Service migration — Core Infra (Phase 1) — ANALYSIS


Purpose: Ensure mapping from core infra services to new images is unambiguous; ports and health contracts do not collide.
Scope: mapping and contracts; not deployment.

Checks:
• Service→image mapping: one image per service role; no parallel images for same service in same env.
• Health contract: /health → 200 {status:"ok"} universally; no per-service deviation.
• Port map uniqueness: declared ports do not conflict with other core services; naming aligns with discovery.
• Non-root runtime: consistent user policy across services; supervisors honor same tag scheme.

LOGIC PARITY CHECK:
• Identify duplicate mapping definitions across compose/manifests.
• Mark conflict if two mappings claim ownership of the same service.

DECISION GATE: Block if service mappings conflict, ports collide, or health-contract varies per service.

      [✗] 5. PHASE 5: Service migration — GPU services on MainPC (4090) — ANALYSIS


Purpose: Validate machine scoping and GPU policy for MainPC-only services without running them.
Scope: scoping, policy, and reservations; not rollout.

Checks:
• Machine scoping: these GPU services target MainPC(4090) only; no ambiguity with PC2.
• GPU policy: CUDA 12.1 images, arch list 89 (4090) acknowledged; resource reservations match policy.
• Driver prerequisite: one policy statement (≥535) acknowledged; no alternate driver baselines elsewhere.
• Env var contracts: GPU-related envs named consistently; no per-service variants.

LOGIC PARITY CHECK:
• Find duplicate or conflicting ‘GPU deployment rules’ across docs/specs.

DECISION GATE: Block if scoping to MainPC is ambiguous, policies diverge, or resource semantics conflict.

      [✗] 6. PHASE 6: Service migration — CPU services on PC2 (3060) — ANALYSIS


Purpose: Validate CPU-only policy and isolation for PC2 services.
Scope: mapping and policy boundaries; not rollout.

Checks:
• CPU-only guarantee: images mapped here must not pull GPU-only deps by policy.
• Ports/discovery: mappings do not conflict with MainPC or other PC2 services; discovery names consistent.
• Image trim & pin: pinning strategy consistent; no local exceptions.
• Organizer references: port maps and names match the organizer’s §F; no drift.

LOGIC PARITY CHECK:
• Detect duplicate CPU-service mappings or alternate policies for the same concern.

DECISION GATE: Block if CPU-only policy is violated, ports collide, or mappings conflict.

      [✗] 7. PHASE 7: Observability integration — SBOM + Git SHA emission at startup — ANALYSIS


Purpose: Ensure one ingestion schema and startup emission policy that does not gate service startup on observability.
Scope: schema/policy only; not execution.

Checks:
• Ingestion schema: single canonical payload (service, image, git_sha, sbom) and transport constraints (compression/base64) if used.
• Startup posture: failures to emit must be non-fatal by policy; logs/metrics still capture attempts.
• Idempotence: repeated emissions are accepted or de-duplicated by contract; no double-count semantics.

LOGIC PARITY CHECK:
• Find alternate ingestion formats or competing endpoints; mark duplicates/conflicts.

DECISION GATE: Block if multiple schemas/endpoints exist or startup would be gated by observability failure.

      [✗] 8. PHASE 8: Rollback procedure — -prev tags and pinning — ANALYSIS


Purpose: Verify a single, predictable rollback model with clear precedence when FORCE_IMAGE_TAG is set.
Scope: policy and precedence; not rollback execution.

Checks:
• Tag semantics: ‘-prev’ is last-known-good; documented and traceable to prior DATE/GIT_SHA.
• Precedence: FORCE_IMAGE_TAG overrides default resolution in one consistent way across supervisors.
• Risk exception: one policy for temporarily downgrading security gates (R4) with explicit approval trail.

LOGIC PARITY CHECK:
• Identify duplicate rollback policies or conflicting precedence rules.

DECISION GATE: Block if rollback semantics/precedence diverge across components or R4 exceptions lack a single authority.
