"""
Legacy Telemetry Compatibility Layer

This module provides backward compatibility for code that still imports from telemetry.py.
All functionality has been migrated to ux_telemetry.py.

DEPRECATED: This module is deprecated and will be removed in a future version.
Please update your code to use ux_telemetry.py directly.
"""

import warnings
from typing import Dict, Any, Optional
from enum import Enum

# Import the new telemetry system
from .ux_telemetry import (
    track_ux_event,
    track_capture_event,
    track_state_transition,
    track_quality_event,
    track_flow_event,
    get_telemetry_manager,
    UXEventType
)

# Show deprecation warning
warnings.warn(
    "telemetry.py is deprecated. Please use ux_telemetry.py instead.",
    DeprecationWarning,
    stacklevel=2
)

# Legacy EventType enum for compatibility
class EventType(Enum):
    """Legacy event types - mapped to new UX event types"""
    # Session events
    SESSION_START = "session.start"
    SESSION_END = "session.end"
    SESSION_TIMEOUT = "session.timeout"
    
    # Lock events  
    LOCK_ATTEMPT = "capture.lock_attempt"
    LOCK_ACHIEVED = "capture.lock_achieved"
    LOCK_LOST = "capture.lock_lost"
    LOCK_TIMEOUT = "capture.lock_timeout"
    
    # PAD events
    PAD_CHECK = "quality.pad_check"
    PAD_PASSED = "quality.pad_passed"
    PAD_FAILED = "quality.pad_failed"
    ATTACK_DETECTED = "security.attack_detected"
    
    # Challenge events
    CHALLENGE_GENERATED = "challenge.generated"
    CHALLENGE_COMPLETED = "challenge.completed"
    CHALLENGE_FAILED = "challenge.failed"
    
    # Decision events
    DECISION_APPROVED = "decision.approved"
    DECISION_REJECTED = "decision.rejected"
    DECISION_REVIEW = "decision.review"

class EventSeverity(Enum):
    """Legacy severity levels - no longer used"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"

def track_event(event_type: EventType, 
                session_id: str,
                data: Optional[Dict[str, Any]] = None,
                severity: Optional[EventSeverity] = None):
    """
    Legacy track_event function - redirects to ux_telemetry
    
    Args:
        event_type: Legacy EventType enum
        session_id: Session identifier
        data: Event data
        severity: Legacy severity (ignored)
    """
    # Convert EventType to string if it's an enum
    if isinstance(event_type, EventType):
        event_type_str = event_type.value
    else:
        event_type_str = str(event_type)
    
    # Redirect to new telemetry
    track_ux_event(
        event_type=event_type_str,
        session_id=session_id,
        data=data or {},
        context={'legacy_call': True, 'severity': severity.value if severity else None}
    )

def record_metric(metric_name: str, value: float, tags: Optional[Dict[str, str]] = None):
    """
    Legacy record_metric function - redirects to ux_telemetry
    
    Args:
        metric_name: Name of the metric
        value: Metric value
        tags: Optional tags (ignored in new system)
    """
    # Create a synthetic event for the metric
    track_ux_event(
        event_type=f"metric.{metric_name}",
        session_id="legacy_metric",
        data={'value': value, 'metric': metric_name},
        context={'tags': tags} if tags else {}
    )

def get_telemetry_collector():
    """
    Legacy function to get telemetry collector
    Returns the new telemetry manager
    """
    return get_telemetry_manager()

# Additional legacy functions that might be imported
def start_session(session_id: str):
    """Legacy session start - redirects to new system"""
    track_ux_event("session.start", session_id, {}, {'source': 'legacy'})

def end_session(session_id: str):
    """Legacy session end - redirects to new system"""
    track_ux_event("session.end", session_id, {}, {'source': 'legacy'})

def get_session_metrics(session_id: str) -> Dict[str, Any]:
    """Legacy metrics retrieval - uses new system"""
    manager = get_telemetry_manager()
    return {
        'events': manager.get_session_events(session_id),
        'metrics': {},  # Legacy format compatibility
        'duration_ms': 0  # Would need to calculate from events
    }

# Export the same interface as the old module
__all__ = [
    'EventType',
    'EventSeverity', 
    'track_event',
    'record_metric',
    'get_telemetry_collector',
    'start_session',
    'end_session',
    'get_session_metrics'
]