"""
PAD Metrics Collection Module
ISO 30107-3 Performance Monitoring
Part of KYC Bank-Grade Parity - Phase 1

This module tracks and reports PAD performance metrics for compliance monitoring.
"""

import logging
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
import json
import numpy as np
from prometheus_client import Counter, Histogram, Gauge, Summary, CollectorRegistry, push_to_gateway

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Manila timezone
MANILA_TZ = timezone(timedelta(hours=8))

# Initialize Prometheus metrics
registry = CollectorRegistry()

# Counters
liveness_attempts = Counter(
    'kyc_liveness_attempts_total',
    'Total number of liveness detection attempts',
    ['result', 'attack_type'],
    registry=registry
)

liveness_errors = Counter(
    'kyc_liveness_errors_total', 
    'Total number of liveness detection errors',
    ['error_type'],
    registry=registry
)

# Gauges for rates
liveness_far = Gauge(
    'kyc_liveness_far',
    'Current False Accept Rate (FAR)',
    registry=registry
)

liveness_frr = Gauge(
    'kyc_liveness_frr',
    'Current False Reject Rate (FRR)', 
    registry=registry
)

liveness_tar = Gauge(
    'kyc_liveness_tar',
    'Current True Accept Rate at FAR 1%',
    registry=registry
)

liveness_apcer = Gauge(
    'kyc_liveness_apcer',
    'Attack Presentation Classification Error Rate',
    registry=registry
)

liveness_bpcer = Gauge(
    'kyc_liveness_bpcer',
    'Bona Fide Presentation Classification Error Rate',
    registry=registry
)

# Histogram for processing time
liveness_processing_time = Histogram(
    'kyc_liveness_processing_seconds',
    'Liveness detection processing time in seconds',
    ['level'],
    buckets=(0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0),
    registry=registry
)

# Summary for confidence scores
liveness_confidence = Summary(
    'kyc_liveness_confidence',
    'Liveness detection confidence scores',
    ['decision'],
    registry=registry
)


@dataclass
class MetricsSample:
    """Single metrics sample for tracking"""
    timestamp: str
    is_live_predicted: bool
    is_live_actual: Optional[bool]
    confidence: float
    attack_type: str
    processing_time_ms: float
    level: str
    scores: Dict[str, float]
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization"""
        return asdict(self)


class PADMetricsCollector:
    """Collects and reports PAD performance metrics"""
    
    def __init__(self, storage_path: Optional[Path] = None,
                 prometheus_gateway: Optional[str] = None):
        """
        Initialize metrics collector
        
        Args:
            storage_path: Path to store metrics history
            prometheus_gateway: URL of Prometheus pushgateway
        """
        self.storage_path = storage_path or Path("/workspace/KYC VERIFICATION/metrics/pad_metrics.jsonl")
        self.prometheus_gateway = prometheus_gateway
        
        # In-memory buffers for rate calculation
        self.samples_buffer: List[MetricsSample] = []
        self.max_buffer_size = 1000
        
        # Current performance stats
        self.current_stats = {
            'far': 0.0,
            'frr': 0.0,
            'tar': 0.0,
            'apcer': 0.0,
            'bpcer': 0.0,
            'total_genuine': 0,
            'total_attacks': 0,
            'total_samples': 0
        }
        
        # Ensure storage directory exists
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Load historical data if exists
        self._load_history()
        
        logger.info(f"PAD Metrics Collector initialized, storage: {self.storage_path}")
    
    def _load_history(self):
        """Load historical metrics from storage"""
        if not self.storage_path.exists():
            return
        
        try:
            with open(self.storage_path, 'r') as f:
                for line in f:
                    if line.strip():
                        sample = json.loads(line)
                        self.samples_buffer.append(MetricsSample(**sample))
            
            # Keep only recent samples
            if len(self.samples_buffer) > self.max_buffer_size:
                self.samples_buffer = self.samples_buffer[-self.max_buffer_size:]
            
            logger.info(f"Loaded {len(self.samples_buffer)} historical samples")
        except Exception as e:
            logger.error(f"Failed to load metrics history: {e}")
    
    def record_detection(self, 
                        is_live_predicted: bool,
                        confidence: float,
                        attack_type: str,
                        processing_time_ms: float,
                        level: str,
                        scores: Dict[str, float],
                        is_live_actual: Optional[bool] = None):
        """
        Record a single liveness detection event
        
        Args:
            is_live_predicted: Predicted liveness result
            confidence: Detection confidence score
            attack_type: Type of attack detected (or 'genuine')
            processing_time_ms: Processing time in milliseconds
            level: PAD level (L1 or L2)
            scores: Detailed detection scores
            is_live_actual: Ground truth if available (for validation)
        """
        # Create sample
        sample = MetricsSample(
            timestamp=datetime.now(MANILA_TZ).isoformat(),
            is_live_predicted=is_live_predicted,
            is_live_actual=is_live_actual,
            confidence=confidence,
            attack_type=attack_type,
            processing_time_ms=processing_time_ms,
            level=level,
            scores=scores
        )
        
        # Add to buffer
        self.samples_buffer.append(sample)
        if len(self.samples_buffer) > self.max_buffer_size:
            self.samples_buffer.pop(0)
        
        # Save to storage
        self._save_sample(sample)
        
        # Update Prometheus metrics
        self._update_prometheus_metrics(sample)
        
        # Recalculate rates if ground truth available
        if is_live_actual is not None:
            self._recalculate_rates()
        
        logger.debug(f"Recorded detection: predicted={is_live_predicted}, "
                    f"actual={is_live_actual}, confidence={confidence:.2f}")
    
    def _save_sample(self, sample: MetricsSample):
        """Save sample to persistent storage"""
        try:
            with open(self.storage_path, 'a') as f:
                f.write(json.dumps(sample.to_dict()) + '\n')
        except Exception as e:
            logger.error(f"Failed to save metrics sample: {e}")
    
    def _update_prometheus_metrics(self, sample: MetricsSample):
        """Update Prometheus metrics with new sample"""
        # Update counters
        result = 'live' if sample.is_live_predicted else 'spoof'
        liveness_attempts.labels(result=result, attack_type=sample.attack_type).inc()
        
        # Update processing time histogram
        liveness_processing_time.labels(level=sample.level).observe(
            sample.processing_time_ms / 1000.0
        )
        
        # Update confidence summary
        decision = 'live' if sample.is_live_predicted else 'spoof'
        liveness_confidence.labels(decision=decision).observe(sample.confidence)
        
        # Push to gateway if configured
        if self.prometheus_gateway:
            try:
                push_to_gateway(self.prometheus_gateway, job='pad_metrics', 
                              registry=registry)
            except Exception as e:
                logger.error(f"Failed to push metrics to gateway: {e}")
    
    def _recalculate_rates(self):
        """Recalculate FAR, FRR, TAR based on samples with ground truth"""
        # Filter samples with ground truth
        validated_samples = [s for s in self.samples_buffer 
                           if s.is_live_actual is not None]
        
        if not validated_samples:
            return
        
        # Calculate confusion matrix
        tp = sum(1 for s in validated_samples 
                if s.is_live_predicted and s.is_live_actual)
        tn = sum(1 for s in validated_samples 
                if not s.is_live_predicted and not s.is_live_actual)
        fp = sum(1 for s in validated_samples 
                if s.is_live_predicted and not s.is_live_actual)
        fn = sum(1 for s in validated_samples 
                if not s.is_live_predicted and s.is_live_actual)
        
        total_genuine = tp + fn
        total_attacks = tn + fp
        
        # Calculate rates
        far = fp / total_attacks if total_attacks > 0 else 0
        frr = fn / total_genuine if total_genuine > 0 else 0
        tar = tp / total_genuine if total_genuine > 0 else 0
        
        # ISO 30107-3 specific metrics
        apcer = fp / total_attacks if total_attacks > 0 else 0
        bpcer = fn / total_genuine if total_genuine > 0 else 0
        
        # Update current stats
        self.current_stats.update({
            'far': far,
            'frr': frr,
            'tar': tar,
            'apcer': apcer,
            'bpcer': bpcer,
            'total_genuine': total_genuine,
            'total_attacks': total_attacks,
            'total_samples': len(validated_samples)
        })
        
        # Update Prometheus gauges
        liveness_far.set(far)
        liveness_frr.set(frr)
        liveness_tar.set(tar)
        liveness_apcer.set(apcer)
        liveness_bpcer.set(bpcer)
        
        logger.info(f"Rates updated: FAR={far:.3f}, FRR={frr:.3f}, TAR={tar:.3f}")
    
    def get_current_stats(self) -> Dict[str, Any]:
        """
        Get current performance statistics
        
        Returns:
            Dictionary with current metrics
        """
        return {
            **self.current_stats,
            'buffer_size': len(self.samples_buffer),
            'timestamp': datetime.now(MANILA_TZ).isoformat()
        }
    
    def get_compliance_status(self) -> Dict[str, Any]:
        """
        Check ISO 30107-3 compliance status
        
        Returns:
            Compliance status dictionary
        """
        # Import threshold manager
        import sys
        sys.path.append('/workspace/KYC VERIFICATION')
        from src.config.threshold_manager import get_threshold_manager
        
        tm = get_threshold_manager()
        
        # Get target thresholds
        far_target = tm.get('pad_far')
        frr_target = tm.get('pad_frr')
        tar_target = tm.get('pad_tar_far1')
        
        # Check compliance
        far_compliant = self.current_stats['far'] <= far_target
        frr_compliant = self.current_stats['frr'] <= frr_target
        tar_compliant = self.current_stats['tar'] >= tar_target
        
        overall_compliant = far_compliant and frr_compliant and tar_compliant
        
        return {
            'iso_30107_3_compliant': overall_compliant,
            'far': {
                'current': self.current_stats['far'],
                'target': far_target,
                'compliant': far_compliant
            },
            'frr': {
                'current': self.current_stats['frr'],
                'target': frr_target,
                'compliant': frr_compliant
            },
            'tar_at_far1': {
                'current': self.current_stats['tar'],
                'target': tar_target,
                'compliant': tar_compliant
            },
            'apcer': self.current_stats['apcer'],
            'bpcer': self.current_stats['bpcer'],
            'sample_size': self.current_stats['total_samples'],
            'timestamp': datetime.now(MANILA_TZ).isoformat()
        }
    
    def generate_performance_report(self) -> str:
        """
        Generate a performance report
        
        Returns:
            Formatted performance report string
        """
        stats = self.get_current_stats()
        compliance = self.get_compliance_status()
        
        report = []
        report.append("=" * 60)
        report.append("PAD PERFORMANCE REPORT")
        report.append("=" * 60)
        report.append(f"Generated: {datetime.now(MANILA_TZ).isoformat()}")
        report.append("")
        
        report.append("CURRENT METRICS:")
        report.append(f"  FAR (False Accept Rate):  {stats['far']:.3%}")
        report.append(f"  FRR (False Reject Rate):   {stats['frr']:.3%}")
        report.append(f"  TAR (True Accept @ FAR1%): {stats['tar']:.3%}")
        report.append(f"  APCER: {stats['apcer']:.3%}")
        report.append(f"  BPCER: {stats['bpcer']:.3%}")
        report.append("")
        
        report.append("SAMPLE STATISTICS:")
        report.append(f"  Total Samples: {stats['total_samples']}")
        report.append(f"  Genuine Samples: {stats['total_genuine']}")
        report.append(f"  Attack Samples: {stats['total_attacks']}")
        report.append("")
        
        report.append("ISO 30107-3 COMPLIANCE:")
        status = "✓ COMPLIANT" if compliance['iso_30107_3_compliant'] else "✗ NON-COMPLIANT"
        report.append(f"  Overall Status: {status}")
        report.append("")
        
        report.append("  Requirement Checks:")
        far_check = "✓" if compliance['far']['compliant'] else "✗"
        report.append(f"    {far_check} FAR ≤ {compliance['far']['target']:.1%} "
                     f"(current: {compliance['far']['current']:.3%})")
        
        frr_check = "✓" if compliance['frr']['compliant'] else "✗"
        report.append(f"    {frr_check} FRR ≤ {compliance['frr']['target']:.1%} "
                     f"(current: {compliance['frr']['current']:.3%})")
        
        tar_check = "✓" if compliance['tar_at_far1']['compliant'] else "✗"
        report.append(f"    {tar_check} TAR@FAR1% ≥ {compliance['tar_at_far1']['target']:.1%} "
                     f"(current: {compliance['tar_at_far1']['current']:.3%})")
        
        report.append("=" * 60)
        
        return "\n".join(report)
    
    def export_metrics(self, output_path: Optional[Path] = None) -> bool:
        """
        Export metrics to JSON file
        
        Args:
            output_path: Path to export file
            
        Returns:
            True if successful
        """
        output_path = output_path or Path("/workspace/KYC VERIFICATION/metrics/pad_export.json")
        
        try:
            export_data = {
                'metadata': {
                    'timestamp': datetime.now(MANILA_TZ).isoformat(),
                    'sample_count': len(self.samples_buffer)
                },
                'current_stats': self.get_current_stats(),
                'compliance': self.get_compliance_status(),
                'samples': [s.to_dict() for s in self.samples_buffer[-100:]]  # Last 100 samples
            }
            
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            
            logger.info(f"Exported metrics to {output_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")
            return False


# Singleton instance
_metrics_collector = None


def get_metrics_collector() -> PADMetricsCollector:
    """Get or create the singleton metrics collector instance"""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = PADMetricsCollector()
    return _metrics_collector


if __name__ == "__main__":
    # Demo and testing
    print("=== PAD Metrics Collector Demo ===")
    
    collector = get_metrics_collector()
    
    # Simulate some detections
    import random
    
    print("\nSimulating 100 detection events...")
    for i in range(100):
        is_genuine = random.random() > 0.3  # 70% genuine
        is_live_pred = is_genuine if random.random() > 0.05 else not is_genuine  # 5% error
        
        collector.record_detection(
            is_live_predicted=is_live_pred,
            confidence=random.uniform(0.6, 0.95) if is_live_pred else random.uniform(0.2, 0.5),
            attack_type='genuine' if is_genuine else random.choice(['print', 'screen', 'mask_2d']),
            processing_time_ms=random.uniform(100, 500),
            level='L2',
            scores={'texture': random.random(), 'color': random.random()},
            is_live_actual=is_genuine
        )
    
    print("\nCurrent Statistics:")
    stats = collector.get_current_stats()
    for key, value in stats.items():
        if isinstance(value, float):
            print(f"  {key}: {value:.3f}")
        else:
            print(f"  {key}: {value}")
    
    print("\n" + collector.generate_performance_report())
    
    # Export metrics
    if collector.export_metrics():
        print("\n✓ Metrics exported successfully")
    
    print("\n✓ PAD Metrics Collector operational")