from __future__ import annotations

import json
from pathlib import Path
import sys

from kyc.evidence_extraction import (
    HeuristicDocClassifier,
    validate_mrz_td3,
    parse_barcode_text,
    detect_face_and_crop,
)


def main(argv):
    if len(argv) < 2:
        print("usage: python3 -m kyc.demo_phase2_extract <image_path> [--mrz line1 line2] [--barcode TEXT]", file=sys.stderr)
        return 2
    img = Path(argv[1])
    classifier = HeuristicDocClassifier()
    cls = classifier.predict(img)

    # Optional MRZ and barcode inputs from CLI
    args = argv[2:]
    mrz_res = None
    barcode_res = None
    if len(args) >= 3 and args[0] == "--mrz":
        mrz_res = validate_mrz_td3(args[1], args[2])
        args = args[3:]
    if len(args) >= 2 and args[0] == "--barcode":
        barcode_res = parse_barcode_text(args[1])

    face = detect_face_and_crop(img, min_size=112, out_crop_path=img.parent / (img.stem + "_face.jpg"))

    out = {
        "classifier": {"label": cls.label, "confidence": cls.confidence, "extra": cls.extra},
        "mrz_validation": mrz_res,
        "barcode_parsed": barcode_res,
        "face_crop": {"x": face.x, "y": face.y, "w": face.w, "h": face.h},
    }
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))


