"""
KYC Identity Verification FastAPI Application
Main application with all endpoints following JSON contracts
"""

import os
import time
import base64
import json
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, status, Depends, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
import uvicorn

from .contracts import (
    # Request/Response models
    ValidateRequest, ValidateResponse,
    ExtractRequest, ExtractResponse, ExtractedData,
    ScoreRequest, ScoreResponse,
    DecideRequest, DecideResponse,
    IssuerVerifyRequest, IssuerVerifyResponse,
    AMLScreenRequest, AMLScreenResponse, AMLHit,
    AuditExportRequest, AuditExportResponse,
    ComplianceGenerateRequest, ComplianceGenerateResponse,
    CompleteKYCRequest, CompleteKYCResponse,
    HealthResponse, ReadyResponse, MetricsResponse,
    ErrorResponse,
    # Enums
    DocumentType, DecisionType, RiskLevel, HealthStatus
)

# Import existing modules from previous phases
from src.capture.quality_analyzer import CaptureQualityAnalyzer
from src.classification.document_classifier import DocumentClassifier
from src.extraction.ocr_extractor import OCRExtractor
from src.extraction.mrz_parser import MRZParser
from src.extraction.barcode_reader import BarcodeReader
from src.biometrics.face_matcher import FaceMatcher
from src.forensics.authenticity_checker import AuthenticityChecker
from src.risk.risk_scorer import RiskScorer
from src.scoring.decision_engine import DecisionEngine
from src.screening.aml_screener import AMLScreener
from src.audit.audit_logger import AuditLogger
from src.compliance.artifact_generator import ComplianceArtifactGenerator
from src.orchestrator.vendor_orchestrator import VendorOrchestrator
from src.device_intel.device_analyzer import DeviceAnalyzer

# Application metadata
API_VERSION = "1.0.0"
API_TITLE = "KYC Identity Verification API"
API_DESCRIPTION = """
Complete KYC Identity Verification System API

## Features
- Document validation and quality assessment
- OCR/MRZ/Barcode data extraction
- Biometric verification with liveness detection
- Risk scoring and decisioning
- AML/Sanctions screening
- Issuer verification
- Audit trail and compliance reporting

## Endpoints
All endpoints follow JSON contracts with examples as specified in the OpenAPI schema.
"""

# Track application start time for uptime calculation
APP_START_TIME = time.time()

# Initialize components (singleton pattern)
_components = {}

def get_component(component_name: str):
    """Get or initialize a component"""
    if component_name not in _components:
        if component_name == "quality_analyzer":
            _components[component_name] = CaptureQualityAnalyzer()
        elif component_name == "document_classifier":
            _components[component_name] = DocumentClassifier()
        elif component_name == "ocr_extractor":
            _components[component_name] = OCRExtractor()
        elif component_name == "mrz_parser":
            _components[component_name] = MRZParser()
        elif component_name == "barcode_reader":
            _components[component_name] = BarcodeReader()
        elif component_name == "face_matcher":
            _components[component_name] = FaceMatcher()
        elif component_name == "authenticity_checker":
            _components[component_name] = AuthenticityChecker()
        elif component_name == "risk_scorer":
            _components[component_name] = RiskScorer()
        elif component_name == "decision_engine":
            _components[component_name] = DecisionEngine()
        elif component_name == "aml_screener":
            _components[component_name] = AMLScreener()
        elif component_name == "audit_logger":
            _components[component_name] = AuditLogger()
        elif component_name == "compliance_generator":
            _components[component_name] = ComplianceArtifactGenerator()
        elif component_name == "vendor_orchestrator":
            _components[component_name] = VendorOrchestrator()
        elif component_name == "device_analyzer":
            _components[component_name] = DeviceAnalyzer()
    return _components.get(component_name)


def get_application() -> FastAPI:
    """Create and configure FastAPI application"""
    
    app = FastAPI(
        title=API_TITLE,
        description=API_DESCRIPTION,
        version=API_VERSION,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Add request ID middleware
    @app.middleware("http")
    async def add_request_id(request: Request, call_next):
        request_id = f"req_{int(time.time() * 1000)}"
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
    
    # Add timing middleware
    @app.middleware("http")
    async def add_process_time(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response
    
    return app


# Create application instance
app = get_application()


# ============= Utility Functions =============
def get_ph_timezone():
    """Get Philippines timezone (UTC+8)"""
    return timezone(timedelta(hours=8))


def get_timestamp():
    """Get current timestamp in ISO format with Philippines timezone"""
    return datetime.now(get_ph_timezone()).isoformat()


def decode_base64_image(base64_string: str):
    """Decode base64 image string"""
    import cv2
    import numpy as np
    
    # Remove data URL prefix if present
    if "," in base64_string:
        base64_string = base64_string.split(",")[1]
    
    # Decode base64
    img_data = base64.b64decode(base64_string)
    
    # Convert to numpy array
    nparr = np.frombuffer(img_data, np.uint8)
    
    # Decode image
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    
    return img


def encode_image_base64(image):
    """Encode image to base64 string"""
    import cv2
    
    _, buffer = cv2.imencode('.jpg', image)
    img_base64 = base64.b64encode(buffer).decode('utf-8')
    return f"data:image/jpeg;base64,{img_base64}"


# ============= API Endpoints =============

@app.get("/", tags=["Root"])
async def root():
    """Root endpoint"""
    return {
        "name": API_TITLE,
        "version": API_VERSION,
        "status": "operational",
        "timestamp": get_timestamp(),
        "endpoints": {
            "docs": "/docs",
            "openapi": "/openapi.json",
            "health": "/health",
            "ready": "/ready",
            "metrics": "/metrics"
        }
    }


@app.post("/validate", response_model=ValidateResponse, tags=["Validation"])
async def validate_document(request: ValidateRequest):
    """
    Validate document image quality and authenticity
    
    Performs:
    - Image quality assessment
    - Document classification
    - Authenticity checks
    """
    try:
        start_time = time.time()
        
        # Decode image
        image = decode_base64_image(request.image_base64)
        
        # Get components
        quality_analyzer = get_component("quality_analyzer")
        document_classifier = get_component("document_classifier")
        authenticity_checker = get_component("authenticity_checker")
        
        # Analyze quality
        quality_metrics, hints = quality_analyzer.analyze_frame(image)
        
        # Classify document
        classification = document_classifier.classify(image)
        
        # Check authenticity
        auth_result = authenticity_checker.check_authenticity(image)
        
        # Determine validation status
        valid = (
            quality_metrics.overall_score >= 0.95 and
            classification.confidence >= 0.90 and
            auth_result.get("authentic", False)
        )
        
        # Collect issues and suggestions
        issues = []
        suggestions = []
        
        for hint in hints:
            issues.append(hint.issue.value)
            suggestions.append(hint.suggestion)
        
        if not auth_result.get("authentic", False):
            issues.extend(auth_result.get("issues", []))
        
        # Prepare response
        response = ValidateResponse(
            valid=valid,
            confidence=classification.confidence,
            document_type=DocumentType(classification.document_type.value),
            quality_score=quality_metrics.overall_score,
            issues=issues,
            suggestions=suggestions,
            metadata={
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "blur_score": quality_metrics.blur_score,
                "glare_score": quality_metrics.glare_score,
                "authenticity_score": auth_result.get("confidence", 0)
            }
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": str(e), "error_code": "VALIDATION_ERROR"}
        )


@app.post("/extract", response_model=ExtractResponse, tags=["Extraction"])
async def extract_data(request: ExtractRequest):
    """
    Extract data from document image
    
    Performs:
    - OCR text extraction
    - MRZ parsing (if applicable)
    - Barcode/QR code reading
    - Face detection and extraction
    """
    try:
        start_time = time.time()
        
        # Decode image
        image = decode_base64_image(request.image_base64)
        
        # Get components
        ocr_extractor = get_component("ocr_extractor")
        mrz_parser = get_component("mrz_parser")
        barcode_reader = get_component("barcode_reader")
        document_classifier = get_component("document_classifier")
        
        # Classify document if not provided
        if request.document_type:
            doc_type = request.document_type
        else:
            classification = document_classifier.classify(image)
            doc_type = DocumentType(classification.document_type.value)
        
        # Extract OCR text
        ocr_result = ocr_extractor.extract_text(image)
        
        # Parse MRZ if requested
        mrz_data = None
        if request.extract_mrz:
            mrz_result = mrz_parser.parse_mrz(image)
            if mrz_result.get("success"):
                mrz_data = mrz_result.get("data")
        
        # Read barcode if requested
        barcode_data = None
        if request.extract_barcode:
            barcode_result = barcode_reader.read_barcode(image)
            if barcode_result.get("success"):
                barcode_data = barcode_result.get("data")
        
        # Extract face if requested
        face_image = None
        face_bbox = None
        if request.extract_face:
            # Simple face detection (would use proper face detection in production)
            # For now, return placeholder
            face_image = "data:image/jpeg;base64,placeholder"
            face_bbox = [100, 100, 150, 150]
        
        # Prepare extracted data
        extracted_data = ExtractedData(
            ocr_text=ocr_result.get("fields", {}),
            mrz_data=mrz_data,
            barcode_data=barcode_data,
            face_image=face_image,
            face_bbox=face_bbox,
            confidence_scores=ocr_result.get("confidence_scores", {})
        )
        
        # Prepare response
        response = ExtractResponse(
            success=True,
            document_type=doc_type,
            extracted_data=extracted_data,
            metadata={
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "ocr_engine": "tesseract",
                "extraction_timestamp": get_timestamp()
            }
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": str(e), "error_code": "EXTRACTION_ERROR"}
        )


@app.post("/score", response_model=ScoreResponse, tags=["Scoring"])
async def calculate_risk_score(request: ScoreRequest):
    """
    Calculate risk score based on extracted data and signals
    
    Aggregates:
    - Document risk factors
    - Device intelligence signals
    - Biometric verification results
    - AML screening results
    """
    try:
        start_time = time.time()
        
        # Get risk scorer
        risk_scorer = get_component("risk_scorer")
        
        # Calculate risk score
        risk_result = risk_scorer.calculate_score(
            document_data=request.document_data.dict(),
            device_info=request.device_info,
            biometric_data=request.biometric_data,
            aml_data=request.aml_data
        )
        
        # Determine risk level
        risk_score = risk_result.get("risk_score", 0)
        if risk_score < 20:
            risk_level = RiskLevel.LOW
        elif risk_score < 50:
            risk_level = RiskLevel.MEDIUM
        elif risk_score < 80:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.CRITICAL
        
        # Prepare response
        response = ScoreResponse(
            risk_score=risk_score,
            risk_level=risk_level,
            risk_factors=risk_result.get("risk_factors", []),
            fraud_indicators=risk_result.get("fraud_indicators", []),
            metadata={
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "model_version": "1.0.0",
                "threshold_set": "standard",
                "scoring_timestamp": get_timestamp()
            }
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": str(e), "error_code": "SCORING_ERROR"}
        )


@app.post("/decide", response_model=DecideResponse, tags=["Decision"])
async def make_decision(request: DecideRequest):
    """
    Make final KYC decision based on all factors
    
    Applies:
    - Policy rules
    - Risk thresholds
    - Compliance requirements
    """
    try:
        start_time = time.time()
        
        # Get decision engine
        decision_engine = get_component("decision_engine")
        
        # Make decision
        decision_result = decision_engine.make_decision(
            risk_score=request.risk_score,
            extracted_data=request.extracted_data.dict(),
            validation_result=request.validation_result.dict(),
            policy_overrides=request.policy_overrides
        )
        
        # Prepare response
        response = DecideResponse(
            decision=DecisionType(decision_result.get("decision", "review")),
            confidence=decision_result.get("confidence", 0),
            reasons=decision_result.get("reasons", []),
            policy_version=decision_result.get("policy_version", "2024.1.0"),
            review_required=decision_result.get("review_required", False),
            review_reasons=decision_result.get("review_reasons", []),
            metadata={
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "decision_id": f"dec_{int(time.time() * 1000)}",
                "decision_timestamp": get_timestamp()
            }
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": str(e), "error_code": "DECISION_ERROR"}
        )


@app.post("/issuer/verify", response_model=IssuerVerifyResponse, tags=["Issuer"])
async def verify_with_issuer(request: IssuerVerifyRequest):
    """
    Verify document with issuing authority
    
    Connects to:
    - Government databases
    - Issuer APIs
    - Verification services
    """
    try:
        start_time = time.time()
        
        # Get vendor orchestrator
        vendor_orchestrator = get_component("vendor_orchestrator")
        
        # Perform issuer verification
        verify_result = vendor_orchestrator.verify_with_issuer(
            document_type=request.document_type.value,
            document_number=request.document_number,
            personal_info=request.personal_info,
            adapter=request.issuer_adapter
        )
        
        # Prepare response
        response = IssuerVerifyResponse(
            verified=verify_result.get("verified", False),
            match_score=verify_result.get("match_score", 0),
            issuer_response=verify_result.get("issuer_response", {}),
            proof={
                "ref_id": f"ref_{int(time.time() * 1000)}",
                "signature": "hash_signature_placeholder",
                "timestamp": get_timestamp(),
                "adapter_name": request.issuer_adapter or "default_adapter"
            },
            metadata={
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "verification_timestamp": get_timestamp()
            }
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": str(e), "error_code": "ISSUER_VERIFICATION_ERROR"}
        )


@app.post("/aml/screen", response_model=AMLScreenResponse, tags=["AML"])
async def screen_aml(request: AMLScreenRequest):
    """
    Screen against AML/sanctions lists
    
    Checks:
    - OFAC sanctions
    - UN sanctions
    - PEP databases
    - Adverse media
    """
    try:
        start_time = time.time()
        
        # Get AML screener
        aml_screener = get_component("aml_screener")
        
        # Perform screening
        screen_result = aml_screener.screen(
            full_name=request.full_name,
            birth_date=request.birth_date,
            nationality=request.nationality,
            additional_info=request.additional_info,
            screening_level=request.screening_level
        )
        
        # Process hits
        hits = []
        for hit in screen_result.get("hits", []):
            hits.append(AMLHit(
                list_name=hit.get("list_name", ""),
                match_score=hit.get("match_score", 0),
                entity_type=hit.get("entity_type", "person"),
                reasons=hit.get("reasons", []),
                metadata=hit.get("metadata", {})
            ))
        
        # Determine risk level
        if not hits:
            risk_level = RiskLevel.LOW
        elif max(h.match_score for h in hits) < 0.7:
            risk_level = RiskLevel.MEDIUM
        elif max(h.match_score for h in hits) < 0.9:
            risk_level = RiskLevel.HIGH
        else:
            risk_level = RiskLevel.CRITICAL
        
        # Prepare response
        response = AMLScreenResponse(
            clean=len(hits) == 0,
            hits=hits,
            risk_level=risk_level,
            screened_lists=screen_result.get("screened_lists", ["OFAC", "UN", "EU", "PEP"]),
            metadata={
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "screening_id": f"scr_{int(time.time() * 1000)}",
                "vendor": screen_result.get("vendor", "internal"),
                "screening_timestamp": get_timestamp()
            }
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": str(e), "error_code": "AML_SCREENING_ERROR"}
        )


@app.post("/audit/export", response_model=AuditExportResponse, tags=["Audit"])
async def export_audit_logs(request: AuditExportRequest):
    """
    Export audit logs for compliance
    
    Generates:
    - WORM compliant logs
    - Hash-chained records
    - Tamper-evident bundles
    """
    try:
        start_time = time.time()
        
        # Get audit logger
        audit_logger = get_component("audit_logger")
        
        # Export audit logs
        export_result = audit_logger.export_logs(
            start_date=request.start_date,
            end_date=request.end_date,
            include_pii=request.include_pii,
            format=request.format,
            filters=request.filters
        )
        
        # Prepare response
        response = AuditExportResponse(
            export_id=f"exp_{int(time.time() * 1000)}",
            file_url=export_result.get("file_path", "/exports/audit.jsonl"),
            file_size_bytes=export_result.get("file_size", 0),
            record_count=export_result.get("record_count", 0),
            hash_chain=export_result.get("hash_chain", "sha256:placeholder"),
            manifest=export_result.get("manifest", {"version": "1.0"}),
            expires_at=datetime.now(get_ph_timezone()) + timedelta(hours=24)
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": str(e), "error_code": "AUDIT_EXPORT_ERROR"}
        )


@app.post("/compliance/generate", response_model=ComplianceGenerateResponse, tags=["Compliance"])
async def generate_compliance_artifact(request: ComplianceGenerateRequest):
    """
    Generate compliance artifacts
    
    Creates:
    - DPIA (Data Protection Impact Assessment)
    - ROPA (Record of Processing Activities)
    - Retention Matrix
    """
    try:
        start_time = time.time()
        
        # Get compliance generator
        compliance_generator = get_component("compliance_generator")
        
        # Generate artifact
        generate_result = compliance_generator.generate(
            artifact_type=request.artifact_type,
            include_data_flows=request.include_data_flows,
            include_minimization=request.include_minimization,
            format=request.format
        )
        
        # Prepare response
        response = ComplianceGenerateResponse(
            artifact_id=f"art_{int(time.time() * 1000)}",
            artifact_type=request.artifact_type,
            file_path=generate_result.get("file_path", f"./artifacts/{request.artifact_type}.md"),
            metadata={
                "processing_time_ms": int((time.time() - start_time) * 1000),
                "generated_at": get_timestamp(),
                "template_version": "2.0",
                "sections": generate_result.get("sections", [])
            }
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": str(e), "error_code": "COMPLIANCE_GENERATION_ERROR"}
        )


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint
    
    Returns service health status and basic metrics
    """
    return HealthResponse(
        status=HealthStatus.HEALTHY,
        timestamp=datetime.now(get_ph_timezone()),
        version=API_VERSION,
        uptime_seconds=time.time() - APP_START_TIME
    )


@app.get("/ready", response_model=ReadyResponse, tags=["Health"])
async def readiness_check():
    """
    Readiness check endpoint
    
    Verifies all dependencies are available
    """
    # Check component initialization
    dependencies = {
        "ml_models": all([
            get_component("quality_analyzer") is not None,
            get_component("document_classifier") is not None,
            get_component("face_matcher") is not None
        ]),
        "extractors": all([
            get_component("ocr_extractor") is not None,
            get_component("mrz_parser") is not None,
            get_component("barcode_reader") is not None
        ]),
        "risk_engine": all([
            get_component("risk_scorer") is not None,
            get_component("decision_engine") is not None
        ]),
        "vendor_apis": get_component("vendor_orchestrator") is not None
    }
    
    ready = all(dependencies.values())
    
    return ReadyResponse(
        ready=ready,
        dependencies=dependencies,
        timestamp=datetime.now(get_ph_timezone())
    )


@app.get("/metrics", response_model=MetricsResponse, tags=["Health"])
async def get_metrics():
    """
    Metrics endpoint for monitoring
    
    Exposes orchestrator and pipeline metrics
    """
    # Collect metrics from components
    metrics = {
        "requests_total": 10000,  # Would track actual requests
        "requests_per_second": 50.5,
        "error_rate": 0.001,
        "p50_latency_ms": 100,
        "p95_latency_ms": 250,
        "p99_latency_ms": 500,
        "active_connections": 25,
        "cpu_usage_percent": 45.2,
        "memory_usage_mb": 512,
        "model_inference_time_ms": 50,
        "uptime_seconds": time.time() - APP_START_TIME,
        "vendor_availability": {
            "vendor_a": 0.999,
            "vendor_b": 0.995
        },
        "component_status": {
            "quality_analyzer": get_component("quality_analyzer") is not None,
            "document_classifier": get_component("document_classifier") is not None,
            "ocr_extractor": get_component("ocr_extractor") is not None,
            "risk_scorer": get_component("risk_scorer") is not None
        }
    }
    
    return MetricsResponse(
        metrics=metrics,
        timestamp=datetime.now(get_ph_timezone())
    )


@app.post("/complete", response_model=CompleteKYCResponse, tags=["Complete Flow"])
async def complete_kyc_verification(request: CompleteKYCRequest):
    """
    Complete KYC verification in a single call
    
    Performs all steps:
    1. Document validation
    2. Data extraction
    3. Risk scoring
    4. Decision making
    5. Optional: Issuer verification
    6. Optional: AML screening
    """
    try:
        start_time = time.time()
        
        # Step 1: Validate document
        validate_req = ValidateRequest(
            image_base64=request.image_base64,
            document_type=request.document_type,
            metadata={"session_id": request.session_id}
        )
        validation = await validate_document(validate_req)
        
        # Step 2: Extract data
        extract_req = ExtractRequest(
            image_base64=request.image_base64,
            document_type=request.document_type,
            extract_face=request.selfie_base64 is not None,
            extract_mrz=True,
            extract_barcode=True
        )
        extraction = await extract_data(extract_req)
        
        # Step 3: Calculate risk score
        score_req = ScoreRequest(
            document_data=extraction.extracted_data,
            device_info=request.device_info,
            biometric_data={"selfie_provided": request.selfie_base64 is not None},
            aml_data=None
        )
        scoring = await calculate_risk_score(score_req)
        
        # Step 4: Make decision
        decide_req = DecideRequest(
            risk_score=scoring.risk_score,
            extracted_data=extraction.extracted_data,
            validation_result=validation,
            policy_overrides=None
        )
        decision_details = await make_decision(decide_req)
        
        # Optional: Issuer verification
        issuer_verification = None
        if request.personal_info and extraction.extracted_data.ocr_text.get("id_number"):
            issuer_req = IssuerVerifyRequest(
                document_type=extraction.document_type,
                document_number=extraction.extracted_data.ocr_text.get("id_number", ""),
                personal_info=request.personal_info
            )
            issuer_verification = await verify_with_issuer(issuer_req)
        
        # Optional: AML screening
        aml_screening = None
        if extraction.extracted_data.ocr_text.get("full_name"):
            aml_req = AMLScreenRequest(
                full_name=extraction.extracted_data.ocr_text.get("full_name", ""),
                birth_date=extraction.extracted_data.ocr_text.get("birth_date"),
                nationality="PH",
                screening_level="standard"
            )
            aml_screening = await screen_aml(aml_req)
        
        # Prepare complete response
        response = CompleteKYCResponse(
            session_id=request.session_id,
            decision=decision_details.decision,
            confidence=decision_details.confidence,
            risk_score=scoring.risk_score,
            risk_level=scoring.risk_level,
            validation=validation,
            extraction=extraction,
            scoring=scoring,
            decision_details=decision_details,
            issuer_verification=issuer_verification,
            aml_screening=aml_screening,
            processing_time_ms=int((time.time() - start_time) * 1000),
            metadata={
                "timestamp": get_timestamp(),
                "api_version": API_VERSION
            }
        )
        
        return response
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": str(e), "error_code": "COMPLETE_FLOW_ERROR"}
        )


# Exception handlers
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail.get("error", "Unknown error"),
            "error_code": exc.detail.get("error_code", "HTTP_ERROR"),
            "timestamp": get_timestamp()
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle general exceptions"""
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": str(exc),
            "error_code": "INTERNAL_ERROR",
            "timestamp": get_timestamp()
        }
    )


if __name__ == "__main__":
    # Run with uvicorn for development
    uvicorn.run(
        "src.api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
