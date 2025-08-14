# Phase 21 Pre-Analysis — DOCKER & DEV TOOLING
Task: kyc_identity_verification_manifest_actionable_20250813
Timestamp: 2025-08-14T16:09:56+08:00

## Objective
Containerize the system and strengthen developer tooling to ensure consistent environments, quick spins, and baseline hygiene.

## IMPORTANT NOTE (from plan)
Pre-commit enforces formatting and secret scanning; containers pass healthchecks; Makefile targets present.

## Scope & Deliverables
- Docker
  - `Dockerfile` (CPU baseline; GPU optional notes) with system deps (opencv, tesseract/zbar optional) and Python runtime (3.10)
  - `docker-compose.yml` with service healthchecks (`/ready`, `/live` if API present), resource limits, volume mounts for datasets/artifacts
  - `.dockerignore`
- Dev Tooling
  - `.pre-commit-config.yaml` with black/ruff/isort, detect-secrets (or equivalent) hooks
  - `.env.example` for non-secret envs and placeholders
  - `Makefile` targets: `venv`, `install`, `test`, `bench`, `pipeline`, `compose-up`, `compose-down`, `artifacts`

## Approach
1) Draft Dockerfile using multi-stage (builder → runtime) to keep image slim; pin Python base.
2) Compose healthchecks (curl/wget) to probe API endpoints if present; otherwise simple `python -c` module import sanity.
3) Pre-commit hooks with reasonable defaults; ensure hooks do not require internet.
4) Makefile abstracts common tasks consistently across local and CI.

## Risks & Mitigations
- System-level cv2, tesseract, zbar packages vary by distro → include optional installs and graceful fallbacks at runtime.
- Secret scanning false positives → allow baseline suppression file.

## Validation
- `docker build` completes; `docker-compose up` runs containers passing healthchecks.
- Pre-commit passes on a clean tree; CI validates hooks.
- `make test` runs pytest; `make bench` runs `scripts/bench_metrics.py` on small subset.

## Next Steps
Implement files above; verify acceptance against Phase 21 IMPORTANT NOTE, then mark the phase done.
