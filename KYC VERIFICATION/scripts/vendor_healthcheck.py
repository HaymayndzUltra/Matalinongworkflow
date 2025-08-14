#!/usr/bin/env python3
"""
Vendor Healthcheck (Phase 18)

Performs a lightweight health check across vendors and prints a JSON summary.

Usage:
  python3 scripts/vendor_healthcheck.py
"""

import json
from datetime import datetime

from src.orchestrator.vendor_orchestrator import VendorOrchestrator


def main():
    orch = VendorOrchestrator()
    summary = orch.get_vendor_health()
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "vendors": summary,
    }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()


