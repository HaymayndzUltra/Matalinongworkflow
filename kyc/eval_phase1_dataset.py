from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import List, Dict, Any

from kyc.capture_validation import validate_input, QualityThresholds


def find_images(root: Path, allowed_exts: List[str]) -> List[Path]:
    files: List[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in allowed_exts:
            files.append(p)
    return files


def evaluate_dataset(dir_path: Path, exts: List[str], max_items: int | None) -> Dict[str, Any]:
    thresholds = QualityThresholds()
    images = find_images(dir_path, exts)
    if max_items is not None:
        images = images[:max_items]
    results: List[Dict[str, Any]] = []
    passed = 0
    for img in images:
        try:
            rep = validate_input(img, None, None, thresholds)
            front = rep.get("front", {})
            is_pass = bool(front.get("meets_resolution") and front.get("meets_file_size") and front.get("meets_sharpness"))
            results.append({
                "path": str(img),
                "width": front.get("width"),
                "height": front.get("height"),
                "quality_score_01": front.get("quality_score_01"),
                "meets_resolution": front.get("meets_resolution"),
                "meets_file_size": front.get("meets_file_size"),
                "meets_sharpness": front.get("meets_sharpness"),
                "passed": is_pass,
            })
            if is_pass:
                passed += 1
        except Exception as e:
            results.append({"path": str(img), "error": str(e), "passed": False})

    total = len(results)
    pass_rate = (passed / total) if total > 0 else 0.0
    summary: Dict[str, Any] = {
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "pass_rate": round(pass_rate, 4),
        "acceptance_target": 0.95,
        "acceptance_met": pass_rate >= 0.95,
        "thresholds": {
            "min_width": thresholds.min_width,
            "min_height": thresholds.min_height,
            "min_laplacian_variance": thresholds.min_laplacian_variance,
            "max_file_size_bytes": thresholds.max_file_size_bytes,
        },
        "items": results,
    }
    return summary


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate Phase 1 pass-rate over a directory of images")
    parser.add_argument("dir", type=str, help="Directory containing images")
    parser.add_argument("--ext", type=str, default=".jpg,.jpeg,.png", help="Comma-separated allowed extensions")
    parser.add_argument("--max", type=int, default=None, help="Max items to process")
    parser.add_argument("--json-out", type=str, default=None, help="Optional path to write JSON summary")
    args = parser.parse_args(argv)

    dir_path = Path(args.dir)
    if not dir_path.exists() or not dir_path.is_dir():
        print(json.dumps({"error": f"Directory not found: {dir_path}"}, indent=2))
        return 2
    exts = [e.strip().lower() for e in args.ext.split(",") if e.strip()]
    summary = evaluate_dataset(dir_path, exts, args.max)
    js = json.dumps(summary, indent=2)
    print(js)
    if args.json_out:
        outp = Path(args.json_out)
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(js, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


