"""
Face Scan API Contracts - Pydantic models for face verification endpoints
Backend-only face scan implementation with strict validation
"""

from typing import Optional, List, Dict, Any, Union, Tuple
from pydantic import BaseModel, Field, validator
from datetime import datetime
from enum import Enum


# ============= Face Scan Enums =============
class FaceLockStatus(str, Enum):
    """Face lock acquisition status"""
    SEARCHING = "searching"
    LOCKED = "locked"
    LOST = "lost"
    FAILED = "failed"


class ChallengeAction(str, Enum):
    """Liveness challenge actions"""
    BLINK = "blink"
    NOD = "nod"
    TURN_LEFT = "turn_left"
    TURN_RIGHT = "turn_right"
    SMILE = "smile"
    OPEN_MOUTH = "open_mouth"


class PADResult(str, Enum):
    """Presentation Attack Detection result"""
    GENUINE = "genuine"
    SPOOF = "spoof"
    UNCERTAIN = "uncertain"


class FaceDecision(str, Enum):
    """Face verification decision"""
    APPROVE = "approve"
    REVIEW = "review"
    DENY = "deny"


# ============= Face Lock Check =============
class FaceLockCheckRequest(BaseModel):
    """Request to check face lock status"""
    session_id: str = Field(..., description="Session identifier")
    frame_metadata: Dict[str, Any] = Field(..., description="Frame metadata (bbox, pose, blur, brightness)")
    timestamp_ms: int = Field(..., description="Client timestamp in milliseconds")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess_1234567890",
                "frame_metadata": {
                    "bbox": [120, 80, 200, 200],
                    "pose": {"yaw": 5.2, "pitch": -3.1, "roll": 0.8},
                    "blur_score": 0.92,
                    "brightness": {"mean": 128, "p05": 45, "p95": 210}
                },
                "timestamp_ms": 1699123456789
            }
        }


class FaceLockCheckResponse(BaseModel):
    """Response for face lock check"""
    ok: bool = Field(..., description="Whether frame passes all checks")
    lock: bool = Field(..., description="Whether lock is achieved (continuous pass ≥900ms)")
    status: FaceLockStatus = Field(..., description="Current lock status")
    reasons: List[str] = Field(default_factory=list, description="Failure reasons if not ok")
    thresholds: Dict[str, Any] = Field(..., description="Applied thresholds")
    continuous_pass_ms: int = Field(0, description="Milliseconds of continuous pass")
    
    class Config:
        schema_extra = {
            "example": {
                "ok": True,
                "lock": True,
                "status": "locked",
                "reasons": [],
                "thresholds": {
                    "bbox_fill_min": 0.15,
                    "centering_max_offset": 0.2,
                    "pose_max_degrees": 15,
                    "blur_min": 0.85,
                    "brightness_mean": [60, 200],
                    "stability_min_ms": 900
                },
                "continuous_pass_ms": 950
            }
        }


# ============= PAD Pre-gate =============
class PADPreGateRequest(BaseModel):
    """Request for passive PAD pre-gate check"""
    session_id: str = Field(..., description="Session identifier")
    image_base64: str = Field(..., description="Base64 encoded face image")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess_1234567890",
                "image_base64": "data:image/jpeg;base64,/9j/4AAQ...",
                "metadata": {"device_model": "iPhone 14 Pro"}
            }
        }


class PADPreGateResponse(BaseModel):
    """Response from PAD pre-gate check"""
    passive_score: float = Field(..., description="Passive liveness score (0-1)")
    result: PADResult = Field(..., description="PAD detection result")
    spoof_indicators: List[str] = Field(default_factory=list, description="Detected spoof indicators")
    proceed: bool = Field(..., description="Whether to proceed with capture")
    
    class Config:
        schema_extra = {
            "example": {
                "passive_score": 0.85,
                "result": "genuine",
                "spoof_indicators": [],
                "proceed": True
            }
        }


# ============= Challenge Sequencer =============
class ChallengeScriptRequest(BaseModel):
    """Request for challenge script generation"""
    session_id: str = Field(..., description="Session identifier")
    difficulty: str = Field("standard", description="Challenge difficulty level")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess_1234567890",
                "difficulty": "standard"
            }
        }


class ChallengeScript(BaseModel):
    """Challenge script with actions and timing"""
    challenge_id: str = Field(..., description="Unique challenge identifier")
    actions: List[ChallengeAction] = Field(..., description="Ordered list of actions")
    ttl_seconds: int = Field(7, description="Time to live for challenge")
    per_action_timeout_ms: int = Field(3500, description="Timeout per action")
    
    class Config:
        schema_extra = {
            "example": {
                "challenge_id": "chal_abc123",
                "actions": ["blink", "turn_left"],
                "ttl_seconds": 7,
                "per_action_timeout_ms": 3500
            }
        }


class ChallengeVerifyRequest(BaseModel):
    """Request to verify challenge completion"""
    session_id: str = Field(..., description="Session identifier")
    challenge_id: str = Field(..., description="Challenge ID to verify")
    action_results: List[Dict[str, Any]] = Field(..., description="Results for each action")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess_1234567890",
                "challenge_id": "chal_abc123",
                "action_results": [
                    {"action": "blink", "ear_values": [0.25, 0.18, 0.22], "timestamp_ms": 1699123456789},
                    {"action": "turn_left", "yaw_values": [-5, -15, -25], "timestamp_ms": 1699123458789}
                ]
            }
        }


class ChallengeVerifyResponse(BaseModel):
    """Response from challenge verification"""
    passed: bool = Field(..., description="Whether all challenges passed")
    action_results: List[Dict[str, Any]] = Field(..., description="Per-action verification results")
    reasons: List[str] = Field(default_factory=list, description="Failure reasons if not passed")
    
    class Config:
        schema_extra = {
            "example": {
                "passed": True,
                "action_results": [
                    {"action": "blink", "passed": True, "confidence": 0.95},
                    {"action": "turn_left", "passed": True, "confidence": 0.88}
                ],
                "reasons": []
            }
        }


# ============= Burst Upload =============
class BurstUploadRequest(BaseModel):
    """Request to upload burst frames"""
    session_id: str = Field(..., description="Session identifier")
    frames: List[str] = Field(..., description="Base64 encoded frames")
    timestamps_ms: List[int] = Field(..., description="Frame timestamps")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    @validator('frames')
    def validate_frame_count(cls, v):
        if len(v) > 24:
            raise ValueError("Maximum 24 frames allowed")
        return v
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess_1234567890",
                "frames": ["data:image/jpeg;base64,/9j/4AAQ..."],
                "timestamps_ms": [1699123456789],
                "metadata": {"capture_duration_ms": 3200}
            }
        }


class BurstUploadResponse(BaseModel):
    """Response from burst upload"""
    upload_id: str = Field(..., description="Unique upload identifier")
    frames_received: int = Field(..., description="Number of frames received")
    frames_accepted: int = Field(..., description="Number of frames accepted after validation")
    storage_path: str = Field(..., description="Temporary storage path (transient)")
    expires_at: datetime = Field(..., description="When frames will be auto-deleted")
    
    class Config:
        schema_extra = {
            "example": {
                "upload_id": "burst_xyz789",
                "frames_received": 20,
                "frames_accepted": 18,
                "storage_path": "/tmp/burst_xyz789",
                "expires_at": "2024-01-01T12:00:00+08:00"
            }
        }


# ============= Consensus Evaluation =============
class BurstEvalRequest(BaseModel):
    """Request to evaluate burst frames"""
    session_id: str = Field(..., description="Session identifier")
    upload_id: str = Field(..., description="Burst upload ID")
    id_photo_base64: str = Field(..., description="Base64 encoded ID photo for matching")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess_1234567890",
                "upload_id": "burst_xyz789",
                "id_photo_base64": "data:image/jpeg;base64,/9j/4AAQ..."
            }
        }


class BurstEvalResponse(BaseModel):
    """Response from burst evaluation"""
    match_score: float = Field(..., description="Median match score from top-k frames")
    consensus_ok: bool = Field(..., description="Whether consensus criteria met")
    frames_used: int = Field(..., description="Number of frames used in consensus")
    topk_scores: List[float] = Field(..., description="Top-k individual frame scores")
    rejected_frames: int = Field(0, description="Frames rejected due to quality")
    
    class Config:
        schema_extra = {
            "example": {
                "match_score": 0.68,
                "consensus_ok": True,
                "frames_used": 5,
                "topk_scores": [0.72, 0.70, 0.68, 0.65, 0.62],
                "rejected_frames": 2
            }
        }


# ============= Face Decision =============
class FaceDecisionRequest(BaseModel):
    """Request for face verification decision"""
    session_id: str = Field(..., description="Session identifier")
    passive_score: float = Field(..., description="Passive PAD score")
    challenges_passed: bool = Field(..., description="Whether challenges passed")
    consensus_ok: bool = Field(..., description="Whether consensus criteria met")
    match_score: float = Field(..., description="Biometric match score")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess_1234567890",
                "passive_score": 0.85,
                "challenges_passed": True,
                "consensus_ok": True,
                "match_score": 0.68,
                "metadata": {"device_model": "iPhone 14 Pro"}
            }
        }


class FaceDecisionResponse(BaseModel):
    """Response with face verification decision"""
    decision: FaceDecision = Field(..., description="Final decision")
    confidence: float = Field(..., description="Decision confidence (0-1)")
    reasons: List[str] = Field(..., description="Decision reasons")
    policy_version: str = Field(..., description="Applied policy version")
    review_required: bool = Field(False, description="Whether manual review needed")
    
    class Config:
        schema_extra = {
            "example": {
                "decision": "approve",
                "confidence": 0.92,
                "reasons": ["All checks passed", "High biometric match"],
                "policy_version": "2024.1.0",
                "review_required": False
            }
        }


# ============= Telemetry =============
class FaceTelemetryEvent(BaseModel):
    """Face scan telemetry event"""
    session_id: str = Field(..., description="Session identifier")
    event_type: str = Field(..., description="Event type")
    timestamp_ms: int = Field(..., description="Event timestamp")
    data: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Event data")
    
    class Config:
        schema_extra = {
            "example": {
                "session_id": "sess_1234567890",
                "event_type": "FACE_LOCK",
                "timestamp_ms": 1699123456789,
                "data": {"lock_time_ms": 1250}
            }
        }


class FaceTelemetryResponse(BaseModel):
    """Response from telemetry submission"""
    accepted: bool = Field(..., description="Whether event was accepted")
    event_id: str = Field(..., description="Assigned event ID")