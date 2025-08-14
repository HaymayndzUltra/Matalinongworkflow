"""
KYC Identity Verification API Module
Provides FastAPI endpoints for the complete KYC verification pipeline
"""

from .app import app, get_application
from .contracts import *
from .endpoints import *

__all__ = ['app', 'get_application']
