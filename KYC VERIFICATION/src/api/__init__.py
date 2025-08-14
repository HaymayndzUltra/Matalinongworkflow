"""
KYC Identity Verification API Module
Provides FastAPI endpoints for the complete KYC verification pipeline
"""

# Keep package init lightweight to avoid importing heavy dependencies at import time.
# Consumers should import concrete modules directly, e.g. `from src.api.app import app`.
__all__: list[str] = []
