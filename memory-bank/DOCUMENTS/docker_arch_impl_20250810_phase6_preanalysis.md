# Phase 6 Pre-Analysis — docker_arch_impl_20250810

Quoted IMPORTANT NOTE:

> IMPORTANT NOTE: This final phase ensures the project is not only complete but also maintainable and resilient. A well-documented rollback plan is a critical piece of operational readiness.

Plan, risks, prerequisites:
- Plan: Tag last-known-good images with `-prev`, create `ROLLBACK_PROCEDURE.md` with step-by-step instructions for toggling `FORCE_IMAGE_TAG` and validating health, and perform a full-system health verification.
- Risks: Incorrect image references, partial rollbacks causing version skew, and missing observability signals masking regressions.
- Prerequisites: Inventory of current production images and tags, CI workflow able to push `-prev` tags, and access to deployment supervisor to set `FORCE_IMAGE_TAG`.

## Plan
- Identify last-known-good images per service from registry and deployment manifests; export list to `rollback/last_known_good.csv`.
- Apply `-prev` tags to those immutable digests in GHCR; verify via registry listing.
- Author `ROLLBACK_PROCEDURE.md` detailing:
  - How to set `FORCE_IMAGE_TAG` per service and perform canary rollback.
  - Health check validation steps and observability verification.
  - Roll forward procedure after rollback validation.
- Dry-run rollback for two services (GPU and CPU representative) in a staging namespace; capture logs and timings.

## Risks
- Mis-tagging wrong digest → mitigate by using digest-pinned tagging and dual-operator review.
- Partial rollback dependency mismatch → include dependency matrix and coordinated rollback order.
- Losing current good state → never delete current tags; only add `-prev` and document mapping.

## Prerequisites
- GHCR permissions to add tags; registry access tokens configured.
- Up-to-date deployment manifests or supervisor config to set `FORCE_IMAGE_TAG`.
- Observability dashboards healthy; alerting in place to detect regressions during rollback.
