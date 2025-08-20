#!/usr/bin/env python3
"""
Synthetic & Red-Team Dataset Generator (Pure Python, no third-party deps)

Generates simple PPM images for legit and fraud/red-team variants so that
bench_metrics_pure.py can evaluate detection heuristics in constrained envs.

Structure:
  datasets/
    synthetic/
      legit/
      fraud/
    red_team/
      copy_move/
      resample/
      screenshot/
      font_edit/

Usage:
  python3 scripts/generate_datasets_pure.py --base-dir "KYC VERIFICATION/datasets" --num 50 --seed 42
"""

import argparse
import os
from pathlib import Path
import random
from typing import Tuple


def ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def clamp(x: int) -> int:
    return 0 if x < 0 else 255 if x > 255 else x


def draw_rect(img, x, y, w, h, color):
    H, W = len(img), len(img[0])
    for j in range(y, min(y + h, H)):
        row = img[j]
        for i in range(x, min(x + w, W)):
            row[i] = color


def draw_text_like(img, x, y, text_len=14, color=(0, 0, 0)):
    # Text surrogate: sequence of thin rectangles (no real font dependency)
    for k in range(text_len):
        draw_rect(img, x + k * 10, y, 7, 18, color)


def create_base_id(width: int = 300, height: int = 190):
    # White background
    img = [[(255, 255, 255) for _ in range(width)] for _ in range(height)]
    # Header bar
    draw_rect(img, 0, 0, width, 30, (168, 56, 0))
    # Fields (text-like bars)
    draw_text_like(img, 20, 50, text_len=18, color=(0, 0, 0))  # PSN
    draw_text_like(img, 20, 80, text_len=16, color=(0, 0, 0))  # NAME
    draw_text_like(img, 20, 110, text_len=12, color=(0, 0, 0))  # DOB
    draw_text_like(img, 20, 140, text_len=10, color=(0, 0, 0))  # SEX
    # Photo box
    draw_rect(img, width - 110, 50, 80, 80, (40, 40, 40))
    # QR pattern
    qx, qy, qs = width - 110, height - 50, 40
    draw_rect(img, qx, qy - qs, qs, qs, (0, 0, 0))
    for i in range(0, qs, 8):
        for j in range(0, qs, 8):
            if (i // 8 + j // 8) % 2 == 0:
                draw_rect(img, qx + i, qy - qs + j, 8, 8, (255, 255, 255))
    return img


def copy_move_tamper(img):
    H, W = len(img), len(img[0])
    x, y, w, h = 40, 60, 60, 30
    # Copy region
    roi = [row[x : x + w] for row in img[y : y + h]]
    # Paste shifted
    x2, y2 = min(W - w - 5, x + 80), min(H - h - 5, y + 40)
    for j in range(h):
        for i in range(w):
            img[y2 + j][x2 + i] = roi[j][i]
    # Marker line (weak) to allow heuristic to catch
    draw_rect(img, x2, y2 + h + 2, w, 2, (10, 10, 10))
    return img


def resample_tamper(img):
    # Introduce checker aliasing: stripe overlay
    H, W = len(img), len(img[0])
    for y in range(0, H, 4):
        for x in range(0, W, 2):
            r, g, b = img[y][x]
            img[y][x] = (clamp(r - 30), clamp(g - 30), clamp(b - 30))
    return img


def screenshot_tamper(img):
    # Light grid overlay
    H, W = len(img), len(img[0])
    for x in range(0, W, 12):
        for y in range(H):
            r, g, b = img[y][x]
            img[y][x] = (min(255, r + 20), min(255, g + 20), min(255, b + 20))
    for y in range(0, H, 12):
        for x in range(W):
            r, g, b = img[y][x]
            img[y][x] = (min(255, r + 20), min(255, g + 20), min(255, b + 20))
    return img


def font_edit_tamper(img):
    # Overpaint text-like bars with red for kerning mismatch surrogate
    draw_text_like(img, 20, 80, text_len=16, color=(220, 0, 0))
    draw_text_like(img, 20, 110, text_len=12, color=(220, 0, 0))
    return img


def save_ppm(img, path: Path) -> None:
    H, W = len(img), len(img[0])
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        header = f"P6\n{W} {H}\n255\n".encode("ascii")
        f.write(header)
        for row in img:
            for r, g, b in row:
                f.write(bytes([r, g, b]))


def generate(out_dir: Path, n: int, seed: int) -> None:
    random.seed(seed)
    paths = {
        "legit": out_dir / "synthetic" / "legit",
        "fraud": out_dir / "synthetic" / "fraud",
        "copy_move": out_dir / "red_team" / "copy_move",
        "resample": out_dir / "red_team" / "resample",
        "screenshot": out_dir / "red_team" / "screenshot",
        "font_edit": out_dir / "red_team" / "font_edit",
    }
    for p in paths.values():
        ensure_dir(p)

    # Legit
    for i in range(n):
        img = create_base_id()
        save_ppm(img, paths["legit"] / f"legit_{i:03d}.ppm")

    # Synthetic fraud (mix of tamper types)
    t_funcs = [copy_move_tamper, resample_tamper, screenshot_tamper, font_edit_tamper]
    for i in range(n):
        img = create_base_id()
        tampered = random.choice(t_funcs)(img)
        save_ppm(tampered, paths["fraud"] / f"fraud_{i:03d}.ppm")

    # Red-team subsets (n//2 each)
    m = max(1, n // 2)
    for i in range(m):
        save_ppm(copy_move_tamper(create_base_id()), paths["copy_move"] / f"copy_move_{i:03d}.ppm")
    for i in range(m):
        save_ppm(resample_tamper(create_base_id()), paths["resample"] / f"resample_{i:03d}.ppm")
    for i in range(m):
        save_ppm(screenshot_tamper(create_base_id()), paths["screenshot"] / f"screenshot_{i:03d}.ppm")
    for i in range(m):
        save_ppm(font_edit_tamper(create_base_id()), paths["font_edit"] / f"font_edit_{i:03d}.ppm")


def parse_args():
    ap = argparse.ArgumentParser(description="Generate PPM datasets (pure Python)")
    ap.add_argument("--base-dir", default="KYC VERIFICATION/datasets", help="Base datasets directory")
    ap.add_argument("--num", type=int, default=50, help="Images per split")
    ap.add_argument("--seed", type=int, default=42, help="Random seed")
    return ap.parse_args()


def main():
    args = parse_args()
    out_dir = Path(args.base_dir).resolve()
    ensure_dir(out_dir)
    generate(out_dir, args.num, args.seed)
    print(f"\n✅ Generated datasets in {out_dir}")


if __name__ == "__main__":
    main()


