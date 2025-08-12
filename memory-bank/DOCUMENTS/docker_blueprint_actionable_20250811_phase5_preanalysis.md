# Phase 5 Pre-Analysis — docker_blueprint_actionable_20250811

> IMPORTANT NOTE (Phase 5): "Traceability is non-negotiable for production-grade debugging and security."

## Scope
Inject SBOM + Git SHA reporting at startup for all services to `UnifiedObservabilityCenter` and verify end-to-end receipt/visibility.

## Prerequisites
- Phase 4 rollout complete (images live with strict health; supervisors pulling the latest tags).
- UnifiedObservabilityCenter reachable and configured (ingest endpoint, auth if required).
- Git SHA available at build/runtime via labels/env (e.g., `org.opencontainers.image.revision`, `GIT_SHA`).
- SBOM generation available in CI artifacts or embedded references (e.g., CycloneDX/SPDX).

## Risks & Mitigations
- Missing/incorrect Git SHA at runtime
  - Mitigation: Bake `GIT_SHA` env + OCI label; validate on container start logs.
- SBOM unavailable for certain images
  - Mitigation: Ensure CI generates SBOMs and exposes artifact URL/hash; fallback to on-demand generation.
- Observability endpoint failures or auth issues
  - Mitigation: Retries with backoff; local buffering; clear error logs.
- Performance overhead at startup
  - Mitigation: Lightweight reporting; async fire-and-forget with strict timeouts.

## Plan of Action
1. Add startup hook in entrypoints to POST `{ service, git_sha, sbom_ref, ts }` to UOC.
2. Propagate `GIT_SHA` and `SBOM_REF` via labels/env during build.
3. Update CI to upload SBOM and record artifact URL/digest.
4. Validate receipt (logs/dashboard) post-deploy.

## Done Criteria
- Each service emits startup report with correct Git SHA + SBOM reference.
- UOC dashboard/logs confirm receipt per service within SLO.
- Playbook documented for troubleshooting/report replay.
