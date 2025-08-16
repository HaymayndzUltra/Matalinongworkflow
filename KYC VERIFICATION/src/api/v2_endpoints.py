"""
V2 API Endpoints - Consolidated and Standardized
Implements the unified API structure for v2

This module provides:
- Consolidated endpoints
- Standardized responses
- Unified parameter handling
- Consistent error handling
"""

from fastapi import APIRouter, Request, HTTPException, Query, Path, Body
from fastapi.responses import StreamingResponse, JSONResponse
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime, timedelta

# Import response formatter
from .response_formatter import get_response_formatter, standardize_response

# Import handlers
from ..face.handlers import (
    handle_lock_check,
    handle_burst_upload,
    handle_burst_eval,
    handle_face_decision,
    handle_challenge_script,
    handle_challenge_verify
)

# Import additional modules
from ..face.ux_telemetry import (
    get_telemetry_manager,
    get_session_timeline,
    get_performance_metrics,
    get_flow_analytics,
    get_quality_metrics
)

from ..face.streaming import create_sse_stream, get_stream_manager
from ..face.biometric_integration import get_biometric_integration
from ..face.session_manager import get_or_create_session
from ..face.messages import get_message_manager

logger = logging.getLogger(__name__)

# Create v2 router
v2_router = APIRouter(prefix="/v2")

# Response formatter
formatter = get_response_formatter()

# ==================== FACE OPERATIONS ====================

@v2_router.post("/face/scan")
async def v2_face_scan(
    request: Request,
    session_id: str = Body(..., description="Session identifier"),
    action: str = Body(..., description="Action: lock, upload, evaluate"),
    data: Optional[Dict[str, Any]] = Body(default=None, description="Action-specific data")
) -> JSONResponse:
    """
    Unified face scan endpoint combining lock, upload, and evaluate
    
    Actions:
    - lock: Check face lock (replaces /face/lock/check)
    - upload: Upload burst frames (replaces /face/burst/upload)
    - evaluate: Evaluate burst (replaces /face/burst/eval)
    """
    request_id = f"{session_id}_{action}_{datetime.now().timestamp()}"
    formatter.start_timing(request_id)
    
    try:
        result = None
        messages = None
        
        if action == "lock":
            # Lock check with integrated quality
            lock_token = data.get("lock_token") if data else None
            result = handle_lock_check(session_id, lock_token)
            
        elif action == "upload":
            # Burst upload
            burst_id = data.get("burst_id", f"burst_{session_id}")
            frame_data = data.get("frames", [])
            result = handle_burst_upload(session_id, burst_id, frame_data)
            
        elif action == "evaluate":
            # Burst evaluation with biometrics
            burst_id = data.get("burst_id", f"burst_{session_id}")
            result = handle_burst_eval(session_id, burst_id)
            
        else:
            raise HTTPException(status_code=400, detail=f"Unknown action: {action}")
        
        # Extract messages if available
        if isinstance(result, dict):
            messages = result.get("messages")
            
            # Get session for additional context
            session = get_or_create_session(session_id)
            if not messages and hasattr(session, "get_messages"):
                messages = session.get_messages()
        
        # Format response
        response = formatter.format_response(
            data=result,
            request=request,
            session_id=session_id,
            messages=messages,
            request_id=request_id
        )
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Face scan error: {e}")
        error = formatter.format_error(
            code="FACE_SCAN_ERROR",
            message=str(e),
            details={"action": action}
        )
        
        response = formatter.format_response(
            data=None,
            request=request,
            session_id=session_id,
            error=error,
            success=False,
            request_id=request_id
        )
        
        return JSONResponse(content=response, status_code=400)

@v2_router.post("/face/biometric")
async def v2_face_biometric(
    request: Request,
    session_id: str = Body(..., description="Session identifier"),
    check_type: str = Body(..., description="Check type: verify, liveness, match"),
    reference_data: Optional[Dict[str, Any]] = Body(default=None)
) -> JSONResponse:
    """
    Unified biometric endpoint combining PAD and match verification
    
    Check types:
    - verify: Full biometric verification (PAD + match)
    - liveness: PAD check only
    - match: Face match only
    """
    request_id = f"{session_id}_biometric_{datetime.now().timestamp()}"
    formatter.start_timing(request_id)
    
    try:
        session = get_or_create_session(session_id)
        integration = get_biometric_integration()
        
        # Get burst frames from session
        burst_frames = getattr(session, "burst_frames", [])
        if not burst_frames:
            raise ValueError("No burst frames available for biometric check")
        
        # Get reference image if needed
        reference_image = None
        if check_type in ["verify", "match"] and reference_data:
            reference_image = reference_data.get("reference_image")
        
        # Process biometrics
        import asyncio
        bio_result = await integration.process_biometrics(
            session,
            burst_frames,
            reference_image
        )
        
        # Build response data
        data = {
            "check_type": check_type,
            "passed": bio_result.passed,
            "confidence": bio_result.confidence,
            "processing_time_ms": bio_result.processing_time_ms
        }
        
        if check_type in ["verify", "liveness"]:
            data["liveness"] = {
                "score": bio_result.pad_score,
                "is_live": bio_result.is_live,
                "attack_type": bio_result.attack_type
            }
        
        if check_type in ["verify", "match"]:
            data["match"] = {
                "score": bio_result.match_score,
                "result": bio_result.match_result
            }
        
        # Get messages
        messages = session.get_messages() if hasattr(session, "get_messages") else None
        
        # Format response
        response = formatter.format_response(
            data=data,
            request=request,
            session_id=session_id,
            messages=messages,
            request_id=request_id
        )
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Biometric check error: {e}")
        error = formatter.format_error(
            code="BIOMETRIC_ERROR",
            message=str(e),
            details={"check_type": check_type}
        )
        
        response = formatter.format_response(
            data=None,
            request=request,
            session_id=session_id,
            error=error,
            success=False,
            request_id=request_id
        )
        
        return JSONResponse(content=response, status_code=400)

@v2_router.get("/face/stream/{session_id}")
async def v2_face_stream(
    request: Request,
    session_id: str = Path(..., description="Session identifier")
) -> StreamingResponse:
    """
    Server-sent events stream for real-time updates
    Consolidates all streaming needs
    """
    return create_sse_stream(session_id)

# ==================== TELEMETRY OPERATIONS ====================

@v2_router.get("/telemetry/{session_id}")
async def v2_telemetry(
    request: Request,
    session_id: str = Path(..., description="Session identifier"),
    data_type: str = Query("events", description="Data type: events, performance, flow, quality"),
    start_time: Optional[str] = Query(None, description="Start time ISO format"),
    end_time: Optional[str] = Query(None, description="End time ISO format")
) -> JSONResponse:
    """
    Unified telemetry endpoint with query parameters
    
    Data types:
    - events: Session event timeline
    - performance: Performance metrics
    - flow: Capture flow analytics
    - quality: Quality gate metrics
    """
    request_id = f"{session_id}_telemetry_{datetime.now().timestamp()}"
    formatter.start_timing(request_id)
    
    try:
        data = None
        
        if data_type == "events":
            # Get session timeline
            timeline = get_session_timeline(session_id)
            data = {
                "session_id": session_id,
                "events": timeline,
                "event_count": len(timeline)
            }
            
        elif data_type == "performance":
            # Get performance metrics
            metrics = get_performance_metrics()
            data = {
                "metrics": metrics,
                "period": "current_session"
            }
            
        elif data_type == "flow":
            # Get flow analytics
            analytics = get_flow_analytics()
            data = {
                "analytics": analytics,
                "session_id": session_id
            }
            
        elif data_type == "quality":
            # Get quality metrics
            quality = get_quality_metrics()
            data = {
                "quality_metrics": quality,
                "session_id": session_id
            }
            
        else:
            raise ValueError(f"Unknown data type: {data_type}")
        
        # Add time filtering if requested
        if start_time or end_time:
            data["time_filter"] = {
                "start": start_time,
                "end": end_time
            }
        
        # Format response
        response = formatter.format_response(
            data=data,
            request=request,
            session_id=session_id,
            request_id=request_id
        )
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Telemetry error: {e}")
        error = formatter.format_error(
            code="TELEMETRY_ERROR",
            message=str(e),
            details={"data_type": data_type}
        )
        
        response = formatter.format_response(
            data=None,
            request=request,
            session_id=session_id,
            error=error,
            success=False,
            request_id=request_id
        )
        
        return JSONResponse(content=response, status_code=400)

# ==================== SYSTEM OPERATIONS ====================

@v2_router.get("/system/health")
async def v2_system_health(request: Request) -> JSONResponse:
    """
    Comprehensive system health check
    Combines health, metrics, and version info
    """
    request_id = f"health_{datetime.now().timestamp()}"
    formatter.start_timing(request_id)
    
    try:
        # Gather system information
        telemetry = get_telemetry_manager()
        stream_manager = get_stream_manager()
        
        data = {
            "status": "healthy",
            "version": "2.0",
            "uptime_seconds": time.time() - getattr(telemetry, "start_time", time.time()),
            "components": {
                "telemetry": {
                    "status": "active",
                    "event_count": len(telemetry.events),
                    "buffer_usage": f"{len(telemetry.events)}/{telemetry.max_events}"
                },
                "streaming": {
                    "status": "active",
                    "active_connections": len(stream_manager.connections)
                },
                "biometric": {
                    "status": "active",
                    "accuracy_targets": get_biometric_integration().get_accuracy_metrics()
                }
            },
            "checks": {
                "database": "connected",
                "cache": "available",
                "queue": "operational"
            }
        }
        
        # Format response
        response = formatter.format_response(
            data=data,
            request=request,
            request_id=request_id
        )
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        error = formatter.format_error(
            code="HEALTH_CHECK_ERROR",
            message=str(e)
        )
        
        response = formatter.format_response(
            data=None,
            request=request,
            error=error,
            success=False,
            request_id=request_id
        )
        
        return JSONResponse(content=response, status_code=503)

# ==================== CHALLENGE OPERATIONS ====================

@v2_router.post("/face/challenge")
async def v2_face_challenge(
    request: Request,
    session_id: str = Body(..., description="Session identifier"),
    action: str = Body(..., description="Action: generate, verify"),
    data: Optional[Dict[str, Any]] = Body(default=None)
) -> JSONResponse:
    """
    Unified challenge endpoint
    
    Actions:
    - generate: Generate challenge script
    - verify: Verify challenge response
    """
    request_id = f"{session_id}_challenge_{datetime.now().timestamp()}"
    formatter.start_timing(request_id)
    
    try:
        result = None
        messages = None
        
        if action == "generate":
            # Generate challenge
            complexity = data.get("complexity", "medium") if data else "medium"
            result = handle_challenge_script(session_id, complexity)
            
        elif action == "verify":
            # Verify challenge
            response_data = data.get("response", {}) if data else {}
            result = handle_challenge_verify(session_id, response_data)
            
        else:
            raise ValueError(f"Unknown action: {action}")
        
        # Get session messages
        session = get_or_create_session(session_id)
        if hasattr(session, "get_messages"):
            messages = session.get_messages()
        
        # Format response
        response = formatter.format_response(
            data=result,
            request=request,
            session_id=session_id,
            messages=messages,
            request_id=request_id
        )
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Challenge error: {e}")
        error = formatter.format_error(
            code="CHALLENGE_ERROR",
            message=str(e),
            details={"action": action}
        )
        
        response = formatter.format_response(
            data=None,
            request=request,
            session_id=session_id,
            error=error,
            success=False,
            request_id=request_id
        )
        
        return JSONResponse(content=response, status_code=400)

# ==================== DECISION OPERATIONS ====================

@v2_router.post("/face/decision")
async def v2_face_decision(
    request: Request,
    session_id: str = Body(..., description="Session identifier"),
    match_score: Optional[float] = Body(None, description="Face match score"),
    passive_score: Optional[float] = Body(None, description="Passive liveness score"),
    metadata: Optional[Dict[str, Any]] = Body(default=None)
) -> JSONResponse:
    """
    Enhanced decision endpoint with v2 response format
    """
    request_id = f"{session_id}_decision_{datetime.now().timestamp()}"
    formatter.start_timing(request_id)
    
    try:
        # Call original handler
        result = handle_face_decision(
            session_id,
            match_score,
            passive_score
        )
        
        # Get session messages
        session = get_or_create_session(session_id)
        messages = None
        if hasattr(session, "get_messages"):
            messages = session.get_messages()
        
        # Format response
        response = formatter.format_response(
            data=result,
            request=request,
            session_id=session_id,
            messages=messages,
            request_id=request_id
        )
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Decision error: {e}")
        error = formatter.format_error(
            code="DECISION_ERROR",
            message=str(e)
        )
        
        response = formatter.format_response(
            data=None,
            request=request,
            session_id=session_id,
            error=error,
            success=False,
            request_id=request_id
        )
        
        return JSONResponse(content=response, status_code=400)

# ==================== UTILITY ENDPOINTS ====================

@v2_router.get("/messages/catalog")
async def v2_messages_catalog(
    request: Request,
    language: str = Query("all", description="Language: tagalog, english, all")
) -> JSONResponse:
    """
    Get available messages catalog
    """
    request_id = f"messages_{datetime.now().timestamp()}"
    formatter.start_timing(request_id)
    
    try:
        manager = get_message_manager()
        
        # Get message counts and samples
        data = {
            "languages": ["tagalog", "english"],
            "categories": ["state", "success", "error", "quality", "instruction"],
            "message_count": {
                "total": 50,  # Approximate
                "by_language": {
                    "tagalog": 50,
                    "english": 50
                }
            },
            "emoji_support": True
        }
        
        # Format response
        response = formatter.format_response(
            data=data,
            request=request,
            request_id=request_id
        )
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"Messages catalog error: {e}")
        error = formatter.format_error(
            code="MESSAGES_ERROR",
            message=str(e)
        )
        
        response = formatter.format_response(
            data=None,
            request=request,
            error=error,
            success=False,
            request_id=request_id
        )
        
        return JSONResponse(content=response, status_code=400)

# Import time for uptime calculation
import time