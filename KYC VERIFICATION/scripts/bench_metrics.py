#!/usr/bin/env python3
"""
Benchmark Metrics Runner (Phase 17 / 18)

Computes simple forensic-detectability metrics over a provided dataset path
and exports CSV with timestamped results. This is a lightweight proxy for
measuring red-team catch rate and basic latency stats.

Usage:
  python3 scripts/bench_metrics.py --dataset datasets/red_team --out artifacts/benchmarks.csv
"""

import argparse
import csv
import time
from pathlib import Path
from typing import Dict, List

import cv2
import numpy as np

from src.forensics.authenticity_verifier import AuthenticityVerifier


def list_images(root: Path) -> List[Path]:
    exts = {".jpg", ".jpeg", ".png", ".bmp"}
    return [p for p in root.rglob("*") if p.suffix.lower() in exts]


def assess_dir(verifier: AuthenticityVerifier, path: Path) -> Dict[str, float]:
    images = list_images(path)
    if not images:
        return {"count": 0, "authentic_ratio": 0.0, "avg_ms": 0.0}

    authentic = 0
    total_ms = 0.0
    for img_path in images:
        img = cv2.imread(str(img_path))
        if img is None:
            continue
        t0 = time.time()
        result = verifier.verify_authenticity(img)
        total_ms += (time.time() - t0) * 1000
        authentic += 1 if result.is_authentic else 0

    n = max(1, len(images))
    return {
        "count": len(images),
        "authentic_ratio": authentic / n,
        "avg_ms": total_ms / n,
    }


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Run benchmark metrics over dataset")
    ap.add_argument("--dataset", required=True, help="Dataset directory (legit/fraud or red_team subset)")
    ap.add_argument("--out", default="artifacts/benchmarks.csv", help="CSV output path")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    dataset_root = Path(args.dataset).resolve()
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    verifier = AuthenticityVerifier()

    # Assess folders if present
    subsets = []
    if (dataset_root / "legit").exists():
        subsets.append(("synthetic_legit", dataset_root / "legit"))
    if (dataset_root / "fraud").exists():
        subsets.append(("synthetic_fraud", dataset_root / "fraud"))

    # Red-team subfolders
    for name in ["copy_move", "resample", "screenshot", "font_edit"]:
        sub = dataset_root / name
        if sub.exists():
            subsets.append((f"red_team_{name}", sub))

    rows: List[List[str]] = []
    header = ["subset", "count", "authentic_ratio", "avg_ms"]

    for label, path in subsets:
        stats = assess_dir(verifier, path)
        rows.append([
            label,
            str(int(stats["count"])),
            f"{stats['authentic_ratio']:.4f}",
            f"{stats['avg_ms']:.2f}",
        ])

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)

    print(f"\n✅ Benchmark written: {out_path}")
    for r in rows:
        print("   ", dict(zip(header, r)))


if __name__ == "__main__":
    main()


