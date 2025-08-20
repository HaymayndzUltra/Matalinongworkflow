"""
Metrics Exporter for Face Scanning System
Provides Prometheus-compatible metrics endpoint

Per AI spec requirements:
- facescan.decisions_total{approve,review,deny}
- facescan.spoof_high, facescan.passive_low
- facescan.consensus_fail, facescan.match_borderline
- Histograms: time_to_lock_ms, match_score, challenge_duration_ms
- Ratios: challenge_success_rate, pad_fmr, pad_fnmr
"""

import time
from typing import Dict, List, Optional, Any
from collections import defaultdict
from dataclasses import dataclass, field
import threading
import logging

logger = logging.getLogger(__name__)

# ============= METRIC TYPES =============

class MetricType:
    """Prometheus metric types"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class MetricValue:
    """Single metric value with labels"""
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: Optional[float] = None


@dataclass
class Metric:
    """Prometheus metric definition"""
    name: str
    type: str
    help: str
    values: List[MetricValue] = field(default_factory=list)
    
    def to_prometheus(self) -> str:
        """Convert to Prometheus text format"""
        lines = []
        
        # Add HELP and TYPE comments
        lines.append(f"# HELP {self.name} {self.help}")
        lines.append(f"# TYPE {self.name} {self.type}")
        
        # Add values
        for mv in self.values:
            label_str = ""
            if mv.labels:
                label_parts = [f'{k}="{v}"' for k, v in mv.labels.items()]
                label_str = "{" + ",".join(label_parts) + "}"
            
            if mv.timestamp:
                lines.append(f"{self.name}{label_str} {mv.value} {int(mv.timestamp * 1000)}")
            else:
                lines.append(f"{self.name}{label_str} {mv.value}")
        
        return "\n".join(lines)


@dataclass
class HistogramBucket:
    """Histogram bucket for Prometheus"""
    le: float  # Less than or equal
    count: int = 0


class Histogram:
    """Prometheus histogram implementation"""
    
    def __init__(self, name: str, help: str, buckets: List[float]):
        self.name = name
        self.help = help
        self.buckets = [HistogramBucket(le=b) for b in sorted(buckets)]
        self.buckets.append(HistogramBucket(le=float('inf')))
        self.sum = 0.0
        self.count = 0
        self.lock = threading.Lock()
    
    def observe(self, value: float):
        """Record an observation"""
        with self.lock:
            self.sum += value
            self.count += 1
            
            for bucket in self.buckets:
                if value <= bucket.le:
                    bucket.count += 1
    
    def to_prometheus(self) -> str:
        """Convert to Prometheus format"""
        lines = []
        
        # HELP and TYPE
        lines.append(f"# HELP {self.name} {self.help}")
        lines.append(f"# TYPE {self.name} histogram")
        
        # Buckets
        for bucket in self.buckets:
            le_str = "+Inf" if bucket.le == float('inf') else str(bucket.le)
            lines.append(f'{self.name}_bucket{{le="{le_str}"}} {bucket.count}')
        
        # Sum and count
        lines.append(f"{self.name}_sum {self.sum}")
        lines.append(f"{self.name}_count {self.count}")
        
        return "\n".join(lines)


# ============= METRICS REGISTRY =============

class MetricsRegistry:
    """Central registry for all metrics"""
    
    def __init__(self):
        self.counters: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.gauges: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self.histograms: Dict[str, Histogram] = {}
        self.lock = threading.Lock()
        
        # Initialize standard metrics
        self._init_standard_metrics()
    
    def _init_standard_metrics(self):
        """Initialize standard face scan metrics"""
        
        # Histograms with buckets
        self.histograms['facescan_time_to_lock_ms'] = Histogram(
            'facescan_time_to_lock_ms',
            'Time to achieve face lock in milliseconds',
            [100, 200, 300, 500, 750, 1000, 1200, 1500, 2000, 2500, 3000]
        )
        
        self.histograms['facescan_match_score'] = Histogram(
            'facescan_match_score',
            'Face match scores distribution',
            [0.3, 0.4, 0.5, 0.58, 0.62, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
        )
        
        self.histograms['facescan_challenge_duration_ms'] = Histogram(
            'facescan_challenge_duration_ms',
            'Challenge completion duration in milliseconds',
            [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 10000]
        )
        
        self.histograms['facescan_passive_score'] = Histogram(
            'facescan_passive_score',
            'Passive liveness scores distribution',
            [0.3, 0.4, 0.5, 0.6, 0.65, 0.7, 0.75, 0.8, 0.85, 0.9, 0.95]
        )
        
        self.histograms['facescan_burst_frame_count'] = Histogram(
            'facescan_burst_frame_count',
            'Number of frames in burst captures',
            [1, 3, 5, 8, 10, 12, 15, 18, 20, 24]
        )
    
    def inc_counter(self, name: str, labels: Optional[Dict[str, str]] = None, value: float = 1):
        """Increment a counter"""
        with self.lock:
            label_key = self._label_key(labels)
            self.counters[name][label_key] += value
    
    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None):
        """Set a gauge value"""
        with self.lock:
            label_key = self._label_key(labels)
            self.gauges[name][label_key] = value
    
    def observe_histogram(self, name: str, value: float):
        """Record a histogram observation"""
        if name in self.histograms:
            self.histograms[name].observe(value)
    
    def _label_key(self, labels: Optional[Dict[str, str]]) -> str:
        """Generate a key from labels"""
        if not labels:
            return ""
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
    
    def get_metrics(self) -> str:
        """Get all metrics in Prometheus format"""
        lines = []
        
        # Counters
        for name, values in self.counters.items():
            help_text = f"Counter for {name.replace('_', ' ')}"
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} counter")
            
            for label_key, value in values.items():
                if label_key:
                    # Parse label key back to dict
                    labels = {}
                    for part in label_key.split(","):
                        if "=" in part:
                            k, v = part.split("=", 1)
                            labels[k] = v
                    label_str = "{" + ",".join(f'{k}="{v}"' for k, v in labels.items()) + "}"
                    lines.append(f"{name}{label_str} {value}")
                else:
                    lines.append(f"{name} {value}")
        
        # Gauges
        for name, values in self.gauges.items():
            help_text = f"Gauge for {name.replace('_', ' ')}"
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} gauge")
            
            for label_key, value in values.items():
                if label_key:
                    labels = {}
                    for part in label_key.split(","):
                        if "=" in part:
                            k, v = part.split("=", 1)
                            labels[k] = v
                    label_str = "{" + ",".join(f'{k}="{v}"' for k, v in labels.items()) + "}"
                    lines.append(f"{name}{label_str} {value}")
                else:
                    lines.append(f"{name} {value}")
        
        # Histograms
        for histogram in self.histograms.values():
            lines.append(histogram.to_prometheus())
        
        # Add process metrics
        lines.extend(self._get_process_metrics())
        
        return "\n".join(lines) + "\n"
    
    def _get_process_metrics(self) -> List[str]:
        """Get process-level metrics"""
        import os
        import resource
        
        lines = []
        
        # Process start time
        lines.append("# HELP process_start_time_seconds Start time of the process since unix epoch")
        lines.append("# TYPE process_start_time_seconds gauge")
        
        # Get process start time from /proc/self/stat if available
        try:
            with open('/proc/self/stat', 'r') as f:
                stat = f.read().split()
                start_time = int(stat[21]) / os.sysconf(os.sysconf_names['SC_CLK_TCK'])
                boot_time = 0
                with open('/proc/stat', 'r') as bf:
                    for line in bf:
                        if line.startswith('btime'):
                            boot_time = int(line.split()[1])
                            break
                if boot_time:
                    start_time = boot_time + start_time
                    lines.append(f"process_start_time_seconds {start_time}")
        except:
            pass
        
        # Memory usage
        try:
            usage = resource.getrusage(resource.RUSAGE_SELF)
            lines.append("# HELP process_resident_memory_bytes Resident memory size")
            lines.append("# TYPE process_resident_memory_bytes gauge")
            lines.append(f"process_resident_memory_bytes {usage.ru_maxrss * 1024}")
        except:
            pass
        
        return lines


# ============= METRICS COLLECTOR =============

class FaceScanMetricsCollector:
    """Collects face scan specific metrics"""
    
    def __init__(self, registry: MetricsRegistry):
        self.registry = registry
        self.start_time = time.time()
        
        # Track rates
        self.challenge_attempts = 0
        self.challenge_successes = 0
        self.pad_attempts = 0
        self.pad_true_positives = 0
        self.pad_false_positives = 0
        self.pad_true_negatives = 0
        self.pad_false_negatives = 0
    
    def record_decision(self, decision: str, confidence: float, reasons: List[str]):
        """Record a face decision"""
        # Increment decision counter
        self.registry.inc_counter('facescan_decisions_total', {'decision': decision})
        
        # Track specific failure reasons
        if decision == 'deny_face':
            for reason in reasons:
                if reason == 'SPOOF_HIGH':
                    self.registry.inc_counter('facescan_spoof_high')
                elif reason == 'PASSIVE_PAD_LOW':
                    self.registry.inc_counter('facescan_passive_low')
                elif reason == 'CONSENSUS_FAIL':
                    self.registry.inc_counter('facescan_consensus_fail')
                elif reason == 'MATCH_LOW':
                    self.registry.inc_counter('facescan_match_low')
        elif decision == 'review_face':
            if 'MATCH_BORDERLINE' in reasons:
                self.registry.inc_counter('facescan_match_borderline')
        
        # Update confidence gauge
        self.registry.set_gauge('facescan_last_decision_confidence', confidence)
    
    def record_lock_time(self, duration_ms: float):
        """Record time to achieve lock"""
        self.registry.observe_histogram('facescan_time_to_lock_ms', duration_ms)
        
        # Update gauge for last lock time
        self.registry.set_gauge('facescan_last_lock_time_ms', duration_ms)
    
    def record_match_score(self, score: float):
        """Record a match score"""
        self.registry.observe_histogram('facescan_match_score', score)
        
        # Track if borderline
        if 0.58 <= score < 0.62:
            self.registry.inc_counter('facescan_match_borderline')
    
    def record_challenge(self, success: bool, duration_ms: float):
        """Record challenge attempt"""
        self.challenge_attempts += 1
        if success:
            self.challenge_successes += 1
        
        self.registry.observe_histogram('facescan_challenge_duration_ms', duration_ms)
        
        # Update success rate gauge
        if self.challenge_attempts > 0:
            rate = self.challenge_successes / self.challenge_attempts
            self.registry.set_gauge('facescan_challenge_success_rate', rate)
    
    def record_pad_result(self, score: float, is_genuine: bool, detected_genuine: bool):
        """Record PAD (liveness) result for FMR/FNMR calculation"""
        self.pad_attempts += 1
        self.registry.observe_histogram('facescan_passive_score', score)
        
        # Calculate confusion matrix
        if is_genuine and detected_genuine:
            self.pad_true_positives += 1
        elif is_genuine and not detected_genuine:
            self.pad_false_negatives += 1
        elif not is_genuine and not detected_genuine:
            self.pad_true_negatives += 1
        else:  # not is_genuine and detected_genuine
            self.pad_false_positives += 1
        
        # Calculate and update FMR/FNMR
        if self.pad_attempts > 0:
            # FMR (False Match Rate) = FP / (FP + TN)
            if (self.pad_false_positives + self.pad_true_negatives) > 0:
                fmr = self.pad_false_positives / (self.pad_false_positives + self.pad_true_negatives)
                self.registry.set_gauge('facescan_pad_fmr', fmr)
            
            # FNMR (False Non-Match Rate) = FN / (FN + TP)
            if (self.pad_false_negatives + self.pad_true_positives) > 0:
                fnmr = self.pad_false_negatives / (self.pad_false_negatives + self.pad_true_positives)
                self.registry.set_gauge('facescan_pad_fnmr', fnmr)
    
    def record_burst_frames(self, frame_count: int):
        """Record burst frame count"""
        self.registry.observe_histogram('facescan_burst_frame_count', frame_count)
    
    def record_cancel(self, reason: str):
        """Record session cancellation"""
        self.registry.inc_counter('facescan_cancellations_total', {'reason': reason})
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics"""
        uptime = time.time() - self.start_time
        
        return {
            'uptime_seconds': uptime,
            'challenge_success_rate': self.challenge_successes / max(1, self.challenge_attempts),
            'pad_attempts': self.pad_attempts,
            'pad_fmr': self.pad_false_positives / max(1, self.pad_false_positives + self.pad_true_negatives),
            'pad_fnmr': self.pad_false_negatives / max(1, self.pad_false_negatives + self.pad_true_positives)
        }


# ============= GLOBAL INSTANCES =============

_metrics_registry = None
_metrics_collector = None


def get_metrics_registry() -> MetricsRegistry:
    """Get global metrics registry"""
    global _metrics_registry
    if _metrics_registry is None:
        _metrics_registry = MetricsRegistry()
    return _metrics_registry


def get_metrics_collector() -> FaceScanMetricsCollector:
    """Get global metrics collector"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = FaceScanMetricsCollector(get_metrics_registry())
    return _metrics_collector


# ============= CONVENIENCE FUNCTIONS =============

def record_decision(decision: str, confidence: float, reasons: List[str]):
    """Record a face decision"""
    collector = get_metrics_collector()
    collector.record_decision(decision, confidence, reasons)


def record_lock_time(duration_ms: float):
    """Record time to lock"""
    collector = get_metrics_collector()
    collector.record_lock_time(duration_ms)


def record_match_score(score: float):
    """Record match score"""
    collector = get_metrics_collector()
    collector.record_match_score(score)


def record_challenge(success: bool, duration_ms: float):
    """Record challenge result"""
    collector = get_metrics_collector()
    collector.record_challenge(success, duration_ms)


def record_pad_result(score: float, is_genuine: bool = True, detected_genuine: bool = True):
    """Record PAD result"""
    collector = get_metrics_collector()
    collector.record_pad_result(score, is_genuine, detected_genuine)


def record_burst_frames(frame_count: int):
    """Record burst frame count"""
    collector = get_metrics_collector()
    collector.record_burst_frames(frame_count)


def get_prometheus_metrics() -> str:
    """Get metrics in Prometheus text format"""
    registry = get_metrics_registry()
    return registry.get_metrics()


def get_summary_stats() -> Dict[str, Any]:
    """Get summary statistics"""
    collector = get_metrics_collector()
    return collector.get_summary_stats()