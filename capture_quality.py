#!/usr/bin/env python3
"""
Capture quality assessment (Phase 1)
- Glare/blur/orientation checks
- pass@Npx metric on long side (default 1000px)
- Per-frame quality score in [0, 1]
- Coaching hints (config-driven)

Config (JSON): configs/capture_quality.json
{
  "weights": { "blur": 0.4, "glare": 0.3, "orientation": 0.1, "resolution": 0.2 },
  "blur": { "target_variance": 400.0, "pass_threshold": 200.0 },
  "glare": { "white_threshold": 240, "max_fraction": 0.02 },
  "resolution": { "min_long_side": 1000 },
  "coaching": { "max_hints": 3 }
}

No magic numbers: all thresholds are in config.
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple

import numpy as np
from PIL import Image, ImageOps


SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}
DEFAULT_CONFIG_PATH = os.environ.get(
    "CAPTURE_QUALITY_CONFIG", "configs/capture_quality.json"
)


@dataclass
class Weights:
    blur: float
    glare: float
    orientation: float
    resolution: float


@dataclass
class BlurCfg:
    target_variance: float
    pass_threshold: float


@dataclass
class GlareCfg:
    white_threshold: int
    max_fraction: float


@dataclass
class ResCfg:
    min_long_side: int


@dataclass
class CoachingCfg:
    max_hints: int


@dataclass
class Config:
    weights: Weights
    blur: BlurCfg
    glare: GlareCfg
    resolution: ResCfg
    coaching: CoachingCfg

    @staticmethod
    def from_dict(d: Dict) -> "Config":
        return Config(
            weights=Weights(**d["weights"]),
            blur=BlurCfg(**d["blur"]),
            glare=GlareCfg(**d["glare"]),
            resolution=ResCfg(**d["resolution"]),
            coaching=CoachingCfg(**d["coaching"]),
        )


# ------------------------- Image utilities -------------------------

def load_image(path: str) -> Image.Image:
    """Open image and auto-correct orientation using EXIF if present."""
    img = Image.open(path)
    try:
        img = ImageOps.exif_transpose(img)
        corrected = True
    except Exception:
        corrected = False
    # Add a flag on the object for downstream use
    img._orientation_corrected = corrected  # type: ignore[attr-defined]
    return img


def to_gray_np(img: Image.Image) -> np.ndarray:
    g = img.convert("L")
    arr = np.asarray(g, dtype=np.float32)
    return arr


def conv2d(img: np.ndarray, kernel: np.ndarray) -> np.ndarray:
    """Naive 2D convolution with reflect padding (no additional deps)."""
    kh, kw = kernel.shape
    py, px = kh // 2, kw // 2
    padded = np.pad(img, ((py, py), (px, px)), mode="reflect")
    out = np.zeros_like(img, dtype=np.float32)
    for y in range(kh):
        for x in range(kw):
            out += kernel[y, x] * padded[y : y + img.shape[0], x : x + img.shape[1]]
    return out


def laplacian_variance(gray: np.ndarray) -> float:
    """Variance of Laplacian as blur indicator."""
    kernel = np.array([[0.0, 1.0, 0.0], [1.0, -4.0, 1.0], [0.0, 1.0, 0.0]], dtype=np.float32)
    lap = conv2d(gray, kernel)
    return float(lap.var())


# ------------------------- Metrics & Scoring -------------------------

def compute_metrics(img: Image.Image, cfg: Config) -> Dict:
    w, h = img.size
    long_side = max(w, h)

    gray = to_gray_np(img)

    # Blur metric (higher variance -> sharper)
    blur_var = laplacian_variance(gray)
    blur_score = min(blur_var / max(cfg.blur.target_variance, 1e-6), 1.0)

    # Glare metric (fraction of near-white pixels)
    glare_frac = float((gray >= float(cfg.glare.white_threshold)).mean())
    glare_score = max(0.0, 1.0 - min(glare_frac / max(cfg.glare.max_fraction, 1e-9), 1.0))

    # Orientation (we only know EXIF correction status)
    orientation_ok = bool(getattr(img, "_orientation_corrected", False))
    # If we corrected, assume good (1.0). If no EXIF, we set a conservative 0.5.
    orientation_score = 1.0 if orientation_ok else 0.5

    # Resolution
    res_score = min(long_side / float(cfg.resolution.min_long_side), 1.0)
    pass_at_n = long_side >= cfg.resolution.min_long_side

    # Weighted quality score
    wts = cfg.weights
    quality = (
        wts.blur * blur_score
        + wts.glare * glare_score
        + wts.orientation * orientation_score
        + wts.resolution * res_score
    )
    # Clamp [0, 1]
    quality = float(max(0.0, min(1.0, quality)))

    metrics = {
        "width": w,
        "height": h,
        "long_side_px": long_side,
        "blur_variance": blur_var,
        "glare_fraction": glare_frac,
        "pass_at_px": cfg.resolution.min_long_side,
        "pass_at_px_ok": pass_at_n,
        "orientation_corrected": orientation_ok,
        "scores": {
            "blur": blur_score,
            "glare": glare_score,
            "orientation": orientation_score,
            "resolution": res_score,
        },
        "quality_score": quality,
    }
    return metrics


def coaching_hints(metrics: Dict, cfg: Config) -> List[str]:
    hints: List[str] = []

    if metrics["scores"]["blur"] < max(cfg.blur.pass_threshold / max(cfg.blur.target_variance, 1e-6), 0.0):
        hints.append("Hold steady and ensure the ID is in focus. Increase lighting if possible.")

    if metrics["glare_fraction"] > cfg.glare.max_fraction:
        hints.append(
            "Reduce glare: avoid direct light on the ID. Tilt slightly or move to softer lighting."
        )

    if not metrics["pass_at_px_ok"]:
        hints.append(
            f"Move closer or capture at higher resolution (long side ≥ {cfg.resolution.min_long_side}px)."
        )

    if not metrics.get("orientation_corrected", False):
        hints.append("Keep the ID upright; if auto-rotation is off, rotate device to portrait/landscape as needed.")

    return hints[: max(cfg.coaching.max_hints, 0)]


# ------------------------- CLI / Runner -------------------------

def load_config(path: str) -> Config:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return Config.from_dict(data)


def list_images(input_path: str) -> List[str]:
    p = os.path.abspath(input_path)
    if os.path.isdir(p):
        files = [
            os.path.join(p, fn)
            for fn in sorted(os.listdir(p))
            if os.path.splitext(fn.lower())[1] in SUPPORTED_EXTS
        ]
        return files
    else:
        ext = os.path.splitext(p.lower())[1]
        if ext in SUPPORTED_EXTS and os.path.exists(p):
            return [p]
        raise FileNotFoundError(f"No supported image(s) at {input_path}")


def now_iso_utc8() -> str:
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz=tz).isoformat()


def run(input_path: str, cfg_path: str, out_path: str | None) -> Dict:
    cfg = load_config(cfg_path)
    files = list_images(input_path)

    frames: List[Dict] = []
    for fp in files:
        img = load_image(fp)
        m = compute_metrics(img, cfg)
        m["file"] = os.path.relpath(fp)
        m["coaching_hints"] = coaching_hints(m, cfg)
        frames.append(m)

    # Pick best frame by quality_score
    best_idx = max(range(len(frames)), key=lambda i: frames[i]["quality_score"]) if frames else -1
    summary = {
        "frames": frames,
        "best_frame_index": best_idx,
        "best_quality_score": (frames[best_idx]["quality_score"] if best_idx >= 0 else None),
        "generated_at": now_iso_utc8(),
        "config_path": os.path.relpath(cfg_path),
        "min_long_side_px": cfg.resolution.min_long_side,
        "weights": {
            "blur": cfg.weights.blur,
            "glare": cfg.weights.glare,
            "orientation": cfg.weights.orientation,
            "resolution": cfg.weights.resolution,
        },
    }

    if out_path:
        os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, ensure_ascii=False, indent=2)
    return summary


def main():
    parser = argparse.ArgumentParser(description="Capture quality assessment")
    parser.add_argument(
        "--input",
        required=True,
        help="Path to image file or directory of images",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG_PATH,
        help="Path to JSON config (default: env CAPTURE_QUALITY_CONFIG or configs/capture_quality.json)",
    )
    parser.add_argument(
        "--out",
        default=None,
        help="Optional path to write JSON output",
    )
    args = parser.parse_args()

    result = run(args.input, args.config, args.out)
    # Print to stdout (PII-safe; only relative file paths)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
