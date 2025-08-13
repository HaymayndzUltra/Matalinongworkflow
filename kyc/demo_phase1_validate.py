from __future__ import annotations

import json
from pathlib import Path
import sys

from kyc.capture_validation import validate_input, QualityThresholds


def main(argv):
    if len(argv) < 2:
        print("usage: python3 -m kyc.demo_phase1_validate <front.jpg> [back.jpg] [selfie.mp4]", file=sys.stderr)
        return 2
    front = Path(argv[1])
    back = Path(argv[2]) if len(argv) >= 3 and not argv[2].lower().endswith('.mp4') else None
    selfie = Path(argv[3]) if len(argv) >= 4 else (Path(argv[2]) if len(argv) >= 3 and argv[2].lower().endswith('.mp4') else None)
    thresholds = QualityThresholds()
    report = validate_input(front, back, selfie, thresholds)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv))


