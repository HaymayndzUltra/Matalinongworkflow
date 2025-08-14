# Phase 18 Pre-Analysis — SCRIPTS & CLIs

Task: `kyc_identity_verification_manifest_actionable_20250813`

## Restated IMPORTANT NOTE
IMPORTANT NOTE: [SYNTHESIZED FROM ORGANIZER] Commands function end-to-end locally with synthetic data; failover sims assert continuity and SLOs.

## Current Context
- Synthetic and red-team datasets are present under `KYC VERIFICATION/datasets/`.
- Benchmarks produced CSVs with per-subset and overall metrics including timestamps (`+08:00`).
- `bench_metrics.py` now supports `.ppm` and logs FPR/FNR/TPR; path import fixed.
- `failover_sim.py` exists under `KYC VERIFICATION/scripts/` for orchestrator reliability checks.

## Proposed Steps (Local E2E)
1. Verify CLI coverage and help messages
   - `python3 "KYC VERIFICATION/scripts/bench_metrics.py" -h`
   - `python3 "KYC VERIFICATION/scripts/generate_datasets.py" -h`
2. Run end-to-end with synthetic data (already validated):
   - `python3 "KYC VERIFICATION/scripts/generate_datasets.py" --base-dir "KYC VERIFICATION/datasets" --num-per-class 30 --seed 42`
   - `python3 "KYC VERIFICATION/scripts/bench_metrics.py" --dataset "KYC VERIFICATION/datasets/red_team" --out "KYC VERIFICATION/artifacts/benchmarks_red_team.csv"`
   - `python3 "KYC VERIFICATION/scripts/bench_metrics.py" --dataset "KYC VERIFICATION/datasets/synthetic" --out "KYC VERIFICATION/artifacts/benchmarks_synthetic.csv"`
3. Failover simulation SLO/assertions (Phase 18 tie-in):
   - `python3 "KYC VERIFICATION/scripts/failover_sim.py" --scenario primary_outage_30pct --assert_p95_ms 3.0x --assert_error_rate 0.05`
   - Ensure exits non-zero on SLO breach.

## Risks & Prerequisites
- Ensure OpenCV, SciPy, scikit-image installed (confirmed: cv2 4.9.0; scipy 1.11.3; skimage 0.21.0).
- Long runtimes for per-image forensics may affect SLO in CI; consider sampling for smoke tests.
- Import paths rely on running from repo root; wrappers may be needed for packaged execution.

## Acceptance Criteria Mapping
- E2E CLIs function locally using synthetic data.
- Failover sim asserts continuity and SLOs with non-zero exit on violation.

## Phase Completion Protocol (for next step)
```bash
python3 todo_manager.py show kyc_identity_verification_manifest_actionable_20250813
python3 todo_manager.py done kyc_identity_verification_manifest_actionable_20250813 18
```
