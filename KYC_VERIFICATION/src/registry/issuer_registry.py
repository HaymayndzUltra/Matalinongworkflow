"""
Issuer Registry & Adapters
Phase 11: Provide adapters and a router that aggregate proofs and route per issuer.
Includes proof structure: {ref_id, signature/hash, timestamp, adapter_name}
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional, Tuple, Any
import hashlib


def _ph_tz_now_iso() -> str:
    return (datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(hours=8)).isoformat()


@dataclass
class AdapterProof:
    ref_id: str
    signature: str
    timestamp: str
    adapter_name: str


class BaseIssuerAdapter:
    name: str = "base_adapter"

    def adapt(self, payload: Dict[str, Any]) -> Tuple["NormalizedRecord", list[str]]:
        raise NotImplementedError


class NormalizedRecord:
    """Minimal normalized structure; can be extended as needed."""

    def __init__(self, fields: Dict[str, Any]):
        self.fields = fields

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.fields)


class PhilIDAdapter(BaseIssuerAdapter):
    name = "philid_adapter_v1"

    def adapt(self, payload: Dict[str, Any]) -> Tuple[NormalizedRecord, list[str]]:
        errors: list[str] = []
        fields = {
            "psn": payload.get("psn") or payload.get("id_number"),
            "full_name": payload.get("name") or payload.get("full_name"),
            "birth_date": payload.get("birth_date") or payload.get("date_of_birth"),
        }
        if not fields["psn"]:
            errors.append("Missing PSN/id_number")
        if not fields["full_name"]:
            errors.append("Missing full_name")
        return NormalizedRecord(fields), errors


class PassportAdapter(BaseIssuerAdapter):
    name = "passport_adapter_v1"

    def adapt(self, payload: Dict[str, Any]) -> Tuple[NormalizedRecord, list[str]]:
        errors: list[str] = []
        fields = {
            "passport_no": payload.get("passport_no") or payload.get("id_number"),
            "surname": payload.get("surname"),
            "given_names": payload.get("given_names"),
            "birth_date": payload.get("birth_date") or payload.get("date_of_birth"),
        }
        if not fields["passport_no"]:
            errors.append("Missing passport_no")
        return NormalizedRecord(fields), errors


class IssuerRegistry:
    """Simple in-memory registry for issuer adapters."""

    def __init__(self) -> None:
        self._adapters: Dict[str, BaseIssuerAdapter] = {
            "PSA": PhilIDAdapter(),
            "DFA": PassportAdapter(),
        }

    def get_adapter(self, issuer_id: str) -> Optional[BaseIssuerAdapter]:
        return self._adapters.get(issuer_id)

    def create_proof(self, adapter_name: str, ref_seed: str) -> AdapterProof:
        ref_id = f"ref_{hashlib.md5(ref_seed.encode()).hexdigest()[:10]}"
        signature = hashlib.sha256(f"{adapter_name}:{ref_seed}".encode()).hexdigest()[:32]
        return AdapterProof(ref_id=ref_id, signature=signature, timestamp=_ph_tz_now_iso(), adapter_name=adapter_name)


