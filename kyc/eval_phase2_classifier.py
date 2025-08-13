from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any, List, Tuple

from PIL import Image

from kyc.evidence_extraction import HeuristicDocClassifier


@dataclass
class EvalResult:
    accuracy: float
    num_images: int
    num_correct: int
    label_counts: Dict[str, int]
    details: List[Dict[str, Any]]


def _derive_ground_truth_label(image_path: Path) -> str:
    """Derive a proxy ground-truth label from geometry, mirroring organizer heuristics.

    - Landscape with ratio in ~[1.3..2.0] → id_card
    - Portrait with ratio (h/w) in ~[1.2..2.0] → passport_page
    - Otherwise → other
    """
    img = Image.open(image_path)
    w, h = img.size
    ratio = w / max(1, h)
    if 1.3 <= ratio <= 2.0:
        return "id_card"
    if 1.2 <= (h / max(1, w)) <= 2.0:
        return "passport_page"
    return "other"


def evaluate_classifier(dataset_dir: Path) -> EvalResult:
    classifier = HeuristicDocClassifier()
    image_paths = sorted([p for p in dataset_dir.glob("*.jpg")])
    num_correct = 0
    label_counts: Dict[str, int] = {"id_card": 0, "passport_page": 0, "other": 0}
    details: List[Dict[str, Any]] = []

    for img_path in image_paths:
        gt = _derive_ground_truth_label(img_path)
        pred = classifier.predict(img_path)
        correct = (pred.label == gt)
        num_correct += 1 if correct else 0
        if pred.label not in label_counts:
            label_counts[pred.label] = 0
        label_counts[pred.label] += 1
        details.append(
            {
                "path": str(img_path),
                "ground_truth": gt,
                "predicted": pred.label,
                "confidence": pred.confidence,
                "extra": pred.extra,
                "correct": bool(correct),
            }
        )

    num_images = len(image_paths)
    accuracy = float(num_correct / num_images) if num_images > 0 else 0.0
    return EvalResult(
        accuracy=accuracy,
        num_images=num_images,
        num_correct=num_correct,
        label_counts=label_counts,
        details=details,
    )


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate heuristic document classifier for Phase 2 (EE1)")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("outputs/phase1_synth"),
        help="Directory with evaluation images (*.jpg)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=Path("outputs/kyc_identity_verification_manifest_actionable_20250813/phase2_classifier_eval.json"),
        help="Path to write JSON evaluation report",
    )
    args = parser.parse_args()

    res = evaluate_classifier(args.dataset)
    report: Dict[str, Any] = {
        "dataset": str(args.dataset),
        "num_images": res.num_images,
        "num_correct": res.num_correct,
        "accuracy": round(res.accuracy, 6),
        "label_counts": res.label_counts,
        "ee1_threshold": 0.9,
        "ee1_pass": bool(res.accuracy >= 0.9),
        "samples": res.details[:20],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()


