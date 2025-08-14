"""
NFC Reader (DG1/DG2 placeholder)
Phase 3 extension: Parse ICAO 9303 LDS files (DG1 basic fields; DG2 face image).
This module provides a stub with a graceful fallback when NFC libraries/hardware are unavailable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


@dataclass
class DG1Data:
    document_number: str
    name: str
    nationality: str
    birth_date: str
    sex: str
    expiry_date: str


@dataclass
class DG2Data:
    face_image_jpeg_base64: Optional[str]


class NFCReader:
    """Stub NFC reader. Replace with pyscard/mrz NFC impl as needed."""

    def read_dg1(self) -> Optional[DG1Data]:
        logger.warning("NFC hardware not available; returning placeholder DG1 data")
        return None

    def read_dg2(self) -> Optional[DG2Data]:
        logger.warning("NFC hardware not available; returning placeholder DG2 data")
        return None


