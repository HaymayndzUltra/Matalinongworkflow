"""
Minimal DecisionEngine to align with API references.
"""

from __future__ import annotations

from typing import Dict, Any


class DecisionEngine:
    def make_decision(
        self,
        risk_score: float,
        extracted_data: Dict[str, Any],
        validation_result: Dict[str, Any],
        policy_overrides: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        if risk_score < 20:
            decision = "approve"
            confidence = 0.95
        elif risk_score < 50:
            decision = "review"
            confidence = 0.8
        elif risk_score < 80:
            decision = "deny"
            confidence = 0.7
        else:
            decision = "deny"
            confidence = 0.6

        return {
            "decision": decision,
            "confidence": confidence,
            "reasons": [],
            "policy_version": "2024.1.0",
            "review_required": decision == "review",
            "review_reasons": [],
        }


