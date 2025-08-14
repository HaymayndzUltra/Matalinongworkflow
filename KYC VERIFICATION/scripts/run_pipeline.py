#!/usr/bin/env python3
"""
End-to-End Pipeline Runner (Phase 18)

Runs a minimal end-to-end flow over images in a directory:
  1) Validate (quality + authenticity)
  2) Extract (OCR/MRZ/barcode)
  3) Score (risk)
  4) Decide

This uses local modules directly (no HTTP) for fast smoke testing.

Usage:
  python3 scripts/run_pipeline.py --input datasets/synthetic/legit --limit 5
"""

import argparse
import time
from pathlib import Path
from typing import List

import cv2

from src.capture.quality_analyzer import CaptureQualityAnalyzer
from src.classification.document_classifier import DocumentClassifier
from src.forensics.authenticity_verifier import AuthenticityVerifier
from src.extraction.evidence_extractor import EvidenceExtractor
from src.risk.risk_engine import RiskEngine


def list_images(root: Path) -> List[Path]:
    exts = {".jpg", ".jpeg", ".png", ".bmp"}
    return [p for p in root.rglob("*") if p.suffix.lower() in exts]


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description="Run local pipeline over a directory of images")
    ap.add_argument("--input", required=True, help="Input directory of images")
    ap.add_argument("--limit", type=int, default=10, help="Max images to process")
    return ap.parse_args()


def main() -> None:
    args = parse_args()
    image_paths = list_images(Path(args.input).resolve())[: args.limit]
    if not image_paths:
        print("No images found.")
        return

    quality = CaptureQualityAnalyzer()
    classifier = DocumentClassifier()
    forensics = AuthenticityVerifier()
    extractor = EvidenceExtractor()
    risk_engine = RiskEngine()

    t0 = time.time()
    approved, review, deny = 0, 0, 0

    for img_path in image_paths:
        img = cv2.imread(str(img_path))
        if img is None:
            continue

        q_metrics, _ = quality.analyze_frame(img)
        cls = classifier.classify(img)
        f_result = forensics.verify_authenticity(img, document_type=cls.document_type.value)
        ex = extractor.extract_all(img, document_type=cls.document_type.value)

        verification_data = {
            "quality": {
                "blur_score": q_metrics.blur_score,
                "glare_score": q_metrics.glare_score,
                "resolution_adequate": q_metrics.resolution[0] * q_metrics.resolution[1] >= 112 * 112,
            },
            "classification": {"confidence": cls.confidence},
            "extraction": {
                "ocr_confidence": ex.ocr_text.get("avg_confidence", 0.0),
                "expected_fields": ["name", "date", "document_number"],
                "extracted_fields": [f.field_name for f in ex.extracted_fields],
                "mrz_valid": bool(ex.mrz_data and ex.mrz_data.confidence >= 0.8),
            },
            "forensics": {
                "is_authentic": f_result.is_authentic,
                "manipulation_score": 1.0 - f_result.authenticity_score,
            },
        }

        risk_score, decision = risk_engine.calculate_risk(verification_data)

        if decision.decision_type.value == "approve":
            approved += 1
        elif decision.decision_type.value == "review":
            review += 1
        else:
            deny += 1

        print(f"Processed: {img_path.name} -> decision={decision.decision_type.value} score={risk_score.overall_score:.3f}")

    dt = time.time() - t0
    print(f"\n✅ Pipeline complete for {len(image_paths)} images in {dt:.2f}s")
    print(f"   approve={approved} review={review} deny={deny}")


if __name__ == "__main__":
    main()


