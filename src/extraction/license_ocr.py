"""
License card OCR + pattern check
Usage:
  python3 license_ocr.py /abs/path/to/image.jpg

Outputs to ./outputs/license_verification_report.json
Requires: pillow, numpy, pytesseract, and a system tesseract binary (e.g., `sudo apt install tesseract-ocr`).
"""

from pathlib import Path
import sys, json
import numpy as np
from PIL import Image
import pytesseract


def to_gray_array(img: Image.Image) -> np.ndarray:
    return np.asarray(img.convert("L"), dtype=np.uint8)


def otsu_threshold(gray: np.ndarray) -> np.ndarray:
    # Simple Otsu implementation (no OpenCV dependency)
    hist, _ = np.histogram(gray.flatten(), 256, [0, 256])
    total = gray.size
    sum_total = np.dot(np.arange(256), hist)
    sumB = 0.0
    wB = 0.0
    var_max = 0.0
    threshold = 0
    for t in range(256):
        wB += hist[t]
        if wB == 0:
            continue
        wF = total - wB
        if wF == 0:
            break
        sumB += t * hist[t]
        mB = sumB / wB
        mF = (sum_total - sumB) / wF
        var_between = wB * wF * (mB - mF) ** 2
        if var_between > var_max:
            var_max = var_between
            threshold = t
    return (gray > threshold).astype(np.uint8) * 255


def high_freq_score(region: np.ndarray) -> float:
    # FFT-based high frequency energy (simple heuristic)
    f = np.fft.fft2(region.astype(np.float32))
    fshift = np.fft.fftshift(f)
    mag = np.abs(fshift)
    h, w = region.shape
    cy, cx = h // 2, w // 2
    r = max(8, min(h, w) // 20)
    mask = np.ones((h, w), dtype=bool)
    mask[cy - r : cy + r, cx - r : cx + r] = False  # ignore low freq center
    return float(mag[mask].mean())


def roi_rects(w: int, h: int):
    return {
        "header": (int(w * 0.05), int(h * 0.15), int(w * 0.90), int(h * 0.13)),
        "background": (int(w * 0.05), int(h * 0.35), int(w * 0.90), int(h * 0.40)),
    }


def run(image_path: Path) -> dict:
    out_dir = Path.cwd() / "outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    img = Image.open(image_path).convert("RGB")
    gray = to_gray_array(img)
    bw = otsu_threshold(gray)

    # OCR on binarized image
    ocr_text = pytesseract.image_to_string(Image.fromarray(bw), lang="eng")

    # Keyword checklist (PH DL front template example)
    expected_keywords = [
        "REPUBLIC OF THE PHILIPPINES",
        "DEPARTMENT OF TRANSPORTATION",
        "LAND TRANSPORTATION OFFICE",
        "DRIVER'S LICENSE",
        "Last Name",
        "First Name",
        "Nationality",
        "Sex",
        "Date of Birth",
        "Weight",
        "Height",
        "Address",
        "License No",
        "Expiration Date",
        "Blood Type",
        "Eyes Color",
        "DL Codes",
        "Conditions",
    ]
    missing_keywords = [kw for kw in expected_keywords if kw.lower() not in ocr_text.lower()]

    # Pattern/microprint check
    h, w = gray.shape
    rois = roi_rects(w, h)
    header = bw[rois["header"][1] : rois["header"][1] + rois["header"][3], rois["header"][0] : rois["header"][0] + rois["header"][2]]
    background = bw[rois["background"][1] : rois["background"][1] + rois["background"][3], rois["background"][0] : rois["background"][0] + rois["background"][2]]

    header_hf = high_freq_score(header)
    bg_hf = high_freq_score(background)
    pattern_detected = (header_hf > 50.0) and (bg_hf > 40.0)

    report = {
        "input_path": str(image_path),
        "ocr_text": ocr_text.strip(),
        "missing_keywords": missing_keywords,
        "pattern_detection": {
            "header_high_freq_score": round(header_hf, 2),
            "background_high_freq_score": round(bg_hf, 2),
            "microprint_expected_present": bool(pattern_detected),
        },
    }

    report_path = out_dir / "license_verification_report.json"
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("OCR length:", len(report["ocr_text"]))
    print("Missing keywords:", len(missing_keywords))
    print("Header HF:", report["pattern_detection"]["header_high_freq_score"], " Background HF:", report["pattern_detection"]["background_high_freq_score"]) 
    print("Report:", str(report_path))
    return report


def main(argv):
    if len(argv) != 2:
        print("usage: python3 license_ocr.py /abs/path/to/image.jpg", file=sys.stderr)
        return 2
    p = Path(argv[1])
    if not p.exists():
        print(f"❌ not found: {p}", file=sys.stderr)
        return 2
    run(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))