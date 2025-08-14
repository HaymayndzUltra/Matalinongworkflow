# On-Call Runbook — KYC Identity Verification

This runbook outlines operational procedures, SLOs, alerts, incident response, and failover drills.

## SLOs & Alerts

- Decision latency:
  - p50 < 20s, p95 < 60s (dev/local tolerances are higher; production targets listed here)
- Availability:
  - 99.9% under vendor issues (via failover, circuit breakers)
- Alerts:
  - Elevated error rate (>5% over 2 minutes) → open circuit breaker
  - Latency degradation (p95 > 3× baseline) → breaker transition and route to healthy vendor
  - Drift/fairness alerts (model lifecycle) per governance cadence

## Health & Diagnostics

- Vendor health summary:

```bash
python3 KYC\ VERIFICATION/scripts/vendor_healthcheck.py
```

- Failover simulation drill:

```bash
python3 KYC\ VERIFICATION/scripts/failover_sim.py --requests 50 --timeout 0.2
```

- Benchmark snapshot (red_team or synthetic subsets):

```bash
python3 KYC\ VERIFICATION/scripts/bench_metrics.py \
  --dataset KYC\ VERIFICATION/datasets/red_team \
  --out artifacts/benchmarks.csv
```

## Circuit Breaker States

- States: closed → open → half-open → closed
- Triggers:
  - Open: error_rate >5% over 2 min OR p95 > 3× baseline
  - Half-open: cooldown elapsed, probe requests
  - Closed: probe success within tolerance

## Incident Response

1) Acknowledge alert; gather evidence (logs, health summary, benchmarks)
2) Identify impacted capability (OCR/FACE/AML) and vendor(s)
3) Verify breaker state transitions; force fallback path if needed
4) Communicate status and ETA; track timeline
5) Post-incident review: root cause, corrective actions, regression guard in tests

## Escalation

- Primary: On-call engineer
- Secondary: Platform owner / ML owner depending on subsystem
- Compliance contact: For audit/logging queries (artifacts in `artifacts/`)

## Change Management

- Follow canary/sign-off gates (see GOVERNANCE.md)
- All operational changes documented with timestamps (+08:00) and rollback steps
