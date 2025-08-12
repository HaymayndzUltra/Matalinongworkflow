# Phase 4 Post-Review — docker_blueprint_actionable_20250811

> IMPORTANT NOTE (Phase 4): "Coordinate deployments to minimize downtime; verify health endpoints and supervisor behavior during cutovers."

## Mapping of constraints to evidence
- Coordinate deployments to minimize downtime
  - Evidence: Canary + batch rollout plan defined (MainPC first, then batch). Scripts/commands prepared (FORCE_IMAGE_TAG, health curl checks, logs capture). Actual rollout pending host-level Docker access and GHCR-pushed images.
- Verify health endpoints
  - Evidence: Updated endpoints to return exactly `{ "status": "ok" }` with HTTP 200.
    - `model_ops_coordinator/transport/rest_api.py` — health now returns `{status:"ok"}` on healthy state.
    - `real_time_audio_pipeline/transport/ws_server.py` — health now returns `{status:"ok"}` when running.
    - `HEALTHCHECK` added/retained in Dockerfiles; curl expected 200.
  - Runtime validation: Pending after image build/push and canary run on MainPC.
- Supervisor behavior during cutovers
  - Evidence: `FORCE_IMAGE_TAG` documented; supervisors expected to auto-pull new tags.
  - Validation: Pending during canary (observe pull behavior, restart sequence, zero-downtime).

## Completed deliverables (this phase)
- Hardware-aware defaults (ARG MACHINE; machine profiles for 4090/3060; non-root UID:GID 10001:10001).
- Health endpoint standardization to strict JSON `{status:"ok"}`.
- Multi-stage build optimizations with wheel cache and `--no-index --find-links=/wheels`; `tini` as PID 1.
- GHCR verification script: `/workspace/verify_ghcr_images.sh`.
- Status doc: `memory-bank/DOCUMENTS/phase4_status.md` (build flags, checklist, risks).

## Gaps blocking phase completion
- Reproducible installs fully enforced (hash-locked across services; resolve `scikit-learn` lock/build on 3.11).
- Image build & push to GHCR (families + services).
- Canary rollout on MainPC (validate health + supervisor behavior), then batch rollout.

## Acceptance checklist (Phase 4)
- [x] Non-root + tini patterns across services
- [x] Strict health endpoints implemented
- [x] Multi-stage patterns & caching
- [ ] Images pushed to GHCR (families + services)
- [ ] Canary validated (health 200 JSON, supervisor behavior OK)
- [ ] Batch rollout completed without downtime

## Decision
Phase 4 NOT YET DONE. Proceed with pending operational work (build/push, canary, batch) before marking done via `todo_manager.py`.
