"""
Face Scan Endpoint Handlers
Integrates geometry analysis, PAD scoring, and threshold validation

This module implements the actual endpoint logic for face scanning:
- Lock checking with stability requirements
- PAD pre-gate validation
- Challenge generation and verification
- Burst frame processing
- Final decision making
"""

import time
import uuid
import hashlib
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum

import numpy as np
from fastapi import HTTPException, status

from .geometry import (
    BoundingBox,
    analyze_face_geometry,
    format_geometry_feedback,
    StabilityTracker,
    QualityIssue
)
from .pad_scorer import (
    analyze_pad,
    format_pad_feedback,
    AttackType
)
# Legacy telemetry removed - using ux_telemetry instead
from .ux_telemetry import (
    track_ux_event,
    track_capture_event,
    UXEventType
)
from .session_manager import (
    get_session_manager,
    StatusCode,
    ReasonCode,
    QUALITY_GATES,
    EnhancedSessionState,
    CaptureState,
    DocumentSide
)
from ..config.threshold_manager import ThresholdManager

logger = logging.getLogger(__name__)


# ============= DATA STRUCTURES =============

class ChallengeType(Enum):
    """Types of liveness challenges"""
    BLINK = "blink"
    HEAD_TURN_LEFT = "head_turn_left"
    HEAD_TURN_RIGHT = "head_turn_right"
    NOD = "nod"
    SMILE = "smile"


# Global session storage (in production, use Redis or similar)
_sessions: Dict[str, EnhancedSessionState] = {}


def get_or_create_session(session_id: Optional[str] = None) -> EnhancedSessionState:
    """Get existing session or create new one"""
    if session_id and session_id in _sessions:
        session = _sessions[session_id]
        # Track activity via request_count increment
        session.request_count += 1
        return session
    
    # Create new session
    new_id = session_id or str(uuid.uuid4())
    session = EnhancedSessionState(
        session_id=new_id,
        stability_tracker=StabilityTracker(history=[])
    )
    _sessions[new_id] = session
    
    # Clean old sessions (older than 5 minutes)
    current_time = time.time()
    expired = [
        sid for sid, s in _sessions.items()
        if current_time - s.created_at > 300
    ]
    for sid in expired:
        del _sessions[sid]
    
    return session


# ============= LOCK CHECK ENDPOINT =============

def handle_lock_check(
    session_id: str,
    bbox: Dict[str, float],
    frame_width: int,
    frame_height: int,
    landmarks: Optional[Dict[str, Tuple[float, float]]] = None,
    gray_face_region: Optional[np.ndarray] = None,
    metrics: Optional[Dict[str, Any]] = None,
    lock_token: Optional[str] = None
) -> Dict[str, Any]:
    """
    Handle /face/lock/check endpoint
    
    Evaluates if face meets lock conditions:
    - Proper geometry (size, centering, pose)
    - Sufficient quality (brightness, sharpness)
    - Stability for required duration (900ms default)
    
    Args:
        session_id: Session identifier
        bbox: Face bounding box {x, y, width, height}
        frame_width: Frame width in pixels
        frame_height: Frame height in pixels
        landmarks: Optional facial landmarks
        gray_face_region: Optional grayscale face for quality analysis
    
    Returns:
        Response with lock status and feedback
    """
    start_time = time.time()
    session_mgr = get_session_manager()
    
    # Check rate limit first
    allowed, retry_after_ms = session_mgr.check_rate_limit(session_id)
    if not allowed:
        raise HTTPException(
            status_code=StatusCode.TOO_MANY_REQUESTS,
            detail={
                'error': 'Rate limit exceeded',
                'reason': 'RATE_LIMIT_EXCEEDED',
                'retry_after_ms': retry_after_ms
            }
        )
    
    # Get enhanced session
    session = session_mgr.get_or_create_session(session_id)
    session.lock_attempt_count += 1
    
    # Start response timing for cancel-on-jitter measurement
    session.start_response_timing()
    
    # Log session start if first request
    if session.request_count == 1:
        from .audit_logger import audit_event, AuditEventType
        audit_event(AuditEventType.SESSION_START, session_id, {'source': 'face_lock_check'})
    
    # Track lock attempt
    track_ux_event(
        event_type="capture.lock_attempt",
        session_id=session_id,
        data={},
        context={'source': 'face_lock_check'}
    )
    
    # If lock_token provided, validate it
    if lock_token:
        valid, reason, retry_after = session_mgr.validate_lock_token(lock_token, session_id)
        if not valid:
            if reason == ReasonCode.COUNTDOWN_NOT_ELAPSED:
                # Return 425 Too Early
                response = {
                    'ok': False,
                    'error': 'Too early',
                    'reason': reason,
                    'retry_after_ms': retry_after
                }
                response['status_code'] = StatusCode.TOO_EARLY
                return response
            else:
                raise HTTPException(
                    status_code=StatusCode.BAD_REQUEST,
                    detail={'error': 'Invalid token', 'reason': reason}
                )
    
    # Check timing gates (cooldown, anti-double capture)
    status_code, reason, retry_after = session.check_timing_gates()
    if status_code != StatusCode.OK:
        if status_code == StatusCode.CONFLICT:
            response = {
                'ok': False,
                'error': 'Timing conflict',
                'reason': reason,
                'retry_after_ms': retry_after
            }
            response['status_code'] = status_code
            return response
    
    # Check quality gates if metrics provided
    quality_ok = True
    quality_reasons = []
    
    if metrics:
        # Check hard quality gates
        quality_ok, quality_reasons = session.check_quality_gates(metrics)
        
        # If quality gates fail, return immediately
        if not quality_ok:
            # Transition back to SEARCHING if we were in LOCKED or COUNTDOWN
            if session.capture_state in [CaptureState.LOCKED, CaptureState.COUNTDOWN]:
                session.transition_to(
                    CaptureState.SEARCHING,
                    reason=f"quality_failed:{','.join(quality_reasons)}"
                )
            return {
                'ok': False,
                'lock': False,
                'session_id': session.session_id,
                'reasons': quality_reasons,
                'metrics': metrics
            }
    
    # Basic geometry checks (existing logic)
    face_bbox = BoundingBox(
        x=bbox['x'],
        y=bbox['y'],
        width=bbox['width'],
        height=bbox['height']
    )
    
    # Calculate fill ratio for ID check
    fill_ratio = (face_bbox.width * face_bbox.height) / (frame_width * frame_height)
    
    # Check ID fill requirements (0.88-0.94)
    if fill_ratio < QUALITY_GATES['id_fill_min'] or fill_ratio > QUALITY_GATES['id_fill_max']:
        quality_reasons.append(ReasonCode.FILL_OUT_OF_RANGE)
        quality_ok = False
    
    # Check ROI size
    roi_pixels = int(face_bbox.width * face_bbox.height)
    if roi_pixels < QUALITY_GATES['roi_min_px']:
        quality_reasons.append(ReasonCode.ROI_TOO_SMALL)
        quality_ok = False
    
    # If all quality checks pass, generate lock token
    lock_token_response = {}
    if quality_ok:
        # Generate new lock token
        new_token = session.generate_lock_token()
        lock_token_response = {
            'lock_token': new_token.token,
            'not_before_ms': new_token.not_before_ms,
            'expires_at': new_token.expires_at
        }
        
        # Mark lock achieved
        session.lock_open_ts = time.time()
        session.lock_achieved_at = time.time()  # For compatibility
        
        # Transition to LOCKED state
        session.transition_to(
            CaptureState.LOCKED, 
            reason=f"quality_ok:{quality_ok},fill_ratio:{fill_ratio:.3f}"
        )
        
        # Record timing event for lock achieved
        session.record_timing_event("lock_achieved")
        
        track_capture_event(
            session_id=session_id,
            capture_type="lock_achieved",
            quality_score=consensus_quality,
            success=True
        )
        
        logger.info(f"Lock achieved: session={session_id}, state={session.capture_state.value}, token={new_token.token[:8]}...")
    
    # Calculate response time
    response_time_ms = (time.time() - start_time) * 1000
    # Response time is tracked via timing metadata in session
    
    # Include state info in response
    state_info = session.get_state_info()
    
    # Get timing metadata for animation synchronization
    timing_metadata = session.get_timing_metadata()
    
    # Set quality issues for message generation
    if quality_reasons:
        session.set_quality_issues(quality_reasons)
    else:
        session.set_quality_issues([])
    
    # Enhanced quality gates check (UX Requirement F)
    try:
        from .quality_gates import get_quality_manager
    except ImportError:
        from face.quality_gates import get_quality_manager
    
    quality_manager = get_quality_manager()
    
    # Prepare metrics for quality gates
    quality_metrics = {
        "focus": focus,
        "motion": motion,
        "glare": glare,
        "corners": corners,
        "fill_ratio": fill_ratio
    }
    
    # Check quality with cancel-on-jitter
    quality_result = quality_manager.check_quality(quality_metrics)
    
    # Override quality_ok if cancel detected
    if quality_result.cancel_reason:
        quality_ok = False
        # Add cancel reason to quality_reasons
        quality_reasons.insert(0, quality_result.cancel_reason.value.upper())
        # Set error for messages
        session.set_error("cancelled")
        # Force state rollback if locked/countdown
        if session.capture_state in [CaptureState.LOCKED, CaptureState.COUNTDOWN]:
            # Rollback to searching state
            session.transition_to(CaptureState.SEARCHING, reason=f"cancel:{quality_result.cancel_reason.value}")
            logger.info(f"Cancel-on-jitter: rolled back to SEARCHING (reason: {quality_result.cancel_reason.value})")
    
    # Update session quality issues with hints
    if quality_result.hints:
        session.set_quality_issues(quality_reasons + quality_result.hints)
    else:
        session.set_quality_issues(quality_reasons)
    
    # Get localized messages (now includes quality gate messages)
    messages = session.get_messages()
    
    # Override with quality gate messages if available
    if quality_result.tagalog_message:
        messages["primary"] = quality_result.tagalog_message
        if quality_result.english_message:
            messages["primary_en"] = quality_result.english_message
    
    # Add quality hints to messages
    if quality_result.hints:
        messages["hints"] = quality_result.hints
    
    # Check cancel-on-jitter timing requirement
    if quality_result.cancel_reason and session.capture_state in [CaptureState.LOCKED, CaptureState.COUNTDOWN]:
        meets_timing = quality_result.response_time_ms < 50
        if not meets_timing:
            logger.warning(f"Cancel-on-jitter response time {quality_result.response_time_ms:.1f}ms exceeds 50ms target")
        else:
            logger.info(f"Cancel-on-jitter achieved {quality_result.response_time_ms:.1f}ms response time")
    
    # Build response
    response = {
        'ok': quality_ok,
        'lock': quality_ok,
        'session_id': session.session_id,
        'state': state_info,
        'timing': timing_metadata,  # Include timing metadata for UX Requirement B
        'messages': messages,  # Include localized messages for UX Requirement C
        'quality_gates': quality_result.to_dict(),  # Include quality gate results for UX Requirement F
        'reasons': quality_reasons if not quality_ok else [],
        'metrics': {
            'fill_ratio': round(fill_ratio, 3),
            'roi_pixels': roi_pixels,
            'response_time_ms': round(response_time_ms, 1),
            'stability_score': quality_manager.get_stability_score(),
            **(metrics or {})
        },
        **lock_token_response  # Include token info if lock achieved
    }
    
    logger.info(f"Lock check: session={session_id}, lock={quality_ok}, time={response_time_ms:.1f}ms")
    
    return response


# ============= PAD PRE-GATE ENDPOINT =============

def handle_pad_pregate(
    session_id: str,
    gray_image: np.ndarray,
    rgb_image: np.ndarray
) -> Dict[str, Any]:
    """
    Handle /face/pad/pre endpoint
    
    Performs passive liveness detection before allowing capture.
    
    Args:
        session_id: Session identifier
        gray_image: Grayscale face image
        rgb_image: RGB face image
    
    Returns:
        Response with PAD score and decision
    """
    start_time = time.time()
    
    # Log PAD check event
    from .audit_logger import audit_event, AuditEventType
    audit_event(AuditEventType.PAD_CHECK, session_id, {'source': 'pad_pregate'})
    
    # Get session
    session = get_or_create_session(session_id)
    
    # Get thresholds
    tm = ThresholdManager()
    pad_thresholds = tm.get_face_pad_thresholds()
    
    # Analyze PAD
    pad_result = analyze_pad(
        gray_image=gray_image,
        rgb_image=rgb_image,
        thresholds={
            'pad_score_min': pad_thresholds['score_min'],
            'spoof_threshold': pad_thresholds['spoof_threshold']
        }
    )
    
    # Store score
    session.pad_scores.append(pad_result.overall_score)
    
    # Format feedback
    feedback = format_pad_feedback(pad_result)
    
    # Calculate response time
    response_time_ms = (time.time() - start_time) * 1000
    
    # Build response
    response = {
        'ok': pad_result.is_live,
        'session_id': session.session_id,
        'pad_score': round(pad_result.overall_score, 3),
        'confidence': round(pad_result.confidence, 3),
        'likely_attack': feedback['likely_attack'],
        'reasons': pad_result.reasons,
        'scores': feedback['scores'],
        'metrics': {
            'response_time_ms': round(response_time_ms, 1),
            **feedback['details']
        },
        'thresholds': {
            'pad_score_min': pad_thresholds['score_min'],
            'spoof_threshold': pad_thresholds['spoof_threshold']
        }
    }
    
    logger.info(f"PAD pre-gate: session={session_id}, live={pad_result.is_live}, score={pad_result.overall_score:.3f}")
    
    return response


# ============= CHALLENGE SCRIPT ENDPOINT =============

def handle_challenge_script(
    session_id: str,
    complexity: str = "medium"
) -> Dict[str, Any]:
    """
    Handle /face/challenge/script endpoint
    
    Generates a random challenge script for active liveness.
    
    Args:
        session_id: Session identifier
        complexity: Challenge complexity (easy/medium/hard)
    
    Returns:
        Challenge script with actions and timing
    """
    from .challenge_generator import generate_challenge_script
    # Track challenge generation
    track_ux_event(
        event_type="challenge.generated",
        session_id=session_id,
        data={'complexity': complexity},
        context={'source': 'face_challenge_script'}
    )
    
    # Get session
    session = get_or_create_session(session_id)
    
    # Get thresholds
    tm = ThresholdManager()
    challenge_thresholds = tm.get_face_challenge_thresholds()
    
    # Map complexity string to int
    complexity_map = {
        'easy': 1,
        'medium': 2,
        'hard': 3
    }
    complexity_int = complexity_map.get(complexity, 2)
    
    # Generate challenge using the new generator
    script_dict = generate_challenge_script(session_id, complexity_int)
    
    # Format response to match existing API
    script = {
        'challenge_id': script_dict['challenge_id'],
        'session_id': session.session_id,
        'created_at': datetime.fromtimestamp(script_dict['created_at']).isoformat(),
        'ttl_ms': int(challenge_thresholds['ttl_ms']),
        'actions': [
            {
                'type': step['action'],
                'duration_ms': step['duration_ms'],
                'instruction': step['instruction']
            }
            for step in script_dict['steps']
        ],
        'total_duration_ms': sum(s['duration_ms'] for s in script_dict['steps']),
        'complexity': complexity
    }
    
    # Store in session
    session.challenge_script = script
    session.challenge_id = script_dict['challenge_id']
    
    logger.info(f"Challenge script: session={session_id}, actions={len(script['actions'])}, complexity={complexity}")
    
    return script


def _get_action_instruction(action: ChallengeType) -> str:
    """Get human-readable instruction for action"""
    instructions = {
        ChallengeType.BLINK: "Please blink your eyes",
        ChallengeType.HEAD_TURN_LEFT: "Turn your head to the left",
        ChallengeType.HEAD_TURN_RIGHT: "Turn your head to the right",
        ChallengeType.NOD: "Nod your head up and down",
        ChallengeType.SMILE: "Please smile"
    }
    return instructions.get(action, "Follow the instruction")


# ============= CHALLENGE VERIFY ENDPOINT =============

def handle_challenge_verify(
    session_id: str,
    challenge_id: str,
    responses: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Handle /face/challenge/verify endpoint
    
    Verifies challenge responses.
    
    Args:
        session_id: Session identifier
        challenge_id: Challenge identifier
        responses: List of action responses with timestamps
    
    Returns:
        Verification result
    """
    # Get session
    session = get_or_create_session(session_id)
    
    # Verify challenge exists and matches
    if not session.challenge_script:
        return {
            'ok': False,
            'session_id': session_id,
            'error': 'No challenge script found'
        }
    
    if session.challenge_script['challenge_id'] != challenge_id:
        return {
            'ok': False,
            'session_id': session_id,
            'error': 'Challenge ID mismatch'
        }
    
    # Check TTL
    created_at = datetime.fromisoformat(session.challenge_script['created_at'])
    ttl_ms = session.challenge_script['ttl_ms']
    if (datetime.utcnow() - created_at).total_seconds() * 1000 > ttl_ms:
        return {
            'ok': False,
            'session_id': session_id,
            'error': 'Challenge expired'
        }
    
    # Verify responses match expected actions
    expected_actions = session.challenge_script['actions']
    if len(responses) != len(expected_actions):
        return {
            'ok': False,
            'session_id': session_id,
            'error': f'Expected {len(expected_actions)} responses, got {len(responses)}'
        }
    
    # Use the challenge generator to verify
    from .challenge_generator import verify_challenge_response
    
    # Format responses for the verifier
    formatted_responses = []
    for i, response in enumerate(responses):
        formatted_responses.append({
            'action_detected': response.get('action'),
            'duration_ms': response.get('duration_ms', 0),
            'metrics': response.get('metrics', {})
        })
    
    # Calculate completion time
    completion_time_ms = sum(r.get('duration_ms', 0) for r in responses)
    
    # Verify using the challenge generator
    result = verify_challenge_response(
        challenge_id,
        formatted_responses,
        completion_time_ms
    )
    
    # Track event
    if result['passed']:
        track_ux_event(
            event_type="challenge.completed",
            session_id=session_id,
            data={'score': result['score'], 'steps_completed': result['steps_completed']},
            context={'source': 'face_challenge_verify'}
        )
        session.challenge_completed = True
    else:
        track_ux_event(
            event_type="challenge.failed",
            session_id=session_id,
            data={'score': result['score'], 'reasons': result['failure_reasons']},
            context={'source': 'face_challenge_verify'}
        )
    
    logger.info(f"Challenge verify: session={session_id}, passed={result['passed']}, score={result['score']}")
    
    return {
        'ok': result['passed'],
        'session_id': session.session_id,
        'challenge_id': challenge_id,
        'verified': result['passed'],
        'score': result['score'],
        'steps_completed': result['steps_completed'],
        'steps_total': result['steps_total'],
        'details': result['failure_reasons'] if not result['passed'] else ['All actions verified']
    }


# ============= BURST UPLOAD ENDPOINT =============

def handle_burst_upload(
    session_id: str,
    frames: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Handle /face/burst/upload endpoint
    
    Receives burst of frames for analysis.
    
    Args:
        session_id: Session identifier
        frames: List of frame data with timestamps
    
    Returns:
        Upload confirmation
    """
    # Get session
    session = get_or_create_session(session_id)
    
    # Get thresholds
    tm = ThresholdManager()
    burst_thresholds = tm.get_face_burst_thresholds()
    
    max_frames = int(burst_thresholds['max_frames'])
    max_duration = burst_thresholds['max_duration_ms']
    
    # Validate frame count
    if len(frames) > max_frames:
        return {
            'ok': False,
            'session_id': session_id,
            'error': f'Too many frames: {len(frames)} > {max_frames}'
        }
    
    # Validate duration
    if frames:
        duration = frames[-1].get('timestamp_ms', 0) - frames[0].get('timestamp_ms', 0)
        if duration > max_duration:
            return {
                'ok': False,
                'session_id': session_id,
                'error': f'Burst too long: {duration}ms > {max_duration}ms'
            }
    
    # Store frames
    session.burst_frames = frames
    
    # Generate burst ID
    burst_id = hashlib.sha256(
        f"{session_id}{time.time()}".encode()
    ).hexdigest()[:16]
    
    logger.info(f"Burst upload: session={session_id}, frames={len(frames)}")
    
    return {
        'ok': True,
        'session_id': session.session_id,
        'burst_id': burst_id,
        'frame_count': len(frames),
        'duration_ms': duration if frames else 0
    }


# ============= BURST EVAL ENDPOINT =============

def handle_burst_eval(
    session_id: str,
    burst_id: str
) -> Dict[str, Any]:
    """
    Handle /face/burst/eval endpoint
    
    Evaluates uploaded burst frames.
    
    Args:
        session_id: Session identifier
        burst_id: Burst identifier
    
    Returns:
        Evaluation results with consensus scoring
    """
    from .burst_processor import process_burst, format_burst_feedback
    
    # Get session
    session = get_or_create_session(session_id)
    
    if not session.burst_frames:
        return {
            'ok': False,
            'session_id': session_id,
            'error': 'No burst frames found'
        }
    
    # Get thresholds
    tm = ThresholdManager()
    burst_thresholds = tm.get_face_burst_thresholds()
    
    # Get geometry and PAD thresholds too
    geometry_thresholds = tm.get_face_geometry_thresholds()
    pad_thresholds = tm.get_face_pad_thresholds()
    
    # Process burst with the new processor
    burst_result = process_burst(
        frames=session.burst_frames,
        frame_width=640,
        frame_height=480,
        thresholds={
            'burst_consensus_frame_min_count': burst_thresholds['consensus_frame_min_count'],
            'burst_consensus_median_min': burst_thresholds['consensus_median_min'],
            'burst_consensus_top_k': burst_thresholds['consensus_top_k'],
            'burst_consensus_frame_min_score': burst_thresholds['consensus_frame_min_score'],
            # Add geometry thresholds for frame quality scoring
            'min_occupancy': geometry_thresholds['bbox_fill_min'],
            'max_occupancy': 0.8,
            'centering_tolerance': geometry_thresholds['centering_tolerance'],
            'max_pose_angle': geometry_thresholds['pose_max_angle'],
            'brightness_mean_min': geometry_thresholds['brightness_mean_min'],
            'brightness_mean_max': geometry_thresholds['brightness_mean_max'],
            'brightness_p05_min': geometry_thresholds['brightness_p05_min'],
            'brightness_p95_max': geometry_thresholds['brightness_p95_max'],
            'min_sharpness': geometry_thresholds['tenengrad_min_640w'],
            # Add PAD thresholds
            'pad_score_min': pad_thresholds['score_min'],
            'spoof_threshold': pad_thresholds['spoof_threshold']
        }
    )
    
    # Format feedback
    feedback = format_burst_feedback(burst_result)
    
    # Build response with detailed frame scores
    frame_scores = [
        {
            'frame_index': f.frame_index,
            'timestamp_ms': f.timestamp_ms,
            'quality_score': f.overall_score,
            'quality_level': f.quality_level.value,
            'geometry_score': f.geometry_score,
            'pad_score': f.pad_score
        }
        for f in burst_result.frame_scores
    ]
    
    # Integrate biometric checks
    try:
        from .biometric_integration import integrate_biometrics_with_burst
        # Get reference image if available (from previous capture or document)
        reference_image = getattr(session, 'reference_image', None)
        burst_result = integrate_biometrics_with_burst(burst_result, session, reference_image)
    except ImportError:
        logger.debug("Biometric integration not available")
    
    # Transition to CAPTURED state if consensus passed
    if burst_result.consensus.passed:
        session.transition_to(
            CaptureState.CAPTURED,
            reason=f"burst_consensus_passed,median_score:{burst_result.consensus.median_score:.3f}"
        )
        
        # Record capture in session
        session.record_capture()
        
        # Track capture flow progress (UX Requirement G)
        try:
            from .capture_flow import get_capture_manager, CaptureStep
        except ImportError:
            from face.capture_flow import get_capture_manager, CaptureStep
        
        capture_manager = get_capture_manager()
        
        # Advance capture flow based on current side
        if session.current_side.value == "front":
            # Front captured
            capture_manager.current_step = CaptureStep.FRONT_CAPTURED
            progress = capture_manager.advance_step(
                success=True,
                quality_score=burst_result.consensus.median_score
            )
            logger.info(f"Front capture complete: {progress.display}")
        else:
            # Back captured
            capture_manager.current_step = CaptureStep.BACK_CAPTURED
            progress = capture_manager.advance_step(
                success=True,
                quality_score=burst_result.consensus.median_score
            )
            logger.info(f"Back capture complete: {progress.display}")
    
    logger.info(f"Burst eval: session={session_id}, consensus={burst_result.consensus.passed}, median={burst_result.consensus.median_score:.3f}, state={session.capture_state.value}")
    
    # Include state info in response
    state_info = session.get_state_info()
    
    # Get timing metadata
    timing_metadata = session.get_timing_metadata()
    
    # Get localized messages
    messages = session.get_messages()
    
    # Apply accessibility adaptations if needed
    try:
        from .accessibility import adapt_response_for_accessibility
        # Get headers/params from session if available
        headers = getattr(session, 'request_headers', {})
        params = getattr(session, 'request_params', {})
    except ImportError:
        adapt_response_for_accessibility = None
        headers = {}
        params = {}
    
    # Record capture timing event
    if burst_result.consensus.passed:
        session.record_timing_event(f"capture_{session.current_side.value}_complete")
        
        # Start extraction process (UX Requirement D)
        try:
            from .extraction import extract_with_confidence
        except ImportError:
            from face.extraction import extract_with_confidence
        
        # Create streaming callback to store events
        def streaming_callback(event):
            session.add_extraction_event(event)
        
        # Start extraction
        session.start_extraction(session.current_side.value)
        
        # Simulate image data (in production, use actual burst frames)
        mock_image_data = b"mock_image_data"
        
        # Extract with confidence scores
        extraction_result = extract_with_confidence(
            mock_image_data,
            session.session_id,
            session.current_side.value,
            streaming_callback
        )
        
        # Store extraction result
        session.store_extraction_result(extraction_result)
    
    # Get extraction summary if extraction was performed
    extraction_summary = session.get_extraction_summary() if burst_result.consensus.passed else None
    
    # Get capture flow progress (UX Requirement G)
    capture_progress = None
    if burst_result.consensus.passed:
        capture_progress = capture_manager.get_progress().to_dict()
    
    response = {
        'ok': True,
        'session_id': session.session_id,
        'state': state_info,
        'timing': timing_metadata,  # Include timing metadata
        'messages': messages,  # Include localized messages
        'capture_progress': capture_progress,  # Include capture flow progress
        'burst_id': burst_result.burst_id,
        'frame_scores': frame_scores,
        'consensus': {
            'passed': burst_result.consensus.passed,
            'confidence': burst_result.consensus.confidence,
            'median_score': burst_result.consensus.median_score,
            'mean_score': burst_result.consensus.mean_score,
            'std_deviation': burst_result.consensus.std_deviation,
            'temporal_consistency': burst_result.consensus.temporal_consistency,
            'usable_frames': burst_result.consensus.usable_frame_count,
            'total_frames': burst_result.consensus.total_frame_count,
            'best_frames': burst_result.consensus.best_frames,
            'reasons': burst_result.consensus.reasons
        },
        'feedback': feedback,
        'thresholds': {
            'consensus_median_min': burst_thresholds['consensus_median_min'],
            'consensus_frame_min_score': burst_thresholds['consensus_frame_min_score'],
            'consensus_frame_min_count': int(burst_thresholds['consensus_frame_min_count'])
        },
        'processing_time_ms': burst_result.processing_time_ms
    }
    
    # Add biometric data if available (Phase 13)
    if 'biometric' in burst_result:
        response['biometric'] = burst_result['biometric']
    
    # Add extraction data if available (UX Requirement D)
    if extraction_summary:
        response['extraction'] = extraction_summary
        
        # If extraction completed, add detailed result
        current_side = session.current_side.value
        if current_side in session.extraction_results:
            response['extraction']['current_result'] = session.extraction_results[current_side]
    
    # Apply accessibility adaptations if available
    if adapt_response_for_accessibility:
        response = adapt_response_for_accessibility(response, headers, params)
    
    return response


# ============= DECISION ENDPOINT =============

def handle_face_decision(
    session_id: str,
    passive_score: Optional[float] = None,
    match_score: Optional[float] = None,
    spoof_score: Optional[float] = None
) -> Dict[str, Any]:
    """
    Handle /face/decision endpoint
    
    Makes final decision based on all collected data per AI spec.
    
    Args:
        session_id: Session identifier
        passive_score: Passive liveness score
        match_score: Face match score
        spoof_score: Spoof detection score
    
    Returns:
        Final decision with confidence and reasons
    """
    # Get enhanced session
    session_mgr = get_session_manager()
    session = session_mgr.get_or_create_session(session_id)
    
    # Update scores if provided
    if passive_score is not None:
        session.passive_score = passive_score
    if match_score is not None:
        session.match_score = match_score
    if spoof_score is not None:
        session.spoof_score = spoof_score
    
    # Make decision using enhanced logic
    decision_result = session.make_decision()
    
    # Track decision event
    if decision_result['decision'] == 'approve_face':
        track_ux_event(
            event_type="decision.approved",
            session_id=session_id,
            data={'confidence': decision_result['confidence']},
            context={'source': 'face_decision'}
        )
    elif decision_result['decision'] == 'deny_face':
        track_ux_event(
            event_type="decision.rejected",
            session_id=session_id,
            data={'reasons': decision_result['reasons']},
            context={'source': 'face_decision'}
        )
    else:  # review_face
        track_ux_event(
            event_type="decision.review",
            session_id=session_id,
            data={'reasons': decision_result['reasons']},
            context={'source': 'face_decision'}
        )
    
    # Metrics are tracked through events and session state
    # Confidence, match_score, and passive_score are included in the decision data
    
    # Record metrics for Prometheus
    from .metrics_exporter import record_decision as record_prometheus_decision
    from .metrics_exporter import record_match_score as record_prometheus_match
    from .metrics_exporter import record_pad_result
    
    record_prometheus_decision(decision_result['decision'], decision_result['confidence'], decision_result['reasons'])
    if match_score:
        record_prometheus_match(match_score)
    if passive_score:
        # Assume genuine for now (would need ground truth in production)
        detected_genuine = passive_score >= 0.70
        record_pad_result(passive_score, is_genuine=True, detected_genuine=detected_genuine)
    
    logger.info(f"Face decision: session={session_id}, decision={decision_result['decision']}, confidence={decision_result['confidence']:.2f}")
    
    # Audit the decision
    from .audit_logger import audit_decision, AuditEventType, audit_event
    
    # Log the decision with policy snapshot
    audit_decision(
        session_id=session_id,
        decision=decision_result['decision'],
        confidence=decision_result['confidence'],
        reasons=decision_result['reasons'],
        thresholds=decision_result['threshold_snapshot'],
        metrics={
            'passive_score': passive_score,
            'match_score': match_score,
            'spoof_score': spoof_score,
            'challenges_passed': session.challenges_passed,
            'consensus_ok': session.consensus_ok
        }
    )
    
    # Log session end event
    audit_event(
        AuditEventType.SESSION_END,
        session_id,
        {'decision': decision_result['decision']}
    )
    
    return {
        'ok': True,
        'session_id': session.session_id,
        **decision_result,
        'timestamp': datetime.utcnow().isoformat()
    }


# ============= TELEMETRY ENDPOINT =============

def handle_telemetry(
    session_id: str,
    events: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Handle /face/telemetry endpoint
    
    Collects telemetry events for monitoring.
    
    Args:
        session_id: Session identifier
        events: List of telemetry events
    
    Returns:
        Acknowledgment
    """
    # In production, would store in time-series database
    event_count = len(events)
    
    # Log summary
    event_types = {}
    for event in events:
        event_type = event.get('type', 'unknown')
        event_types[event_type] = event_types.get(event_type, 0) + 1
    
    logger.info(f"Telemetry: session={session_id}, events={event_count}, types={event_types}")
    
    return {
        'ok': True,
        'session_id': session_id,
        'events_received': event_count,
        'timestamp': datetime.utcnow().isoformat()
    }


# ============= METRICS ENDPOINT =============

def handle_metrics() -> Dict[str, Any]:
    """
    Handle /face/metrics endpoint
    
    Returns aggregated metrics for monitoring.
    
    Returns:
        Current metrics
    """
    # Calculate metrics from active sessions
    active_sessions = len(_sessions)
    
    # Calculate average scores
    all_pad_scores = []
    decisions = {'approved': 0, 'rejected': 0, 'pending': 0}
    
    for session in _sessions.values():
        all_pad_scores.extend(session.pad_scores)
        if session.decision:
            decisions[session.decision] = decisions.get(session.decision, 0) + 1
        else:
            decisions['pending'] += 1
    
    avg_pad_score = np.mean(all_pad_scores) if all_pad_scores else 0
    
    return {
        'ok': True,
        'timestamp': datetime.utcnow().isoformat(),
        'sessions': {
            'active': active_sessions,
            'total': active_sessions  # In production, would track total
        },
        'pad_scores': {
            'average': round(avg_pad_score, 3),
            'count': len(all_pad_scores)
        },
        'decisions': decisions,
        'performance': {
            'avg_response_time_ms': 15.0,  # Simulated
            'p95_response_time_ms': 25.0   # Simulated
        }
    }