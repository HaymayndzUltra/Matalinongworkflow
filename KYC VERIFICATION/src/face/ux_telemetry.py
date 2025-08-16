"""
UX Telemetry Module
Comprehensive telemetry for all UX events with precise timing data

Implements UX Requirement H: All telemetry must include precise timing data
for performance analysis and UX optimization.
"""

import time
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime
from collections import defaultdict, deque
import threading
import statistics

logger = logging.getLogger(__name__)


# ============= UX EVENT TYPES =============

class UXEventType(Enum):
    """UX-specific telemetry event types"""
    
    # State transition events
    STATE_TRANSITION = "state_transition"
    STATE_SEARCHING = "state.searching"
    STATE_LOCKED = "state.locked"
    STATE_COUNTDOWN = "state.countdown"
    STATE_CAPTURED = "state.captured"
    STATE_CONFIRM = "state.confirm"
    STATE_FLIP = "state.flip_to_back"
    STATE_BACK_SEARCHING = "state.back_searching"
    STATE_COMPLETE = "state.complete"
    
    # Capture events
    CAPTURE_START = "capture.start"
    CAPTURE_LOCK_OPEN = "capture.lock_open"
    CAPTURE_LOCK_LOST = "capture.lock_lost"
    CAPTURE_DONE_FRONT = "capture.done_front"
    CAPTURE_DONE_BACK = "capture.done_back"
    CAPTURE_RETRY = "capture.retry"
    CAPTURE_ABANDONED = "capture.abandoned"
    
    # Countdown events
    COUNTDOWN_START = "countdown.start"
    COUNTDOWN_TICK = "countdown.tick"
    COUNTDOWN_COMPLETE = "countdown.complete"
    COUNTDOWN_CANCEL = "countdown.cancel"
    COUNTDOWN_CANCEL_REASON = "countdown.cancel_reason"
    
    # Quality events
    QUALITY_CHECK = "quality.check"
    QUALITY_PASSED = "quality.passed"
    QUALITY_FAILED = "quality.failed"
    QUALITY_CANCEL_JITTER = "quality.cancel_jitter"
    QUALITY_MOTION_DETECTED = "quality.motion_detected"
    QUALITY_FOCUS_LOST = "quality.focus_lost"
    QUALITY_GLARE_HIGH = "quality.glare_high"
    
    # Flow events
    FLOW_FRONT_START = "flow.front_start"
    FLOW_FRONT_COMPLETE = "flow.front_complete"
    FLOW_FLIP_INSTRUCTION = "flow.flip_instruction"
    FLOW_BACK_START = "flow.back_start"
    FLOW_BACK_COMPLETE = "flow.back_complete"
    FLOW_COMPLETE = "flow.complete"
    FLOW_ABANDONED = "flow.abandoned"
    
    # Transition events
    TRANSITION_FRONT_TO_BACK = "transition.front_to_back"
    TRANSITION_RETRY = "transition.retry"
    TRANSITION_ROLLBACK = "transition.rollback"
    
    # Extraction events
    EXTRACT_START = "extract.start"
    EXTRACT_FIELD = "extract.field"
    EXTRACT_PROGRESS = "extract.progress"
    EXTRACT_COMPLETE = "extract.complete"
    EXTRACT_ERROR = "extract.error"
    
    # Performance events
    PERF_RESPONSE_TIME = "perf.response_time"
    PERF_CANCEL_LATENCY = "perf.cancel_latency"
    PERF_EXTRACTION_TIME = "perf.extraction_time"
    PERF_STATE_TRANSITION = "perf.state_transition"
    
    # Error events
    ERROR_QUALITY = "error.quality"
    ERROR_TIMEOUT = "error.timeout"
    ERROR_EXTRACTION = "error.extraction"
    ERROR_SYSTEM = "error.system"
    
    # Session events
    SESSION_START = "session.start"
    SESSION_END = "session.end"
    SESSION_TIMEOUT = "session.timeout"
    SESSION_RESUME = "session.resume"


@dataclass
class TimingData:
    """Precise timing information for events"""
    timestamp: float  # Unix timestamp
    elapsed_ms: float  # Time since last event
    since_start_ms: float  # Time since session start
    response_time_ms: Optional[float] = None  # Response time if applicable
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "timestamp": self.timestamp,
            "elapsed_ms": round(self.elapsed_ms, 2),
            "since_start_ms": round(self.since_start_ms, 2),
            "response_time_ms": round(self.response_time_ms, 2) if self.response_time_ms else None
        }


@dataclass
class UXTelemetryEvent:
    """UX telemetry event with timing data"""
    event_type: UXEventType
    session_id: str
    timing: TimingData
    data: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "event_type": self.event_type.value,
            "session_id": self.session_id,
            "timing": self.timing.to_dict(),
            "data": self.data,
            "context": self.context,
            "timestamp_iso": datetime.fromtimestamp(self.timing.timestamp).isoformat()
        }


@dataclass
class PerformanceMetrics:
    """Performance metrics aggregation"""
    response_times: List[float] = field(default_factory=list)
    state_transitions: Dict[str, List[float]] = field(default_factory=lambda: defaultdict(list))
    quality_checks: List[float] = field(default_factory=list)
    extraction_times: List[float] = field(default_factory=list)
    cancel_latencies: List[float] = field(default_factory=list)
    
    def get_percentiles(self, values: List[float]) -> Dict[str, float]:
        """Calculate percentiles for a list of values"""
        if not values:
            return {"p50": 0, "p95": 0, "p99": 0, "mean": 0}
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        
        return {
            "p50": sorted_values[n // 2],
            "p95": sorted_values[int(n * 0.95)] if n > 1 else sorted_values[0],
            "p99": sorted_values[int(n * 0.99)] if n > 1 else sorted_values[0],
            "mean": statistics.mean(values),
            "min": min(values),
            "max": max(values)
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        return {
            "response_times": self.get_percentiles(self.response_times),
            "quality_checks": self.get_percentiles(self.quality_checks),
            "extraction_times": self.get_percentiles(self.extraction_times),
            "cancel_latencies": self.get_percentiles(self.cancel_latencies),
            "state_transitions": {
                state: self.get_percentiles(times)
                for state, times in self.state_transitions.items()
            }
        }


class UXTelemetryManager:
    """Manages UX telemetry collection and analysis"""
    
    def __init__(self, buffer_size: int = 1000):
        """
        Initialize telemetry manager
        
        Args:
            buffer_size: Maximum events to keep in memory
        """
        self.buffer_size = buffer_size
        self.events: deque = deque(maxlen=buffer_size)
        self.session_starts: Dict[str, float] = {}
        self.last_event_times: Dict[str, float] = {}
        self.metrics = PerformanceMetrics()
        self.event_counts: Dict[str, int] = defaultdict(int)
        self.lock = threading.Lock()
        
        # Flow tracking
        self.flow_metrics: Dict[str, Dict[str, Any]] = {}
        self.abandonment_points: Dict[str, int] = defaultdict(int)
        
        logger.info("UX Telemetry Manager initialized")
    
    def track_event(self,
                   event_type: str,
                   session_id: str,
                   data: Optional[Dict[str, Any]] = None,
                   context: Optional[Dict[str, Any]] = None,
                   response_time_ms: Optional[float] = None) -> UXTelemetryEvent:
        """
        Track a UX telemetry event
        
        Args:
            event_type: Event type (string or UXEventType)
            session_id: Session identifier
            data: Event-specific data
            context: Event context
            response_time_ms: Response time if applicable
            
        Returns:
            Created telemetry event
        """
        with self.lock:
            # Convert string to enum if needed
            if isinstance(event_type, str):
                # Try to find matching enum
                try:
                    event_enum = UXEventType(event_type)
                except ValueError:
                    # Create a generic event type
                    event_enum = UXEventType.STATE_TRANSITION
                    if data is None:
                        data = {}
                    data['original_event'] = event_type
            else:
                event_enum = event_type
            
            # Get timing data
            current_time = time.time()
            
            # Track session start
            if session_id not in self.session_starts:
                self.session_starts[session_id] = current_time
            
            # Calculate timing
            since_start = (current_time - self.session_starts[session_id]) * 1000
            
            elapsed = 0
            if session_id in self.last_event_times:
                elapsed = (current_time - self.last_event_times[session_id]) * 1000
            
            self.last_event_times[session_id] = current_time
            
            # Create timing data
            timing = TimingData(
                timestamp=current_time,
                elapsed_ms=elapsed,
                since_start_ms=since_start,
                response_time_ms=response_time_ms
            )
            
            # Create event
            event = UXTelemetryEvent(
                event_type=event_enum,
                session_id=session_id,
                timing=timing,
                data=data or {},
                context=context or {}
            )
            
            # Store event
            self.events.append(event)
            self.event_counts[event_enum.value] += 1
            
            # Update metrics
            self._update_metrics(event)
            
            # Log significant events
            if event_enum in [UXEventType.STATE_TRANSITION, UXEventType.QUALITY_CANCEL_JITTER,
                             UXEventType.FLOW_COMPLETE, UXEventType.FLOW_ABANDONED]:
                logger.info(f"UX Event: {event_enum.value} | Session: {session_id} | "
                          f"Time: {since_start:.1f}ms | Data: {data}")
            
            return event
    
    def _update_metrics(self, event: UXTelemetryEvent):
        """Update performance metrics from event"""
        # Response times
        if event.timing.response_time_ms is not None:
            self.metrics.response_times.append(event.timing.response_time_ms)
        
        # State transitions
        if event.event_type == UXEventType.STATE_TRANSITION:
            if 'to_state' in event.data:
                state = event.data['to_state']
                self.metrics.state_transitions[state].append(event.timing.elapsed_ms)
        
        # Quality checks
        if event.event_type in [UXEventType.QUALITY_CHECK, UXEventType.QUALITY_CANCEL_JITTER]:
            if event.timing.response_time_ms:
                self.metrics.quality_checks.append(event.timing.response_time_ms)
        
        # Cancel latencies
        if event.event_type == UXEventType.QUALITY_CANCEL_JITTER:
            if event.timing.response_time_ms:
                self.metrics.cancel_latencies.append(event.timing.response_time_ms)
        
        # Extraction times
        if event.event_type == UXEventType.EXTRACT_COMPLETE:
            if 'extraction_time_ms' in event.data:
                self.metrics.extraction_times.append(event.data['extraction_time_ms'])
        
        # Flow tracking
        if event.event_type == UXEventType.FLOW_ABANDONED:
            if 'abandonment_point' in event.data:
                self.abandonment_points[event.data['abandonment_point']] += 1
    
    def get_session_events(self, session_id: str) -> List[UXTelemetryEvent]:
        """Get all events for a session"""
        with self.lock:
            return [e for e in self.events if e.session_id == session_id]
    
    def get_event_timeline(self, session_id: str) -> List[Dict[str, Any]]:
        """Get timeline of events for a session"""
        events = self.get_session_events(session_id)
        
        timeline = []
        for event in sorted(events, key=lambda e: e.timing.timestamp):
            timeline.append({
                "time_ms": round(event.timing.since_start_ms, 1),
                "event": event.event_type.value,
                "data": event.data,
                "response_ms": event.timing.response_time_ms
            })
        
        return timeline
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance metrics summary"""
        with self.lock:
            return self.metrics.get_summary()
    
    def get_flow_analytics(self) -> Dict[str, Any]:
        """Get capture flow analytics"""
        with self.lock:
            total_sessions = len(self.session_starts)
            completed = self.event_counts.get(UXEventType.FLOW_COMPLETE.value, 0)
            abandoned = self.event_counts.get(UXEventType.FLOW_ABANDONED.value, 0)
            
            return {
                "total_sessions": total_sessions,
                "completed": completed,
                "abandoned": abandoned,
                "completion_rate": (completed / total_sessions * 100) if total_sessions > 0 else 0,
                "abandonment_points": dict(self.abandonment_points),
                "front_captures": self.event_counts.get(UXEventType.CAPTURE_DONE_FRONT.value, 0),
                "back_captures": self.event_counts.get(UXEventType.CAPTURE_DONE_BACK.value, 0),
                "quality_cancels": self.event_counts.get(UXEventType.QUALITY_CANCEL_JITTER.value, 0)
            }
    
    def get_quality_metrics(self) -> Dict[str, Any]:
        """Get quality-related metrics"""
        with self.lock:
            return {
                "total_checks": self.event_counts.get(UXEventType.QUALITY_CHECK.value, 0),
                "passed": self.event_counts.get(UXEventType.QUALITY_PASSED.value, 0),
                "failed": self.event_counts.get(UXEventType.QUALITY_FAILED.value, 0),
                "cancel_jitter": self.event_counts.get(UXEventType.QUALITY_CANCEL_JITTER.value, 0),
                "motion_detected": self.event_counts.get(UXEventType.QUALITY_MOTION_DETECTED.value, 0),
                "focus_lost": self.event_counts.get(UXEventType.QUALITY_FOCUS_LOST.value, 0),
                "glare_high": self.event_counts.get(UXEventType.QUALITY_GLARE_HIGH.value, 0),
                "cancel_latencies": self.metrics.get_percentiles(self.metrics.cancel_latencies)
            }
    
    def get_event_counts(self) -> Dict[str, int]:
        """Get counts of all event types"""
        with self.lock:
            return dict(self.event_counts)
    
    def export_events(self, 
                      session_id: Optional[str] = None,
                      event_types: Optional[List[UXEventType]] = None) -> List[Dict[str, Any]]:
        """
        Export events for analysis
        
        Args:
            session_id: Filter by session
            event_types: Filter by event types
            
        Returns:
            List of event dictionaries
        """
        with self.lock:
            events = list(self.events)
            
            # Filter by session
            if session_id:
                events = [e for e in events if e.session_id == session_id]
            
            # Filter by type
            if event_types:
                type_values = [t.value for t in event_types]
                events = [e for e in events if e.event_type.value in type_values]
            
            return [e.to_dict() for e in events]
    
    def clear_session(self, session_id: str):
        """Clear data for a specific session"""
        with self.lock:
            # Remove session tracking
            self.session_starts.pop(session_id, None)
            self.last_event_times.pop(session_id, None)
            
            # Note: Events remain in buffer for analysis
    
    def reset(self):
        """Reset all telemetry data"""
        with self.lock:
            self.events.clear()
            self.session_starts.clear()
            self.last_event_times.clear()
            self.metrics = PerformanceMetrics()
            self.event_counts.clear()
            self.flow_metrics.clear()
            self.abandonment_points.clear()


# Global telemetry manager instance
_telemetry_manager = None


def get_telemetry_manager() -> UXTelemetryManager:
    """Get or create the global telemetry manager"""
    global _telemetry_manager
    if _telemetry_manager is None:
        _telemetry_manager = UXTelemetryManager()
    return _telemetry_manager


# ============= CONVENIENCE FUNCTIONS =============

def track_ux_event(event_type: str,
                  session_id: str,
                  data: Optional[Dict[str, Any]] = None,
                  context: Optional[Dict[str, Any]] = None,
                  response_time_ms: Optional[float] = None) -> UXTelemetryEvent:
    """
    Track a UX event (convenience function)
    
    This function accepts string event types for compatibility
    with existing code that uses strings like 'capture.lock_open'
    """
    manager = get_telemetry_manager()
    return manager.track_event(event_type, session_id, data, context, response_time_ms)


def track_state_transition(session_id: str,
                          from_state: str,
                          to_state: str,
                          reason: Optional[str] = None,
                          elapsed_ms: Optional[float] = None):
    """Track a state transition"""
    manager = get_telemetry_manager()
    return manager.track_event(
        UXEventType.STATE_TRANSITION,
        session_id,
        data={
            "from_state": from_state,
            "to_state": to_state,
            "reason": reason
        },
        response_time_ms=elapsed_ms
    )


def track_quality_event(session_id: str,
                       quality_score: float,
                       passed: bool,
                       cancel_reason: Optional[str] = None,
                       response_time_ms: Optional[float] = None):
    """Track a quality check event"""
    manager = get_telemetry_manager()
    
    if cancel_reason:
        event_type = UXEventType.QUALITY_CANCEL_JITTER
    elif passed:
        event_type = UXEventType.QUALITY_PASSED
    else:
        event_type = UXEventType.QUALITY_FAILED
    
    return manager.track_event(
        event_type,
        session_id,
        data={
            "quality_score": quality_score,
            "passed": passed,
            "cancel_reason": cancel_reason
        },
        response_time_ms=response_time_ms
    )


def track_capture_event(session_id: str,
                       side: str,
                       success: bool,
                       quality_score: Optional[float] = None,
                       attempts: int = 1):
    """Track a capture event"""
    manager = get_telemetry_manager()
    
    if side == "front":
        event_type = UXEventType.CAPTURE_DONE_FRONT if success else UXEventType.CAPTURE_RETRY
    else:
        event_type = UXEventType.CAPTURE_DONE_BACK if success else UXEventType.CAPTURE_RETRY
    
    return manager.track_event(
        event_type,
        session_id,
        data={
            "side": side,
            "success": success,
            "quality_score": quality_score,
            "attempts": attempts
        }
    )


def track_flow_event(session_id: str,
                    flow_step: str,
                    progress: int,
                    completed: bool = False,
                    abandoned: bool = False,
                    abandonment_reason: Optional[str] = None):
    """Track capture flow progress"""
    manager = get_telemetry_manager()
    
    if completed:
        event_type = UXEventType.FLOW_COMPLETE
    elif abandoned:
        event_type = UXEventType.FLOW_ABANDONED
    elif flow_step == "flip_instruction":
        event_type = UXEventType.FLOW_FLIP_INSTRUCTION
    elif "front" in flow_step:
        event_type = UXEventType.FLOW_FRONT_START
    elif "back" in flow_step:
        event_type = UXEventType.FLOW_BACK_START
    else:
        event_type = UXEventType.STATE_TRANSITION
    
    return manager.track_event(
        event_type,
        session_id,
        data={
            "flow_step": flow_step,
            "progress": progress,
            "completed": completed,
            "abandoned": abandoned,
            "abandonment_point": flow_step if abandoned else None,
            "abandonment_reason": abandonment_reason
        }
    )


def get_session_timeline(session_id: str) -> List[Dict[str, Any]]:
    """Get event timeline for a session"""
    manager = get_telemetry_manager()
    return manager.get_event_timeline(session_id)


def get_performance_metrics() -> Dict[str, Any]:
    """Get current performance metrics"""
    manager = get_telemetry_manager()
    return manager.get_performance_summary()


def get_flow_analytics() -> Dict[str, Any]:
    """Get capture flow analytics"""
    manager = get_telemetry_manager()
    return manager.get_flow_analytics()


def get_quality_metrics() -> Dict[str, Any]:
    """Get quality-related metrics"""
    manager = get_telemetry_manager()
    return manager.get_quality_metrics()