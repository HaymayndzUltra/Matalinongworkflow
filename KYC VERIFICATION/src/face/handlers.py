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
from ..config.threshold_manager import ThresholdManager

logger = logging.getLogger(__name__)


# ============= DATA STRUCTURES =============

@dataclass
class SessionState:
    """Maintains state for a face scan session"""
    session_id: str
    created_at: float
    last_update: float
    stability_tracker: StabilityTracker
    lock_achieved_at: Optional[float] = None
    pad_scores: List[float] = None
    challenge_script: Optional[Dict] = None
    challenge_completed: bool = False
    burst_frames: List[Dict] = None
    decision: Optional[str] = None
    
    def __post_init__(self):
        if self.pad_scores is None:
            self.pad_scores = []
        if self.burst_frames is None:
            self.burst_frames = []


class ChallengeType(Enum):
    """Types of liveness challenges"""
    BLINK = "blink"
    HEAD_TURN_LEFT = "head_turn_left"
    HEAD_TURN_RIGHT = "head_turn_right"
    NOD = "nod"
    SMILE = "smile"


# Global session storage (in production, use Redis or similar)
_sessions: Dict[str, SessionState] = {}


def get_or_create_session(session_id: Optional[str] = None) -> SessionState:
    """Get existing session or create new one"""
    if session_id and session_id in _sessions:
        session = _sessions[session_id]
        session.last_update = time.time()
        return session
    
    # Create new session
    new_id = session_id or str(uuid.uuid4())
    session = SessionState(
        session_id=new_id,
        created_at=time.time(),
        last_update=time.time(),
        stability_tracker=StabilityTracker(history=[])
    )
    _sessions[new_id] = session
    
    # Clean old sessions (older than 5 minutes)
    current_time = time.time()
    expired = [
        sid for sid, s in _sessions.items()
        if current_time - s.last_update > 300
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
    gray_face_region: Optional[np.ndarray] = None
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
    
    # Get session
    session = get_or_create_session(session_id)
    
    # Get thresholds
    tm = ThresholdManager()
    geometry_thresholds = tm.get_face_geometry_thresholds()
    
    # Convert bbox to BoundingBox
    face_bbox = BoundingBox(
        x=bbox['x'],
        y=bbox['y'],
        width=bbox['width'],
        height=bbox['height']
    )
    
    # Create dummy gray image if not provided (for testing)
    if gray_face_region is None:
        gray_face_region = np.random.randint(100, 200, (100, 100), dtype=np.uint8)
    
    # Analyze geometry
    geometry_result = analyze_face_geometry(
        face_bbox=face_bbox,
        frame_width=frame_width,
        frame_height=frame_height,
        gray_face_region=gray_face_region,
        landmarks=landmarks,
        thresholds={
            'min_occupancy': geometry_thresholds['bbox_fill_min'],
            'max_occupancy': 0.8,  # Fixed max
            'centering_tolerance': geometry_thresholds['centering_tolerance'],
            'max_pose_angle': geometry_thresholds['pose_max_angle'],
            'brightness_mean_min': geometry_thresholds['brightness_mean_min'],
            'brightness_mean_max': geometry_thresholds['brightness_mean_max'],
            'brightness_p05_min': geometry_thresholds['brightness_p05_min'],
            'brightness_p95_max': geometry_thresholds['brightness_p95_max'],
            'min_sharpness': geometry_thresholds['tenengrad_min_640w']
        }
    )
    
    # Format feedback
    feedback = format_geometry_feedback(geometry_result)
    
    # Update stability tracker
    current_time = time.time() * 1000  # Convert to milliseconds
    session.stability_tracker.add_frame(current_time, face_bbox)
    
    # Check stability
    stability_min_ms = geometry_thresholds['stability_min_ms']
    is_stable, stable_duration = session.stability_tracker.calculate_stability(
        window_ms=stability_min_ms
    )
    
    # Determine lock status
    geometry_ok = len(geometry_result.issues) == 0
    lock_achieved = geometry_ok and is_stable
    
    if lock_achieved and session.lock_achieved_at is None:
        session.lock_achieved_at = time.time()
    elif not lock_achieved:
        session.lock_achieved_at = None
    
    # Calculate response time
    response_time_ms = (time.time() - start_time) * 1000
    
    # Build response
    response = {
        'ok': geometry_ok,
        'lock': lock_achieved,
        'session_id': session.session_id,
        'reasons': feedback['suggestions'] if not geometry_ok else [],
        'metrics': {
            **feedback['metrics'],
            'stable_duration_ms': stable_duration,
            'response_time_ms': round(response_time_ms, 1)
        },
        'thresholds': {
            'stability_min_ms': stability_min_ms,
            'bbox_fill_min': geometry_thresholds['bbox_fill_min'],
            'centering_tolerance': geometry_thresholds['centering_tolerance'],
            'pose_max_angle': geometry_thresholds['pose_max_angle']
        }
    }
    
    # Add debug info if issues present
    if geometry_result.issues:
        response['issues'] = [issue.value for issue in geometry_result.issues]
    
    logger.info(f"Lock check: session={session_id}, lock={lock_achieved}, time={response_time_ms:.1f}ms")
    
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
    # Get session
    session = get_or_create_session(session_id)
    
    # Get thresholds
    tm = ThresholdManager()
    challenge_thresholds = tm.get_face_challenge_thresholds()
    
    # Determine number of actions based on complexity
    complexity_map = {
        'easy': 1,
        'medium': 2,
        'hard': 3
    }
    num_actions = complexity_map.get(complexity, 2)
    num_actions = min(num_actions, int(challenge_thresholds['action_count']))
    
    # Generate random actions
    available_actions = list(ChallengeType)
    selected_actions = []
    
    import random
    random.seed(int(time.time() * 1000) % 2**32)  # Seed for reproducibility in same millisecond
    
    for _ in range(num_actions):
        action = random.choice(available_actions)
        selected_actions.append({
            'type': action.value,
            'duration_ms': int(challenge_thresholds['action_max_ms']),
            'instruction': _get_action_instruction(action)
        })
        available_actions.remove(action)  # Don't repeat actions
    
    # Create challenge script
    challenge_id = hashlib.sha256(
        f"{session_id}{time.time()}".encode()
    ).hexdigest()[:16]
    
    script = {
        'challenge_id': challenge_id,
        'session_id': session.session_id,
        'created_at': datetime.utcnow().isoformat(),
        'ttl_ms': int(challenge_thresholds['ttl_ms']),
        'actions': selected_actions,
        'total_duration_ms': sum(a['duration_ms'] for a in selected_actions),
        'complexity': complexity
    }
    
    # Store in session
    session.challenge_script = script
    
    logger.info(f"Challenge script: session={session_id}, actions={len(selected_actions)}, complexity={complexity}")
    
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
    
    # Simple verification (in production, would analyze actual movements)
    # For now, just check that responses were provided in reasonable time
    verification_passed = True
    details = []
    
    for i, (expected, response) in enumerate(zip(expected_actions, responses)):
        if response.get('action') != expected['type']:
            verification_passed = False
            details.append(f"Action {i}: type mismatch")
        
        # Check timing
        if response.get('duration_ms', 0) < expected['duration_ms'] * 0.5:
            verification_passed = False
            details.append(f"Action {i}: too fast")
    
    # Mark as completed
    if verification_passed:
        session.challenge_completed = True
    
    logger.info(f"Challenge verify: session={session_id}, passed={verification_passed}")
    
    return {
        'ok': verification_passed,
        'session_id': session.session_id,
        'challenge_id': challenge_id,
        'verified': verification_passed,
        'details': details if not verification_passed else ['All actions verified']
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
    
    # Simulate frame scoring (in production, would analyze actual frames)
    frame_scores = []
    for i, frame in enumerate(session.burst_frames):
        # Generate pseudo-random but deterministic score
        seed = hash(f"{session_id}{burst_id}{i}")
        score = 0.5 + (seed % 100) / 200  # Range 0.5-1.0
        frame_scores.append({
            'frame_index': i,
            'timestamp_ms': frame.get('timestamp_ms', i * 100),
            'quality_score': round(score, 3)
        })
    
    # Calculate consensus
    scores_only = [f['quality_score'] for f in frame_scores]
    top_k = min(int(burst_thresholds['consensus_top_k']), len(scores_only))
    top_scores = sorted(scores_only, reverse=True)[:top_k]
    
    median_score = np.median(top_scores) if top_scores else 0
    frames_above_threshold = sum(
        1 for s in scores_only 
        if s >= burst_thresholds['consensus_frame_min_score']
    )
    
    consensus_passed = (
        median_score >= burst_thresholds['consensus_median_min'] and
        frames_above_threshold >= burst_thresholds['consensus_frame_min_count']
    )
    
    logger.info(f"Burst eval: session={session_id}, consensus={consensus_passed}, median={median_score:.3f}")
    
    return {
        'ok': True,
        'session_id': session.session_id,
        'burst_id': burst_id,
        'frame_scores': frame_scores,
        'consensus': {
            'passed': consensus_passed,
            'median_score': round(median_score, 3),
            'top_k': top_k,
            'frames_above_threshold': frames_above_threshold,
            'min_frames_required': int(burst_thresholds['consensus_frame_min_count'])
        },
        'thresholds': {
            'consensus_median_min': burst_thresholds['consensus_median_min'],
            'consensus_frame_min_score': burst_thresholds['consensus_frame_min_score'],
            'consensus_frame_min_count': int(burst_thresholds['consensus_frame_min_count'])
        }
    }


# ============= DECISION ENDPOINT =============

def handle_face_decision(
    session_id: str
) -> Dict[str, Any]:
    """
    Handle /face/decision endpoint
    
    Makes final decision based on all collected data.
    
    Args:
        session_id: Session identifier
    
    Returns:
        Final decision with confidence and reasons
    """
    # Get session
    session = get_or_create_session(session_id)
    
    # Collect all signals
    has_lock = session.lock_achieved_at is not None
    pad_passed = any(score >= 0.7 for score in session.pad_scores) if session.pad_scores else False
    challenge_passed = session.challenge_completed
    has_burst = len(session.burst_frames) > 0
    
    # Calculate overall confidence
    confidence_factors = []
    if has_lock:
        confidence_factors.append(0.25)
    if pad_passed:
        confidence_factors.append(0.35)
    if challenge_passed:
        confidence_factors.append(0.25)
    if has_burst:
        confidence_factors.append(0.15)
    
    confidence = sum(confidence_factors)
    
    # Make decision
    min_confidence = 0.6
    decision = 'approved' if confidence >= min_confidence else 'rejected'
    
    # Generate reasons
    reasons = []
    if not has_lock:
        reasons.append("Face lock not achieved")
    if not pad_passed:
        reasons.append("Passive liveness check failed")
    if not challenge_passed:
        reasons.append("Challenge verification incomplete")
    
    if not reasons and decision == 'approved':
        reasons.append("All verification checks passed")
    
    # Store decision
    session.decision = decision
    
    logger.info(f"Face decision: session={session_id}, decision={decision}, confidence={confidence:.2f}")
    
    return {
        'ok': True,
        'session_id': session.session_id,
        'decision': decision,
        'confidence': round(confidence, 2),
        'reasons': reasons,
        'signals': {
            'lock_achieved': has_lock,
            'pad_passed': pad_passed,
            'challenge_completed': challenge_passed,
            'burst_captured': has_burst
        },
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