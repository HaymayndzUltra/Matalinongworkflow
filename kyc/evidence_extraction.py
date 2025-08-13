from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

from PIL import Image


# ------------------------------
# Document Classifier (heuristic)
# ------------------------------

@dataclass
class DocClassifierResult:
    label: str
    confidence: float
    extra: Dict[str, Any]


class HeuristicDocClassifier:
    """Simple shape-based classifier to separate ID card vs passport vs other.

    - Landscape with ratio in ~[1.3..2.0] → id_card
    - Portrait with ratio (h/w) in ~[1.2..2.0] → passport_page
    - Otherwise → other
    """

    def predict(self, image_path: Path) -> DocClassifierResult:
        img = Image.open(image_path)
        w, h = img.size
        ratio = w / max(1, h)
        label = "other"
        conf = 0.7
        if ratio >= 1.3 and ratio <= 2.0:
            label = "id_card"
            conf = 0.95
        elif (h / max(1, w)) >= 1.2 and (h / max(1, w)) <= 2.0:
            label = "passport_page"
            conf = 0.92
        return DocClassifierResult(label=label, confidence=conf, extra={"width": w, "height": h, "ratio": ratio})


# ------------------------------
# MRZ Parser & Validator (ICAO 9303)
# ------------------------------

MRZ_WEIGHTS = [7, 3, 1]


def _char_value(c: str) -> int:
    if c.isdigit():
        return ord(c) - ord('0')
    if 'A' <= c <= 'Z':
        return ord(c) - ord('A') + 10
    if c == '<':
        return 0
    # For safety, treat others as 0
    return 0


def _mrz_checksum(data: str) -> int:
    total = 0
    for i, ch in enumerate(data):
        total += _char_value(ch) * MRZ_WEIGHTS[i % 3]
    return total % 10


def validate_mrz_td3(line1: str, line2: str) -> Dict[str, Any]:
    """Validate TD3 (passport) MRZ (2 lines, 44 chars each)."""
    ok = True
    issues: List[str] = []
    if len(line1) != 44 or len(line2) != 44:
        ok = False
        issues.append("TD3 must be 2x44 chars")
        return {"ok": ok, "issues": issues}

    # Extract fields per ICAO 9303 (simplified):
    # line2: passport number (9 chars) + check(1) at positions 0..9
    passport_number = line2[0:9]
    pn_check = line2[9]
    birth_date = line2[13:19]
    birth_check = line2[19]
    expiry_date = line2[21:27]
    expiry_check = line2[27]
    personal_number = line2[28:42]
    personal_check = line2[42]
    final_check = line2[43]

    # Validate checksums
    if str(_mrz_checksum(passport_number)) != pn_check:
        ok = False
        issues.append("passport_number checksum fail")
    if str(_mrz_checksum(birth_date)) != birth_check:
        ok = False
        issues.append("birth_date checksum fail")
    if str(_mrz_checksum(expiry_date)) != expiry_check:
        ok = False
        issues.append("expiry_date checksum fail")
    if str(_mrz_checksum(personal_number)) != personal_check:
        ok = False
        issues.append("personal_number checksum fail")

    # Composite final checksum uses concatenation of several fields
    composite = passport_number + pn_check + line2[10:13] + birth_date + birth_check + line2[20] + expiry_date + expiry_check + personal_number + personal_check
    if str(_mrz_checksum(composite)) != final_check:
        ok = False
        issues.append("final checksum fail")

    return {
        "ok": ok,
        "issues": issues,
        "fields": {
            "passport_number": passport_number,
            "birth_date": birth_date,
            "expiry_date": expiry_date,
            "personal_number": personal_number,
        },
    }


# ------------------------------
# Barcode Parser (text-based stub)
# ------------------------------

def parse_barcode_text(text: str) -> Dict[str, Any]:
    """Parse a simple key-value payload from a PDF417/QR text dump.

    Expected formats (examples):
    - "PDF417:ID=123;NAME=JOHN DOE"
    - "QR:K=V|K2=V2"
    """
    result: Dict[str, Any] = {"raw": text}
    try:
        if ":" in text:
            prefix, payload = text.split(":", 1)
        else:
            prefix, payload = "raw", text
        items = []
        if ";" in payload:
            items = payload.split(";")
        elif "|" in payload:
            items = payload.split("|")
        else:
            items = [payload]
        kv: Dict[str, str] = {}
        for it in items:
            if "=" in it:
                k, v = it.split("=", 1)
                kv[k.strip()] = v.strip()
        result.update({"type": prefix.strip().upper(), "data": kv})
    except Exception as e:
        result["error"] = str(e)
    return result


# ------------------------------
# Face Crop (center-based stub)
# ------------------------------

@dataclass
class DetectedFace:
    x: int
    y: int
    w: int
    h: int


def detect_face_and_crop(image_path: Path, min_size: int = 112, out_crop_path: Optional[Path] = None) -> DetectedFace:
    img = Image.open(image_path).convert("RGB")
    w, h = img.size
    # Center square crop occupying 50% of the min dimension
    side = max(min_size, int(min(w, h) * 0.5))
    cx, cy = w // 2, h // 2
    x0 = max(0, cx - side // 2)
    y0 = max(0, cy - side // 2)
    x1 = min(w, x0 + side)
    y1 = min(h, y0 + side)
    crop = img.crop((x0, y0, x1, y1))
    if out_crop_path is not None:
        out_crop_path.parent.mkdir(parents=True, exist_ok=True)
        crop.save(out_crop_path)
    return DetectedFace(x=x0, y=y0, w=(x1 - x0), h=(y1 - y0))


