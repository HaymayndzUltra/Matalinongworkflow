You are a KYC Fraud-Detection Engineer. Build a production-ready, bank-grade eKYC Fraud ID detection system with tests, configs, datasets, and docs. Deliver a complete repo scaffold that's runnable locally and in Docker.

STRICT CONSTRAINTS
- Do not write to shared state/queue files; provide functions + CLI + API + unit/integration tests.
- Security: never hardcode secrets; provide .env.example and use env vars; redact PII in logs by default.
- Timestamps: ISO8601 +08:00. Deterministic seeds for tests; reproducible builds.
- KPIs/Targets:
  - Capture pass@1000px ≥ 95%
  - Doc classifier top-1 ≥ 0.90
  - Tamper/forensics AUC ≥ 0.90
  - Face TAR@FAR1% ≥ 0.98
  - Liveness FMR ≤ 1%, FNMR ≤ 3%
  - Decision p50<20s p95<60s; Availability ≥ 99.9% under vendor outage sim
  - False-approve rate ≤ target in policy_pack.yaml

DELIVERABLES (folders/files)
1) capture_quality.py — glare/blur/orientation; coaching hints; per-frame quality; pass@1000px metric.
2) doc_classifier.py — multi-ID/country classifier (top-1 ≥0.90). Auto-loads issuer templates.
3) extract.py — OCR; MRZ (ICAO 9303 checksums); Barcode (PDF417/QR); NFC passport (DG1/DG2 passive auth).
4) forensics.py — ELA/noise/resample/copy-move detection; ROI heatmaps; texture/FFT checks; font/kerning scoring.
5) biometrics.py — multi-frame face match (report TAR@FAR1%); passive + challenge liveness.
6) rules.py — issuer-specific validators (expiry/format/name/DOB logic, checksum per ID type).
7) device_intel.py — VPN/TOR/proxy; emulator/root/jailbreak; IP/SIM/GPS mismatch; geovelocity; velocity/reuse.
8) risk_model.py — feature aggregation; rules + ML ensemble; JSON policy thresholds; explainable reasons.
9) sanctions_aml.py — sanctions/PEP/adverse media; IP/geo controls; explainable hits; multi-vendor via orchestrator.
10) vendor_orchestrator.py — timeouts/retries/backoff; circuit breakers; PRIMARY→SECONDARY failover; hedged requests; SLAs and cost/latency budgets; Prometheus metrics.
11) issuer_registry/  (adapters + router)
    - adapters/: philid_adapter.py, lto_adapter.py, prc_adapter.py, psa_adapter.py, passport_adapter.py
    - contracts/: request/response pydantic models; availability, rate limits, evidence fields
    - registry_router.py — routes & aggregates proofs (reference ID, signature/hash, timestamp)
    - tests/ with simulators and golden JSON
12) ui_reviewer/ — minimal reviewer console (PII toggle, ELA/noise heatmaps, face-timeline); two-person approval on high-risk; audit links.
13) api.py — FastAPI service: /validate, /extract, /score, /decide, /issuer/verify, /aml/screen, /audit/export, /compliance/generate, /metrics, /ready, /health. Provide OpenAPI spec.
14) audit_export.py — WORM/append-only JSONL bundle + manifest with SHA-256 hash chain; verify script; S3/GCS/local targets.
15) compliance/ — artifact generators:
    - templates: dpia_template.md.j2, ropa_register.csv.j2, retention_matrix.csv.j2, breach_notif_playbook.md.j2
    - generators/: generate_dpia.py, generate_ropa.py, generate_retention.py (pulls from configs + code inventory)
16) configs/
    - policy_pack.yaml — CDD/EDD tiers; auto-approve/deny rules; review queues; dispute/appeal SOP; reviewer calibration checks
    - vendors.yaml — vendor priorities, timeouts, retry/backoff, breaker thresholds, cost weights, quotas
    - issuer_templates/PH/
        philid.yaml
        umid.yaml
        drivers_license.yaml
        passport.yaml
        prc.yaml
      (ROI boxes, fonts, tolerances, checksum rules, security features incl. uv_expected/hologram zones)
17) datasets/  (synthetic & red-team)
    - generator/: synth_legit.py, synth_fraud.py (reprint, screenshot-of-screenshot, font-edit, field-swap, barcode/MRZ mismatch, resample, copy-move, GAN face swap)
    - fixtures/: legit/*, fraud/*
    - README_dataset.md — consent & usage, bias notes, and splits
18) scripts/
    - run_pipeline.py — end-to-end from session JSON to decision JSON
    - bench_metrics.py — AUC/TAR@FAR1%/FPR per issuer & overall; latency TAT; exporter to CSV
    - vendor_healthcheck.py — vendor probes; SLA conformance
    - failover_sim.py — simulate outages/latency; assert continuity & SLOs
    - generate_artifacts.py — DPIA/ROPA/retention outputs into ./artifacts/
    - redact_dataset.py — strip PII for sharing
19) tests/ — pytest unit + integration; contract tests for adapters; red-team regression suite; golden contracts.
20) docs/
    - README.md — setup, run, KPIs, dashboards, SLOs, failover patterns, artifact generation, reviewer SOPs
    - RUNBOOK_oncall.md — incident triage, vendor outage playbook, breach timelines
    - GOVERNANCE.md — model registry, lineage, canary, sign-off gates, bias/fairness schedule
21) docker/
    - Dockerfile (GPU-optional) + docker-compose.yml with healthchecks; /ready & /live; resource limits; tmpfs for PII staging
22) .env.example — placeholders for vendor keys; local defaults
23) .pre-commit-config.yaml — black/isort/ruff/mypy; secrets scan; large file guard
24) Makefile — make dev | test | bench | compose-up | compose-down | generate-artifacts

ACCEPTANCE CRITERIA (must implement)
- Multi-ID support: PH National ID (PhilID), UMID, Driver’s License, Passport, PRC with working templates under configs/issuer_templates/PH/.
- Vendor Failover: sustain ≥99.9% availability with failover_sim primary_outage_30pct; decision p95<60s.
- Circuit Breakers: open on error_rate >5% over 2 min or p95 latency >3× baseline; support half-open recovery; metrics visible in /metrics.
- Issuer/Registry proofs: when adapter available, include proofs {ref_id, signature/hash, timestamp, adapter_name}.
- Compliance artifacts: generate_artifacts.py outputs DPIA.md, ROPA.csv, retention_matrix.csv; populated with data flows and minimization map.
- Audit export: /audit/export returns signed JSONL bundle + manifest; verify tool passes.
- Policy pack: enforce two-person approval on high-risk; dispute/appeal path; reviewer calibration checks (IRR κ≥0.8 target).
- Dataset generator: produce legit & fraud splits; red-team variants; benchmark via bench_metrics.py; store metrics with timestamps.
- Logs: redact PII by default; per-request correlation IDs; WORM links in decisions.
- Config-driven thresholds: no magic numbers in code; everything tunable in configs.

API SURFACE (JSON contracts; examples included in code)
- POST /validate  — capture quality report (glare/blur/orientation, coaching)
- POST /extract   — OCR/MRZ/Barcode/NFC results + ROIs and confidences
- POST /score     — features → risk_score, flags, reasons
- POST /decide    — final decision {approve|review|deny}, risk_score, reasons[], audit_refs[], policy_version
- GET  /issuer/verify?type=PHILID&id=... — {verified, proofs{...}, adapter}
- POST /aml/screen — multi-vendor sanctions/PEP/adverse media with explainable hits
- GET  /audit/export?from=...&to=... — signed bundle + manifest
- POST /compliance/generate — returns DPIA/ROPA/retention artifacts (files)
- GET  /metrics | /health | /ready

CONFIG SNIPPETS (minimal examples)
# configs/vendors.yaml
vendors:
  - name: vendorA_sanctions
    type: sanctions
    priority: 1
    timeout_ms: 2500
    retry: {max: 2, backoff: exponential, base_ms: 200}
    breaker: {error_rate_threshold: 0.05, min_samples: 100, reset_sec: 60}
    cost_weight: 1.0
  - name: vendorB_sanctions
    type: sanctions
    priority: 2
    timeout_ms: 3500
    retry: {max: 1, backoff: linear, base_ms: 300}
    breaker: {error_rate_threshold: 0.05, min_samples: 100, reset_sec: 60}
    cost_weight: 0.7

# configs/policy_pack.yaml (excerpt)
decisions:
  auto_deny:
    - mrz_checksum_fail AND barcode_mismatch
    - device.vpn AND forensics.ela_auc >= 0.9
  auto_approve:
    - nfc.passive_auth_ok AND integrity.consistency_ok AND biometrics.tar_far1 >= 0.98
review_thresholds:
  risk_score_review_min: 0.20
  risk_score_deny_min: 0.45
queues:
  high_risk: {two_person_approval: true, sla_min: 15}

# configs/issuer_templates/PH/philid.yaml (excerpt)
issuer: "PH"
id_type: "PHILID"
version: "v1.0"
dimensions_mm: [85.60, 53.98]
dpi_expected: 300
rois:
  full_name: {bbox_mm: [15.2, 20.5, 50.0, 6.0], font: "Arial-Bold", font_size_pt: 9}
  philid_number: {bbox_mm: [60.0, 10.0, 20.0, 5.0], checksum: "mod10"}
security_features:
  uv_expected: true
checks:
  expiry: null
  barcode: {format: "QR", required: true, data_fields: ["philid_number","full_name","dob"]}
tolerances:
  roi_shift_mm: 0.5
# (Also provide umid.yaml, drivers_license.yaml, passport.yaml, prc.yaml similarly.)

SCRIPTS & CLI EXAMPLES
- End-to-end:      python scripts/run_pipeline.py --input sample/session.json
- Benchmarks:      python scripts/bench_metrics.py --dataset datasets/redteam/
- Vendor Health:   python scripts/vendor_healthcheck.py --configs configs/vendors.yaml
- Failover Sim:    python scripts/failover_sim.py --scenario primary_outage_30pct
- Artifacts:       python scripts/generate_artifacts.py --out ./artifacts/
- Audit Export:    curl -o export.zip 'http://localhost:8000/audit/export?from=...&to=...'

TESTING REQUIREMENTS
- pytest unit & integration; contract tests for issuer adapters; circuit breaker state transitions covered.
- Red-team regression: ensure ≥95% fraud catch rate on attack set; log FPR/FNR per ID type & overall.
- Bias/fairness: report metrics per demographic bucket (if labels available); document in GOVERNANCE.md.

OPS & METRICS
- /metrics (Prometheus): vendor latencies, error rates, breaker states, decision TAT, capture pass rate, fraud catch rate, FPR/FNR.
- SLOs: Decision p50<20s p95<60s; Availability 99.9% under vendor issues; Error budget policy documented.
- On-call: RUNBOOK_oncall.md with incident flow; breach notification timelines; DR (RPO/RTO) checklist.

DOCUMENTATION
- docs/README.md: setup (venv + Docker), running, configs, KPIs, dashboards, SLOs, failover patterns, reviewer SOPs (CDD/EDD, dispute/appeal), data minimization map & retention.
- GOVERNANCE.md: model registry, lineage, datasets, canary rollout, approval gate, periodic bias/fairness audits.

OUTPUTS
- Complete repo scaffold with code, configs, datasets, tests, docs, Docker setup.
- Clear TODOs where external vendor/issuer credentials are required. Everything else should run locally with synthetic data.
