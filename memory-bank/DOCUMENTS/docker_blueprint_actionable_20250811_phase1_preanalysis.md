# Phase 1 Pre-Analysis — docker_blueprint_actionable_20250811

## Quoted IMPORTANT NOTE (from Phase 1 text)
"Foundational images must be reproducible (hash-locked), hardware-aware, multi-stage, non-root with `tini` (UID:GID 10001:10001), and correctly tagged."

## Risks
- Hash drift if lock files are incomplete; `--require-hashes` may fail.
- Buildx registry cache eviction causing slower rebuilds.
- CUDA arch coverage mismatch; must set `TORCH_CUDA_ARCH_LIST="89;86"`.
- Tag format mistakes (`YYYYMMDD-<git_sha>`) complicate rollback.

## Prerequisites
- Buildx cache configured: `type=registry,ref=ghcr.io/<org>/cache`.
- Non-root runtime user `appuser` (10001:10001) and `tini` as PID 1.
- Dependency pinning with planned transition to `--require-hashes`.
- MACHINE build-arg and `/etc/machine-profile.json` baked per host.

## Planned Actions
- Build and push base families in order with correct tags.
- Enforce multi-stage builds with minimal apt and non-root runtime.
- Set `TORCH_CUDA_ARCH_LIST="89;86"` for GPU images; verify CUDA 12.1 baseline.
- Enable pip cache mount and buildx registry cache.

## Gate Readiness
PASS — Preconditions identified; risks and mitigations documented.
