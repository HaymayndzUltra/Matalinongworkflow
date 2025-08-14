# Phase 19 Pre-Analysis — TESTS & QA
Task: kyc_identity_verification_manifest_actionable_20250813
Timestamp: 2025-08-14T14:28:16+08:00

## Objective
Prepare and scope automated tests and QA tasks to validate the KYC identity verification system end-to-end, focusing on red-team regressions and adapter/contract correctness.

## IMPORTANT NOTE (from plan)
Red-team regression ensures ≥95% fraud catch; tests cover adapters/contracts and breaker transitions.

## Scope & Approach
- Unit tests for `src/capture`, `src/classification`, `src/extraction`, `src/forensics`, `src/risk`, `src/orchestrator` modules.
- Integration tests: end-to-end pipeline for small subsets (legit/fraud) with deterministic seeds and fixed configs.
- Contract tests for issuer adapters and vendor orchestrator (request/response schemas, error handling, breaker transitions, half-open recovery).
- Regression: run `bench_metrics.py` across synthetic red-team subsets and assert ≥95% catch rate (FNR ≤ 5%) per organizer acceptance.

## Data & Environment
- Use `datasets/red_team/*` and `datasets/synthetic/*`. Prefer CPU-only venv `.venv`. Ensure deterministic flags where applicable.
- Avoid PII; stick to synthetic/red-team images.

## Risks & Mitigations
- Numerical instability warnings from forensics: treat as non-fatal initially; add thresholds and tolerances in assertions.
- Missing system binaries (Tesseract/ZBar): already gracefully handled; mock barcode/OCR in unit tests where needed.
- Timing flakiness: use generous timeouts and record CPU baseline metrics.

## Deliverables
- Pytest suite under `tests/` with unit + integration + contract coverage.
- CI-ready pytest command and sample config.
- Regression report with TPR/FNR per subset and overall.

## Next Step
After Phase 18 is marked done, begin implementing the tests per scope above and validate against the IMPORTANT NOTE.
