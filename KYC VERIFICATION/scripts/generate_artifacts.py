#!/usr/bin/env python3
"""
Compliance Artifacts Generator (Phase 18)

Generates DPIA.md, ROPA.csv, and retention_matrix.csv into ./artifacts.

Usage:
  python3 scripts/generate_artifacts.py --all
  python3 scripts/generate_artifacts.py --dpia
"""

import argparse
from pathlib import Path

from src.compliance.artifact_generator import ComplianceArtifactGenerator


def parse_args():
    ap = argparse.ArgumentParser(description="Generate compliance artifacts")
    ap.add_argument("--all", action="store_true", help="Generate all artifacts")
    ap.add_argument("--dpia", action="store_true", help="Generate DPIA only")
    ap.add_argument("--ropa", action="store_true", help="Generate ROPA only")
    ap.add_argument("--retention", action="store_true", help="Generate retention matrix only")
    return ap.parse_args()


def main():
    args = parse_args()
    gen = ComplianceArtifactGenerator(project_path=str(Path(__file__).resolve().parents[1]))

    if args.all or not (args.dpia or args.ropa or args.retention):
        paths = gen.generate_all()
        print("\n✅ Generated all artifacts:")
        for k, v in paths.items():
            print(f"  - {k}: {v}")
        return

    if args.dpia:
        print("DPIA:", gen.generate_dpia())
    if args.ropa:
        print("ROPA:", gen.generate_ropa())
    if args.retention:
        print("Retention:", gen.generate_retention_matrix())


if __name__ == "__main__":
    main()


