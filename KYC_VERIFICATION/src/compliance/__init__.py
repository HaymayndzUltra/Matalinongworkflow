"""
Compliance Module - GDPR/Privacy Compliance Artifact Generation
Generates DPIA, ROPA, and retention matrix documents
"""

from .artifact_generator import (
    ComplianceArtifactGenerator,
    DataField,
    ProcessingActivity,
    PrivacyRisk,
    DataCategory,
    ProcessingPurpose,
    LawfulBasis
)

__all__ = [
    'ComplianceArtifactGenerator',
    'DataField',
    'ProcessingActivity',
    'PrivacyRisk',
    'DataCategory',
    'ProcessingPurpose',
    'LawfulBasis'
]
