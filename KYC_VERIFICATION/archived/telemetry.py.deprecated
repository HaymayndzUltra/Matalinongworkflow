"""
Telemetry and Event Collection Module
Handles event tracking, metrics aggregation, and audit trails

This module implements:
- Event definition and collection
- Metrics aggregation
- Performance tracking
- Audit trail generation
- Privacy-compliant logging
"""

import time
import json
import hashlib
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from datetime import datetime, timedelta
from collections import defaultdict, deque
import threading
from contextlib import contextmanager

logger = logging.getLogger(__name__)


# ============= EVENT TYPES =============

class EventType(Enum):
    """Types of telemetry events"""
    # Session events
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    SESSION_TIMEOUT = "session_timeout"
    
    # Lock events
    LOCK_ATTEMPT = "lock_attempt"
    LOCK_ACHIEVED = "lock_achieved"
    LOCK_LOST = "lock_lost"
    LOCK_TIMEOUT = "lock_timeout"
    
    # PAD events
    PAD_CHECK = "pad_check"
    PAD_PASSED = "pad_passed"
    PAD_FAILED = "pad_failed"
    ATTACK_DETECTED = "attack_detected"
    
    # Challenge events
    CHALLENGE_GENERATED = "challenge_generated"
    CHALLENGE_STARTED = "challenge_started"
    CHALLENGE_COMPLETED = "challenge_completed"
    CHALLENGE_FAILED = "challenge_failed"
    CHALLENGE_TIMEOUT = "challenge_timeout"
    
    # Burst events
    BURST_STARTED = "burst_started"
    BURST_UPLOADED = "burst_uploaded"
    BURST_EVALUATED = "burst_evaluated"
    BURST_CONSENSUS_PASSED = "burst_consensus_passed"
    BURST_CONSENSUS_FAILED = "burst_consensus_failed"
    
    # Decision events
    DECISION_REQUESTED = "decision_requested"
    DECISION_APPROVED = "decision_approved"
    DECISION_REJECTED = "decision_rejected"
    DECISION_REVIEW = "decision_review"
    
    # Error events
    ERROR_GEOMETRY = "error_geometry"
    ERROR_BRIGHTNESS = "error_brightness"
    ERROR_POSE = "error_pose"
    ERROR_STABILITY = "error_stability"
    ERROR_QUALITY = "error_quality"
    ERROR_SYSTEM = "error_system"
    
    # Performance events
    PERF_SLOW_RESPONSE = "perf_slow_response"
    PERF_FRAME_DROP = "perf_frame_drop"
    PERF_TIMEOUT = "perf_timeout"


class EventSeverity(Enum):
    """Event severity levels"""
    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class TelemetryEvent:
    """Individual telemetry event"""
    event_type: EventType
    timestamp: float
    session_id: str
    severity: EventSeverity = EventSeverity.INFO
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            'event_type': self.event_type.value,
            'timestamp': self.timestamp,
            'session_id': self.session_id,
            'severity': self.severity.value,
            'data': self.data,
            'metadata': self.metadata
        }
    
    def to_audit_entry(self) -> str:
        """Generate audit trail entry (privacy-compliant)"""
        # Hash sensitive data
        audit_data = {
            'event': self.event_type.value,
            'session_hash': hashlib.sha256(self.session_id.encode()).hexdigest()[:16],
            'timestamp': datetime.fromtimestamp(self.timestamp).isoformat(),
            'severity': self.severity.value
        }
        
        # Add non-sensitive data
        safe_keys = ['duration_ms', 'score', 'confidence', 'result', 'reason']
        for key in safe_keys:
            if key in self.data:
                audit_data[key] = self.data[key]
        
        return json.dumps(audit_data, separators=(',', ':'))


# ============= METRICS =============

@dataclass
class MetricSnapshot:
    """Point-in-time metric snapshot"""
    name: str
    value: float
    timestamp: float
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class AggregatedMetric:
    """Aggregated metric statistics"""
    name: str
    count: int
    sum: float
    min: float
    max: float
    avg: float
    p50: float
    p95: float
    p99: float
    last_updated: float


class MetricsAggregator:
    """Aggregates metrics over time windows"""
    
    def __init__(self, window_size: int = 300):  # 5 minutes default
        self.window_size = window_size
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.lock = threading.Lock()
    
    def record(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Record a metric value"""
        with self.lock:
            snapshot = MetricSnapshot(
                name=name,
                value=value,
                timestamp=time.time(),
                tags=tags or {}
            )
            self.metrics[name].append(snapshot)
    
    def get_aggregated(self, name: str) -> Optional[AggregatedMetric]:
        """Get aggregated statistics for a metric"""
        with self.lock:
            if name not in self.metrics or not self.metrics[name]:
                return None
            
            # Filter to window
            current_time = time.time()
            window_start = current_time - self.window_size
            values = [
                s.value for s in self.metrics[name]
                if s.timestamp >= window_start
            ]
            
            if not values:
                return None
            
            # Calculate statistics
            values.sort()
            count = len(values)
            
            return AggregatedMetric(
                name=name,
                count=count,
                sum=sum(values),
                min=min(values),
                max=max(values),
                avg=sum(values) / count,
                p50=values[count // 2],
                p95=values[int(count * 0.95)] if count > 20 else values[-1],
                p99=values[int(count * 0.99)] if count > 100 else values[-1],
                last_updated=current_time
            )
    
    def get_all_metrics(self) -> Dict[str, AggregatedMetric]:
        """Get all aggregated metrics"""
        result = {}
        for name in list(self.metrics.keys()):
            metric = self.get_aggregated(name)
            if metric:
                result[name] = metric
        return result


# ============= TELEMETRY COLLECTOR =============

class TelemetryCollector:
    """Main telemetry collection system"""
    
    def __init__(self, 
                 buffer_size: int = 1000,
                 flush_interval: float = 10.0,
                 enable_audit: bool = True):
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.enable_audit = enable_audit
        
        self.events: deque = deque(maxlen=buffer_size)
        self.metrics = MetricsAggregator()
        self.audit_trail: deque = deque(maxlen=10000)
        
        self.session_stats: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.Lock()
        
        # Start time for uptime tracking
        self.start_time = time.time()
    
    def track_event(self, 
                   event_type: EventType,
                   session_id: str,
                   data: Optional[Dict[str, Any]] = None,
                   severity: EventSeverity = EventSeverity.INFO):
        """Track a telemetry event"""
        event = TelemetryEvent(
            event_type=event_type,
            timestamp=time.time(),
            session_id=session_id,
            severity=severity,
            data=data or {},
            metadata={
                'thread_id': threading.current_thread().name,
                'uptime_s': time.time() - self.start_time
            }
        )
        
        with self.lock:
            self.events.append(event)
            
            # Update session stats
            if session_id not in self.session_stats:
                self.session_stats[session_id] = {
                    'start_time': event.timestamp,
                    'event_count': 0,
                    'last_event': event.timestamp
                }
            
            stats = self.session_stats[session_id]
            stats['event_count'] += 1
            stats['last_event'] = event.timestamp
            
            # Add to audit trail if enabled
            if self.enable_audit:
                self.audit_trail.append(event.to_audit_entry())
        
        # Log based on severity
        if severity == EventSeverity.ERROR:
            logger.error(f"Telemetry: {event_type.value} - {data}")
        elif severity == EventSeverity.WARNING:
            logger.warning(f"Telemetry: {event_type.value} - {data}")
        else:
            logger.debug(f"Telemetry: {event_type.value}")
    
    def record_metric(self, name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Record a metric value"""
        self.metrics.record(name, value, tags)
    
    @contextmanager
    def timer(self, metric_name: str, tags: Optional[Dict[str, str]] = None):
        """Context manager for timing operations"""
        start_time = time.time()
        try:
            yield
        finally:
            duration_ms = (time.time() - start_time) * 1000
            self.record_metric(metric_name, duration_ms, tags)
    
    def get_session_summary(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get summary statistics for a session"""
        with self.lock:
            if session_id not in self.session_stats:
                return None
            
            stats = self.session_stats[session_id].copy()
            
            # Count events by type
            event_counts = defaultdict(int)
            for event in self.events:
                if event.session_id == session_id:
                    event_counts[event.event_type.value] += 1
            
            stats['event_breakdown'] = dict(event_counts)
            stats['duration_s'] = stats['last_event'] - stats['start_time']
            
            return stats
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get system-wide metrics"""
        with self.lock:
            total_events = len(self.events)
            active_sessions = sum(
                1 for sid, stats in self.session_stats.items()
                if time.time() - stats['last_event'] < 300  # Active in last 5 min
            )
            
            # Event type distribution
            event_distribution = defaultdict(int)
            severity_distribution = defaultdict(int)
            
            for event in self.events:
                event_distribution[event.event_type.value] += 1
                severity_distribution[event.severity.value] += 1
            
            # Get aggregated metrics
            metrics = self.metrics.get_all_metrics()
            
            return {
                'uptime_s': time.time() - self.start_time,
                'total_events': total_events,
                'active_sessions': active_sessions,
                'total_sessions': len(self.session_stats),
                'event_distribution': dict(event_distribution),
                'severity_distribution': dict(severity_distribution),
                'metrics': {
                    name: {
                        'avg': metric.avg,
                        'p50': metric.p50,
                        'p95': metric.p95,
                        'p99': metric.p99,
                        'min': metric.min,
                        'max': metric.max,
                        'count': metric.count
                    }
                    for name, metric in metrics.items()
                }
            }
    
    def get_audit_trail(self, limit: int = 100) -> List[str]:
        """Get recent audit trail entries"""
        with self.lock:
            # Return most recent entries
            entries = list(self.audit_trail)
            return entries[-limit:] if len(entries) > limit else entries
    
    def flush_events(self) -> List[TelemetryEvent]:
        """Flush and return all events (for external processing)"""
        with self.lock:
            events = list(self.events)
            self.events.clear()
            return events
    
    def cleanup_old_sessions(self, max_age_s: float = 3600):
        """Clean up old session data"""
        with self.lock:
            current_time = time.time()
            to_remove = [
                sid for sid, stats in self.session_stats.items()
                if current_time - stats['last_event'] > max_age_s
            ]
            
            for sid in to_remove:
                del self.session_stats[sid]
            
            return len(to_remove)


# ============= PERFORMANCE TRACKING =============

class PerformanceTracker:
    """Tracks performance metrics for face scanning operations"""
    
    def __init__(self, collector: TelemetryCollector):
        self.collector = collector
        self.operation_timers: Dict[str, float] = {}
    
    def start_operation(self, operation_id: str):
        """Start timing an operation"""
        self.operation_timers[operation_id] = time.time()
    
    def end_operation(self, operation_id: str, metric_name: str) -> float:
        """End timing an operation and record metric"""
        if operation_id not in self.operation_timers:
            return 0.0
        
        start_time = self.operation_timers.pop(operation_id)
        duration_ms = (time.time() - start_time) * 1000
        
        self.collector.record_metric(metric_name, duration_ms)
        
        # Track slow operations
        if duration_ms > 100:  # Over 100ms is considered slow
            self.collector.track_event(
                EventType.PERF_SLOW_RESPONSE,
                session_id=operation_id.split('_')[0] if '_' in operation_id else 'system',
                data={'operation': metric_name, 'duration_ms': duration_ms},
                severity=EventSeverity.WARNING
            )
        
        return duration_ms
    
    def track_frame_rate(self, session_id: str, fps: float):
        """Track frame rate"""
        self.collector.record_metric('frame_rate', fps, {'session': session_id})
        
        if fps < 15:  # Below 15 FPS is concerning
            self.collector.track_event(
                EventType.PERF_FRAME_DROP,
                session_id=session_id,
                data={'fps': fps},
                severity=EventSeverity.WARNING
            )
    
    def track_response_time(self, endpoint: str, duration_ms: float):
        """Track API response time"""
        self.collector.record_metric(
            f'response_time_{endpoint}',
            duration_ms,
            {'endpoint': endpoint}
        )


# ============= GLOBAL INSTANCE =============

# Create global telemetry collector instance
_telemetry_collector = None


def get_telemetry_collector() -> TelemetryCollector:
    """Get or create the global telemetry collector"""
    global _telemetry_collector
    if _telemetry_collector is None:
        _telemetry_collector = TelemetryCollector()
    return _telemetry_collector


def track_event(event_type: EventType, 
               session_id: str,
               data: Optional[Dict[str, Any]] = None,
               severity: EventSeverity = EventSeverity.INFO):
    """Convenience function to track events"""
    collector = get_telemetry_collector()
    collector.track_event(event_type, session_id, data, severity)


def record_metric(name: str, value: float, tags: Optional[Dict[str, str]] = None):
    """Convenience function to record metrics"""
    collector = get_telemetry_collector()
    collector.record_metric(name, value, tags)


# ============= ANALYTICS =============

def analyze_session_performance(session_id: str) -> Dict[str, Any]:
    """Analyze performance for a specific session"""
    collector = get_telemetry_collector()
    summary = collector.get_session_summary(session_id)
    
    if not summary:
        return {}
    
    # Calculate key metrics
    events = summary.get('event_breakdown', {})
    
    # Lock achievement rate
    lock_attempts = events.get('lock_attempt', 0)
    lock_achieved = events.get('lock_achieved', 0)
    lock_rate = lock_achieved / lock_attempts if lock_attempts > 0 else 0
    
    # PAD pass rate
    pad_checks = events.get('pad_check', 0)
    pad_passed = events.get('pad_passed', 0)
    pad_rate = pad_passed / pad_checks if pad_checks > 0 else 0
    
    # Challenge success rate
    challenge_started = events.get('challenge_started', 0)
    challenge_completed = events.get('challenge_completed', 0)
    challenge_rate = challenge_completed / challenge_started if challenge_started > 0 else 0
    
    # Error rate
    error_events = sum(
        count for event, count in events.items()
        if event.startswith('error_')
    )
    error_rate = error_events / summary['event_count'] if summary['event_count'] > 0 else 0
    
    return {
        'session_id': session_id,
        'duration_s': summary['duration_s'],
        'total_events': summary['event_count'],
        'lock_achievement_rate': round(lock_rate, 3),
        'pad_pass_rate': round(pad_rate, 3),
        'challenge_success_rate': round(challenge_rate, 3),
        'error_rate': round(error_rate, 3),
        'events': events
    }


def generate_analytics_report() -> Dict[str, Any]:
    """Generate comprehensive analytics report"""
    collector = get_telemetry_collector()
    system_metrics = collector.get_system_metrics()
    
    # Calculate aggregate statistics
    all_sessions = []
    for sid in list(collector.session_stats.keys()):
        perf = analyze_session_performance(sid)
        if perf:
            all_sessions.append(perf)
    
    if all_sessions:
        avg_duration = sum(s['duration_s'] for s in all_sessions) / len(all_sessions)
        avg_lock_rate = sum(s['lock_achievement_rate'] for s in all_sessions) / len(all_sessions)
        avg_pad_rate = sum(s['pad_pass_rate'] for s in all_sessions) / len(all_sessions)
        avg_error_rate = sum(s['error_rate'] for s in all_sessions) / len(all_sessions)
    else:
        avg_duration = avg_lock_rate = avg_pad_rate = avg_error_rate = 0
    
    return {
        'timestamp': datetime.utcnow().isoformat(),
        'system': system_metrics,
        'aggregate': {
            'total_sessions': len(all_sessions),
            'avg_session_duration_s': round(avg_duration, 1),
            'avg_lock_achievement_rate': round(avg_lock_rate, 3),
            'avg_pad_pass_rate': round(avg_pad_rate, 3),
            'avg_error_rate': round(avg_error_rate, 3)
        },
        'top_events': sorted(
            system_metrics['event_distribution'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
    }