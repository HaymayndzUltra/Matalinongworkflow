"""
API Contracts - Pydantic models for request/response validation
Following JSON contracts with examples as per IMPORTANT NOTE
"""

from typing import Optional, List, Dict, Any, Union
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum


# ============= Enums =============
class DocumentType(str, Enum):
    """Supported document types"""
    PHILIPPINE_ID = "PHILIPPINE_ID"
    UMID = "UMID"
    DRIVERS_LICENSE = "DRIVERS_LICENSE"
    PASSPORT = "PASSPORT"
    PRC_LICENSE = "PRC_LICENSE"
    UNKNOWN = "UNKNOWN"


class DecisionType(str, Enum):
    """Decision outcomes"""
    APPROVE = "approve"
    REVIEW = "review"
    DENY = "deny"
    PENDING = "pending"


class RiskLevel(str, Enum):
    """Risk levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class HealthStatus(str, Enum):
    """Service health status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


# ============= Base Models =============
class TimestampMixin(BaseModel):
    """Mixin for timestamp fields (ISO8601 +08:00)"""
    created_at: datetime = Field(default_factory=lambda: datetime.now())
    updated_at: datetime = Field(default_factory=lambda: datetime.now())
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str = Field(..., description="Error message")
    error_code: str = Field(..., description="Error code")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


# ============= /validate Endpoint =============
class ValidateRequest(BaseModel):
    """Request for document validation"""
    image_base64: str = Field(..., description="Base64 encoded document image")
    document_type: Optional[DocumentType] = Field(None, description="Expected document type")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
                "document_type": "PHILIPPINE_ID",
                "metadata": {"session_id": "sess_123", "user_id": "user_456"}
            }
        }


class ValidateResponse(BaseModel):
    """Response from document validation"""
    valid: bool = Field(..., description="Overall validation result")
    confidence: float = Field(..., description="Confidence score (0-1)")
    document_type: DocumentType = Field(..., description="Detected document type")
    quality_score: float = Field(..., description="Image quality score (0-1)")
    issues: List[str] = Field(default_factory=list, description="Validation issues found")
    suggestions: List[str] = Field(default_factory=list, description="Improvement suggestions")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "valid": True,
                "confidence": 0.95,
                "document_type": "PHILIPPINE_ID",
                "quality_score": 0.98,
                "issues": [],
                "suggestions": ["Ensure good lighting for better quality"],
                "metadata": {"processing_time_ms": 250}
            }
        }


# ============= /extract Endpoint =============
class ExtractRequest(BaseModel):
    """Request for data extraction"""
    image_base64: str = Field(..., description="Base64 encoded document image")
    document_type: Optional[DocumentType] = Field(None, description="Document type hint")
    extract_face: bool = Field(True, description="Extract face image")
    extract_mrz: bool = Field(True, description="Extract MRZ if available")
    extract_barcode: bool = Field(True, description="Extract barcode if available")
    
    class Config:
        schema_extra = {
            "example": {
                "image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
                "document_type": "PASSPORT",
                "extract_face": True,
                "extract_mrz": True,
                "extract_barcode": False
            }
        }


class ExtractedData(BaseModel):
    """Extracted document data"""
    ocr_text: Dict[str, Any] = Field(..., description="OCR extracted fields")
    mrz_data: Optional[Dict[str, Any]] = Field(None, description="MRZ parsed data")
    barcode_data: Optional[Dict[str, Any]] = Field(None, description="Barcode parsed data")
    face_image: Optional[str] = Field(None, description="Base64 encoded face crop")
    face_bbox: Optional[List[int]] = Field(None, description="Face bounding box [x,y,w,h]")
    confidence_scores: Dict[str, float] = Field(default_factory=dict, description="Field confidence scores")


class ExtractResponse(BaseModel):
    """Response from data extraction"""
    success: bool = Field(..., description="Extraction success status")
    document_type: DocumentType = Field(..., description="Detected document type")
    extracted_data: ExtractedData = Field(..., description="Extracted data")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "success": True,
                "document_type": "PHILIPPINE_ID",
                "extracted_data": {
                    "ocr_text": {
                        "full_name": "JUAN DELA CRUZ",
                        "birth_date": "1990-01-01",
                        "id_number": "1234-5678-9012-3456"
                    },
                    "mrz_data": None,
                    "barcode_data": {"raw": "encoded_data"},
                    "face_image": "data:image/jpeg;base64,/9j/...",
                    "face_bbox": [100, 150, 120, 160],
                    "confidence_scores": {"full_name": 0.98, "birth_date": 0.95}
                },
                "metadata": {"processing_time_ms": 450}
            }
        }


# ============= /score Endpoint =============
class ScoreRequest(BaseModel):
    """Request for risk scoring"""
    document_data: ExtractedData = Field(..., description="Extracted document data")
    device_info: Optional[Dict[str, Any]] = Field(None, description="Device intelligence data")
    biometric_data: Optional[Dict[str, Any]] = Field(None, description="Biometric verification data")
    aml_data: Optional[Dict[str, Any]] = Field(None, description="AML screening data")


class ScoreResponse(BaseModel):
    """Response from risk scoring"""
    risk_score: float = Field(..., description="Overall risk score (0-100)")
    risk_level: RiskLevel = Field(..., description="Risk level category")
    risk_factors: List[Dict[str, Any]] = Field(..., description="Individual risk factors")
    fraud_indicators: List[str] = Field(default_factory=list, description="Detected fraud indicators")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "risk_score": 15.5,
                "risk_level": "low",
                "risk_factors": [
                    {"factor": "document_quality", "score": 5.0, "weight": 0.2},
                    {"factor": "device_risk", "score": 10.0, "weight": 0.3}
                ],
                "fraud_indicators": [],
                "metadata": {"model_version": "1.0.0", "threshold_set": "standard"}
            }
        }


# ============= /decide Endpoint =============
class DecideRequest(BaseModel):
    """Request for final decision"""
    risk_score: float = Field(..., description="Risk score from scoring")
    extracted_data: ExtractedData = Field(..., description="Extracted document data")
    validation_result: ValidateResponse = Field(..., description="Validation result")
    policy_overrides: Optional[Dict[str, Any]] = Field(None, description="Policy overrides")


class DecideResponse(BaseModel):
    """Response from decision engine"""
    decision: DecisionType = Field(..., description="Final decision")
    confidence: float = Field(..., description="Decision confidence (0-1)")
    reasons: List[str] = Field(..., description="Decision reasons")
    policy_version: str = Field(..., description="Applied policy version")
    review_required: bool = Field(False, description="Manual review required")
    review_reasons: List[str] = Field(default_factory=list, description="Review reasons")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "decision": "approve",
                "confidence": 0.95,
                "reasons": ["Low risk score", "All validations passed"],
                "policy_version": "2024.1.0",
                "review_required": False,
                "review_reasons": [],
                "metadata": {"decision_id": "dec_789", "processing_time_ms": 50}
            }
        }


# ============= /issuer/verify Endpoint =============
class IssuerVerifyRequest(BaseModel):
    """Request for issuer verification"""
    document_type: DocumentType = Field(..., description="Document type")
    document_number: str = Field(..., description="Document ID number")
    personal_info: Dict[str, Any] = Field(..., description="Personal information to verify")
    issuer_adapter: Optional[str] = Field(None, description="Specific issuer adapter to use")


class IssuerVerifyResponse(BaseModel):
    """Response from issuer verification"""
    verified: bool = Field(..., description="Verification status")
    match_score: float = Field(..., description="Match score (0-1)")
    issuer_response: Dict[str, Any] = Field(..., description="Raw issuer response")
    proof: Dict[str, Any] = Field(..., description="Verification proof")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "verified": True,
                "match_score": 0.98,
                "issuer_response": {"status": "VALID", "issued_date": "2020-01-15"},
                "proof": {
                    "ref_id": "ref_abc123",
                    "signature": "hash_signature",
                    "timestamp": "2024-01-14T10:30:00+08:00",
                    "adapter_name": "philid_adapter_v1"
                },
                "metadata": {"query_time_ms": 1250}
            }
        }


# ============= /aml/screen Endpoint =============
class AMLScreenRequest(BaseModel):
    """Request for AML/sanctions screening"""
    full_name: str = Field(..., description="Full name to screen")
    birth_date: Optional[str] = Field(None, description="Date of birth (YYYY-MM-DD)")
    nationality: Optional[str] = Field(None, description="Nationality/Country code")
    additional_info: Optional[Dict[str, Any]] = Field(None, description="Additional screening info")
    screening_level: str = Field("standard", description="Screening level: basic|standard|enhanced")


class AMLHit(BaseModel):
    """AML/sanctions hit"""
    list_name: str = Field(..., description="Sanctions list name")
    match_score: float = Field(..., description="Match score (0-1)")
    entity_type: str = Field(..., description="Entity type: person|organization")
    reasons: List[str] = Field(..., description="Match reasons")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Hit metadata")


class AMLScreenResponse(BaseModel):
    """Response from AML screening"""
    clean: bool = Field(..., description="No hits found")
    hits: List[AMLHit] = Field(default_factory=list, description="Sanctions/PEP hits")
    risk_level: RiskLevel = Field(..., description="AML risk level")
    screened_lists: List[str] = Field(..., description="Lists screened")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "clean": True,
                "hits": [],
                "risk_level": "low",
                "screened_lists": ["OFAC", "UN", "EU", "PEP"],
                "metadata": {"screening_id": "scr_456", "vendor": "vendor_a"}
            }
        }


# ============= /audit/export Endpoint =============
class AuditExportRequest(BaseModel):
    """Request for audit log export"""
    start_date: datetime = Field(..., description="Start date for export")
    end_date: datetime = Field(..., description="End date for export")
    include_pii: bool = Field(False, description="Include PII in export")
    format: str = Field("jsonl", description="Export format: jsonl|csv")
    filters: Optional[Dict[str, Any]] = Field(None, description="Additional filters")


class AuditExportResponse(BaseModel):
    """Response from audit export"""
    export_id: str = Field(..., description="Export ID")
    file_url: str = Field(..., description="Download URL for export")
    file_size_bytes: int = Field(..., description="File size in bytes")
    record_count: int = Field(..., description="Number of records exported")
    hash_chain: str = Field(..., description="SHA-256 hash chain for verification")
    manifest: Dict[str, Any] = Field(..., description="Export manifest")
    expires_at: datetime = Field(..., description="URL expiration time")
    
    class Config:
        schema_extra = {
            "example": {
                "export_id": "exp_789abc",
                "file_url": "/exports/audit_20240114_102030.jsonl",
                "file_size_bytes": 1048576,
                "record_count": 1500,
                "hash_chain": "sha256:abc123...",
                "manifest": {"version": "1.0", "created_by": "system"},
                "expires_at": "2024-01-15T10:20:30+08:00"
            }
        }


# ============= /compliance/generate Endpoint =============
class ComplianceGenerateRequest(BaseModel):
    """Request for compliance artifact generation"""
    artifact_type: str = Field(..., description="Artifact type: dpia|ropa|retention_matrix")
    include_data_flows: bool = Field(True, description="Include data flow diagrams")
    include_minimization: bool = Field(True, description="Include data minimization map")
    format: str = Field("markdown", description="Output format: markdown|csv|pdf")


class ComplianceGenerateResponse(BaseModel):
    """Response from compliance generation"""
    artifact_id: str = Field(..., description="Artifact ID")
    artifact_type: str = Field(..., description="Generated artifact type")
    file_path: str = Field(..., description="Path to generated artifact")
    metadata: Dict[str, Any] = Field(..., description="Generation metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "artifact_id": "art_123xyz",
                "artifact_type": "dpia",
                "file_path": "./artifacts/DPIA_20240114.md",
                "metadata": {
                    "generated_at": "2024-01-14T10:30:00+08:00",
                    "template_version": "2.0",
                    "sections": ["purpose", "data_types", "risks", "mitigation"]
                }
            }
        }


# ============= Health Check Endpoints =============
class HealthResponse(BaseModel):
    """Health check response"""
    status: HealthStatus = Field(..., description="Service health status")
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
    version: str = Field(..., description="API version")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")
    
    class Config:
        schema_extra = {
            "example": {
                "status": "healthy",
                "timestamp": "2024-01-14T10:30:00+08:00",
                "version": "1.0.0",
                "uptime_seconds": 3600.5
            }
        }


class ReadyResponse(BaseModel):
    """Readiness check response"""
    ready: bool = Field(..., description="Service ready status")
    dependencies: Dict[str, bool] = Field(..., description="Dependency status")
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
    
    class Config:
        schema_extra = {
            "example": {
                "ready": True,
                "dependencies": {
                    "database": True,
                    "redis": True,
                    "ml_models": True,
                    "vendor_apis": True
                },
                "timestamp": "2024-01-14T10:30:00+08:00"
            }
        }


class MetricsResponse(BaseModel):
    """Metrics endpoint response"""
    metrics: Dict[str, Any] = Field(..., description="System metrics")
    timestamp: datetime = Field(default_factory=lambda: datetime.now())
    
    class Config:
        schema_extra = {
            "example": {
                "metrics": {
                    "requests_total": 10000,
                    "requests_per_second": 50.5,
                    "error_rate": 0.001,
                    "p50_latency_ms": 100,
                    "p95_latency_ms": 250,
                    "p99_latency_ms": 500,
                    "active_connections": 25,
                    "cpu_usage_percent": 45.2,
                    "memory_usage_mb": 512,
                    "model_inference_time_ms": 50,
                    "vendor_availability": {
                        "vendor_a": 0.999,
                        "vendor_b": 0.995
                    }
                },
                "timestamp": "2024-01-14T10:30:00+08:00"
            }
        }


# ============= Complete KYC Flow Request/Response =============
class CompleteKYCRequest(BaseModel):
    """Complete KYC verification request (all-in-one)"""
    image_base64: str = Field(..., description="Front document image (base64)")
    back_image_base64: Optional[str] = Field(None, description="Back document image (base64)")
    selfie_base64: Optional[str] = Field(None, description="Selfie image (base64)")
    liveness_results: Optional[Dict[str, Any]] = Field(None, description="Liveness check results")
    document_type: Optional[DocumentType] = Field(None, description="Expected document type")
    personal_info: Optional[Dict[str, Any]] = Field(None, description="Personal information")
    device_info: Optional[Dict[str, Any]] = Field(None, description="Device information")
    session_id: Optional[str] = Field(None, description="Session ID")
    
    class Config:
        schema_extra = {
            "example": {
                "image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
                "back_image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
                "selfie_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
                "liveness_results": {"head_turn": True, "blink_or_nod": True, "details": {"focus_avg": 12.3}},  # type: ignore[reportGeneralTypeIssues]
                "document_type": "PHILIPPINE_ID",
                "personal_info": {
                    "full_name": "JUAN DELA CRUZ",
                    "birth_date": "1990-01-01"
                },
                "device_info": {
                    "ip": "120.29.100.50",
                    "user_agent": "Mozilla/5.0...",
                    "device_id": "dev_123"
                },
                "session_id": "sess_abc123"
            }
        }


# ============= Face Scan Endpoints =============
class FaceLockCheckRequest(BaseModel):
    """Request for face lock detection"""
    session_id: str = Field(..., description="Session identifier")
    frame_metadata: Dict[str, Any] = Field(..., description="Frame metadata (dimensions, face bbox, etc)")
    timestamp_ms: int = Field(..., description="Client timestamp in milliseconds")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess_abc123",
                "frame_metadata": {
                    "width": 640,
                    "height": 480,
                    "face_bbox": {"x": 200, "y": 150, "width": 240, "height": 280},
                    "brightness": {"mean": 128, "p05": 45, "p95": 210},
                    "sharpness": 0.85
                },
                "timestamp_ms": 1642345678901
            }
        }


class FaceLockCheckResponse(BaseModel):
    """Response for face lock detection"""
    ok: bool = Field(..., description="Whether face position is acceptable")
    lock: bool = Field(..., description="Whether face lock is achieved (stable for required duration)")
    reasons: List[str] = Field(default_factory=list, description="Reasons for not achieving lock")
    thresholds: Dict[str, Any] = Field(..., description="Applied thresholds")
    stability_ms: int = Field(..., description="Current stability duration in milliseconds")
    
    class Config:
        schema_extra = {
            "example": {
                "ok": True,
                "lock": True,
                "reasons": [],
                "thresholds": {
                    "bbox_fill_min": 0.3,
                    "centering_tolerance": 0.15,
                    "stability_min_ms": 900
                },
                "stability_ms": 950
            }
        }


class FacePADPreGateRequest(BaseModel):
    """Request for passive PAD pre-gate check"""
    session_id: str = Field(..., description="Session identifier")
    image_base64: str = Field(..., description="Face image in base64")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess_abc123",
                "image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
                "metadata": {"device_id": "dev_123", "capture_source": "front_camera"}
            }
        }


class FacePADPreGateResponse(BaseModel):
    """Response for passive PAD pre-gate check"""
    passive_score: float = Field(..., description="Passive liveness score (0-1)")
    spoof_detected: bool = Field(..., description="Whether spoofing is detected")
    spoof_type: Optional[str] = Field(None, description="Type of spoof detected if any")
    flags: Dict[str, bool] = Field(..., description="Specific spoof detection flags")
    confidence: float = Field(..., description="Overall confidence in the assessment")
    
    class Config:
        schema_extra = {
            "example": {
                "passive_score": 0.92,
                "spoof_detected": False,
                "spoof_type": None,
                "flags": {
                    "moire_pattern": False,
                    "flat_texture": False,
                    "uniform_glare": False,
                    "screen_detected": False
                },
                "confidence": 0.95
            }
        }


class FaceChallengeScriptRequest(BaseModel):
    """Request for challenge script generation"""
    session_id: str = Field(..., description="Session identifier")
    challenge_count: Optional[int] = Field(2, description="Number of challenges to generate")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess_abc123",
                "challenge_count": 2
            }
        }


class FaceChallengeAction(BaseModel):
    """Individual challenge action"""
    action_id: str = Field(..., description="Unique action identifier")
    action_type: str = Field(..., description="Type of action (blink, smile, turn_left, turn_right, nod)")
    instruction: str = Field(..., description="Human-readable instruction")
    timeout_ms: int = Field(..., description="Maximum time allowed for this action")
    validation_params: Dict[str, Any] = Field(..., description="Parameters for validating this action")


class FaceChallengeScriptResponse(BaseModel):
    """Response with challenge script"""
    session_id: str = Field(..., description="Session identifier")
    challenge_id: str = Field(..., description="Unique challenge identifier")
    actions: List[FaceChallengeAction] = Field(..., description="Ordered list of actions to perform")
    total_timeout_ms: int = Field(..., description="Total timeout for all actions")
    expires_at: datetime = Field(..., description="When this challenge expires")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess_abc123",
                "challenge_id": "chal_xyz789",
                "actions": [
                    {
                        "action_id": "act_1",
                        "action_type": "blink",
                        "instruction": "Please blink your eyes",
                        "timeout_ms": 3500,
                        "validation_params": {"ear_threshold": 0.2, "min_duration_ms": 100}
                    },
                    {
                        "action_id": "act_2",
                        "action_type": "turn_left",
                        "instruction": "Please turn your head to the left",
                        "timeout_ms": 3500,
                        "validation_params": {"yaw_threshold": -30, "tolerance": 5}
                    }
                ],
                "total_timeout_ms": 7000,
                "expires_at": "2025-01-16T14:30:07+08:00"
            }
        }


class FaceChallengeVerifyRequest(BaseModel):
    """Request to verify challenge completion"""
    session_id: str = Field(..., description="Session identifier")
    challenge_id: str = Field(..., description="Challenge identifier from script")
    action_results: List[Dict[str, Any]] = Field(..., description="Results for each action")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess_abc123",
                "challenge_id": "chal_xyz789",
                "action_results": [
                    {
                        "action_id": "act_1",
                        "completed": True,
                        "metrics": {"ear_min": 0.15, "duration_ms": 150},
                        "timestamp_ms": 1642345678901
                    },
                    {
                        "action_id": "act_2",
                        "completed": True,
                        "metrics": {"yaw_angle": -32.5},
                        "timestamp_ms": 1642345682401
                    }
                ]
            }
        }


class FaceChallengeVerifyResponse(BaseModel):
    """Response for challenge verification"""
    verified: bool = Field(..., description="Whether all challenges passed")
    challenge_results: List[Dict[str, Any]] = Field(..., description="Detailed results per action")
    overall_score: float = Field(..., description="Overall challenge completion score (0-1)")
    reasons: List[str] = Field(default_factory=list, description="Reasons for failure if any")
    
    class Config:
        schema_extra = {
            "example": {
                "verified": True,
                "challenge_results": [
                    {"action_id": "act_1", "passed": True, "score": 0.95},
                    {"action_id": "act_2", "passed": True, "score": 0.88}
                ],
                "overall_score": 0.915,
                "reasons": []
            }
        }


class FaceBurstUploadRequest(BaseModel):
    """Request for burst frame upload"""
    session_id: str = Field(..., description="Session identifier")
    frames: List[str] = Field(..., description="List of base64 encoded frames")
    capture_duration_ms: int = Field(..., description="Total capture duration")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Capture metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess_abc123",
                "frames": [
                    "data:image/jpeg;base64,/9j/4AAQSkZJRg...",
                    "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
                ],
                "capture_duration_ms": 3200,
                "metadata": {"fps": 30, "resolution": "640x480"}
            }
        }


class FaceBurstUploadResponse(BaseModel):
    """Response for burst upload"""
    session_id: str = Field(..., description="Session identifier")
    burst_id: str = Field(..., description="Unique burst identifier")
    frames_received: int = Field(..., description="Number of frames received")
    frames_accepted: int = Field(..., description="Number of frames accepted after validation")
    ready_for_eval: bool = Field(..., description="Whether burst is ready for evaluation")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess_abc123",
                "burst_id": "burst_def456",
                "frames_received": 24,
                "frames_accepted": 22,
                "ready_for_eval": True
            }
        }


class FaceBurstEvalRequest(BaseModel):
    """Request for burst evaluation"""
    session_id: str = Field(..., description="Session identifier")
    burst_id: str = Field(..., description="Burst identifier from upload")
    reference_image_base64: str = Field(..., description="Reference ID photo for matching")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess_abc123",
                "burst_id": "burst_def456",
                "reference_image_base64": "data:image/jpeg;base64,/9j/4AAQSkZJRg..."
            }
        }


class FaceBurstEvalResponse(BaseModel):
    """Response for burst evaluation"""
    match_score: float = Field(..., description="Overall match score (0-1)")
    consensus_ok: bool = Field(..., description="Whether consensus criteria are met")
    frames_used: int = Field(..., description="Number of frames used in evaluation")
    topk_scores: List[float] = Field(..., description="Top-k individual frame scores")
    median_score: float = Field(..., description="Median of top-k scores")
    min_score: float = Field(..., description="Minimum score in top-k")
    confidence: float = Field(..., description="Confidence in the evaluation")
    
    class Config:
        schema_extra = {
            "example": {
                "match_score": 0.68,
                "consensus_ok": True,
                "frames_used": 5,
                "topk_scores": [0.72, 0.70, 0.68, 0.65, 0.63],
                "median_score": 0.68,
                "min_score": 0.63,
                "confidence": 0.92
            }
        }


class FaceDecisionRequest(BaseModel):
    """Request for face verification decision"""
    session_id: str = Field(..., description="Session identifier")
    passive_score: float = Field(..., description="Passive PAD score")
    challenges_passed: bool = Field(..., description="Whether challenges were passed")
    consensus_ok: bool = Field(..., description="Whether consensus criteria met")
    match_score: float = Field(..., description="Biometric match score")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional context")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess_abc123",
                "passive_score": 0.85,
                "challenges_passed": True,
                "consensus_ok": True,
                "match_score": 0.68,
                "metadata": {"device_trust_score": 0.9}
            }
        }


class FaceDecisionResponse(BaseModel):
    """Response with face verification decision"""
    decision: DecisionType = Field(..., description="Final decision")
    reasons: List[str] = Field(..., description="Human-readable reasons for decision")
    policy_version: str = Field(..., description="Policy version used")
    thresholds_applied: Dict[str, Any] = Field(..., description="Thresholds used in decision")
    risk_indicators: List[str] = Field(default_factory=list, description="Risk indicators if any")
    confidence: float = Field(..., description="Confidence in decision")
    
    class Config:
        schema_extra = {
            "example": {
                "decision": "approve",
                "reasons": ["All biometric checks passed", "High confidence match"],
                "policy_version": "1.0.0",
                "thresholds_applied": {
                    "pad_min": 0.70,
                    "match_min": 0.62,
                    "consensus_frames_min": 3
                },
                "risk_indicators": [],
                "confidence": 0.94
            }
        }


class FaceTelemetryEvent(BaseModel):
    """Face scan telemetry event"""
    session_id: str = Field(..., description="Session identifier")
    event_type: str = Field(..., description="Event type")
    timestamp_ms: int = Field(..., description="Event timestamp in milliseconds")
    data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Event-specific data")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess_abc123",
                "event_type": "FACE_LOCK",
                "timestamp_ms": 1642345678901,
                "data": {"lock_time_ms": 1250, "attempts": 2}
            }
        }


class FaceTelemetryRequest(BaseModel):
    """Request to submit telemetry events"""
    events: List[FaceTelemetryEvent] = Field(..., description="List of telemetry events")
    
    class Config:
        schema_extra = {
            "example": {
                "events": [
                    {
                        "session_id": "sess_abc123",
                        "event_type": "FACE_SEARCHING",
                        "timestamp_ms": 1642345677651,
                        "data": {}
                    },
                    {
                        "session_id": "sess_abc123",
                        "event_type": "FACE_LOCK",
                        "timestamp_ms": 1642345678901,
                        "data": {"lock_time_ms": 1250}
                    }
                ]
            }
        }


class FaceTelemetryResponse(BaseModel):
    """Response for telemetry submission"""
    received: int = Field(..., description="Number of events received")
    processed: int = Field(..., description="Number of events processed")
    
    class Config:
        schema_extra = {
            "example": {
                "received": 2,
                "processed": 2
            }
        }


class FaceMetricsResponse(BaseModel):
    """Face scan metrics response"""
    time_to_lock_ms: Dict[str, float] = Field(..., description="Time to lock statistics")
    cancel_rate: float = Field(..., description="Session cancellation rate")
    challenge_success_rate: float = Field(..., description="Challenge completion rate")
    median_match_score: float = Field(..., description="Median biometric match score")
    passive_pad_fmr: float = Field(..., description="PAD False Match Rate")
    passive_pad_fnmr: float = Field(..., description="PAD False Non-Match Rate")
    total_sessions: int = Field(..., description="Total face scan sessions")
    successful_sessions: int = Field(..., description="Successfully completed sessions")
    
    class Config:
        schema_extra = {
            "example": {
                "time_to_lock_ms": {"p50": 1150, "p95": 2300, "p99": 2850},
                "cancel_rate": 0.12,
                "challenge_success_rate": 0.96,
                "median_match_score": 0.71,
                "passive_pad_fmr": 0.008,
                "passive_pad_fnmr": 0.025,
                "total_sessions": 10000,
                "successful_sessions": 8800
            }
        }


class CompleteKYCResponse(BaseModel):
    """Complete KYC verification response"""
    session_id: str = Field(..., description="Session ID")
    decision: DecisionType = Field(..., description="Final decision")
    confidence: float = Field(..., description="Overall confidence")
    risk_score: float = Field(..., description="Risk score")
    risk_level: RiskLevel = Field(..., description="Risk level")
    validation: ValidateResponse = Field(..., description="Validation results")
    extraction: ExtractResponse = Field(..., description="Extraction results")
    scoring: ScoreResponse = Field(..., description="Scoring results")
    decision_details: DecideResponse = Field(..., description="Decision details")
    issuer_verification: Optional[IssuerVerifyResponse] = Field(None, description="Issuer verification")
    aml_screening: Optional[AMLScreenResponse] = Field(None, description="AML screening")
    processing_time_ms: int = Field(..., description="Total processing time")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
