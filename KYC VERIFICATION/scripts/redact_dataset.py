#!/usr/bin/env python3
"""
Dataset PII Redaction Utility (Phase 18)

Blurs regions that look like text to reduce residual PII in sample images.
This is a heuristic redactor for synthetic datasets and should not be used for
real PII without stronger OCR-based approaches.

Usage:
  python3 scripts/redact_dataset.py --input datasets/synthetic/legit --out datasets/synthetic/legit_redacted
"""

import argparse
from pathlib import Path
from typing import List

import cv2
import numpy as np


def list_images(root: Path) -> List[Path]:
    exts = {".jpg", ".jpeg", ".png", ".bmp", ".ppm"}
    return [p for p in root.rglob("*") if p.suffix.lower() in exts]


def redact_text_regions(img: np.ndarray) -> np.ndarray:
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if len(img.shape) == 3 else img
    # Binary for text-like contrasts
    _, bin_img = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    # Dilate to connect characters
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 5))
    dil = cv2.dilate(bin_img, kernel, iterations=1)
    contours, _ = cv2.findContours(dil, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    redacted = img.copy()
    for c in contours:
        x, y, w, h = cv2.boundingRect(c)
        # Heuristic filter for text-ish regions
        if w > 60 and h < 120 and w > h * 2:
            roi = redacted[y:y + h, x:x + w]
            roi = cv2.GaussianBlur(roi, (21, 21), 8)
            redacted[y:y + h, x:x + w] = roi
    return redacted


def parse_args():
    ap = argparse.ArgumentParser(description="Redact text-like regions in dataset images")
    ap.add_argument("--input", required=True, help="Input directory of images")
    ap.add_argument("--out", required=True, help="Output directory for redacted images")
    return ap.parse_args()


def main():
    args = parse_args()
    in_dir = Path(args.input).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    imgs = list_images(in_dir)
    if not imgs:
        print("No images found.")
        return

    for p in imgs:
        img = cv2.imread(str(p))
        if img is None:
            continue
        red = redact_text_regions(img)
        rel = p.relative_to(in_dir)
        dst = out_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(dst), red)

    print(f"\n✅ Redaction complete → {out_dir}")


if __name__ == "__main__":
    main()


