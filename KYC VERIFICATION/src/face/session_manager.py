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
import threading

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