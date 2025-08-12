# Phase 1 Pre-Analysis — docker_arch_blueprint_actionable_20250811

Phase: PHASE 1: Build & Push Family Base Images

IMPORTANT NOTE (from plan):
"Enforce multi-stage builds, tini, USER appuser, pinned apt/pip with --require-hashes, and buildx registry cache (type=registry). GPU variants must embed CUDA 12.1 and set TORCH_CUDA_ARCH_LIST=\"89;86\"."

Scope and prerequisites:
- Ensure GHCR login available with proper PAT scopes (read:packages, write:packages)
- Confirm buildx and registry cache ref usable: ghcr.io/<org>/cache
- Decide on immediate version alignment for torch (2.2.2+cu121 per plan vs current 2.3.1+cu121). Recommendation: align to plan or update plan note; proceed reproducibly either way.

Risks and mitigations:
- Reproducibility incomplete if --require-hashes is not available for all deps → integrate lock/wheels; stage hashes per family
- GHCR quota/caching failures → allow builds without cache temporarily; document impact
- Non-root propagation gaps → adjust base images to add USER appuser and ENTRYPOINT tini, then rebuild dependent families

Exit criteria:
- All family and base images built and pushed with TAG=${YYYYMMDD}-${git_sha}
- Non-root + tini enforced at least in runtime images
- Reproducibility documented; locks or wheels published where feasible


