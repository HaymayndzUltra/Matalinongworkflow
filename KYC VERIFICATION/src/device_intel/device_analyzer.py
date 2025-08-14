"""
Device Intelligence & Velocity
Phase 7: Detect VPN/TOR/proxy; emulator/root/jailbreak; IP/SIM/GPS mismatch; geovelocity anomalies.
This is a lightweight, local heuristic implementation with placeholders for real integrations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any, Optional, Tuple
import re
import math
from datetime import datetime, timezone, timedelta


def _ph_tz_now_iso() -> str:
    return (datetime.utcnow().replace(tzinfo=timezone.utc) + timedelta(hours=8)).isoformat()


@dataclass
class DeviceAnalysis:
    risk_score: float
    vpn_detected: bool
    tor_detected: bool
    proxy_detected: bool
    emulator_detected: bool
    root_jailbreak_detected: bool
    geo_anomaly: bool
    velocity_impossible: bool
    reasons: list[str]
    metadata: Dict[str, Any]


class DeviceAnalyzer:
    """Local heuristics for device risk analysis."""

    def analyze(self, device_info: Dict[str, Any], last_seen: Optional[Dict[str, Any]] = None) -> DeviceAnalysis:
        ip = (device_info or {}).get("ip", "")
        user_agent = (device_info or {}).get("user_agent", "")
        device_id = (device_info or {}).get("device_id", "")
        sim_country = (device_info or {}).get("sim_country")
        gps_country = (device_info or {}).get("gps_country")

        reasons: list[str] = []
        vpn = self._looks_like_vpn_ip(ip)
        if vpn:
            reasons.append("VPN IP range pattern detected")

        tor = self._looks_like_tor_exit(ip)
        if tor:
            reasons.append("TOR exit node pattern detected")

        proxy = self._looks_like_proxy(user_agent)
        if proxy:
            reasons.append("Proxy/automation user-agent pattern")

        emulator = self._looks_like_emulator(user_agent, device_id)
        if emulator:
            reasons.append("Emulator fingerprint detected")

        root_jb = self._root_or_jailbreak_hints(user_agent)
        if root_jb:
            reasons.append("Root/Jailbreak hints in UA")

        geo_anomaly = False
        if sim_country and gps_country and sim_country != gps_country:
            geo_anomaly = True
            reasons.append("SIM/GPS country mismatch")

        velocity_impossible = False
        if last_seen:
            velocity_impossible = self._impossible_travel(last_seen, device_info)
            if velocity_impossible:
                reasons.append("Impossible travel between sessions")

        # Aggregate risk
        risk_score = 0.0
        risk_score += 0.2 if vpn else 0.0
        risk_score += 0.2 if tor else 0.0
        risk_score += 0.1 if proxy else 0.0
        risk_score += 0.2 if emulator else 0.0
        risk_score += 0.1 if root_jb else 0.0
        risk_score += 0.1 if geo_anomaly else 0.0
        risk_score += 0.1 if velocity_impossible else 0.0
        risk_score = min(1.0, max(0.0, risk_score))

        return DeviceAnalysis(
            risk_score=risk_score,
            vpn_detected=vpn,
            tor_detected=tor,
            proxy_detected=proxy,
            emulator_detected=emulator,
            root_jailbreak_detected=root_jb,
            geo_anomaly=geo_anomaly,
            velocity_impossible=velocity_impossible,
            reasons=reasons,
            metadata={"timestamp": _ph_tz_now_iso(), "ip": ip}
        )

    def _looks_like_vpn_ip(self, ip: str) -> bool:
        # Heuristic placeholder: private or datacenter-like ranges
        if not ip:
            return False
        return bool(re.match(r"^(10\.|172\.(1[6-9]|2\d|3[01])\.|192\.168\.)", ip))

    def _looks_like_tor_exit(self, ip: str) -> bool:
        # Placeholder: match unusual / known test prefixes
        return ip.startswith("100.") or ip.startswith("198.51.100.")

    def _looks_like_proxy(self, ua: str) -> bool:
        ua_lower = (ua or "").lower()
        return any(token in ua_lower for token in ["curl/", "python-requests", "okhttp", "phantomjs", "selenium"])  # noqa: E501

    def _looks_like_emulator(self, ua: str, device_id: str) -> bool:
        ua_lower = (ua or "").lower()
        if "emulator" in ua_lower or "sdk_gphone" in ua_lower:
            return True
        return device_id.startswith("emu_") if device_id else False

    def _root_or_jailbreak_hints(self, ua: str) -> bool:
        ua_lower = (ua or "").lower()
        return "magisk" in ua_lower or "xposed" in ua_lower or "cydia" in ua_lower

    def _impossible_travel(self, last: Dict[str, Any], current: Dict[str, Any]) -> bool:
        # Very rough: if countries differ within short interval
        try:
            last_country = last.get("gps_country")
            cur_country = current.get("gps_country")
            last_ts = last.get("timestamp_s")
            cur_ts = current.get("timestamp_s")
            if not last_country or not cur_country or last_ts is None or cur_ts is None:
                return False
            dt = abs(float(cur_ts) - float(last_ts))
            # If < 1 hour and country changed, flag
            return dt < 3600 and last_country != cur_country
        except Exception:
            return False


