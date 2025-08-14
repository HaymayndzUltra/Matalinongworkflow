#!/usr/bin/env python3
"""
Synthetic & Red-Team Dataset Generator (Phase 17)

Generates minimal synthetic ID-like images for "legit" and multiple fraud variants
that common forensic checks can detect (copy-move, resample, screenshot-of-screenshot,
overpainted text). This is intended for benchmarking and red-team regression.

Output structure (created if missing):
  datasets/
    synthetic/
      legit/                 # legitimate images
      fraud/                 # intentionally tampered images
    red_team/
      copy_move/
      resample/
      screenshot/
      font_edit/

Usage:
  python3 scripts/generate_datasets.py --base-dir datasets --num-per-class 25 --seed 42
"""

import argparse
import os
from pathlib import Path
from typing import Tuple
import random
import math

import cv2
import numpy as np


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def draw_base_id(width: int = 856, height: int = 540) -> np.ndarray:
    """Create a simple synthetic ID-like card image."""
    image = np.ones((height, width, 3), dtype=np.uint8) * 255

    # Header bar
    cv2.rectangle(image, (0, 0), (width, 90), (168, 56, 0), -1)
    cv2.putText(image, "REPUBLIC OF THE PHILIPPINES", (150, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
    cv2.putText(image, "PHILIPPINE NATIONAL ID", (210, 75), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # Fields
    cv2.putText(image, "PSN: 1234-5678-9012-3456", (50, 150), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(image, "NAME: JUAN DELA CRUZ", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(image, "DATE OF BIRTH: 1990-01-01", (50, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(image, "SEX: M", (50, 300), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)
    cv2.putText(image, "NATIONALITY: PHL", (50, 350), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 0), 2)

    # Simulated face placeholder
    cv2.rectangle(image, (width - 220, 140), (width - 60, 300), (40, 40, 40), 2)
    cv2.putText(image, "PHOTO", (width - 190, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (40, 40, 40), 2)

    # QR/Barcode placeholder
    qr_x, qr_y, qr_size = width - 220, height - 180, 120
    cv2.rectangle(image, (qr_x, qr_y), (qr_x + qr_size, qr_y + qr_size), (0, 0, 0), 2)
    for i in range(10):
        for j in range(10):
            if (i + j) % 2 == 0:
                x1 = qr_x + i * (qr_size // 10)
                y1 = qr_y + j * (qr_size // 10)
                cv2.rectangle(image, (x1, y1), (x1 + qr_size // 10, y1 + qr_size // 10), (0, 0, 0), -1)

    return image


def save_image(img: np.ndarray, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(path), img)


def tamper_copy_move(img: np.ndarray) -> np.ndarray:
    """Copy a region and paste it elsewhere (detectable by copy-move)."""
    tampered = img.copy()
    h, w = tampered.shape[:2]
    bw, bh = 120, 60
    x1 = random.randint(80, w // 2)
    y1 = random.randint(120, h // 2)
    roi = tampered[y1:y1 + bh, x1:x1 + bw].copy()
    x2 = min(w - bw - 10, x1 + random.randint(140, 240))
    y2 = min(h - bh - 10, y1 + random.randint(60, 160))
    tampered[y2:y2 + bh, x2:x2 + bw] = roi
    return tampered


def tamper_resample(img: np.ndarray) -> np.ndarray:
    """Apply resampling artifacts via scale+rotate+re-encode."""
    tampered = img.copy()
    h, w = tampered.shape[:2]
    scale = random.uniform(0.8, 1.2)
    angle = random.uniform(-7, 7)
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, scale)
    tampered = cv2.warpAffine(tampered, M, (w, h), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
    # Down-up sample to introduce artifacts
    small = cv2.resize(tampered, (w // 2, h // 2), interpolation=cv2.INTER_LINEAR)
    tampered = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR)
    return tampered


def tamper_screenshot(img: np.ndarray) -> np.ndarray:
    """Simulate screenshot-of-screenshot: blur + compression blocks."""
    tampered = cv2.GaussianBlur(img, (5, 5), 1.2)
    # Overlay faint grid to mimic screen texture
    grid = tampered.copy()
    step = 12
    for x in range(0, grid.shape[1], step):
        cv2.line(grid, (x, 0), (x, grid.shape[0] - 1), (235, 235, 235), 1)
    for y in range(0, grid.shape[0], step):
        cv2.line(grid, (0, y), (grid.shape[1] - 1, y), (235, 235, 235), 1)
    tampered = cv2.addWeighted(tampered, 0.85, grid, 0.15, 0)
    return tampered


def tamper_font_edit(img: np.ndarray) -> np.ndarray:
    """Overpaint critical text with mismatched kerning/size."""
    tampered = img.copy()
    cv2.putText(tampered, "NAME: JU4N  DELA  CRUZ", (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
    cv2.putText(tampered, "DATE OF BIRTH: 1990-01-32", (50, 250), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
    return tampered


def generate_samples(out_dir: Path, count: int, seed: int) -> Tuple[int, int]:
    random.seed(seed)
    np.random.seed(seed)

    legit_dir = out_dir / "synthetic" / "legit"
    fraud_dir = out_dir / "synthetic" / "fraud"
    rt_copy = out_dir / "red_team" / "copy_move"
    rt_resample = out_dir / "red_team" / "resample"
    rt_screenshot = out_dir / "red_team" / "screenshot"
    rt_font = out_dir / "red_team" / "font_edit"

    for p in [legit_dir, fraud_dir, rt_copy, rt_resample, rt_screenshot, rt_font]:
        ensure_dir(p)

    # Legit samples
    for i in range(count):
        base = draw_base_id()
        # Add subtle random noise to diversify
        noise = np.random.normal(0, 1.0, base.shape).astype(np.float32)
        legit = np.clip(base.astype(np.float32) + noise, 0, 255).astype(np.uint8)
        save_image(legit, legit_dir / f"legit_{i:03d}.jpg")

    # Fraud samples (mixed)
    tamper_funcs = [tamper_copy_move, tamper_resample, tamper_screenshot, tamper_font_edit]
    for i in range(count):
        base = draw_base_id()
        f = random.choice(tamper_funcs)
        fraud = f(base)
        save_image(fraud, fraud_dir / f"fraud_{i:03d}.jpg")

    # Red-team variants per type (count//2 each)
    per_type = max(1, count // 2)
    for i in range(per_type):
        base = draw_base_id()
        save_image(tamper_copy_move(base), rt_copy / f"copy_move_{i:03d}.jpg")
    for i in range(per_type):
        base = draw_base_id()
        save_image(tamper_resample(base), rt_resample / f"resample_{i:03d}.jpg")
    for i in range(per_type):
        base = draw_base_id()
        save_image(tamper_screenshot(base), rt_screenshot / f"screenshot_{i:03d}.jpg")
    for i in range(per_type):
        base = draw_base_id()
        save_image(tamper_font_edit(base), rt_font / f"font_edit_{i:03d}.jpg")

    total_legit = len(list(legit_dir.glob("*.jpg")))
    total_fraud = len(list(fraud_dir.glob("*.jpg"))) + sum(len(list(d.glob("*.jpg"))) for d in [rt_copy, rt_resample, rt_screenshot, rt_font])
    return total_legit, total_fraud


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Generate synthetic and red-team datasets")
    ap.add_argument("--base-dir", default="datasets", help="Base datasets directory (relative to project root)")
    ap.add_argument("--num-per-class", type=int, default=30, help="Number of images for legit and fraud synthetic sets")
    ap.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    return ap.parse_args()


def main():
    args = parse_args()
    project_root = Path(__file__).resolve().parents[1]
    out_dir = (project_root / args.base_dir).resolve()
    ensure_dir(out_dir)

    total_legit, total_fraud = generate_samples(out_dir, args.num_per_class, args.seed)

    print(f"\n✅ Dataset generation complete → {out_dir}")
    print(f"   Legit images: {total_legit}")
    print(f"   Fraud images (incl. red-team): {total_fraud}")


if __name__ == "__main__":
    main()


