#!/usr/bin/env python3
"""
Failover Simulation (Phase 18)

Simulates vendor errors and latency spikes to verify circuit breaker behavior
in the VendorOrchestrator. Prints a short health summary at the end.

Usage:
  python3 scripts/failover_sim.py --requests 50 --timeout 0.1
"""

import argparse
import asyncio
import random
import time

from src.orchestrator.vendor_orchestrator import (
    VendorOrchestrator,
    VendorCapability,
    RequestPriority,
)


async def simulate_requests(orchestrator: VendorOrchestrator, n: int, timeout: float) -> None:
    for i in range(n):
        # Random capability
        capability = random.choice([
            VendorCapability.OCR,
            VendorCapability.FACE_MATCH,
            VendorCapability.AML_SCREEN,
        ])
        # Payload
        payload = {"request_id": i, "timeout_hint": timeout}
        _ = await orchestrator.execute_request(capability, payload, RequestPriority.NORMAL)
        await asyncio.sleep(0.01)


def parse_args():
    ap = argparse.ArgumentParser(description="Simulate vendor failover and breaker behavior")
    ap.add_argument("--requests", type=int, default=50, help="Number of simulated requests")
    ap.add_argument("--timeout", type=float, default=0.2, help="Base timeout hint (seconds)")
    return ap.parse_args()


def main():
    args = parse_args()
    orchestrator = VendorOrchestrator()
    t0 = time.time()
    asyncio.run(simulate_requests(orchestrator, args.requests, args.timeout))
    dt = time.time() - t0
    print(f"\n✅ Failover simulation done in {dt:.2f}s for {args.requests} requests")
    print("Health summary:")
    health = orchestrator.get_vendor_health()
    for vid, h in health.items():
        print(f"  - {vid}: status={h['status']} available={h['available']} metrics={h.get('metrics', {})}")


if __name__ == "__main__":
    main()


