## Step-by-step execution guide for docker_blueprint_actionable_20250811

Purpose: A sequential checklist and runnable commands per phase (0 → 6), strictly following the approved Docker Architecture Blueprint. Do not skip phases. Apply on mainpc first, then pc2 where applicable.

Prereqs
- Docker + Buildx installed and working
- Logged-in to GHCR with a PAT that has read:packages and write:packages
- Set environment variables before builds

```bash
export ORG=haymayndzultra
export DATE=$(date -u +%Y%m%d)
export SHA=$(git rev-parse --short HEAD)
export TAG=${DATE}-${SHA}
export PLATFORM=linux/amd64
# buildx cache settings (registry cache)
export CACHE_FROM=type=registry,ref=ghcr.io/$ORG/cache
export CACHE_TO=type=registry,ref=ghcr.io/$ORG/cache,mode=max
```

### Phase 0: Setup & Protocol (READ FIRST)
- Read and follow the protocol in the plan; execute phases in order and use gating docs per phase.
- Commands
```bash
python3 todo_manager.py show docker_blueprint_actionable_20250811 | cat
```
- Gate: Before marking any phase done, you must create post-review and next-phase pre-analysis files per rules.

### Phase 1: Build foundational base images
Key requirements: reproducible builds (pin deps; use --require-hashes where ready), non-root, tini, hardware-aware defaults, CUDA 12.1 baseline, correct tagging.

1) Build and push base hierarchy (in order). Example commands:
```bash
# base-python
docker buildx build -f docker/base-images/base-python/Dockerfile \
  --platform $PLATFORM \
  --cache-from=$CACHE_FROM --cache-to=$CACHE_TO \
  -t ghcr.io/$ORG/base-python:$TAG \
  --push .

# base-utils (FROM base-python)
docker buildx build -f docker/base-images/base-utils/Dockerfile \
  --platform $PLATFORM \
  --build-arg BASE_IMAGE=ghcr.io/$ORG/base-python:$TAG \
  --cache-from=$CACHE_FROM --cache-to=$CACHE_TO \
  -t ghcr.io/$ORG/base-utils:$TAG \
  --push .

# base-cpu-pydeps (FROM base-utils)
docker buildx build -f docker/base-images/base-cpu-pydeps/Dockerfile \
  --platform $PLATFORM \
  --build-arg BASE_IMAGE=ghcr.io/$ORG/base-utils:$TAG \
  --cache-from=$CACHE_FROM --cache-to=$CACHE_TO \
  -t ghcr.io/$ORG/base-cpu-pydeps:$TAG \
  --push .

# base-gpu-cu121 (CUDA 12.1 runtime)
docker buildx build -f docker/base-images/base-gpu-cu121/Dockerfile \
  --platform $PLATFORM \
  --cache-from=$CACHE_FROM --cache-to=$CACHE_TO \
  -t ghcr.io/$ORG/base-gpu-cu121:$TAG \
  --push .

# family-web (FROM base-cpu-pydeps)
docker buildx build -f docker/families/family-web/Dockerfile \
  --platform $PLATFORM \
  --build-arg BASE_IMAGE=ghcr.io/$ORG/base-cpu-pydeps:$TAG \
  --cache-from=$CACHE_FROM --cache-to=$CACHE_TO \
  -t ghcr.io/$ORG/family-web:$TAG \
  --push .

# family-torch-cu121 (FROM base-gpu-cu121) – ensure CUDA 12.1, TORCH_CUDA_ARCH_LIST covers 89;86
docker buildx build -f docker/families/family-torch-cu121/Dockerfile \
  --platform $PLATFORM \
  --build-arg BASE_IMAGE=ghcr.io/$ORG/base-gpu-cu121:$TAG \
  --cache-from=$CACHE_FROM --cache-to=$CACHE_TO \
  -t ghcr.io/$ORG/family-torch-cu121:$TAG \
  --push .

# family-llm-cu121 (FROM family-torch)
docker buildx build -f docker/families/family-llm-cu121/Dockerfile \
  --platform $PLATFORM \
  --build-arg BASE_IMAGE=ghcr.io/$ORG/family-torch-cu121:$TAG \
  --cache-from=$CACHE_FROM --cache-to=$CACHE_TO \
  -t ghcr.io/$ORG/family-llm-cu121:$TAG \
  --push .

# family-vision-cu121 (FROM base-gpu-cu121)
docker buildx build -f docker/families/family-vision-cu121/Dockerfile \
  --platform $PLATFORM \
  --build-arg BASE_IMAGE=ghcr.io/$ORG/base-gpu-cu121:$TAG \
  --cache-from=$CACHE_FROM --cache-to=$CACHE_TO \
  -t ghcr.io/$ORG/family-vision-cu121:$TAG \
  --push .

# legacy-py310-cpu
docker buildx build -f docker/legacy/legacy-py310-cpu/Dockerfile \
  --platform $PLATFORM \
  --cache-from=$CACHE_FROM --cache-to=$CACHE_TO \
  -t ghcr.io/$ORG/legacy-py310-cpu:$TAG \
  --push .
```

2) Verify GHCR inventory vs local
```bash
GH_USERNAME=$ORG GH_TOKEN=$GH_TOKEN \
python3 scripts/docker_inventory_compare.py --output docker_image_inventory.md
```

3) Gate before marking Phase 1 done
- Create `memory-bank/DOCUMENTS/docker_blueprint_actionable_20250811_phase1_postreview.md` (quote the IMPORTANT NOTE and map evidence)
- Create `memory-bank/DOCUMENTS/docker_blueprint_actionable_20250811_phase2_preanalysis.md` (state IMPORTANT NOTE, risks, prerequisites)
- Then:
```bash
python3 todo_manager.py done docker_blueprint_actionable_20250811 1
```

### Phase 2: Dependency audit & GPU image refinement
Actions
- Static analysis (imports) for audio/vision deps
- ldd on native .so files to derive minimal apt packages
- Update only `family-torch-cu121` / `family-vision-cu121` as needed; rebuild and push with new $TAG

Commands (examples)
```bash
# Example ldd pass (adjust targets as needed)
docker run --rm -t ghcr.io/$ORG/family-vision-cu121:$TAG bash -lc 'ldd /usr/local/lib/python*/site-packages/**/*.so || true'

# Rebuild amended families and push (repeat as needed)
docker buildx build -f docker/families/family-vision-cu121/Dockerfile \
  --platform $PLATFORM \
  --build-arg BASE_IMAGE=ghcr.io/$ORG/base-gpu-cu121:$TAG \
  --cache-from=$CACHE_FROM --cache-to=$CACHE_TO \
  -t ghcr.io/$ORG/family-vision-cu121:$TAG \
  --push .
```

Gate (postreview + preanalysis for Phase 3), then mark done with:
```bash
python3 todo_manager.py done docker_blueprint_actionable_20250811 2
```

### Phase 3: CI/CD automation pipeline
Actions
- Create GH Actions matrix (families × {mainpc, pc2}); enable registry cache
- Integrate Trivy (fail on HIGH/CRITICAL), generate SBOM, enforce size budgets, tag guard

Artifacts
- .github/workflows/docker-build.yml
- .github/workflows/security.yml (Trivy + SBOM)

Gate (postreview + preanalysis for Phase 4), then:
```bash
python3 todo_manager.py done docker_blueprint_actionable_20250811 3
```

### Phase 4: Phased service migration (canonical patterns)
Actions (apply to listed services per sub-phases)
- Multi-stage: builder → runtime
- Enforce `USER appuser` (10001:10001) and `ENTRYPOINT ["/usr/bin/tini","--"]`
- Standardize `.dockerignore` and add HTTP `/health` returning {"status":"ok"}

Example build (GPU-heavy):
```bash
docker buildx build -f model_ops_coordinator/Dockerfile \
  --platform $PLATFORM \
  --build-arg MACHINE=mainpc \
  --build-arg BASE_IMAGE=ghcr.io/$ORG/family-llm-cu121:$TAG \
  --cache-from=$CACHE_FROM --cache-to=$CACHE_TO \
  -t ghcr.io/$ORG/model_ops_coordinator:$TAG \
  --push model_ops_coordinator
```

Gate (postreview + preanalysis for Phase 5), then:
```bash
python3 todo_manager.py done docker_blueprint_actionable_20250811 4
```

### Phase 5: Observability & traceability integration
Actions
- On service startup, emit SBOM + Git SHA to `UnifiedObservabilityCenter`
- Verify logs/dashboard ingestion

Gate (postreview + preanalysis for Phase 6), then:
```bash
python3 todo_manager.py done docker_blueprint_actionable_20250811 5
```

### Phase 6: Rollback procedures & documentation
Actions
- Tag last-known-good images with `-prev`
- Create `ROLLBACK_PROCEDURE.md` including `FORCE_IMAGE_TAG` usage
- Capture risk fallbacks per blueprint (R1-R4)

Mark done when all items validated:
```bash
python3 todo_manager.py done docker_blueprint_actionable_20250811 6
```

### Verification utilities
```bash
# Inventory & compare local vs GHCR
GH_USERNAME=$ORG GH_TOKEN=$GH_TOKEN \
python3 scripts/docker_inventory_compare.py --output docker_image_inventory.md
```

Notes
- Always adhere to IMPORTANT NOTE per phase; include evidence in postreview docs
- Use `--require-hashes` for final production builds once lock files are complete


