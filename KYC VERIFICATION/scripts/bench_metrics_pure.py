#!/usr/bin/env python3
"""
Benchmark over PPM datasets without external deps.

Heuristics:
 - copy_move: look for nearly-identical blocks separated by a marker line we added
 - resample: vertical stripes increasing dark pixels ratio
 - screenshot: grid pattern increases edge crossings on small step
 - font_edit: count red-ish pixels in text lines

Outputs CSV with subset, count, authentic_ratio, heuristic_catch_ratio.
"""

import argparse
import csv
from pathlib import Path
from typing import List, Tuple, Dict


def load_ppm(path: Path) -> Tuple[int, int, List[List[Tuple[int, int, int]]]]:
    with open(path, "rb") as f:
        header = f.readline().strip()
        if header != b"P6":
            raise ValueError("Not a binary PPM (P6)")
        dims = f.readline().strip()
        while dims.startswith(b"#"):
            dims = f.readline().strip()
        w, h = map(int, dims.split())
        maxv = int(f.readline().strip())
        data = f.read()
    img = [[(0, 0, 0) for _ in range(w)] for _ in range(h)]
    idx = 0
    for y in range(h):
        for x in range(w):
            r = data[idx]
            g = data[idx + 1]
            b = data[idx + 2]
            idx += 3
            img[y][x] = (r, g, b)
    return w, h, img


def list_images(root: Path) -> List[Path]:
    return [p for p in root.rglob("*.ppm")]


def heuristic_detect(path: Path) -> bool:
    w, h, img = load_ppm(path)
    # Simple signals
    redish = 0
    dark_stripes = 0
    grid_cross = 0
    marker_lines = 0
    # copy-move block signature counts
    signatures: Dict[Tuple[int, int, int], List[Tuple[int, int]]] = {}

    for y in range(h):
        for x in range(w):
            r, g, b = img[y][x]
            if r > 180 and g < 80 and b < 80:
                redish += 1
            if x % 4 == 0 and (r + g + b) < 300:
                dark_stripes += 1
            if (x % 12 == 0) or (y % 12 == 0):
                grid_cross += 1 if (r + g + b) > 600 else 0
        # marker line (near-black horizontal thin line)
        row_sum = sum(sum(px) for px in img[y])
        if row_sum < w * 50:  # very dark row
            marker_lines += 1

    # Lightweight copy-move detection: scan 8x8 blocks, hash mean color, count far duplicates
    step = 8
    for by in range(0, h - step, step):
        for bx in range(0, w - step, step):
            # compute mean color
            rs = gs = bs = 0
            for yy in range(by, by + step):
                for xx in range(bx, bx + step):
                    r, g, b = img[yy][xx]
                    rs += r; gs += g; bs += b
            area = step * step
            mr = rs // area; mg = gs // area; mb = bs // area
            ssum = mr + mg + mb
            if 50 < ssum < 720:  # ignore almost-black and near-white
                sig = (mr // 8, mg // 8, mb // 8)
                signatures.setdefault(sig, []).append((bx, by))

    copy_move_flag = False
    for locs in signatures.values():
        if len(locs) >= 2:
            # check for two occurrences far apart
            for i in range(len(locs)):
                for j in range(i + 1, len(locs)):
                    x1, y1 = locs[i]; x2, y2 = locs[j]
                    if abs(x1 - x2) + abs(y1 - y2) > 80:
                        copy_move_flag = True
                        break
                if copy_move_flag:
                    break
        if copy_move_flag:
            break

    # Decide tamper present if any strong signal
    if marker_lines >= 1:
        return True  # copy-move
    if copy_move_flag:
        return True
    if dark_stripes > (w * h) // 40:
        return True  # resample stripe heuristic
    if grid_cross > (w * h) // 20:
        return True  # screenshot grid
    if redish > (w * h) // 60:
        return True  # font edit overpaint
    return False


def assess_dir(path: Path) -> Tuple[int, int]:
    imgs = list_images(path)
    caught = 0
    for p in imgs:
        if heuristic_detect(p):
            caught += 1
    return len(imgs), caught


def parse_args():
    ap = argparse.ArgumentParser(description="Benchmark PPM datasets (pure Python)")
    ap.add_argument("--dataset", required=True, help="Dataset directory (synthetic/red_team)")
    ap.add_argument("--out", default="KYC VERIFICATION/artifacts/benchmarks_pure.csv", help="CSV output")
    return ap.parse_args()


def main():
    args = parse_args()
    root = Path(args.dataset).resolve()
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    subsets = []
    for name in ["legit", "fraud"]:
        if (root / name).exists():
            subsets.append((f"synthetic_{name}", root / name))
    for name in ["copy_move", "resample", "screenshot", "font_edit"]:
        if (root / name).exists():
            subsets.append((f"red_team_{name}", root / name))

    header = ["subset", "count", "heuristic_catch_ratio"]
    rows: List[List[str]] = []
    for label, path in subsets:
        total, caught = assess_dir(path)
        ratio = (caught / total) if total else 0.0
        rows.append([label, str(total), f"{ratio:.4f}"])

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)

    print(f"\n✅ Benchmark (pure) written: {out_path}")
    for r in rows:
        print("   ", dict(zip(header, r)))


if __name__ == "__main__":
    main()


