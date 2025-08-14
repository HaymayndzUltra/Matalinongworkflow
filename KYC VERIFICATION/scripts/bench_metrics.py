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
from datetime import datetime, timezone, timedelta
import sys

import cv2
import numpy as np

# Ensure package root is on sys.path so `src` can be imported when running from repo root
PKG_ROOT = Path(__file__).resolve().parents[1]  # .../KYC VERIFICATION
if str(PKG_ROOT) not in sys.path:
    sys.path.append(str(PKG_ROOT))

from src.forensics.authenticity_verifier import AuthenticityVerifier


def list_images(root: Path) -> List[Path]:
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".ppm"}
    return [p for p in root.rglob("*") if p.suffix.lower() in exts]


def assess_dir(verifier: AuthenticityVerifier, path: Path) -> Dict[str, float]:
    images = list_images(path)
    if not images:
        return {"count": 0, "authentic_count": 0, "authentic_ratio": 0.0, "avg_ms": 0.0}

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
        "authentic_count": authentic,
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
    header = ["subset", "id_type", "count", "authentic_ratio", "avg_ms", "fpr", "fnr", "tpr", "timestamp"]

    # Aggregates for overall metrics
    overall_legit_count = 0
    overall_legit_fp = 0
    overall_legit_ms_sum = 0.0
    overall_fraud_count = 0
    overall_fraud_fn = 0
    overall_fraud_ms_sum = 0.0

    for label, path in subsets:
        stats = assess_dir(verifier, path)
        ts = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
        count = int(stats["count"])
        authentic_count = int(stats.get("authentic_count", round(stats["authentic_ratio"] * max(1, count))))
        pred_fraud = max(0, count - authentic_count)  # predicted tamper
        id_type = "legit" if label.endswith("legit") else "fraud"
        # Metrics
        fpr = (pred_fraud / count) if (id_type == "legit" and count) else 0.0
        fnr = (authentic_count / count) if (id_type != "legit" and count) else 0.0
        tpr = (1.0 - fnr) if (id_type != "legit" and count) else ""

        # Aggregates
        if id_type == "legit":
            overall_legit_count += count
            overall_legit_fp += pred_fraud
            overall_legit_ms_sum += stats["avg_ms"] * count
        else:
            overall_fraud_count += count
            overall_fraud_fn += authentic_count
            overall_fraud_ms_sum += stats["avg_ms"] * count

        rows.append([
            label,
            id_type,
            str(count),
            f"{stats['authentic_ratio']:.4f}",
            f"{stats['avg_ms']:.2f}",
            f"{fpr:.4f}",
            f"{fnr:.4f}" if fnr != 0.0 else "",
            f"{tpr:.4f}" if isinstance(tpr, float) else "",
            ts,
        ])

    # Append overall summaries
    ts_all = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")
    # Overall legit
    if overall_legit_count > 0:
        overall_legit_auth = overall_legit_count - overall_legit_fp
        rows.append([
            "overall_legit",
            "legit",
            str(overall_legit_count),
            f"{(overall_legit_auth / overall_legit_count):.4f}",
            f"{(overall_legit_ms_sum / max(1, overall_legit_count)):.2f}",
            f"{(overall_legit_fp / overall_legit_count):.4f}",
            "",
            "",
            ts_all,
        ])
    # Overall fraud (incl. red-team)
    if overall_fraud_count > 0:
        rows.append([
            "overall_fraud",
            "fraud",
            str(overall_fraud_count),
            f"{(overall_fraud_fn / overall_fraud_count):.4f}",
            f"{(overall_fraud_ms_sum / max(1, overall_fraud_count)):.2f}",
            "",
            f"{(overall_fraud_fn / overall_fraud_count):.4f}",
            f"{(1.0 - (overall_fraud_fn / overall_fraud_count)):.4f}",
            ts_all,
        ])
    # Overall all
    total_count = overall_legit_count + overall_fraud_count
    if total_count > 0:
        overall_ms = (overall_legit_ms_sum + overall_fraud_ms_sum) / total_count
        overall_fp = overall_legit_fp
        overall_fn = overall_fraud_fn
        rows.append([
            "overall_all",
            "mixed",
            str(total_count),
            "",
            f"{overall_ms:.2f}",
            f"{(overall_fp / overall_legit_count):.4f}" if overall_legit_count else "",
            f"{(overall_fn / overall_fraud_count):.4f}" if overall_fraud_count else "",
            "",
            ts_all,
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


