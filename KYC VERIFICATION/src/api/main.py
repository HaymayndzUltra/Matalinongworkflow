"""
FastAPI Service (Phase 13)
==========================
Creates API endpoints for KYC verification pipeline.  Each endpoint returns JSON
schemas aligned with pydantic models (omitted for brevity) and delegates to the
corresponding internal modules:
    /quality/analyze  -> CaptureQualityAnalyzer
    /classify         -> DocumentClassifier
    /extract          -> EvidenceExtractor
    /forensics        -> AuthenticityVerifier
    /biometrics       -> FaceMatcher
    /validate         -> PhilippineIDValidator (via Registry)
    /risk/score       -> RiskEngine
    /aml/screen       -> AMLScreener

Additional endpoints:
    /metrics          -> Prometheus-style metrics placeholder
    /ready, /health   -> Liveness & readiness probes

NOTE: Uses in-memory instances for now; dependency injection layer will be
refined in later phases.
"""

from __future__ import annotations

import uvicorn
from fastapi import FastAPI, File, UploadFile, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import numpy as np
import cv2
import io
from typing import Dict, Any

from src.capture.quality_analyzer import CaptureQualityAnalyzer
from src.classification.document_classifier import DocumentClassifier
from src.extraction.evidence_extractor import EvidenceExtractor
from src.forensics.authenticity_verifier import AuthenticityVerifier
from src.biometrics.face_matcher import FaceMatcher
from src.registry.issuer_registry import IssuerRegistry
from src.risk.risk_engine import RiskEngine
from src.screening.aml_screener import AMLScreener

app = FastAPI(title="KYC Verification API", version="0.1.0")

# Initialize services (singleton instances)
quality_analyzer = CaptureQualityAnalyzer()
classifier = DocumentClassifier()
extractor = EvidenceExtractor()
verifier = AuthenticityVerifier()
face_matcher = FaceMatcher()
issuer_registry = IssuerRegistry()
risk_engine = RiskEngine()
aml_screener = AMLScreener()

# ------------------------------ Models ---------------------------------------

class QualityResponse(BaseModel):
    passed: bool
    blur_score: float
    glare_score: float

# For brevity, other response models are omitted; returning Dict[str, Any].

# ------------------------------ Helpers --------------------------------------

def _img_from_upload(file: UploadFile) -> np.ndarray:
    content = file.file.read()
    img_arr = np.frombuffer(content, np.uint8)
    image = cv2.imdecode(img_arr, cv2.IMREAD_COLOR)
    if image is None:
        raise HTTPException(status_code=400, detail="Invalid image upload")
    return image

# ------------------------------ Endpoints ------------------------------------

@app.post("/quality/analyze", response_model=QualityResponse)
async def analyze_quality(file: UploadFile = File(...)):
    image = _img_from_upload(file)
    result = quality_analyzer.analyze_frame(image)
    return QualityResponse(**result)

@app.post("/classify")
async def classify_document(file: UploadFile = File(...)):
    image = _img_from_upload(file)
    result = classifier.classify(image)
    return JSONResponse(content=result)

@app.post("/extract")
async def extract_evidence(file: UploadFile = File(...)):
    image = _img_from_upload(file)
    result = extractor.extract_all(image, "auto")
    return JSONResponse(content=result.to_dict())

@app.post("/forensics")
async def forensics(file: UploadFile = File(...)):
    image = _img_from_upload(file)
    result = verifier.verify_authenticity(image, "auto")
    return JSONResponse(content=result.to_dict())

@app.post("/biometrics/selfie-match")
async def selfie_match(id_doc: UploadFile = File(...), selfie: UploadFile = File(...)):
    id_img = _img_from_upload(id_doc)
    selfie_img = _img_from_upload(selfie)
    result = face_matcher.verify_biometric(id_img, selfie_img)
    return JSONResponse(content=result.__dict__)

@app.post("/validate")
async def validate_document(data: Dict[str, Any]):
    issuer_id = data.get("issuer_id", "PSA")
    adapter = issuer_registry.get_adapter(issuer_id)
    if not adapter:
        raise HTTPException(status_code=400, detail="Unsupported issuer")
    normalized, errors = adapter.adapt(data)
    return {"normalized": normalized.to_dict(), "errors": errors}

@app.post("/risk/score")
async def risk_score(payload: Dict[str, Any]):
    score, decision = risk_engine.calculate_risk(payload)
    return {"risk_score": score.overall_score, "decision": decision.decision_type.value, "reasons": decision.reasons}

@app.post("/aml/screen")
async def aml_screen(payload: Dict[str, Any]):
    result = aml_screener.screen_individual(payload)
    return JSONResponse(content={"overall_risk": result.overall_risk.value, "explanations": result.explanations})

@app.get("/ready")
async def ready():
    return {"status": "ready"}

@app.get("/health")
async def health():
    return {"status": "healthy"}

@app.get("/metrics")
async def metrics():
    # Placeholder Prometheus metrics
    return {
        "document_classifications_total": 0,
        "face_matches_total": 0,
    }

# ------------------------------ Run ------------------------------------------

if __name__ == "__main__":
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=False)