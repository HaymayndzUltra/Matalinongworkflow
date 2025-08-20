"""
Wrapper checker to align API with existing AuthenticityVerifier.
Provides check_authenticity(image) -> dict.
"""

from __future__ import annotations

from typing import Dict, Any

from .authenticity_verifier import AuthenticityVerifier, ForensicResult


class AuthenticityChecker:
    def __init__(self) -> None:
        self._verifier = AuthenticityVerifier()

    def check_authenticity(self, image) -> Dict[str, Any]:  # image: np.ndarray
        result: ForensicResult = self._verifier.verify_authenticity(image)
        issues = []
        for f in result.findings:
            issues.append(f"{f.tamper_type.value}:{f.severity}")
        return {
            "authentic": bool(result.is_authentic),
            "confidence": float(result.authenticity_score),
            "issues": issues,
        }


