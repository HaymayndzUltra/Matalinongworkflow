"""
Compatibility wrapper exposing calculate_score(...) similar to RiskEngine.calculate_risk input.
"""

from __future__ import annotations

from typing import Dict, Any, Tuple
from .risk_engine import RiskEngine


class RiskScorer:
    def __init__(self) -> None:
        self._engine = RiskEngine()

    def calculate_score(
        self,
        document_data: Dict[str, Any],
        device_info: Dict[str, Any] | None,
        biometric_data: Dict[str, Any] | None,
        aml_data: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        verification_data: Dict[str, Any] = {
            "extraction": {
                "ocr_confidence": 0.8,
                "expected_fields": list((document_data or {}).keys()),
                "extracted_fields": list((document_data or {}).keys()),
                "mrz_valid": bool((document_data or {}).get("mrz_data")),
            },
            "device": device_info or {},
            "biometrics": biometric_data or {},
            "validation": {"checksum_valid": True, "expiry_status": "valid"},
            "forensics": {"is_authentic": True, "manipulation_score": 0.0},
            "classification": {"confidence": 0.95},
        }
        score, decision = self._engine.calculate_risk(verification_data)

        # Convert feature_importance (List[Tuple[str, float]]) → List[Dict[str, Any]]
        risk_factors: list[dict[str, Any]] = [
            {"feature": name, "impact": float(impact)} for name, impact in (score.feature_importance or [])
        ]

        return {
            "risk_score": float(score.overall_score) * 100.0,
            "risk_factors": risk_factors,
            "fraud_indicators": list(decision.reasons or []),
        }


