"""
Face Threshold Validator
Phase 2: Strict validation and bounds enforcement for face scan thresholds

This module provides validation for all face scan thresholds with:
- Strict bounds checking
- Type validation
- Range enforcement
- Configuration validation
"""

import logging
from typing import Dict, Any, Optional, Tuple, List
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class ValidationResult:
    """Result of threshold validation"""
    def __init__(self, valid: bool, message: str = "", details: Optional[Dict] = None):
        self.valid = valid
        self.message = message
        self.details = details or {}


class ThresholdType(Enum):
    """Types of threshold values"""
    RATIO = "ratio"  # 0.0 to 1.0
    PERCENTAGE = "percentage"  # 0 to 100
    MILLISECONDS = "milliseconds"  # Time in ms
    PIXELS = "pixels"  # Pixel values
    DEGREES = "degrees"  # Angle in degrees
    COUNT = "count"  # Integer count
    SCORE = "score"  # Arbitrary score
    INTENSITY = "intensity"  # 0-255 brightness


@dataclass
class ThresholdDefinition:
    """Definition of a threshold with validation rules"""
    name: str
    type: ThresholdType
    min_value: float
    max_value: float
    default_value: float
    description: str
    strict: bool = True  # If True, enforce hard bounds
    
    def validate(self, value: Any) -> ValidationResult:
        """Validate a value against this threshold definition"""
        # Type checking
        if self.type in [ThresholdType.COUNT]:
            if not isinstance(value, int):
                try:
                    value = int(value)
                except (ValueError, TypeError):
                    return ValidationResult(
                        False, 
                        f"{self.name} must be an integer, got {type(value).__name__}"
                    )
        else:
            if not isinstance(value, (int, float)):
                try:
                    value = float(value)
                except (ValueError, TypeError):
                    return ValidationResult(
                        False,
                        f"{self.name} must be numeric, got {type(value).__name__}"
                    )
        
        # Bounds checking
        if self.strict:
            if value < self.min_value:
                return ValidationResult(
                    False,
                    f"{self.name} value {value} is below minimum {self.min_value}",
                    {"value": value, "min": self.min_value}
                )
            if value > self.max_value:
                return ValidationResult(
                    False,
                    f"{self.name} value {value} is above maximum {self.max_value}",
                    {"value": value, "max": self.max_value}
                )
        else:
            # Soft bounds - log warning but allow
            if value < self.min_value or value > self.max_value:
                logger.warning(
                    f"{self.name} value {value} is outside recommended range "
                    f"[{self.min_value}, {self.max_value}]"
                )
        
        return ValidationResult(True, "Valid", {"value": value})


class FaceThresholdValidator:
    """Validator for face scan thresholds with strict enforcement"""
    
    def __init__(self):
        """Initialize with threshold definitions"""
        self.thresholds = self._define_thresholds()
    
    def _define_thresholds(self) -> Dict[str, ThresholdDefinition]:
        """Define all face scan thresholds with strict validation rules"""
        return {
            # Geometry Thresholds
            "face_bbox_fill_min": ThresholdDefinition(
                "face_bbox_fill_min",
                ThresholdType.RATIO,
                0.1, 0.8, 0.3,
                "Minimum face bounding box fill ratio"
            ),
            "face_centering_tolerance": ThresholdDefinition(
                "face_centering_tolerance",
                ThresholdType.RATIO,
                0.05, 0.3, 0.15,
                "Maximum deviation from center"
            ),
            "face_pose_max_angle": ThresholdDefinition(
                "face_pose_max_angle",
                ThresholdType.DEGREES,
                10, 45, 30,
                "Maximum allowed pose angles (yaw/pitch/roll)"
            ),
            "face_tenengrad_min_640w": ThresholdDefinition(
                "face_tenengrad_min_640w",
                ThresholdType.SCORE,
                100, 2000, 500,
                "Minimum sharpness at 640px width"
            ),
            "face_brightness_mean_min": ThresholdDefinition(
                "face_brightness_mean_min",
                ThresholdType.INTENSITY,
                0, 255, 60,
                "Minimum acceptable brightness mean"
            ),
            "face_brightness_mean_max": ThresholdDefinition(
                "face_brightness_mean_max",
                ThresholdType.INTENSITY,
                0, 255, 200,
                "Maximum acceptable brightness mean"
            ),
            "face_brightness_p05_min": ThresholdDefinition(
                "face_brightness_p05_min",
                ThresholdType.INTENSITY,
                0, 255, 20,
                "5th percentile brightness minimum"
            ),
            "face_brightness_p95_max": ThresholdDefinition(
                "face_brightness_p95_max",
                ThresholdType.INTENSITY,
                0, 255, 235,
                "95th percentile brightness maximum"
            ),
            "face_stability_min_ms": ThresholdDefinition(
                "face_stability_min_ms",
                ThresholdType.MILLISECONDS,
                500, 2000, 900,
                "Minimum stable detection duration"
            ),
            
            # PAD Thresholds
            "face_pad_score_min": ThresholdDefinition(
                "face_pad_score_min",
                ThresholdType.SCORE,
                0.5, 1.0, 0.70,
                "Minimum passive liveness score"
            ),
            "face_pad_spoof_threshold": ThresholdDefinition(
                "face_pad_spoof_threshold",
                ThresholdType.SCORE,
                0.1, 0.5, 0.30,
                "Spoof detection threshold"
            ),
            "face_pad_fmr_target": ThresholdDefinition(
                "face_pad_fmr_target",
                ThresholdType.RATIO,
                0.001, 0.05, 0.01,
                "PAD False Match Rate target"
            ),
            "face_pad_fnmr_target": ThresholdDefinition(
                "face_pad_fnmr_target",
                ThresholdType.RATIO,
                0.01, 0.1, 0.03,
                "PAD False Non-Match Rate target"
            ),
            
            # Burst & Consensus
            "face_burst_max_frames": ThresholdDefinition(
                "face_burst_max_frames",
                ThresholdType.COUNT,
                10, 60, 24,
                "Maximum frames per burst"
            ),
            "face_burst_max_duration_ms": ThresholdDefinition(
                "face_burst_max_duration_ms",
                ThresholdType.MILLISECONDS,
                2000, 5000, 3500,
                "Maximum burst duration"
            ),
            "face_consensus_top_k": ThresholdDefinition(
                "face_consensus_top_k",
                ThresholdType.COUNT,
                3, 10, 5,
                "Number of top frames to consider"
            ),
            "face_consensus_median_min": ThresholdDefinition(
                "face_consensus_median_min",
                ThresholdType.SCORE,
                0.5, 0.8, 0.62,
                "Minimum median match score"
            ),
            "face_consensus_frame_min_count": ThresholdDefinition(
                "face_consensus_frame_min_count",
                ThresholdType.COUNT,
                1, 10, 3,
                "Minimum frames above threshold"
            ),
            "face_consensus_frame_min_score": ThresholdDefinition(
                "face_consensus_frame_min_score",
                ThresholdType.SCORE,
                0.4, 0.7, 0.58,
                "Per-frame minimum score"
            ),
            
            # Challenge Thresholds
            "face_challenge_action_count": ThresholdDefinition(
                "face_challenge_action_count",
                ThresholdType.COUNT,
                1, 5, 2,
                "Number of actions per challenge"
            ),
            "face_challenge_ttl_ms": ThresholdDefinition(
                "face_challenge_ttl_ms",
                ThresholdType.MILLISECONDS,
                5000, 15000, 7000,
                "Challenge time-to-live"
            ),
            "face_challenge_action_max_ms": ThresholdDefinition(
                "face_challenge_action_max_ms",
                ThresholdType.MILLISECONDS,
                2000, 5000, 3500,
                "Maximum time per action"
            ),
            "face_challenge_ear_threshold": ThresholdDefinition(
                "face_challenge_ear_threshold",
                ThresholdType.RATIO,
                0.1, 0.4, 0.2,
                "Eye Aspect Ratio threshold"
            ),
            "face_challenge_mar_threshold": ThresholdDefinition(
                "face_challenge_mar_threshold",
                ThresholdType.RATIO,
                0.3, 0.8, 0.5,
                "Mouth Aspect Ratio threshold"
            ),
            "face_challenge_yaw_threshold": ThresholdDefinition(
                "face_challenge_yaw_threshold",
                ThresholdType.DEGREES,
                20, 45, 30,
                "Yaw angle threshold"
            ),
            
            # Performance Targets
            "face_lock_p50_ms": ThresholdDefinition(
                "face_lock_p50_ms",
                ThresholdType.MILLISECONDS,
                500, 3000, 1200,
                "P50 time to achieve face lock"
            ),
            "face_lock_p95_ms": ThresholdDefinition(
                "face_lock_p95_ms",
                ThresholdType.MILLISECONDS,
                1000, 5000, 2500,
                "P95 time to achieve face lock"
            ),
            "face_countdown_min_ms": ThresholdDefinition(
                "face_countdown_min_ms",
                ThresholdType.MILLISECONDS,
                300, 1500, 600,
                "Minimum countdown duration after lock"
            ),
            "face_cancel_jitter_max_ms": ThresholdDefinition(
                "face_cancel_jitter_max_ms",
                ThresholdType.MILLISECONDS,
                10, 200, 50,
                "Maximum cancel-on-jitter response time"
            ),
            "face_challenge_pass_rate_target": ThresholdDefinition(
                "face_challenge_pass_rate_target",
                ThresholdType.RATIO,
                0.8, 1.0, 0.95,
                "Challenge pass rate target (good lighting)"
            ),
            "face_tar_at_far1_target": ThresholdDefinition(
                "face_tar_at_far1_target",
                ThresholdType.RATIO,
                0.9, 1.0, 0.98,
                "TAR@FAR1% target"
            ),
        }
    
    def validate_threshold(self, name: str, value: Any) -> ValidationResult:
        """Validate a single threshold value"""
        if name not in self.thresholds:
            return ValidationResult(
                False,
                f"Unknown threshold: {name}",
                {"available": list(self.thresholds.keys())}
            )
        
        return self.thresholds[name].validate(value)
    
    def validate_all(self, values: Dict[str, Any]) -> Tuple[bool, List[ValidationResult]]:
        """Validate all threshold values"""
        results = []
        all_valid = True
        
        for name, value in values.items():
            if name.startswith("face_"):  # Only validate face thresholds
                result = self.validate_threshold(name, value)
                results.append(result)
                if not result.valid:
                    all_valid = False
                    logger.error(f"Threshold validation failed: {result.message}")
        
        return all_valid, results
    
    def get_defaults(self) -> Dict[str, Any]:
        """Get default values for all thresholds"""
        return {
            name: definition.default_value
            for name, definition in self.thresholds.items()
        }
    
    def get_bounds(self, name: str) -> Optional[Tuple[float, float]]:
        """Get min/max bounds for a threshold"""
        if name in self.thresholds:
            definition = self.thresholds[name]
            return (definition.min_value, definition.max_value)
        return None
    
    def validate_brightness_range(self, mean_min: float, mean_max: float) -> ValidationResult:
        """Special validation for brightness range consistency"""
        if mean_min >= mean_max:
            return ValidationResult(
                False,
                f"Brightness mean_min ({mean_min}) must be less than mean_max ({mean_max})",
                {"mean_min": mean_min, "mean_max": mean_max}
            )
        return ValidationResult(True, "Brightness range valid")
    
    def validate_performance_targets(self, p50: float, p95: float) -> ValidationResult:
        """Special validation for performance percentiles"""
        if p50 >= p95:
            return ValidationResult(
                False,
                f"P50 ({p50}ms) must be less than P95 ({p95}ms)",
                {"p50": p50, "p95": p95}
            )
        return ValidationResult(True, "Performance targets valid")
    
    def export_config(self) -> Dict[str, Any]:
        """Export threshold configuration for documentation"""
        config = {}
        for name, definition in self.thresholds.items():
            config[name] = {
                "type": definition.type.value,
                "min": definition.min_value,
                "max": definition.max_value,
                "default": definition.default_value,
                "description": definition.description,
                "strict": definition.strict
            }
        return config


# Singleton instance
_validator = None

def get_validator() -> FaceThresholdValidator:
    """Get singleton validator instance"""
    global _validator
    if _validator is None:
        _validator = FaceThresholdValidator()
    return _validator