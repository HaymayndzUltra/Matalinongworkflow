# Phase 22 Pre-Analysis — OPERATIONS, OBSERVABILITY, AND MODEL LIFECYCLE
Task: kyc_identity_verification_manifest_actionable_20250813
Timestamp: 2025-08-14T16:38:13+08:00

## Objective
Harden operations with observability, SLOs, dashboards, alerts, and lifecycle workflows (drift + fairness). Ensure the service meets latency and availability targets and long-term governance.

## IMPORTANT NOTE (from plan)
Decision p50 < 20s and p95 < 60s; availability 99.9% under vendor issues; dashboards show risk distributions and FPR; drift alarms and fairness audits scheduled.

## Scope & Deliverables
- Observability
  - Metrics: extend `/metrics` to expose counts, latencies (histograms), breaker states, vendor health; scrape-ready format
  - Tracing: instrument key flows (quality → classification → forensics → extraction → risk) with spans
  - Logging: structured logs with request_id; redact PII by default
- Dashboards & Alerts
  - Dashboards for: latency (p50/p95), availability, TPR/FPR by subset, risk distribution, breaker transitions, vendor health
  - Alerts: error rate, latency SLO violation, breaker open duration, drift alarms
- Lifecycle
  - Drift detection jobs (weekly) and fairness audits (monthly) with reports
  - Retraining decision gates and sign-off integration (link to GOVERNANCE.md)

## Inputs
- `src/api/main.py` endpoints `/ready`, `/health`, `/metrics`
- `scripts/bench_metrics.py` CSV for FPR/FNR/TPR inputs to dashboards
- Orchestrator/vendor health summaries

## Risks & Mitigations
- Metric cardinality explosion: use bounded label sets (issuer, id_type, subset)
- Privacy in logs: enforce redaction and avoid sensitive fields

## Validation
- Synthetic load meets p50/p95 targets in local profile; breaker behavior resilient under `failover_sim.py`
- Dashboards reflect FPR/TPR and risk distributions from benchmark CSVs

## Next Steps
Implement metrics/tracing/logging extensions, provision dashboard JSON, define alert rules, and schedule drift/fairness jobs. Validate against IMPORTANT NOTE, then mark Phase 22 done.
