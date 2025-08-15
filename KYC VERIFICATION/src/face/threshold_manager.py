"""
Face Threshold Manager - Configurable thresholds for strict face gates
Phase 2: Centralized threshold management with validation and environment overrides
"""

import os
from typing import Dict, Any, Optional, Tuple, Union, List
from dataclasses import dataclass, field
import json
import logging

logger = logging.getLogger(__name__)


@dataclass
class FaceThresholds:
    """Face verification thresholds with validation"""
    
    # Bounding box and positioning
    bbox_fill_min: float = 0.15  # Minimum face area as fraction of frame
    bbox_fill_max: float = 0.65  # Maximum face area to prevent too close
    centering_max_offset: float = 0.2  # Max offset from center (fraction)
    
    # Pose limits (degrees)
    pose_max_yaw: float = 15.0  # Left/right head turn
    pose_max_pitch: float = 15.0  # Up/down head tilt
    pose_max_roll: float = 10.0  # Head tilt/rotation
    
    # Image quality
    blur_min_tenengrad: float = 0.85  # Minimum Tenengrad sharpness at 640w
    brightness_mean_min: int = 60  # Minimum mean brightness
    brightness_mean_max: int = 200  # Maximum mean brightness
    brightness_p05_min: int = 20  # Minimum 5th percentile (avoid too dark)
    brightness_p95_max: int = 235  # Maximum 95th percentile (avoid blown out)
    
    # Stability and timing
    stability_min_ms: int = 900  # Minimum continuous pass time for lock
    jitter_cancel_ms: int = 50  # Cancel if jitter exceeds this
    countdown_min_ms: int = 600  # Minimum countdown after lock
    
    # PAD (Presentation Attack Detection)
    pad_min_score: float = 0.70  # Minimum passive liveness score
    pad_spoof_threshold: float = 0.30  # Below this = definite spoof
    
    # Burst capture limits
    burst_max_frames: int = 24  # Maximum frames in burst
    burst_max_duration_ms: int = 3500  # Maximum burst duration
    burst_min_frames: int = 8  # Minimum frames for consensus
    
    # Biometric matching
    match_threshold_median: float = 0.62  # Median of top-k must exceed
    match_threshold_min: float = 0.58  # No frame in top-k below this
    match_threshold_count: int = 3  # Minimum frames above threshold
    match_top_k: int = 5  # Number of best frames to consider
    
    # Challenge verification
    challenge_ear_threshold: float = 0.21  # Eye aspect ratio for blink
    challenge_mar_threshold: float = 0.5  # Mouth aspect ratio for open
    challenge_yaw_threshold: float = 20.0  # Degrees for head turn
    challenge_timeout_ms: int = 3500  # Per-action timeout
    challenge_ttl_seconds: int = 7  # Total challenge time limit
    
    def validate(self) -> Tuple[bool, List[str]]:
        """Validate threshold values are within reasonable bounds"""
        errors = []
        
        # Validate ranges
        if not 0.05 <= self.bbox_fill_min <= 0.5:
            errors.append(f"bbox_fill_min {self.bbox_fill_min} out of range [0.05, 0.5]")
        if not 0.3 <= self.bbox_fill_max <= 0.9:
            errors.append(f"bbox_fill_max {self.bbox_fill_max} out of range [0.3, 0.9]")
        if self.bbox_fill_min >= self.bbox_fill_max:
            errors.append("bbox_fill_min must be less than bbox_fill_max")
            
        if not 0 <= self.centering_max_offset <= 0.5:
            errors.append(f"centering_max_offset {self.centering_max_offset} out of range [0, 0.5]")
            
        if not 5 <= self.pose_max_yaw <= 30:
            errors.append(f"pose_max_yaw {self.pose_max_yaw} out of range [5, 30]")
        if not 5 <= self.pose_max_pitch <= 30:
            errors.append(f"pose_max_pitch {self.pose_max_pitch} out of range [5, 30]")
        if not 5 <= self.pose_max_roll <= 20:
            errors.append(f"pose_max_roll {self.pose_max_roll} out of range [5, 20]")
            
        if not 0.5 <= self.blur_min_tenengrad <= 1.0:
            errors.append(f"blur_min_tenengrad {self.blur_min_tenengrad} out of range [0.5, 1.0]")
            
        if not 30 <= self.brightness_mean_min <= 100:
            errors.append(f"brightness_mean_min {self.brightness_mean_min} out of range [30, 100]")
        if not 150 <= self.brightness_mean_max <= 250:
            errors.append(f"brightness_mean_max {self.brightness_mean_max} out of range [150, 250]")
        if self.brightness_mean_min >= self.brightness_mean_max:
            errors.append("brightness_mean_min must be less than brightness_mean_max")
            
        if not 500 <= self.stability_min_ms <= 2000:
            errors.append(f"stability_min_ms {self.stability_min_ms} out of range [500, 2000]")
        if not 10 <= self.jitter_cancel_ms <= 200:
            errors.append(f"jitter_cancel_ms {self.jitter_cancel_ms} out of range [10, 200]")
        if not 300 <= self.countdown_min_ms <= 1500:
            errors.append(f"countdown_min_ms {self.countdown_min_ms} out of range [300, 1500]")
            
        if not 0.5 <= self.pad_min_score <= 0.95:
            errors.append(f"pad_min_score {self.pad_min_score} out of range [0.5, 0.95]")
        if not 0.1 <= self.pad_spoof_threshold <= 0.5:
            errors.append(f"pad_spoof_threshold {self.pad_spoof_threshold} out of range [0.1, 0.5]")
            
        if not 5 <= self.burst_max_frames <= 50:
            errors.append(f"burst_max_frames {self.burst_max_frames} out of range [5, 50]")
        if not 1000 <= self.burst_max_duration_ms <= 10000:
            errors.append(f"burst_max_duration_ms {self.burst_max_duration_ms} out of range [1000, 10000]")
        if not 3 <= self.burst_min_frames <= 20:
            errors.append(f"burst_min_frames {self.burst_min_frames} out of range [3, 20]")
            
        if not 0.4 <= self.match_threshold_median <= 0.8:
            errors.append(f"match_threshold_median {self.match_threshold_median} out of range [0.4, 0.8]")
        if not 0.3 <= self.match_threshold_min <= 0.7:
            errors.append(f"match_threshold_min {self.match_threshold_min} out of range [0.3, 0.7]")
        if self.match_threshold_min >= self.match_threshold_median:
            errors.append("match_threshold_min must be less than match_threshold_median")
        if not 1 <= self.match_threshold_count <= 10:
            errors.append(f"match_threshold_count {self.match_threshold_count} out of range [1, 10]")
        if not 3 <= self.match_top_k <= 10:
            errors.append(f"match_top_k {self.match_top_k} out of range [3, 10]")
            
        if not 0.1 <= self.challenge_ear_threshold <= 0.4:
            errors.append(f"challenge_ear_threshold {self.challenge_ear_threshold} out of range [0.1, 0.4]")
        if not 0.3 <= self.challenge_mar_threshold <= 0.8:
            errors.append(f"challenge_mar_threshold {self.challenge_mar_threshold} out of range [0.3, 0.8]")
        if not 10 <= self.challenge_yaw_threshold <= 45:
            errors.append(f"challenge_yaw_threshold {self.challenge_yaw_threshold} out of range [10, 45]")
        if not 1000 <= self.challenge_timeout_ms <= 10000:
            errors.append(f"challenge_timeout_ms {self.challenge_timeout_ms} out of range [1000, 10000]")
        if not 3 <= self.challenge_ttl_seconds <= 30:
            errors.append(f"challenge_ttl_seconds {self.challenge_ttl_seconds} out of range [3, 30]")
            
        return len(errors) == 0, errors
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "bbox_fill_min": self.bbox_fill_min,
            "bbox_fill_max": self.bbox_fill_max,
            "centering_max_offset": self.centering_max_offset,
            "pose_max_yaw": self.pose_max_yaw,
            "pose_max_pitch": self.pose_max_pitch,
            "pose_max_roll": self.pose_max_roll,
            "blur_min_tenengrad": self.blur_min_tenengrad,
            "brightness_mean_min": self.brightness_mean_min,
            "brightness_mean_max": self.brightness_mean_max,
            "brightness_p05_min": self.brightness_p05_min,
            "brightness_p95_max": self.brightness_p95_max,
            "stability_min_ms": self.stability_min_ms,
            "jitter_cancel_ms": self.jitter_cancel_ms,
            "countdown_min_ms": self.countdown_min_ms,
            "pad_min_score": self.pad_min_score,
            "pad_spoof_threshold": self.pad_spoof_threshold,
            "burst_max_frames": self.burst_max_frames,
            "burst_max_duration_ms": self.burst_max_duration_ms,
            "burst_min_frames": self.burst_min_frames,
            "match_threshold_median": self.match_threshold_median,
            "match_threshold_min": self.match_threshold_min,
            "match_threshold_count": self.match_threshold_count,
            "match_top_k": self.match_top_k,
            "challenge_ear_threshold": self.challenge_ear_threshold,
            "challenge_mar_threshold": self.challenge_mar_threshold,
            "challenge_yaw_threshold": self.challenge_yaw_threshold,
            "challenge_timeout_ms": self.challenge_timeout_ms,
            "challenge_ttl_seconds": self.challenge_ttl_seconds,
        }


class ThresholdManager:
    """Manages face verification thresholds with environment overrides"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize threshold manager
        
        Args:
            config_path: Optional path to JSON config file
        """
        self.thresholds = FaceThresholds()
        
        # Load from config file if provided
        if config_path and os.path.exists(config_path):
            self._load_from_file(config_path)
        
        # Apply environment variable overrides
        self._apply_env_overrides()
        
        # Validate final thresholds
        valid, errors = self.thresholds.validate()
        if not valid:
            logger.warning(f"Threshold validation errors: {errors}")
            # Continue with defaults for invalid values
            self._apply_safe_defaults(errors)
    
    def _load_from_file(self, config_path: str) -> None:
        """Load thresholds from JSON config file"""
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            for key, value in config.items():
                if hasattr(self.thresholds, key):
                    setattr(self.thresholds, key, value)
                else:
                    logger.warning(f"Unknown threshold key in config: {key}")
        except Exception as e:
            logger.error(f"Failed to load threshold config: {e}")
    
    def _apply_env_overrides(self) -> None:
        """Apply environment variable overrides
        
        Environment variables should be prefixed with FACE_THRESHOLD_
        e.g., FACE_THRESHOLD_BBOX_FILL_MIN=0.2
        """
        prefix = "FACE_THRESHOLD_"
        
        for key in dir(self.thresholds):
            if key.startswith('_'):
                continue
            
            env_key = f"{prefix}{key.upper()}"
            env_value = os.getenv(env_key)
            
            if env_value is not None:
                try:
                    # Determine type from current value
                    current_value = getattr(self.thresholds, key)
                    if isinstance(current_value, float):
                        new_value = float(env_value)
                    elif isinstance(current_value, int):
                        new_value = int(env_value)
                    else:
                        new_value = env_value
                    
                    setattr(self.thresholds, key, new_value)
                    logger.info(f"Applied env override: {key} = {new_value}")
                except Exception as e:
                    logger.error(f"Failed to apply env override for {key}: {e}")
    
    def _apply_safe_defaults(self, errors: List[str]) -> None:
        """Apply safe default values for invalid thresholds"""
        # Parse errors and reset to safe defaults
        for error in errors:
            if "bbox_fill_min" in error:
                self.thresholds.bbox_fill_min = 0.15
            elif "bbox_fill_max" in error:
                self.thresholds.bbox_fill_max = 0.65
            elif "centering_max_offset" in error:
                self.thresholds.centering_max_offset = 0.2
            elif "pose_max_yaw" in error:
                self.thresholds.pose_max_yaw = 15.0
            elif "pose_max_pitch" in error:
                self.thresholds.pose_max_pitch = 15.0
            elif "pose_max_roll" in error:
                self.thresholds.pose_max_roll = 10.0
            elif "blur_min_tenengrad" in error:
                self.thresholds.blur_min_tenengrad = 0.85
            elif "brightness_mean_min" in error:
                self.thresholds.brightness_mean_min = 60
            elif "brightness_mean_max" in error:
                self.thresholds.brightness_mean_max = 200
            elif "stability_min_ms" in error:
                self.thresholds.stability_min_ms = 900
            elif "pad_min_score" in error:
                self.thresholds.pad_min_score = 0.70
            elif "match_threshold_median" in error:
                self.thresholds.match_threshold_median = 0.62
            elif "match_threshold_min" in error:
                self.thresholds.match_threshold_min = 0.58
    
    def get_thresholds(self) -> FaceThresholds:
        """Get current threshold values"""
        return self.thresholds
    
    def get_threshold_dict(self) -> Dict[str, Any]:
        """Get thresholds as dictionary"""
        return self.thresholds.to_dict()
    
    def get_lock_thresholds(self) -> Dict[str, Any]:
        """Get thresholds specific to face lock checking"""
        return {
            "bbox_fill_min": self.thresholds.bbox_fill_min,
            "bbox_fill_max": self.thresholds.bbox_fill_max,
            "centering_max_offset": self.thresholds.centering_max_offset,
            "pose_max_degrees": max(
                self.thresholds.pose_max_yaw,
                self.thresholds.pose_max_pitch,
                self.thresholds.pose_max_roll
            ),
            "blur_min": self.thresholds.blur_min_tenengrad,
            "brightness_mean": [
                self.thresholds.brightness_mean_min,
                self.thresholds.brightness_mean_max
            ],
            "brightness_p05_min": self.thresholds.brightness_p05_min,
            "brightness_p95_max": self.thresholds.brightness_p95_max,
            "stability_min_ms": self.thresholds.stability_min_ms,
            "jitter_cancel_ms": self.thresholds.jitter_cancel_ms,
        }
    
    def get_pad_thresholds(self) -> Dict[str, float]:
        """Get PAD-specific thresholds"""
        return {
            "min_score": self.thresholds.pad_min_score,
            "spoof_threshold": self.thresholds.pad_spoof_threshold,
        }
    
    def get_match_thresholds(self) -> Dict[str, Any]:
        """Get biometric matching thresholds"""
        return {
            "median": self.thresholds.match_threshold_median,
            "min": self.thresholds.match_threshold_min,
            "count": self.thresholds.match_threshold_count,
            "top_k": self.thresholds.match_top_k,
        }
    
    def get_challenge_thresholds(self) -> Dict[str, Any]:
        """Get challenge verification thresholds"""
        return {
            "ear": self.thresholds.challenge_ear_threshold,
            "mar": self.thresholds.challenge_mar_threshold,
            "yaw": self.thresholds.challenge_yaw_threshold,
            "timeout_ms": self.thresholds.challenge_timeout_ms,
            "ttl_seconds": self.thresholds.challenge_ttl_seconds,
        }
    
    def save_snapshot(self, path: str) -> None:
        """Save current thresholds to file for audit"""
        try:
            with open(path, 'w') as f:
                json.dump(self.get_threshold_dict(), f, indent=2)
            logger.info(f"Saved threshold snapshot to {path}")
        except Exception as e:
            logger.error(f"Failed to save threshold snapshot: {e}")


# Global instance
_threshold_manager: Optional[ThresholdManager] = None


def get_threshold_manager() -> ThresholdManager:
    """Get or create global threshold manager instance"""
    global _threshold_manager
    if _threshold_manager is None:
        config_path = os.getenv("FACE_THRESHOLD_CONFIG_PATH")
        _threshold_manager = ThresholdManager(config_path)
    return _threshold_manager