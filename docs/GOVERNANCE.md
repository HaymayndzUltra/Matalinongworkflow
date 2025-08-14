# Governance — Model Registry, Lineage, Canary, Sign-off, Fairness Cadence

This document defines governance for KYC identity verification covering registry/lineage, canary process, sign-off gates, and fairness audit cadence.

## Model Registry & Lineage

- Register every deployable artifact with:
  - model_id, version, training_data_ref, code_commit, hyperparams, metrics (AUC/TPR/FPR), timestamp (+08:00)
  - artifact hashes (weights, configs) and storage location
- Maintain lineage: parent versions, data snapshots, preprocessing code refs
- Keep audit logs for change history; link to DPIA/ROPA entries when applicable

## Canary Process

- Stage rollout: canary (≤5%) → 25% → 50% → 100%
- Guardrails during canary:
  - Decision latency SLOs (p50 < 20s, p95 < 60s)
  - Fraud catch TPR targets on red-team probes (≥95%)
  - Error budget policy; automatic rollback when exceeded
- Monitor dashboards: risk distributions, TPR/FPR, drift indicators

## Sign-off Gates

- Required approvals before production promotion:
  - ML owner: performance validation and drift checks
  - Platform owner: reliability/observability checks (breakers, healthchecks)
  - Compliance: DPIA/ROPA/retention updated; audit export verifications
- Evidence bundle must include:
  - Latest benchmark CSVs, test reports, and failover_sim results
  - Versioned configs (policy packs, templates)

## Fairness Audit Cadence

- Monthly fairness audit across demographic slices where applicable
- Metrics: TPR/FPR parity deltas within acceptable bounds; bias documentation
- Action items tracked and linked to change management entries

## Retraining & Drift

- Quarterly drift assessment using production-like distributions; trigger retraining if drift alarms persist
- Document retraining data changes, new metrics, and updated risks

## Change Management

- All changes PR-reviewed; CI must pass tests and red-team regression thresholds
- Canary schedule and sign-offs recorded with timestamps (+08:00)
- Rollback procedures documented for each release

## Audit Trails

- Exportable audit logs with decision records, vendor health summaries, and artifact references
- Ensure WORM/tamper-evident links for compliance artifacts (see `artifacts/`)

## Mapping to Phase 20 IMPORTANT NOTE

- Governance includes registry/lineage/canary/sign-off and fairness audit cadence → Covered in sections above with explicit processes and cadences.
