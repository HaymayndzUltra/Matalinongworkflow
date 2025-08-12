# Phase 5 Pre-Analysis — docker_arch_impl_20250810

Quoted IMPORTANT NOTE:

> IMPORTANT NOTE: This step is crucial for runtime security and debugging. Knowing exactly which version of code is running in every container is non-negotiable for a production-grade system.

Plan, risks, prerequisites:
- Plan:
  - Modify service entrypoints (e.g., `entrypoint.sh` or Python startup) to emit: service id, image tag, Git SHA (CI-provided), and SBOM reference to the `UnifiedObservabilityCenter` API at startup.
  - Pass Git SHA via CI/CD (env `GIT_SHA`), ensure SBOM path/digest is labeled in image.
  - Implement non-blocking async/report with bounded retries to avoid startup impact.
  - Roll out gradually using `FORCE_IMAGE_TAG` for canary services.
- Risks:
  - Startup latency if synchronous reporting → mitigate via background, bounded retry.
  - Missing `GIT_SHA` propagation → enforce in CI workflow and fail build if absent.
  - UOC outage could drop reports → add retry/backoff and idempotent server handling.
- Prerequisites:
  - CI pipeline generates SBOM and surfaces `GIT_SHA` to images and deployments.
  - Network reachability from services to UOC confirmed; firewall/ports validated.
  - Minimal HTTP client available in service images.

Confidence: 92%
