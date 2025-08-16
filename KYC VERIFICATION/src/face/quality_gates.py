"""
Enhanced Quality Gates & Cancel-on-Jitter
Implements instant quality detection with Tagalog messages (UX Requirement F)

This module provides enhanced quality gates with instant cancel detection
to prevent shaky frame captures, with clear Tagalog error messages.
"""

import time
import logging
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from dataclasses import dataclass, field
from collections import deque
import statistics

logger = logging.getLogger(__name__)


class QualityMetric(Enum):
    """Individual quality metrics"""
    FOCUS = "focus"
    MOTION = "motion"
    GLARE = "glare"
    CORNERS = "corners"
    FILL_RATIO = "fill_ratio"
    BRIGHTNESS = "brightness"
    CONTRAST = "contrast"
    SHARPNESS = "sharpness"


class QualityLevel(Enum):
    """Overall quality levels"""
    EXCELLENT = "excellent"  # > 0.90
    GOOD = "good"           # 0.75 - 0.90
    ACCEPTABLE = "acceptable"  # 0.60 - 0.75
    POOR = "poor"           # < 0.60
    
    @classmethod
    def from_score(cls, score: float) -> 'QualityLevel':
        """Get quality level from score"""
        if score > 0.90:
            return cls.EXCELLENT
        elif score > 0.75:
            return cls.GOOD
        elif score > 0.60:
            return cls.ACCEPTABLE
        else:
            return cls.POOR


class CancelReason(Enum):
    """Reasons for cancellation"""
    MOTION_DETECTED = "motion_detected"
    FOCUS_LOST = "focus_lost"
    GLARE_HIGH = "glare_high"
    CORNERS_MISSING = "corners_missing"
    FILL_RATIO_LOW = "fill_ratio_low"
    STABILITY_LOST = "stability_lost"
    QUALITY_DEGRADED = "quality_degraded"


@dataclass
class QualityScore:
    """Individual quality score with history"""
    metric: QualityMetric
    value: float  # 0.0 to 1.0
    timestamp: float
    threshold: float
    passed: bool
    
    def __post_init__(self):
        """Validate score"""
        self.value = max(0.0, min(1.0, self.value))
        self.passed = self.value >= self.threshold


@dataclass
class QualityGateResult:
    """Result of quality gate check"""
    overall_score: float
    level: QualityLevel
    passed: bool
    scores: Dict[QualityMetric, QualityScore]
    cancel_reason: Optional[CancelReason] = None
    tagalog_message: Optional[str] = None
    english_message: Optional[str] = None
    hints: List[str] = field(default_factory=list)
    response_time_ms: float = 0.0
    
    def get_failed_metrics(self) -> List[QualityMetric]:
        """Get list of failed metrics"""
        return [
            metric for metric, score in self.scores.items()
            if not score.passed
        ]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "overall_score": round(self.overall_score, 3),
            "level": self.level.value,
            "passed": self.passed,
            "scores": {
                metric.value: {
                    "value": round(score.value, 3),
                    "threshold": round(score.threshold, 3),
                    "passed": score.passed
                }
                for metric, score in self.scores.items()
            },
            "cancel_reason": self.cancel_reason.value if self.cancel_reason else None,
            "message": {
                "tagalog": self.tagalog_message,
                "english": self.english_message
            },
            "hints": self.hints,
            "response_time_ms": round(self.response_time_ms, 1)
        }


class QualityGateManager:
    """Manages quality gates and cancel-on-jitter detection"""
    
    def __init__(self, 
                 history_size: int = 10,
                 stability_window: int = 5):
        """
        Initialize quality gate manager
        
        Args:
            history_size: Number of quality scores to keep in history
            stability_window: Number of frames to check for stability
        """
        self.history_size = history_size
        self.stability_window = stability_window
        self.quality_history: deque = deque(maxlen=history_size)
        self.cancel_count = 0
        self.last_cancel_time = 0
        
        # Load thresholds
        self._load_thresholds()
        
        # Cancel messages (Tagalog/English)
        self.cancel_messages = {
            CancelReason.MOTION_DETECTED: (
                "Gumalaw—subukan ulit",
                "Movement detected—try again"
            ),
            CancelReason.FOCUS_LOST: (
                "Hindi malinaw—steady lang",
                "Not clear—hold steady"
            ),
            CancelReason.GLARE_HIGH: (
                "Sobrang liwanag—bawas glare",
                "Too bright—reduce glare"
            ),
            CancelReason.CORNERS_MISSING: (
                "Kulang ang corners—ayusin sa frame",
                "Missing corners—adjust in frame"
            ),
            CancelReason.FILL_RATIO_LOW: (
                "Ilapit ng kaunti ang dokumento",
                "Move document closer"
            ),
            CancelReason.STABILITY_LOST: (
                "Hindi stable—hawak nang steady",
                "Not stable—hold steady"
            ),
            CancelReason.QUALITY_DEGRADED: (
                "Bumaba ang quality—subukan ulit",
                "Quality degraded—try again"
            )
        }
        
        # Quality hints
        self.quality_hints = {
            QualityMetric.FOCUS: ("I-focus ang camera", "Focus the camera"),
            QualityMetric.MOTION: ("Hawak nang steady", "Hold steady"),
            QualityMetric.GLARE: ("Bawas glare/reflection", "Reduce glare/reflection"),
            QualityMetric.CORNERS: ("Ipakita lahat ng corners", "Show all corners"),
            QualityMetric.FILL_RATIO: ("Punuin ang frame", "Fill the frame"),
            QualityMetric.BRIGHTNESS: ("Dagdagan ang ilaw", "Add more light"),
            QualityMetric.CONTRAST: ("Ayusin ang contrast", "Adjust contrast"),
            QualityMetric.SHARPNESS: ("Linisin ang lens", "Clean the lens")
        }
    
    def _load_thresholds(self):
        """Load quality thresholds from configuration"""
        try:
            from ..config.threshold_manager import ThresholdManager
        except ImportError:
            from config.threshold_manager import ThresholdManager
        
        tm = ThresholdManager()
        
        # Get thresholds for each metric with fallback defaults
        try:
            focus_min = tm.get("face_focus_min")
        except:
            focus_min = 0.70
            
        try:
            motion_max = tm.get("face_motion_max")
        except:
            motion_max = 0.15
            
        try:
            glare_max = tm.get("face_glare_max")
        except:
            glare_max = 0.20
            
        try:
            corners_min = tm.get("face_corners_min")
        except:
            corners_min = 0.85
            
        try:
            fill_ratio_min = tm.get("face_fill_ratio_min")
        except:
            fill_ratio_min = 0.25
        
        self.thresholds = {
            QualityMetric.FOCUS: focus_min,
            QualityMetric.MOTION: 1.0 - motion_max,  # Invert for score
            QualityMetric.GLARE: 1.0 - glare_max,  # Invert for score
            QualityMetric.CORNERS: corners_min,
            QualityMetric.FILL_RATIO: fill_ratio_min,
            QualityMetric.BRIGHTNESS: 0.30,  # Default thresholds
            QualityMetric.CONTRAST: 0.40,
            QualityMetric.SHARPNESS: 0.60
        }
        
        # Cancel-on-jitter thresholds (stricter)
        self.cancel_thresholds = {
            QualityMetric.MOTION: 0.70,  # Cancel if motion > 0.30
            QualityMetric.FOCUS: 0.50,   # Cancel if focus < 0.50
            QualityMetric.GLARE: 0.60,   # Cancel if glare > 0.40
        }
        
        # Response time target
        try:
            self.cancel_response_target_ms = tm.get("face_cancel_response_ms")
        except:
            self.cancel_response_target_ms = 50.0
    
    def check_quality(self, metrics: Dict[str, float]) -> QualityGateResult:
        """
        Check quality gates with instant cancel detection
        
        Args:
            metrics: Dictionary of quality metrics
            
        Returns:
            QualityGateResult with pass/fail and messages
        """
        start_time = time.time()
        
        # Convert metrics to scores
        scores = {}
        
        # Map input metrics to QualityMetric enum
        metric_map = {
            "focus": QualityMetric.FOCUS,
            "motion": QualityMetric.MOTION,
            "glare": QualityMetric.GLARE,
            "corners": QualityMetric.CORNERS,
            "fill_ratio": QualityMetric.FILL_RATIO,
            "brightness": QualityMetric.BRIGHTNESS,
            "contrast": QualityMetric.CONTRAST,
            "sharpness": QualityMetric.SHARPNESS
        }
        
        # Create quality scores
        for key, value in metrics.items():
            if key in metric_map:
                metric = metric_map[key]
                
                # Normalize motion and glare (they come as "badness" scores)
                if metric == QualityMetric.MOTION:
                    value = 1.0 - value  # Convert to quality score
                elif metric == QualityMetric.GLARE:
                    value = 1.0 - value  # Convert to quality score
                
                scores[metric] = QualityScore(
                    metric=metric,
                    value=value,
                    timestamp=time.time(),
                    threshold=self.thresholds[metric],
                    passed=value >= self.thresholds[metric]
                )
        
        # Check for instant cancel conditions
        cancel_reason = self._check_cancel_conditions(scores)
        
        # Calculate overall score
        if scores:
            # Weighted average based on importance
            weights = {
                QualityMetric.FOCUS: 1.5,
                QualityMetric.MOTION: 2.0,  # High weight for stability
                QualityMetric.GLARE: 1.0,
                QualityMetric.CORNERS: 1.2,
                QualityMetric.FILL_RATIO: 0.8,
                QualityMetric.BRIGHTNESS: 0.5,
                QualityMetric.CONTRAST: 0.5,
                QualityMetric.SHARPNESS: 0.7
            }
            
            weighted_sum = 0
            total_weight = 0
            
            for metric, score in scores.items():
                weight = weights.get(metric, 1.0)
                weighted_sum += score.value * weight
                total_weight += weight
            
            overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0
        else:
            overall_score = 0.0
        
        # Determine quality level
        level = QualityLevel.from_score(overall_score)
        
        # Check if passed
        passed = cancel_reason is None and overall_score >= 0.60
        
        # Generate messages
        tagalog_msg, english_msg = self._generate_messages(
            passed, cancel_reason, scores
        )
        
        # Generate hints for failed metrics
        hints = self._generate_hints(scores)
        
        # Add to history
        self.quality_history.append({
            "timestamp": time.time(),
            "overall_score": overall_score,
            "passed": passed,
            "cancel_reason": cancel_reason
        })
        
        # Calculate response time
        response_time_ms = (time.time() - start_time) * 1000
        
        # Create result
        result = QualityGateResult(
            overall_score=overall_score,
            level=level,
            passed=passed,
            scores=scores,
            cancel_reason=cancel_reason,
            tagalog_message=tagalog_msg,
            english_message=english_msg,
            hints=hints,
            response_time_ms=response_time_ms
        )
        
        # Log if cancel detected
        if cancel_reason:
            self.cancel_count += 1
            self.last_cancel_time = time.time()
            logger.info(f"Cancel-on-jitter triggered: {cancel_reason.value} (response: {response_time_ms:.1f}ms)")
        
        return result
    
    def _check_cancel_conditions(self, scores: Dict[QualityMetric, QualityScore]) -> Optional[CancelReason]:
        """
        Check for instant cancel conditions
        
        Returns:
            CancelReason if should cancel, None otherwise
        """
        # Check motion (highest priority)
        if QualityMetric.MOTION in scores:
            if scores[QualityMetric.MOTION].value < self.cancel_thresholds[QualityMetric.MOTION]:
                return CancelReason.MOTION_DETECTED
        
        # Check focus
        if QualityMetric.FOCUS in scores:
            if scores[QualityMetric.FOCUS].value < self.cancel_thresholds[QualityMetric.FOCUS]:
                return CancelReason.FOCUS_LOST
        
        # Check glare
        if QualityMetric.GLARE in scores:
            if scores[QualityMetric.GLARE].value < self.cancel_thresholds[QualityMetric.GLARE]:
                return CancelReason.GLARE_HIGH
        
        # Check stability (if we have history)
        if len(self.quality_history) >= self.stability_window:
            if not self._is_stable():
                return CancelReason.STABILITY_LOST
        
        # Check quality degradation
        if self._has_quality_degraded():
            return CancelReason.QUALITY_DEGRADED
        
        return None
    
    def _is_stable(self) -> bool:
        """Check if quality is stable over recent frames"""
        if len(self.quality_history) < self.stability_window:
            return True  # Not enough history
        
        # Get recent scores
        recent = list(self.quality_history)[-self.stability_window:]
        scores = [h["overall_score"] for h in recent]
        
        # Check variance
        if scores:
            variance = statistics.variance(scores)
            # Stable if variance < 0.01 (1% variation)
            return variance < 0.01
        
        return True
    
    def _has_quality_degraded(self) -> bool:
        """Check if quality has degraded significantly"""
        if len(self.quality_history) < 2:
            return False
        
        # Compare last two scores
        prev = self.quality_history[-2]["overall_score"]
        curr = self.quality_history[-1]["overall_score"]
        
        # Degraded if dropped by more than 20%
        return (prev - curr) > 0.20
    
    def _generate_messages(self, 
                          passed: bool,
                          cancel_reason: Optional[CancelReason],
                          scores: Dict[QualityMetric, QualityScore]) -> Tuple[str, str]:
        """Generate appropriate messages"""
        if cancel_reason:
            # Return cancel message
            return self.cancel_messages[cancel_reason]
        
        if passed:
            return ("Malinaw ang kuha!", "Good quality!")
        else:
            # Find main issue
            failed = [s for s in scores.values() if not s.passed]
            if failed:
                # Sort by how much they failed
                failed.sort(key=lambda s: s.value - s.threshold)
                main_issue = failed[0].metric
                
                # Get hint for main issue
                if main_issue in self.quality_hints:
                    return self.quality_hints[main_issue]
            
            return ("Hindi sapat ang quality", "Quality not sufficient")
    
    def _generate_hints(self, scores: Dict[QualityMetric, QualityScore]) -> List[str]:
        """Generate hints for failed metrics"""
        hints = []
        
        for metric, score in scores.items():
            if not score.passed and metric in self.quality_hints:
                tagalog_hint, _ = self.quality_hints[metric]
                hints.append(tagalog_hint)
        
        # Limit to top 3 hints
        return hints[:3]
    
    def get_stability_score(self) -> float:
        """
        Get stability score based on recent history
        
        Returns:
            Stability score (0.0 to 1.0)
        """
        if len(self.quality_history) < self.stability_window:
            return 1.0  # Assume stable if not enough history
        
        # Get recent scores
        recent = list(self.quality_history)[-self.stability_window:]
        scores = [h["overall_score"] for h in recent]
        
        if not scores:
            return 1.0
        
        # Calculate stability based on variance
        variance = statistics.variance(scores)
        
        # Convert variance to stability score
        # variance of 0 = stability of 1.0
        # variance of 0.1 = stability of 0.0
        stability = max(0.0, 1.0 - (variance * 10))
        
        return stability
    
    def reset(self):
        """Reset quality history and counters"""
        self.quality_history.clear()
        self.cancel_count = 0
        self.last_cancel_time = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get quality gate statistics"""
        return {
            "history_size": len(self.quality_history),
            "cancel_count": self.cancel_count,
            "last_cancel_time": self.last_cancel_time,
            "stability_score": self.get_stability_score(),
            "recent_scores": [
                h["overall_score"] 
                for h in list(self.quality_history)[-5:]
            ] if self.quality_history else []
        }


# Global quality gate manager
_quality_manager = None


def get_quality_manager() -> QualityGateManager:
    """Get or create the global quality manager"""
    global _quality_manager
    if _quality_manager is None:
        _quality_manager = QualityGateManager()
    return _quality_manager


def check_quality_gates(metrics: Dict[str, float]) -> Dict[str, Any]:
    """
    Convenience function to check quality gates
    
    Args:
        metrics: Quality metrics dictionary
        
    Returns:
        Quality gate result dictionary
    """
    manager = get_quality_manager()
    result = manager.check_quality(metrics)
    return result.to_dict()