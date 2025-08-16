"""
Enhanced Session Manager
Implements lock tokens, timing controls, and rate limiting per AI spec

Requirements:
- Lock token generation and validation
- Countdown enforcement (600ms minimum)
- Cooldown periods (800ms after capture)
- Anti-double capture (2000ms minimum interval)
- Rate limiting (10 QPS per session)
"""

import time
import hashlib
import secrets
from typing import Dict, Optional, Tuple, List, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
from enum import Enum
import threading
import logging

logger = logging.getLogger(__name__)

# ============= CAPTURE STATES (UX Requirement A) =============
class CaptureState(Enum):
    """Document capture state machine states"""
    SEARCHING = "searching"          # Looking for document in frame
    LOCKED = "locked"                # Document detected and stable
    COUNTDOWN = "countdown"          # Capture countdown in progress
    CAPTURED = "captured"            # Image captured successfully
    CONFIRM = "confirm"              # User confirmation step
    FLIP_TO_BACK = "flip_to_back"   # Prompting user to flip document
    BACK_SEARCHING = "back_searching"  # Looking for back of document
    COMPLETE = "complete"            # Process finished

class DocumentSide(Enum):
    """Document side being captured"""
    FRONT = "front"
    BACK = "back"

# ============= STATE TRANSITIONS MATRIX =============
ALLOWED_TRANSITIONS = {
    CaptureState.SEARCHING: [CaptureState.LOCKED],
    CaptureState.LOCKED: [CaptureState.COUNTDOWN, CaptureState.SEARCHING],
    CaptureState.COUNTDOWN: [CaptureState.CAPTURED, CaptureState.SEARCHING],
    CaptureState.CAPTURED: [CaptureState.CONFIRM],
    CaptureState.CONFIRM: [CaptureState.FLIP_TO_BACK, CaptureState.COMPLETE],
    CaptureState.FLIP_TO_BACK: [CaptureState.BACK_SEARCHING],
    CaptureState.BACK_SEARCHING: [CaptureState.LOCKED],
    CaptureState.COMPLETE: []  # Terminal state
}

# ============= TIMING CONSTANTS (per AI spec) =============
COUNTDOWN_MIN_MS = 600  # Minimum time before capture allowed
COOLDOWN_DURATION_MS = 800  # Cooldown after capture
MIN_CAPTURE_INTERVAL_MS = 2000  # Minimum interval between captures
LOCK_TOKEN_TTL_SEC = 30  # Lock token expiry
SESSION_TTL_SEC = 3600  # Session expiry (1 hour)
MAX_QPS_PER_SESSION = 10  # Rate limit

# ============= HARD QUALITY GATES (per AI spec) =============
QUALITY_GATES = {
    'focus_min': 7.0,
    'motion_max': 0.4,
    'glare_max': 3.5,  # percentage
    'corners_min': 0.95,
    'id_fill_min': 0.88,
    'id_fill_max': 0.94,
    'roi_min_px': 1200
}

# ============= STATUS CODES =============
class StatusCode:
    OK = 200
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    CONFLICT = 409
    TOO_EARLY = 425
    TOO_MANY_REQUESTS = 429
    INTERNAL_ERROR = 500

# ============= REASON CODES (per AI spec) =============
class ReasonCode:
    # Quality reasons
    FOCUS_LOW = "FOCUS_LOW"
    MOTION_HIGH = "MOTION_HIGH"
    GLARE_HIGH = "GLARE_HIGH"
    CORNERS_LOW = "CORNERS_LOW"
    FILL_OUT_OF_RANGE = "FILL_OUT_OF_RANGE"
    ROI_TOO_SMALL = "ROI_TOO_SMALL"
    
    # Timing reasons
    COUNTDOWN_NOT_ELAPSED = "COUNTDOWN_NOT_ELAPSED"
    COOLDOWN_ACTIVE = "COOLDOWN_ACTIVE"
    MIN_INTERVAL_NOT_MET = "MIN_INTERVAL_NOT_MET"
    
    # Auth/validation reasons
    MISSING_METRICS = "MISSING_METRICS"
    BAD_TOKEN = "BAD_TOKEN"
    SEQUENCE_ERROR = "SEQUENCE_ERROR"
    
    # PAD/liveness reasons
    PASSIVE_PAD_LOW = "PASSIVE_PAD_LOW"
    SPOOF_HIGH = "SPOOF_HIGH"
    CHALLENGE_TIMEOUT = "CHALLENGE_TIMEOUT"
    CHALLENGE_FAIL = "CHALLENGE_FAIL"
    
    # Consensus/matching reasons
    CONSENSUS_FAIL = "CONSENSUS_FAIL"
    MATCH_LOW = "MATCH_LOW"
    MATCH_BORDERLINE = "MATCH_BORDERLINE"


@dataclass
class LockToken:
    """Lock token with timing controls"""
    token: str
    session_id: str
    created_at: float
    not_before_ms: int  # Countdown duration
    expires_at: float  # Absolute expiry time
    
    def is_valid(self) -> bool:
        """Check if token is still valid"""
        now = time.time()
        return now < self.expires_at
    
    def can_use(self) -> Tuple[bool, Optional[str], Optional[int]]:
        """Check if token can be used now"""
        now_ms = time.time() * 1000
        created_ms = self.created_at * 1000
        
        # Check expiry
        if not self.is_valid():
            return False, ReasonCode.BAD_TOKEN, None
        
        # Check countdown
        elapsed_ms = now_ms - created_ms
        if elapsed_ms < self.not_before_ms:
            retry_after_ms = int(self.not_before_ms - elapsed_ms)
            return False, ReasonCode.COUNTDOWN_NOT_ELAPSED, retry_after_ms
        
        return True, None, None


@dataclass
class RateLimiter:
    """Rate limiter for session requests"""
    max_qps: int
    window_size_sec: float = 1.0
    
    def __post_init__(self):
        self.requests: deque = deque()
        self.lock = threading.Lock()
    
    def check_and_add(self) -> Tuple[bool, Optional[int]]:
        """Check rate limit and add request if allowed"""
        with self.lock:
            now = time.time()
            
            # Remove old requests outside window
            cutoff = now - self.window_size_sec
            while self.requests and self.requests[0] < cutoff:
                self.requests.popleft()
            
            # Check limit
            if len(self.requests) >= self.max_qps:
                # Calculate retry after
                oldest = self.requests[0]
                retry_after_ms = int((oldest + self.window_size_sec - now) * 1000)
                return False, retry_after_ms
            
            # Add request
            self.requests.append(now)
            return True, None


@dataclass
class EnhancedSessionState:
    """Enhanced session state with full timing controls"""
    session_id: str
    created_at: float = field(default_factory=time.time)
    
    # Lock token management
    current_lock_token: Optional[LockToken] = None
    lock_open_ts: Optional[float] = None
    not_before_ts: Optional[float] = None
    expires_ts: Optional[float] = None
    
    # Capture timing
    last_capture_ts: Optional[float] = None
    cooldown_until_ts: Optional[float] = None
    
    # Quality metrics
    last_focus_score: Optional[float] = None
    last_motion_score: Optional[float] = None
    last_glare_percent: Optional[float] = None
    last_corners_score: Optional[float] = None
    last_fill_ratio: Optional[float] = None
    last_roi_pixels: Optional[int] = None
    
    # PAD/liveness scores
    passive_score: Optional[float] = None
    spoof_score: Optional[float] = None
    challenges_passed: bool = False
    consensus_ok: bool = False
    match_score: Optional[float] = None
    
    # Decision tracking
    decision: Optional[str] = None
    decision_reasons: List[str] = field(default_factory=list)
    decision_timestamp: Optional[float] = None
    
    # Configuration
    threshold_set: str = "default"
    policy_version: str = "1.0.0"
    
    # Rate limiting
    rate_limiter: RateLimiter = field(default_factory=lambda: RateLimiter(MAX_QPS_PER_SESSION))
    
    # Telemetry
    request_count: int = 0
    lock_attempt_count: int = 0
    capture_count: int = 0
    
    # Additional fields for handlers.py compatibility
    stability_tracker: Optional[Any] = None  # StabilityTracker from geometry.py
    lock_achieved_at: Optional[float] = None
    pad_scores: List[float] = field(default_factory=list)
    challenge_script: Optional[Dict] = None
    challenge_completed: bool = False
    burst_frames: Optional[List[Dict]] = None
    
    # State machine fields (UX Requirement A)
    capture_state: CaptureState = field(default=CaptureState.SEARCHING)
    current_side: DocumentSide = field(default=DocumentSide.FRONT)
    front_captured: bool = False
    back_captured: bool = False
    state_history: List[Tuple[CaptureState, float, Optional[str]]] = field(default_factory=list)
    
    # Timing metadata fields (UX Requirement B)
    timing_events: Dict[str, float] = field(default_factory=dict)
    animation_timings: Optional[Dict[str, Any]] = None
    response_start_time: Optional[float] = None
    
    # Message fields (UX Requirement C)
    current_language: str = "tl"  # Default to Tagalog
    quality_issues: List[str] = field(default_factory=list)
    last_error: Optional[str] = None
    
    # Extraction fields (UX Requirement D)
    extraction_results: Dict[str, Any] = field(default_factory=dict)  # side -> ExtractionResult
    extraction_events: List[Dict[str, Any]] = field(default_factory=list)
    extraction_in_progress: bool = False
    
    def __post_init__(self):
        """Initialize mutable default values"""
        if self.burst_frames is None:
            self.burst_frames = []
        # Record initial state
        self.state_history.append((self.capture_state, time.time(), "session_created"))
    
    def generate_lock_token(self) -> LockToken:
        """Generate new lock token with countdown"""
        token_data = f"{self.session_id}:{time.time()}:{secrets.token_hex(16)}"
        token_str = hashlib.sha256(token_data.encode()).hexdigest()
        
        now = time.time()
        lock_token = LockToken(
            token=token_str,
            session_id=self.session_id,
            created_at=now,
            not_before_ms=COUNTDOWN_MIN_MS,
            expires_at=now + LOCK_TOKEN_TTL_SEC
        )
        
        # Update session state
        self.current_lock_token = lock_token
        self.lock_open_ts = now
        self.not_before_ts = now + (COUNTDOWN_MIN_MS / 1000)
        self.expires_ts = lock_token.expires_at
        
        # Transition to COUNTDOWN state
        self.transition_to(CaptureState.COUNTDOWN, reason="lock_token_generated")
        
        return lock_token
    
    def check_timing_gates(self) -> Tuple[int, Optional[str], Optional[int]]:
        """Check all timing gates"""
        now_ms = time.time() * 1000
        
        # Check cooldown
        if self.cooldown_until_ts:
            cooldown_ms = self.cooldown_until_ts * 1000
            if now_ms < cooldown_ms:
                retry_after = int(cooldown_ms - now_ms)
                return StatusCode.CONFLICT, ReasonCode.COOLDOWN_ACTIVE, retry_after
        
        # Check minimum interval
        if self.last_capture_ts:
            last_capture_ms = self.last_capture_ts * 1000
            elapsed = now_ms - last_capture_ms
            if elapsed < MIN_CAPTURE_INTERVAL_MS:
                retry_after = int(MIN_CAPTURE_INTERVAL_MS - elapsed)
                return StatusCode.CONFLICT, ReasonCode.MIN_INTERVAL_NOT_MET, retry_after
        
        return StatusCode.OK, None, None
    
    def record_capture(self):
        """Record a capture event and set cooldowns"""
        now = time.time()
        self.last_capture_ts = now
        self.cooldown_until_ts = now + (COOLDOWN_DURATION_MS / 1000)
        self.capture_count += 1
    
    def check_quality_gates(self, metrics: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """Check if metrics pass quality gates"""
        failures = []
        
        # Focus check
        focus = metrics.get('focus_score')
        if focus is not None:
            self.last_focus_score = focus
            if focus < QUALITY_GATES['focus_min']:
                failures.append(ReasonCode.FOCUS_LOW)
        
        # Motion check
        motion = metrics.get('motion_score')
        if motion is not None:
            self.last_motion_score = motion
            if motion > QUALITY_GATES['motion_max']:
                failures.append(ReasonCode.MOTION_HIGH)
        
        # Glare check
        glare = metrics.get('glare_percent')
        if glare is not None:
            self.last_glare_percent = glare
            if glare > QUALITY_GATES['glare_max']:
                failures.append(ReasonCode.GLARE_HIGH)
        
        # Corners check
        corners = metrics.get('corners_score')
        if corners is not None:
            self.last_corners_score = corners
            if corners < QUALITY_GATES['corners_min']:
                failures.append(ReasonCode.CORNERS_LOW)
        
        # Fill ratio check
        fill = metrics.get('fill_ratio')
        if fill is not None:
            self.last_fill_ratio = fill
            if fill < QUALITY_GATES['id_fill_min'] or fill > QUALITY_GATES['id_fill_max']:
                failures.append(ReasonCode.FILL_OUT_OF_RANGE)
        
        # ROI size check
        roi = metrics.get('roi_pixels')
        if roi is not None:
            self.last_roi_pixels = roi
            if roi < QUALITY_GATES['roi_min_px']:
                failures.append(ReasonCode.ROI_TOO_SMALL)
        
        return len(failures) == 0, failures
    
    def make_decision(self) -> Dict[str, Any]:
        """Make face decision based on all signals"""
        reasons = []
        
        # AUTO-DENY conditions
        if self.spoof_score and self.spoof_score > 0.3:
            decision = "deny_face"
            reasons.append(ReasonCode.SPOOF_HIGH)
        elif self.passive_score and self.passive_score < 0.70:
            decision = "deny_face"
            reasons.append(ReasonCode.PASSIVE_PAD_LOW)
        elif not self.challenges_passed:
            decision = "deny_face"
            reasons.append(ReasonCode.CHALLENGE_FAIL)
        elif not self.consensus_ok:
            decision = "deny_face"
            reasons.append(ReasonCode.CONSENSUS_FAIL)
        elif self.match_score and self.match_score < 0.58:
            decision = "deny_face"
            reasons.append(ReasonCode.MATCH_LOW)
        
        # REVIEW conditions
        elif self.match_score and 0.58 <= self.match_score < 0.62:
            decision = "review_face"
            reasons.append(ReasonCode.MATCH_BORDERLINE)
        
        # APPROVE conditions
        elif (self.passive_score and self.passive_score >= 0.70 and
              self.challenges_passed and
              self.consensus_ok and
              self.match_score and self.match_score >= 0.62):
            decision = "approve_face"
            reasons.append("All checks passed")
        
        else:
            decision = "review_face"
            reasons.append("Incomplete verification")
        
        # Calculate confidence
        confidence = self._calculate_confidence()
        
        # Store decision
        self.decision = decision
        self.decision_reasons = reasons
        self.decision_timestamp = time.time()
        
        return {
            'decision': decision,
            'confidence': confidence,
            'reasons': reasons,
            'policy_version': self.policy_version,
            'threshold_snapshot': self._get_threshold_snapshot(),
            'ttl_sec': 300  # 5 minute TTL
        }
    
    def _calculate_confidence(self) -> float:
        """Calculate decision confidence"""
        factors = []
        
        if self.passive_score:
            factors.append(min(self.passive_score, 1.0) * 0.3)
        if self.match_score:
            factors.append(min(self.match_score, 1.0) * 0.3)
        if self.challenges_passed:
            factors.append(0.2)
        if self.consensus_ok:
            factors.append(0.2)
        
        return min(sum(factors), 1.0)
    
    def _get_threshold_snapshot(self) -> Dict[str, Any]:
        """Get current threshold snapshot"""
        return {
            'quality_gates': QUALITY_GATES.copy(),
            'timing': {
                'countdown_ms': COUNTDOWN_MIN_MS,
                'cooldown_ms': COOLDOWN_DURATION_MS,
                'min_interval_ms': MIN_CAPTURE_INTERVAL_MS
            },
            'decision_thresholds': {
                'passive_min': 0.70,
                'match_min': 0.58,
                'match_review_max': 0.62,
                'spoof_max': 0.3
            }
        }
    
    def transition_to(self, new_state: CaptureState, reason: Optional[str] = None) -> bool:
        """
        Transition to a new capture state with validation
        
        Args:
            new_state: Target state to transition to
            reason: Optional reason for transition (for telemetry)
            
        Returns:
            bool: True if transition successful, False if invalid
        """
        # Check if transition is allowed
        if new_state not in ALLOWED_TRANSITIONS.get(self.capture_state, []):
            logger.warning(f"Invalid state transition: {self.capture_state.value} -> {new_state.value}")
            return False
        
        # Record old state for telemetry
        old_state = self.capture_state
        timestamp = time.time()
        
        # Perform transition
        self.capture_state = new_state
        self.state_history.append((new_state, timestamp, reason))
        
        # Update capture flags based on state
        if new_state == CaptureState.CAPTURED:
            if self.current_side == DocumentSide.FRONT:
                self.front_captured = True
            else:
                self.back_captured = True
        elif new_state == CaptureState.FLIP_TO_BACK:
            self.current_side = DocumentSide.BACK
        elif new_state == CaptureState.SEARCHING:
            # Reset lock-related fields when returning to searching
            self.lock_achieved_at = None
            self.current_lock_token = None
        
        # Emit telemetry event
        self._emit_state_transition_event(old_state, new_state, timestamp, reason)
        
        # Broadcast state change via streaming (UX Requirement E)
        self._broadcast_state_change_async(old_state, new_state, reason)
        
        logger.info(f"State transition: {old_state.value} -> {new_state.value} (reason: {reason})")
        return True
    
    def _emit_state_transition_event(self, old_state: CaptureState, new_state: CaptureState, 
                                    timestamp: float, reason: Optional[str] = None):
        """Emit telemetry event for state transition"""
        try:
            # Import new UX telemetry module
            try:
                from .ux_telemetry import track_ux_event, track_state_transition
            except ImportError:
                from face.ux_telemetry import track_ux_event, track_state_transition
            
            # Calculate elapsed time
            elapsed_ms = None
            if hasattr(self, '_last_transition_time'):
                elapsed_ms = (timestamp - self._last_transition_time) * 1000
            self._last_transition_time = timestamp
            
            # Track state transition with precise timing
            track_state_transition(
                session_id=self.session_id,
                from_state=old_state.value,
                to_state=new_state.value,
                reason=reason,
                elapsed_ms=elapsed_ms
            )
            
            # Prepare context data
            context = {
                'current_side': self.current_side.value,
                'front_captured': self.front_captured,
                'back_captured': self.back_captured
            }
            
            # Map specific transitions to UX telemetry events
            if new_state == CaptureState.LOCKED:
                track_ux_event('capture.lock_open', self.session_id, {'reason': reason}, context)
            elif new_state == CaptureState.COUNTDOWN:
                track_ux_event('countdown.start', self.session_id, {'reason': reason}, context)
            elif old_state == CaptureState.COUNTDOWN and new_state == CaptureState.SEARCHING:
                track_ux_event('countdown.cancel_reason', self.session_id, {'reason': reason}, context)
            elif new_state == CaptureState.CAPTURED:
                if self.current_side == DocumentSide.FRONT:
                    track_ux_event('capture.done_front', self.session_id, {'reason': reason}, context)
                else:
                    track_ux_event('capture.done_back', self.session_id, {'reason': reason}, context)
            elif new_state == CaptureState.FLIP_TO_BACK:
                track_ux_event('transition.front_to_back', self.session_id, {'reason': reason}, context)
            
        except ImportError:
            # Telemetry module not available, skip event emission
            pass
        except Exception as e:
            # Log at debug level to avoid noise
            logger.debug(f"Telemetry event skipped: {e}")
    
    def get_state_info(self) -> Dict[str, Any]:
        """Get current state information for API responses"""
        return {
            'capture_state': self.capture_state.value,
            'current_side': self.current_side.value,
            'front_captured': self.front_captured,
            'back_captured': self.back_captured,
            'can_transition_to': [s.value for s in ALLOWED_TRANSITIONS.get(self.capture_state, [])],
            'state_history_count': len(self.state_history)
        }
    
    def reset_for_recapture(self, side: Optional[DocumentSide] = None):
        """Reset state for recapture attempt"""
        if side:
            self.current_side = side
            if side == DocumentSide.FRONT:
                self.front_captured = False
                self.capture_state = CaptureState.SEARCHING
            else:
                self.back_captured = False
                self.capture_state = CaptureState.BACK_SEARCHING
        else:
            # Full reset
            self.capture_state = CaptureState.SEARCHING
            self.current_side = DocumentSide.FRONT
            self.front_captured = False
            self.back_captured = False
        
        self.state_history.append((self.capture_state, time.time(), "recapture_reset"))
    
    def record_timing_event(self, event_name: str, timestamp: Optional[float] = None):
        """Record a timing event for animation synchronization"""
        if timestamp is None:
            timestamp = time.time()
        self.timing_events[event_name] = timestamp
        
    def get_timing_metadata(self) -> Dict[str, Any]:
        """Get timing metadata for API response (UX Requirement B)"""
        try:
            from ..config.threshold_manager import ThresholdManager
        except ImportError:
            # Fallback for test environment
            from config.threshold_manager import ThresholdManager
        
        # Get animation timings if not cached
        if self.animation_timings is None:
            tm = ThresholdManager()
            self.animation_timings = tm.get_face_animation_timings()
        
        # Calculate response time if tracking
        response_time_ms = None
        if self.response_start_time:
            response_time_ms = (time.time() - self.response_start_time) * 1000
        
        # Build timing metadata
        metadata = {
            "animation_timings": self.animation_timings,
            "current_state": self.capture_state.value,
            "timing_events": {
                name: int(ts * 1000)  # Convert to milliseconds
                for name, ts in self.timing_events.items()
            },
            "response_time_ms": response_time_ms
        }
        
        # Add state-specific timing hints
        if self.capture_state == CaptureState.LOCKED:
            metadata["next_animation"] = "countdown_ring"
            metadata["next_duration_ms"] = self.animation_timings["countdown"]["ring_duration_ms"]
        elif self.capture_state == CaptureState.COUNTDOWN:
            metadata["next_animation"] = "capture_flash"
            metadata["next_duration_ms"] = self.animation_timings["capture"]["flash_check_total_ms"]
        elif self.capture_state == CaptureState.CAPTURED:
            if self.current_side == DocumentSide.FRONT:
                metadata["next_animation"] = "card_flip_y"
                metadata["next_duration_ms"] = self.animation_timings["transition"]["card_flip_y_ms"]
            else:
                metadata["next_animation"] = "extraction_skeleton"
                metadata["next_duration_ms"] = self.animation_timings["extraction"]["skeleton_fields_ms"]
        elif self.capture_state == CaptureState.FLIP_TO_BACK:
            metadata["next_animation"] = "frame_pulse"
            metadata["next_duration_ms"] = self.animation_timings["back"]["frame_pulse_total_ms"]
        
        return metadata
    
    def start_response_timing(self):
        """Start timing for response time measurement"""
        self.response_start_time = time.time()
    
    def check_cancel_on_jitter_timing(self) -> Tuple[bool, float]:
        """
        Check if cancel-on-jitter response time meets <50ms requirement
        Returns: (meets_requirement, actual_time_ms)
        """
        if not self.response_start_time:
            return True, 0.0
        
        response_time_ms = (time.time() - self.response_start_time) * 1000
        meets_requirement = response_time_ms < 50  # UX Requirement B
        return meets_requirement, response_time_ms
    
    def get_messages(self) -> Dict[str, Any]:
        """Get localized messages for current state (UX Requirement C)"""
        try:
            from .messages import get_message_manager, Language
        except ImportError:
            # Fallback for test environment
            try:
                from face.messages import get_message_manager, Language
            except ImportError:
                # Return empty if messages module not available
                return {}
        
        # Get message manager
        msg_manager = get_message_manager()
        
        # Set language
        lang = Language.TAGALOG if self.current_language == "tl" else Language.ENGLISH
        
        # Map quality issues to message keys
        quality_issue_keys = []
        for issue in self.quality_issues:
            # Map ReasonCode to message keys
            issue_map = {
                "FOCUS_LOW": "focus_low",
                "MOTION_HIGH": "motion_high",
                "GLARE_HIGH": "glare_high",
                "CORNERS_LOW": "focus_low",
                "FILL_OUT_OF_RANGE": "not_centered",
                "TOO_SMALL": "too_far",
                "TOO_LARGE": "too_close",
                "BRIGHTNESS_LOW": "too_dark",
                "BRIGHTNESS_HIGH": "too_bright",
                "CENTERING_FAIL": "not_centered"
            }
            if issue in issue_map:
                quality_issue_keys.append(issue_map[issue])
        
        # Get messages for current state
        messages = msg_manager.get_messages_for_response(
            state=self.capture_state.value,
            success=(self.capture_state == CaptureState.LOCKED or 
                    self.capture_state == CaptureState.CAPTURED),
            quality_issues=quality_issue_keys if quality_issue_keys else None,
            error=self.last_error,
            language=lang
        )
        
        # Add specific success messages based on capture state
        if self.capture_state == CaptureState.CAPTURED:
            if self.current_side == DocumentSide.FRONT and self.front_captured:
                messages["success"] = msg_manager.get_message("success.front_captured", lang)
            elif self.current_side == DocumentSide.BACK and self.back_captured:
                messages["success"] = msg_manager.get_message("success.back_captured", lang)
        
        return messages
    
    def set_quality_issues(self, issues: List[str]):
        """Set current quality issues for message generation"""
        self.quality_issues = issues
    
    def set_error(self, error: Optional[str]):
        """Set current error for message generation"""
        self.last_error = error
    
    def _broadcast_state_change_async(self, old_state: CaptureState, new_state: CaptureState, reason: Optional[str] = None):
        """Broadcast state change via streaming (runs in background)"""
        try:
            import asyncio
            from .streaming import get_stream_manager
            
            # Create task to broadcast asynchronously
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def broadcast():
                manager = get_stream_manager()
                await manager.broadcast_state_change(
                    self.session_id,
                    old_state.value,
                    new_state.value,
                    reason
                )
            
            # Run in background (fire and forget)
            try:
                loop.run_until_complete(broadcast())
            finally:
                loop.close()
                
        except Exception as e:
            # Don't fail state transition if broadcast fails
            logger.warning(f"Failed to broadcast state change: {e}")
    
    def _broadcast_quality_update_async(self, metrics: Dict[str, Any], passed: bool):
        """Broadcast quality update via streaming"""
        try:
            import asyncio
            from .streaming import get_stream_manager
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def broadcast():
                manager = get_stream_manager()
                await manager.broadcast_quality_update(
                    self.session_id,
                    metrics,
                    passed
                )
            
            try:
                loop.run_until_complete(broadcast())
            finally:
                loop.close()
                
        except Exception as e:
            logger.warning(f"Failed to broadcast quality update: {e}")
    
    def _broadcast_extraction_progress_async(self, field_name: str, value: str, confidence: float):
        """Broadcast extraction field progress via streaming"""
        try:
            import asyncio
            from .streaming import get_stream_manager
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
            async def broadcast():
                manager = get_stream_manager()
                await manager.broadcast_extraction_field(
                    self.session_id,
                    field_name,
                    value,
                    confidence
                )
            
            try:
                loop.run_until_complete(broadcast())
            finally:
                loop.close()
                
        except Exception as e:
            logger.warning(f"Failed to broadcast extraction progress: {e}")
    
    def start_extraction(self, document_side: str):
        """Start extraction process for a document side"""
        self.extraction_in_progress = True
        self.record_timing_event(f"extraction_{document_side}_start")
    
    def store_extraction_result(self, result: Dict[str, Any]):
        """Store extraction result for document side"""
        if "document_side" in result:
            self.extraction_results[result["document_side"]] = result
            self.extraction_in_progress = False
            self.record_timing_event(f"extraction_{result['document_side']}_complete")
    
    def add_extraction_event(self, event: Dict[str, Any]):
        """Add extraction streaming event"""
        self.extraction_events.append(event)
        # Keep only last 50 events to avoid memory issues
        if len(self.extraction_events) > 50:
            self.extraction_events = self.extraction_events[-50:]
    
    def get_extraction_summary(self) -> Dict[str, Any]:
        """Get extraction summary for API response"""
        summary = {
            "in_progress": self.extraction_in_progress,
            "front_extracted": "front" in self.extraction_results,
            "back_extracted": "back" in self.extraction_results,
            "results": {}
        }
        
        # Add simplified results for each side
        for side, result in self.extraction_results.items():
            if isinstance(result, dict):
                summary["results"][side] = {
                    "overall_confidence": result.get("overall_confidence", 0),
                    "confidence_level": result.get("confidence_level", "low"),
                    "fields_extracted": len(result.get("fields", {})),
                    "low_confidence_fields": result.get("low_confidence_fields", []),
                    "extraction_duration_ms": result.get("extraction_duration_ms", 0)
                }
        
        return summary


class SessionManager:
    """Manages enhanced sessions with timing and rate limiting"""
    
    def __init__(self):
        self.sessions: Dict[str, EnhancedSessionState] = {}
        self.lock = threading.Lock()
        self.cleanup_interval = 300  # 5 minutes
        self.last_cleanup = time.time()
    
    def get_or_create_session(self, session_id: str) -> EnhancedSessionState:
        """Get existing session or create new one"""
        with self.lock:
            # Periodic cleanup
            if time.time() - self.last_cleanup > self.cleanup_interval:
                self._cleanup_expired_sessions()
            
            if session_id not in self.sessions:
                self.sessions[session_id] = EnhancedSessionState(session_id=session_id)
            
            return self.sessions[session_id]
    
    def validate_lock_token(self, token: str, session_id: str) -> Tuple[bool, Optional[str], Optional[int]]:
        """Validate lock token"""
        session = self.get_or_create_session(session_id)
        
        if not session.current_lock_token:
            return False, ReasonCode.BAD_TOKEN, None
        
        if session.current_lock_token.token != token:
            return False, ReasonCode.BAD_TOKEN, None
        
        return session.current_lock_token.can_use()
    
    def check_rate_limit(self, session_id: str) -> Tuple[bool, Optional[int]]:
        """Check rate limit for session"""
        session = self.get_or_create_session(session_id)
        return session.rate_limiter.check_and_add()
    
    def _cleanup_expired_sessions(self):
        """Remove expired sessions"""
        now = time.time()
        expired = []
        
        for sid, session in self.sessions.items():
            if now - session.created_at > SESSION_TTL_SEC:
                expired.append(sid)
        
        for sid in expired:
            del self.sessions[sid]
        
        self.last_cleanup = now
        
        if expired:
            import logging
            logging.info(f"Cleaned up {len(expired)} expired sessions")


# Global session manager instance
_session_manager = None

def get_session_manager() -> SessionManager:
    """Get global session manager instance"""
    global _session_manager
    if _session_manager is None:
        _session_manager = SessionManager()
    return _session_manager