from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, Tuple

from PIL import Image, ExifTags


@dataclass
class QualityThresholds:
    min_width: int = 1000
    min_height: int = 600
    min_laplacian_variance: float = 30.0
    max_file_size_bytes: int = 6 * 1024 * 1024
    max_video_size_bytes: int = 40 * 1024 * 1024
    max_video_duration_seconds: float = 12.0


def _ensure_rgb(img: Image.Image) -> Image.Image:
    if img.mode != "RGB":
        return img.convert("RGB")
    return img


def _auto_orient(img: Image.Image) -> Image.Image:
    # Prefer EXIF orientation if present; fallback heuristic otherwise
    try:
        exif = getattr(img, "_getexif", lambda: None)()
        if exif:
            # Find orientation tag ID
            orientation_tag = None
            for k, v in ExifTags.TAGS.items():
                if v == "Orientation":
                    orientation_tag = k
                    break
            if orientation_tag and orientation_tag in exif:
                o = exif.get(orientation_tag, 1)
                if o == 3:
                    return img.rotate(180, expand=True)
                if o == 6:
                    return img.rotate(270, expand=True)
                if o == 8:
                    return img.rotate(90, expand=True)
    except Exception:
        pass
    # Heuristic fallback for ID cards typically landscape
    w, h = img.size
    if h > w * 1.2:
        return img.rotate(90, expand=True)
    return img


def analyze_quality(image_path: Path, thresholds: QualityThresholds = QualityThresholds()) -> Dict[str, Any]:
    path = Path(image_path)
    stat = path.stat()
    img = _ensure_rgb(Image.open(path))
    img = _auto_orient(img)
    w, h = img.size
    lap_var = float(_laplacian_variance_pure_pil(img))

    # Normalized quality score [0,1] derived from Laplacian variance
    q01 = _normalize_score(lap_var, low=thresholds.min_laplacian_variance * 0.5, high=thresholds.min_laplacian_variance * 10.0)

    result: Dict[str, Any] = {
        "path": str(path),
        "width": w,
        "height": h,
        "size_bytes": stat.st_size,
        "laplacian_variance": round(lap_var, 4),
        "quality_score_01": round(q01, 4),
        "meets_resolution": (w >= thresholds.min_width and h >= thresholds.min_height),
        "meets_file_size": (stat.st_size <= thresholds.max_file_size_bytes),
        "meets_sharpness": (lap_var >= thresholds.min_laplacian_variance),
    }
    result["quality_ok"] = bool(
        result["meets_resolution"] and result["meets_file_size"] and result["meets_sharpness"]
    )
    return result


def validate_mime_and_ext(path: Path, allowed_exts: Tuple[str, ...] = (".jpg", ".jpeg", ".png")) -> bool:
    # Use extension allowlist and light content sniff via imghdr for images
    try:
        import imghdr
        kind = imghdr.what(path)
        if kind not in {"jpeg", "png"}:
            return False
    except Exception:
        pass
    return path.suffix.lower() in allowed_exts


def validate_input(
    front_image: Path,
    back_image: Path | None = None,
    selfie_video_path: Path | None = None,
    thresholds: QualityThresholds = QualityThresholds(),
) -> Dict[str, Any]:
    """Validate Phase 1 inputs per IC1/IC2 acceptance.

    - Front/back images must be valid, correct size, and meet sharpness threshold.
    - File sizes must be within limits.
    - Extensions must be from an allowlist.
    - Orientation is auto-corrected heuristically for analysis purposes.
    """
    front_path = Path(front_image)
    if not front_path.exists():
        raise FileNotFoundError(front_path)
    if not validate_mime_and_ext(front_path):
        raise ValueError(f"Disallowed file type: {front_path.suffix}")
    front_report = analyze_quality(front_path, thresholds)

    back_report = None
    if back_image is not None:
        back_path = Path(back_image)
        if not back_path.exists():
            raise FileNotFoundError(back_path)
        if not validate_mime_and_ext(back_path):
            raise ValueError(f"Disallowed file type: {back_path.suffix}")
        back_report = analyze_quality(back_path, thresholds)

    video_report = None
    if selfie_video_path is not None:
        # Enforce size limit and attempt duration detection via ffprobe if available.
        vp = Path(selfie_video_path)
        if not vp.exists():
            raise FileNotFoundError(vp)
        duration_s, duration_checked = _probe_video_duration_seconds(vp)
        video_report = {
            "path": str(vp),
            "size_bytes": vp.stat().st_size,
            "within_size_limit": vp.stat().st_size <= thresholds.max_video_size_bytes,
            "duration_seconds": duration_s,
            "duration_checked": duration_checked,
            "within_duration_limit": (duration_s is not None and duration_s <= thresholds.max_video_duration_seconds) if duration_checked else None,
        }

    return {
        "front": front_report,
        "back": back_report,
        "selfie_video": video_report,
    }


def _to_gray_2d(img: Image.Image) -> Tuple[int, int, list[list[float]]]:
    g = img.convert("L")
    w, h = g.size
    px = g.load()
    # Build a 2D list of luminance values
    arr: list[list[float]] = []
    for y in range(h):
        row = [float(px[x, y]) for x in range(w)]
        arr.append(row)
    return w, h, arr


def _laplacian_variance_pure_pil(img: Image.Image) -> float:
    # 4-neighbor Laplacian kernel: [[0,1,0],[1,-4,1],[0,1,0]]
    w, h, arr = _to_gray_2d(img)
    if w < 3 or h < 3:
        return 0.0
    sum_l = 0.0
    sum_l2 = 0.0
    n = 0
    for y in range(1, h - 1):
        row_up = arr[y - 1]
        row = arr[y]
        row_dn = arr[y + 1]
        for x in range(1, w - 1):
            center = row[x]
            lap = (row[x - 1] + row[x + 1] + row_up[x] + row_dn[x]) - 4.0 * center
            sum_l += lap
            sum_l2 += lap * lap
            n += 1
    if n == 0:
        return 0.0
    mean = sum_l / n
    var = (sum_l2 / n) - (mean * mean)
    return var if var > 0 else 0.0


def _normalize_score(value: float, low: float, high: float) -> float:
    if high <= low:
        return 0.0
    x = (value - low) / (high - low)
    if x < 0.0:
        return 0.0
    if x > 1.0:
        return 1.0
    return x


def _probe_video_duration_seconds(path: Path) -> Tuple[float | None, bool]:
    """Return (duration_seconds, checked) using ffprobe if available."""
    import shutil
    import subprocess

    if not shutil.which("ffprobe"):
        return None, False
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode != 0:
            return None, False
        out = res.stdout.strip()
        if not out:
            return None, False
        return float(out), True
    except Exception:
        return None, False


