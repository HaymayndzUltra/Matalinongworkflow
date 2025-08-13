# Image forensics helper: ELA, metadata, residual map, and sharpness stats across ROIs.
# Usage: python3 image.py /abs/path/to/image
# Outputs saved under ./outputs

from pathlib import Path
import sys, io, json
import numpy as np
from PIL import Image, ImageChops, ImageFilter, ImageEnhance, ImageDraw, ExifTags


def error_level_analysis(pil_img: Image.Image, quality: int = 90):
    buf = io.BytesIO()
    pil_img.save(buf, "JPEG", quality=quality)
    buf.seek(0)
    jpg = Image.open(buf).convert("RGB")
    ela = ImageChops.difference(pil_img, jpg)
    extrema = ela.getextrema()  # per-channel (min,max)
    if isinstance(extrema[0], tuple):
        max_diff = max(ex[1] for ex in extrema)
    else:
        max_diff = extrema[1]
    scale = 255.0 / max(1, max_diff)
    ela = ImageEnhance.Brightness(ela).enhance(scale)
    return jpg, ela, int(max_diff), float(scale)


def to_gray_array(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("L"), dtype=np.float32)


def laplacian_variance_via_grad(gray_arr: np.ndarray) -> float:
    # Approximate Laplacian variance using numpy gradients (no OpenCV dependency)
    gy, gx = np.gradient(gray_arr)
    gxx, _ = np.gradient(gx)
    _, gyy = np.gradient(gy)
    lap = gxx + gyy
    return float(lap.var())


def roi_rects(w: int, h: int):
    return {
        "roi_left_mid": (int(w * 0.16), int(h * 0.43), int(w * 0.18), int(h * 0.22)),
        "roi_upper_center": (int(w * 0.45), int(h * 0.23), int(w * 0.35), int(h * 0.12)),
        "roi_right_mid": (int(w * 0.62), int(h * 0.50), int(w * 0.28), int(h * 0.18)),
        "roi_background": (int(w * 0.09), int(h * 0.83), int(w * 0.20), int(h * 0.12)),
    }


def analyze_image(image_path: Path) -> dict:
    out_dir = Path.cwd() / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    basic_info = {"path": str(image_path), "format": "RGB", "width": w, "height": h}

    # Metadata (best-effort)
    meta = {}
    try:
        exif = getattr(img, "_getexif", lambda: None)()
        if exif:
            for tag, value in exif.items():
                key = ExifTags.TAGS.get(tag, str(tag))
                meta[key] = str(value)
        for k, v in img.info.items():
            meta[str(k)] = str(v)
    except Exception as e:
        meta = {"error": str(e)}

    # ELA
    _, ela_img, ela_max_diff, ela_scale = error_level_analysis(img, quality=92)
    ela_path = out_dir / "ela.png"
    ela_img.save(ela_path)

    # Residual (unsharp)
    blurred = img.filter(ImageFilter.GaussianBlur(radius=1.2))
    residual = ImageChops.subtract(img, blurred)
    residual_gray = residual.convert("L")
    residual_path = out_dir / "residual.png"
    residual_gray.save(residual_path)

    # Sharpness stats over ROIs
    gray_arr = to_gray_array(img)
    rois = roi_rects(w, h)
    sharp_stats = {}
    for name, (x, y, w0, h0) in rois.items():
        x2, y2 = min(w, x + w0), min(h, y + h0)
        crop = gray_arr[y:y2, x:x2]
        sharp_stats[name] = {
            "laplacian_variance": round(laplacian_variance_via_grad(crop), 4),
            "mean": round(float(np.mean(crop)), 4),
            "std": round(float(np.std(crop)), 4),
            "shape": [int(crop.shape[0]), int(crop.shape[1])],
        }

    # Annotated ROI overlay
    annot = img.copy()
    drw = ImageDraw.Draw(annot)
    for name, (x, y, w0, h0) in rois.items():
        drw.rectangle([x, y, x + w0, y + h0], outline=(255, 255, 255), width=2)
        drw.text((x, max(0, y - 12)), name, fill=(255, 255, 255))
    annot_path = out_dir / "annotated_rois.jpg"
    annot.save(annot_path)

    report = {
        "basic_info": basic_info,
        "metadata_info": meta,
        "ela": {"max_diff": ela_max_diff, "scale_used": ela_scale, "image_path": str(ela_path)},
        "residual_image": str(residual_path),
        "sharpness_stats": sharp_stats,
        "artifacts": {"annotated_rois": str(annot_path), "ela_image": str(ela_path), "residual_image": str(residual_path)},
    }
    report_path = out_dir / "forensic_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("BASIC INFO:", basic_info)
    print("\nEla: max diff:", ela_max_diff, " scale:", round(ela_scale, 3))
    print("\nSharpness stats per ROI:")
    for k, v in sharp_stats.items():
        print(" ", k, "=> LapVar:", v["laplacian_variance"], " mean:", v["mean"], " std:", v["std"])
    print("\nArtifacts written:")
    for k, v in report["artifacts"].items():
        print(" ", k, "->", v)
    print("\nForensic JSON report:", str(report_path))

    return report


def main(argv) -> int:
    if len(argv) != 2:
        print("usage: python3 image.py /abs/path/to/image", file=sys.stderr)
        return 2
    img_path = Path(argv[1])
    if not img_path.exists():
        print(f"❌ not found: {img_path}", file=sys.stderr)
        return 2
    analyze_image(img_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
