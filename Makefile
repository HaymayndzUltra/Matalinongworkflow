# Makefile — KYC Identity Verification

PY?=python3
PIP?=pip
VENV=.venv
ACTIVATE=. $(VENV)/bin/activate;
KYC_DIR=KYC\ VERIFICATION
TEST_DIR=$(KYC_DIR)/tests
DATASET?=$(KYC_DIR)/datasets/red_team
LIMIT?=5

.PHONY: help venv install api test bench pipeline artifacts compose-up compose-down pre-commit-install hooks lint format

help:
	@echo "Targets: venv, install, api, test, bench, pipeline, artifacts, compose-up, compose-down, pre-commit-install, hooks, lint, format"

venv:
	$(PY) -m venv $(VENV)
	@echo "Run: . $(VENV)/bin/activate"

install:
	$(ACTIVATE) $(PIP) install --upgrade pip
	$(ACTIVATE) $(PIP) install -r "$(KYC_DIR)/requirements.txt"

api:
	$(ACTIVATE) uvicorn src.api.app:app --host 0.0.0.0 --port 8000

test:
	PYTHONPATH="$(PWD)/KYC VERIFICATION/src" $(ACTIVATE) pytest -q "$(TEST_DIR)"

bench:
	$(PY) "$(KYC_DIR)/scripts/bench_metrics.py" --dataset "$(DATASET)" --out artifacts/benchmarks.csv

pipeline:
	$(PY) "$(KYC_DIR)/scripts/run_pipeline.py" --input "$(KYC_DIR)/datasets/synthetic/legit" --limit $(LIMIT)

artifacts:
	$(PY) "$(KYC_DIR)/scripts/generate_artifacts.py" --all

compose-up:
	docker compose up -d --build

compose-down:
	docker compose down

pre-commit-install:
	$(ACTIVATE) pre-commit install

hooks:
	$(ACTIVATE) pre-commit run --all-files

lint:
	$(ACTIVATE) black --check . && isort --check-only . && ruff .

format:
	$(ACTIVATE) black . && isort .
