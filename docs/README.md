# KYC Identity Verification — Documentation

This repository contains a local, CLI-driven KYC identity verification system for experimentation with synthetic datasets.

- End-to-end pipeline: quality → classification → authenticity → extraction → risk → decision
- CPU-only friendly; external system binaries (Tesseract, ZBar) are optional. The code gracefully degrades if absent.

## Environment Setup

- Python: 3.10 recommended
- Virtualenv (already used in this repo):

```bash
python3 -m venv .venv
. .venv/bin/activate
# Install your dependencies as needed (CPU-only torch/vision verified locally)
```

## Datasets

- Synthetic datasets under `KYC VERIFICATION/datasets/`:
  - `datasets/synthetic/{legit,fraud}`
  - `datasets/red_team/{screenshot,font_edit,copy_move,resample,...}`

Images may include `.jpg`, `.jpeg`, `.png`, `.bmp`, `.ppm` (PPM supported).

## Key CLIs

All scripts live under `KYC VERIFICATION/scripts/` and are intended to be run from the repo root.

- End-to-end smoke test:

```bash
.venv/bin/python KYC\ VERIFICATION/scripts/run_pipeline.py \
  --input KYC\ VERIFICATION/datasets/synthetic/legit \
  --limit 5
```

- Benchmark metrics (per subset + overall):

```bash
python3 KYC\ VERIFICATION/scripts/bench_metrics.py \
  --dataset KYC\ VERIFICATION/datasets/red_team \
  --out artifacts/benchmarks.csv
```

- Vendor health summary:

```bash
python3 KYC\ VERIFICATION/scripts/vendor_healthcheck.py
```

- Failover simulation (breaker behavior and continuity):

```bash
python3 KYC\ VERIFICATION/scripts/failover_sim.py --requests 50 --timeout 0.2
```

- Compliance artifacts:

```bash
python3 KYC\ VERIFICATION/scripts/generate_artifacts.py --all
# or granular
python3 KYC\ VERIFICATION/scripts/generate_artifacts.py --dpia
python3 KYC\ VERIFICATION/scripts/generate_artifacts.py --ropa
python3 KYC\ VERIFICATION/scripts/generate_artifacts.py --retention
```

- Dataset PII redaction heuristic:

```bash
python3 KYC\ VERIFICATION/scripts/redact_dataset.py \
  --input KYC\ VERIFICATION/datasets/synthetic/legit \
  --out KYC\ VERIFICATION/datasets/synthetic/legit_redacted
```

## Configuration

- Capture quality configuration: `configs/capture_quality.json`
- Issuer templates, policy packs, vendor configs: document-specific configs may be referenced from `configs/` if present.

## KPIs and Metrics

- `bench_metrics.py` CSV columns: `subset, id_type, count, authentic_ratio, avg_ms, fpr, fnr, tpr, timestamp(+08:00)`
  - Legit subsets: FPR is the key metric
  - Fraud/red-team subsets: FNR and TPR (≥0.95 target in regression)

## Failover Patterns & Breakers (Overview)

- Use `failover_sim.py` to simulate vendor errors/latency spikes
- Circuit breakers: closed → open (on elevated error/p95) → half-open → closed
- Health summaries via `vendor_healthcheck.py`

## Reviewer SOP (High-Level)

1) Inspect per-image decision and score from `run_pipeline.py`
2) If decision is `review`, inspect:
   - quality metrics (glare/blur/resolution)
   - classification confidence and predicted document type
   - extraction fields and MRZ validity
   - forensics authenticity score
3) Use artifacts and logs (synthetic only; no PII) to support decisions

## Data Minimization & Retention

- Heuristic redaction available via `redact_dataset.py`
- Compliance artifacts generated into `artifacts/`:
  - `DPIA.md`, `ROPA.csv`, `retention_matrix.csv`

## Notes

- OCR/Barcode: if Tesseract or ZBar are missing, the pipeline continues with graceful fallbacks.
- All examples above are intended for local synthetic data only.
