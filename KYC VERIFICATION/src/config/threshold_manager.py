"""
Config-driven Threshold Management Framework
Part of KYC Bank-Grade Parity - Phase 0

This module provides centralized threshold management with:
- Environment variable loading
- Dynamic threshold updates
- Validation and bounds checking
- Audit logging of changes
"""

import os
import json
import logging
from typing import Dict, Any, Optional, Union, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Manila timezone (UTC+8)
MANILA_TZ = timezone(timedelta(hours=8))


class ThresholdCategory(Enum):
    """Categories of thresholds for organization"""
    SLO = "slo"
    PAD = "pad"
    NFC = "nfc"
    ADAPTER = "adapter"
    RISK = "risk"
    AML = "aml"
    TM = "tm"
    REVIEW = "review"
    SECURITY = "security"
    RETENTION = "retention"
    OBSERVABILITY = "observability"
    DEPLOYMENT = "deployment"
    COMPLIANCE = "compliance"
    API = "api"
    QUALITY = "quality"
    OPERATIONAL = "operational"
    BUILD = "build"
    FACE = "face"  # Added for face scan thresholds


@dataclass
class ThresholdConfig:
    """Configuration for a single threshold"""
    name: str
    category: ThresholdCategory
    value: Union[float, int, str, bool]
    min_value: Optional[Union[float, int]] = None
    max_value: Optional[Union[float, int]] = None
    unit: Optional[str] = None
    description: Optional[str] = None
    env_var: Optional[str] = None
    last_updated: Optional[str] = None
    updated_by: Optional[str] = None
    
    def validate(self) -> bool:
        """Validate threshold against bounds"""
        if isinstance(self.value, (int, float)):
            if self.min_value is not None and self.value < self.min_value:
                raise ValueError(f"{self.name} value {self.value} below minimum {self.min_value}")
            if self.max_value is not None and self.value > self.max_value:
                raise ValueError(f"{self.name} value {self.value} above maximum {self.max_value}")
        return True


class ThresholdManager:
    """Manages all system thresholds with config-driven approach"""
    
    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize threshold manager
        
        Args:
            config_path: Optional path to JSON config file
        """
        self.config_path = config_path or Path("/workspace/KYC VERIFICATION/configs/thresholds.json")
        self.thresholds: Dict[str, ThresholdConfig] = {}
        self._load_defaults()
        self._load_from_env()
        if self.config_path.exists():
            self._load_from_file()
    
    def _load_defaults(self):
        """Load default threshold configurations"""
        defaults = [
            # SLO Thresholds
            ThresholdConfig("decision_p50", ThresholdCategory.SLO, 20000, 0, 60000, "ms", 
                          "P50 decision latency", "SLO_DECISION_P50_MS"),
            ThresholdConfig("decision_p95", ThresholdCategory.SLO, 60000, 0, 120000, "ms",
                          "P95 decision latency", "SLO_DECISION_P95_MS"),
            ThresholdConfig("availability_target", ThresholdCategory.SLO, 0.999, 0.9, 1.0, "ratio",
                          "System availability target", "SLO_AVAILABILITY_TARGET"),
            
            # PAD Thresholds
            ThresholdConfig("pad_far", ThresholdCategory.PAD, 0.01, 0, 0.1, "ratio",
                          "PAD False Accept Rate", "PAD_FAR_THRESHOLD"),
            ThresholdConfig("pad_frr", ThresholdCategory.PAD, 0.03, 0, 0.1, "ratio",
                          "PAD False Reject Rate", "PAD_FRR_THRESHOLD"),
            ThresholdConfig("pad_tar_far1", ThresholdCategory.PAD, 0.98, 0.9, 1.0, "ratio",
                          "PAD TAR at FAR 1%", "PAD_TAR_FAR1_TARGET"),
            
            # AML Thresholds
            ThresholdConfig("aml_rescreen_days", ThresholdCategory.AML, 30, 1, 365, "days",
                          "AML rescreen interval", "AML_RESCREEN_INTERVAL_DAYS"),
            ThresholdConfig("aml_circuit_breaker", ThresholdCategory.AML, 5, 1, 20, "failures",
                          "Circuit breaker threshold", "AML_CIRCUIT_BREAKER_THRESHOLD"),
            
            # Transaction Monitoring
            ThresholdConfig("tm_velocity_hourly", ThresholdCategory.TM, 10, 1, 100, "transactions",
                          "Hourly velocity limit", "TM_VELOCITY_THRESHOLD_HOURLY"),
            ThresholdConfig("tm_velocity_daily", ThresholdCategory.TM, 50, 1, 500, "transactions",
                          "Daily velocity limit", "TM_VELOCITY_THRESHOLD_DAILY"),
            ThresholdConfig("tm_geovelocity", ThresholdCategory.TM, 500, 10, 10000, "km/hour",
                          "Geovelocity threshold", "TM_GEOVELOCITY_THRESHOLD_KM_PER_HOUR"),
            ThresholdConfig("tm_structuring_amount", ThresholdCategory.TM, 500000, 10000, 10000000, "PHP",
                          "Structuring detection amount", "TM_STRUCTURING_THRESHOLD_AMOUNT"),
            
            # Review Console
            ThresholdConfig("review_irr_kappa", ThresholdCategory.REVIEW, 0.8, 0.6, 1.0, "ratio",
                          "Inter-rater reliability target", "REVIEW_IRR_KAPPA_TARGET"),
            ThresholdConfig("review_dual_control_risk_threshold", ThresholdCategory.REVIEW, 0.8, 0.0, 1.0, "score",
                          "Risk threshold for dual control", "REVIEW_DUAL_CONTROL_RISK_THRESHOLD"),
            
            # Retention
            ThresholdConfig("retention_days", ThresholdCategory.RETENTION, 2555, 365, 3650, "days",
                          "Data retention period", "RETENTION_POLICY_DAYS"),
            
            # Operational
            ThresholdConfig("rate_limit_per_minute", ThresholdCategory.OPERATIONAL, 1000, 10, 10000, "requests",
                          "API rate limit", "RATE_LIMIT_PER_MINUTE"),
            
            # Face Scan - Geometry Thresholds
            ThresholdConfig("face_bbox_fill_min", ThresholdCategory.FACE, 0.3, 0.1, 0.8, "ratio",
                          "Minimum face bounding box fill ratio", "FACE_BBOX_FILL_MIN"),
            ThresholdConfig("face_centering_tolerance", ThresholdCategory.FACE, 0.15, 0.05, 0.3, "ratio",
                          "Maximum deviation from center", "FACE_CENTERING_TOLERANCE"),
            ThresholdConfig("face_pose_max_angle", ThresholdCategory.FACE, 30, 10, 45, "degrees",
                          "Maximum allowed pose angles (yaw/pitch/roll)", "FACE_POSE_MAX_ANGLE"),
            ThresholdConfig("face_tenengrad_min_640w", ThresholdCategory.FACE, 500, 100, 2000, "score",
                          "Minimum sharpness at 640px width", "FACE_TENENGRAD_MIN_640W"),
            ThresholdConfig("face_brightness_mean_min", ThresholdCategory.FACE, 60, 0, 255, "intensity",
                          "Minimum acceptable brightness mean", "FACE_BRIGHTNESS_MEAN_MIN"),
            ThresholdConfig("face_brightness_mean_max", ThresholdCategory.FACE, 200, 0, 255, "intensity",
                          "Maximum acceptable brightness mean", "FACE_BRIGHTNESS_MEAN_MAX"),
            ThresholdConfig("face_brightness_p05_min", ThresholdCategory.FACE, 20, 0, 255, "intensity",
                          "5th percentile brightness minimum", "FACE_BRIGHTNESS_P05_MIN"),
            ThresholdConfig("face_brightness_p95_max", ThresholdCategory.FACE, 235, 0, 255, "intensity",
                          "95th percentile brightness maximum", "FACE_BRIGHTNESS_P95_MAX"),
            ThresholdConfig("face_stability_min_ms", ThresholdCategory.FACE, 900, 500, 2000, "ms",
                          "Minimum stable detection duration", "FACE_STABILITY_MIN_MS"),
            
            # Face Scan - PAD Thresholds
            ThresholdConfig("face_pad_score_min", ThresholdCategory.FACE, 0.70, 0.5, 1.0, "score",
                          "Minimum passive liveness score", "FACE_PAD_SCORE_MIN"),
            ThresholdConfig("face_pad_spoof_threshold", ThresholdCategory.FACE, 0.30, 0.1, 0.5, "score",
                          "Spoof detection threshold", "FACE_PAD_SPOOF_THRESHOLD"),
            ThresholdConfig("face_pad_fmr_target", ThresholdCategory.FACE, 0.01, 0.001, 0.05, "ratio",
                          "PAD False Match Rate target", "FACE_PAD_FMR_TARGET"),
            ThresholdConfig("face_pad_fnmr_target", ThresholdCategory.FACE, 0.03, 0.01, 0.1, "ratio",
                          "PAD False Non-Match Rate target", "FACE_PAD_FNMR_TARGET"),
            
            # Face Scan - Burst & Consensus
            ThresholdConfig("face_burst_max_frames", ThresholdCategory.FACE, 24, 10, 60, "frames",
                          "Maximum frames per burst", "FACE_BURST_MAX_FRAMES"),
            ThresholdConfig("face_burst_max_duration_ms", ThresholdCategory.FACE, 3500, 2000, 5000, "ms",
                          "Maximum burst duration", "FACE_BURST_MAX_DURATION_MS"),
            ThresholdConfig("face_consensus_top_k", ThresholdCategory.FACE, 5, 3, 10, "frames",
                          "Number of top frames to consider", "FACE_CONSENSUS_TOP_K"),
            ThresholdConfig("face_consensus_median_min", ThresholdCategory.FACE, 0.62, 0.5, 0.8, "score",
                          "Minimum median match score", "FACE_CONSENSUS_MEDIAN_MIN"),
            ThresholdConfig("face_consensus_frame_min_count", ThresholdCategory.FACE, 3, 1, 10, "frames",
                          "Minimum frames above threshold", "FACE_CONSENSUS_FRAME_MIN_COUNT"),
            ThresholdConfig("face_consensus_frame_min_score", ThresholdCategory.FACE, 0.58, 0.4, 0.7, "score",
                          "Per-frame minimum score", "FACE_CONSENSUS_FRAME_MIN_SCORE"),
            
            # Face Scan - Challenge Thresholds
            ThresholdConfig("face_challenge_action_count", ThresholdCategory.FACE, 2, 1, 5, "actions",
                          "Number of actions per challenge", "FACE_CHALLENGE_ACTION_COUNT"),
            ThresholdConfig("face_challenge_ttl_ms", ThresholdCategory.FACE, 7000, 5000, 15000, "ms",
                          "Challenge time-to-live", "FACE_CHALLENGE_TTL_MS"),
            ThresholdConfig("face_challenge_action_max_ms", ThresholdCategory.FACE, 3500, 2000, 5000, "ms",
                          "Maximum time per action", "FACE_CHALLENGE_ACTION_MAX_MS"),
            ThresholdConfig("face_challenge_ear_threshold", ThresholdCategory.FACE, 0.2, 0.1, 0.4, "ratio",
                          "Eye Aspect Ratio threshold", "FACE_CHALLENGE_EAR_THRESHOLD"),
            ThresholdConfig("face_challenge_mar_threshold", ThresholdCategory.FACE, 0.5, 0.3, 0.8, "ratio",
                          "Mouth Aspect Ratio threshold", "FACE_CHALLENGE_MAR_THRESHOLD"),
            ThresholdConfig("face_challenge_yaw_threshold", ThresholdCategory.FACE, 30, 20, 45, "degrees",
                          "Yaw angle threshold", "FACE_CHALLENGE_YAW_THRESHOLD"),
            
            # Face Scan - Performance Targets
            ThresholdConfig("face_lock_p50_ms", ThresholdCategory.FACE, 1200, 500, 3000, "ms",
                          "P50 time to achieve face lock", "FACE_LOCK_P50_MS"),
            ThresholdConfig("face_lock_p95_ms", ThresholdCategory.FACE, 2500, 1000, 5000, "ms",
                          "P95 time to achieve face lock", "FACE_LOCK_P95_MS"),
            ThresholdConfig("face_countdown_min_ms", ThresholdCategory.FACE, 600, 300, 1500, "ms",
                          "Minimum countdown duration after lock", "FACE_COUNTDOWN_MIN_MS"),
            ThresholdConfig("face_cancel_jitter_max_ms", ThresholdCategory.FACE, 50, 10, 200, "ms",
                          "Maximum cancel-on-jitter response time", "FACE_CANCEL_JITTER_MAX_MS"),
            ThresholdConfig("face_challenge_pass_rate_target", ThresholdCategory.FACE, 0.95, 0.8, 1.0, "ratio",
                          "Challenge pass rate target (good lighting)", "FACE_CHALLENGE_PASS_RATE_TARGET"),
            ThresholdConfig("face_tar_at_far1_target", ThresholdCategory.FACE, 0.98, 0.9, 1.0, "ratio",
                          "TAR@FAR1% target", "FACE_TAR_AT_FAR1_TARGET"),
        ]
        
        for config in defaults:
            self.thresholds[config.name] = config
    
    def _load_from_env(self):
        """Load threshold values from environment variables"""
        for name, config in self.thresholds.items():
            if config.env_var and config.env_var in os.environ:
                env_value = os.environ[config.env_var]
                try:
                    # Convert to appropriate type
                    if isinstance(config.value, bool):
                        config.value = env_value.lower() in ('true', '1', 'yes')
                    elif isinstance(config.value, int):
                        config.value = int(env_value)
                    elif isinstance(config.value, float):
                        config.value = float(env_value)
                    else:
                        config.value = env_value
                    
                    config.validate()
                    logger.info(f"Loaded {name} from env: {config.value}")
                except Exception as e:
                    logger.error(f"Failed to load {name} from env: {e}")
    
    def _load_from_file(self):
        """Load thresholds from JSON config file"""
        try:
            with open(self.config_path, 'r') as f:
                data = json.load(f)
                for name, values in data.items():
                    if name in self.thresholds:
                        for key, value in values.items():
                            if hasattr(self.thresholds[name], key):
                                setattr(self.thresholds[name], key, value)
                        self.thresholds[name].validate()
                logger.info(f"Loaded {len(data)} thresholds from {self.config_path}")
        except FileNotFoundError:
            logger.info(f"No config file at {self.config_path}, using defaults")
        except Exception as e:
            logger.error(f"Error loading config file: {e}")
    
    def get(self, name: str) -> Any:
        """
        Get threshold value by name
        
        Args:
            name: Threshold name
            
        Returns:
            Threshold value
            
        Raises:
            KeyError: If threshold not found
        """
        if name not in self.thresholds:
            raise KeyError(f"Threshold '{name}' not found")
        return self.thresholds[name].value
    
    def set(self, name: str, value: Any, updated_by: str = "system") -> bool:
        """
        Update threshold value
        
        Args:
            name: Threshold name
            value: New value
            updated_by: User/system making the change
            
        Returns:
            True if successful
            
        Raises:
            KeyError: If threshold not found
            ValueError: If validation fails
        """
        if name not in self.thresholds:
            raise KeyError(f"Threshold '{name}' not found")
        
        config = self.thresholds[name]
        old_value = config.value
        config.value = value
        
        try:
            config.validate()
            config.last_updated = datetime.now(MANILA_TZ).isoformat()
            config.updated_by = updated_by
            
            # Log the change
            logger.info(f"Threshold '{name}' updated: {old_value} -> {value} by {updated_by}")
            
            # Save to file if path exists
            if self.config_path:
                self.save()
            
            return True
        except Exception as e:
            # Rollback on failure
            config.value = old_value
            raise ValueError(f"Failed to update threshold: {e}")
    
    def get_by_category(self, category: ThresholdCategory) -> Dict[str, Any]:
        """
        Get all thresholds in a category
        
        Args:
            category: Threshold category
            
        Returns:
            Dictionary of threshold names to values
        """
        return {
            name: config.value
            for name, config in self.thresholds.items()
            if config.category == category
        }
    
    def save(self) -> bool:
        """
        Save current thresholds to config file
        
        Returns:
            True if successful
        """
        try:
            # Ensure directory exists
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Convert to serializable format
            data = {}
            for name, config in self.thresholds.items():
                data[name] = {
                    "value": config.value,
                    "category": config.category.value,
                    "unit": config.unit,
                    "description": config.description,
                    "last_updated": config.last_updated,
                    "updated_by": config.updated_by
                }
            
            # Write to file
            with open(self.config_path, 'w') as f:
                json.dump(data, f, indent=2)
            
            logger.info(f"Saved {len(data)} thresholds to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save thresholds: {e}")
            return False
    
    def validate_all(self) -> Dict[str, bool]:
        """
        Validate all thresholds
        
        Returns:
            Dictionary of threshold names to validation status
        """
        results = {}
        for name, config in self.thresholds.items():
            try:
                config.validate()
                results[name] = True
            except Exception as e:
                logger.error(f"Validation failed for {name}: {e}")
                results[name] = False
        return results
    
    def export_env_template(self) -> str:
        """
        Export threshold configuration as environment variable template
        
        Returns:
            Environment variable template string
        """
        lines = ["# Threshold Configuration Environment Variables"]
        lines.append(f"# Generated: {datetime.now(MANILA_TZ).isoformat()}")
        lines.append("")
        
        current_category = None
        for name, config in sorted(self.thresholds.items(), key=lambda x: (x[1].category.value, x[0])):
            if config.category != current_category:
                current_category = config.category
                lines.append(f"\n# {current_category.value.upper()} Thresholds")
            
            if config.env_var:
                comment = f"  # {config.description}" if config.description else ""
                unit = f" ({config.unit})" if config.unit else ""
                lines.append(f"{config.env_var}={config.value}{comment}{unit}")
        
        return "\n".join(lines)
    
    # ============= Face Threshold Getter Methods =============
    
    def get_face_geometry_thresholds(self) -> Dict[str, Any]:
        """Get all face geometry thresholds"""
        return {
            "bbox_fill_min": self.get("face_bbox_fill_min"),
            "centering_tolerance": self.get("face_centering_tolerance"),
            "pose_max_angle": self.get("face_pose_max_angle"),
            "tenengrad_min_640w": self.get("face_tenengrad_min_640w"),
            "brightness_mean_min": self.get("face_brightness_mean_min"),
            "brightness_mean_max": self.get("face_brightness_mean_max"),
            "brightness_p05_min": self.get("face_brightness_p05_min"),
            "brightness_p95_max": self.get("face_brightness_p95_max"),
            "stability_min_ms": self.get("face_stability_min_ms")
        }
    
    def get_face_pad_thresholds(self) -> Dict[str, Any]:
        """Get all face PAD (Presentation Attack Detection) thresholds"""
        return {
            "score_min": self.get("face_pad_score_min"),
            "spoof_threshold": self.get("face_pad_spoof_threshold"),
            "fmr_target": self.get("face_pad_fmr_target"),
            "fnmr_target": self.get("face_pad_fnmr_target")
        }
    
    def get_face_burst_thresholds(self) -> Dict[str, Any]:
        """Get all face burst and consensus thresholds"""
        return {
            "max_frames": self.get("face_burst_max_frames"),
            "max_duration_ms": self.get("face_burst_max_duration_ms"),
            "consensus_top_k": self.get("face_consensus_top_k"),
            "consensus_median_min": self.get("face_consensus_median_min"),
            "consensus_frame_min_count": self.get("face_consensus_frame_min_count"),
            "consensus_frame_min_score": self.get("face_consensus_frame_min_score")
        }
    
    def get_face_challenge_thresholds(self) -> Dict[str, Any]:
        """Get all face challenge thresholds"""
        return {
            "action_count": self.get("face_challenge_action_count"),
            "ttl_ms": self.get("face_challenge_ttl_ms"),
            "action_max_ms": self.get("face_challenge_action_max_ms"),
            "ear_threshold": self.get("face_challenge_ear_threshold"),
            "mar_threshold": self.get("face_challenge_mar_threshold"),
            "yaw_threshold": self.get("face_challenge_yaw_threshold")
        }
    
    def get_face_performance_targets(self) -> Dict[str, Any]:
        """Get all face performance target thresholds"""
        return {
            "lock_p50_ms": self.get("face_lock_p50_ms"),
            "lock_p95_ms": self.get("face_lock_p95_ms"),
            "countdown_min_ms": self.get("face_countdown_min_ms"),
            "cancel_jitter_max_ms": self.get("face_cancel_jitter_max_ms"),
            "challenge_pass_rate_target": self.get("face_challenge_pass_rate_target"),
            "tar_at_far1_target": self.get("face_tar_at_far1_target")
        }
    
    def validate_face_thresholds(self) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate all face thresholds with strict bounds checking
        
        Returns:
            Tuple of (all_valid, validation_results)
        """
        from src.face.threshold_validator import get_validator
        
        validator = get_validator()
        face_values = {
            name: config.value
            for name, config in self.thresholds.items()
            if name.startswith("face_")
        }
        
        all_valid, results = validator.validate_all(face_values)
        
        # Additional cross-threshold validations
        if all_valid:
            # Check brightness range consistency
            brightness_result = validator.validate_brightness_range(
                self.get("face_brightness_mean_min"),
                self.get("face_brightness_mean_max")
            )
            if not brightness_result.valid:
                all_valid = False
                results.append(brightness_result)
            
            # Check performance targets consistency
            perf_result = validator.validate_performance_targets(
                self.get("face_lock_p50_ms"),
                self.get("face_lock_p95_ms")
            )
            if not perf_result.valid:
                all_valid = False
                results.append(perf_result)
        
        return all_valid, {
            "valid": all_valid,
            "results": [{"valid": r.valid, "message": r.message} for r in results]
        }
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of all thresholds by category
        
        Returns:
            Summary dictionary
        """
        summary = {
            "total_thresholds": len(self.thresholds),
            "categories": {},
            "last_update": None
        }
        
        # Group by category
        for category in ThresholdCategory:
            category_thresholds = self.get_by_category(category)
            if category_thresholds:
                summary["categories"][category.value] = {
                    "count": len(category_thresholds),
                    "thresholds": category_thresholds
                }
        
        # Find most recent update
        latest_update = None
        for config in self.thresholds.values():
            if config.last_updated:
                if latest_update is None or config.last_updated > latest_update:
                    latest_update = config.last_updated
        summary["last_update"] = latest_update
        
        return summary


# Singleton instance
_threshold_manager = None


def get_threshold_manager() -> ThresholdManager:
    """Get or create the singleton threshold manager instance"""
    global _threshold_manager
    if _threshold_manager is None:
        _threshold_manager = ThresholdManager()
    return _threshold_manager


if __name__ == "__main__":
    # Demo and validation
    manager = get_threshold_manager()
    
    print("=== KYC Bank-Grade Parity Threshold Manager ===")
    print(f"Loaded {len(manager.thresholds)} thresholds")
    print("\nCategories:")
    for category in ThresholdCategory:
        thresholds = manager.get_by_category(category)
        if thresholds:
            print(f"  {category.value}: {len(thresholds)} thresholds")
    
    print("\nSample Thresholds:")
    print(f"  SLO Decision P50: {manager.get('decision_p50')}ms")
    print(f"  PAD FAR Target: {manager.get('pad_far')}")
    print(f"  AML Rescreen Days: {manager.get('aml_rescreen_days')}")
    
    print("\nValidation Results:")
    results = manager.validate_all()
    print(f"  Valid: {sum(results.values())}/{len(results)}")
    
    # Save configuration
    if manager.save():
        print(f"\n✓ Configuration saved to {manager.config_path}")
    
    print("\n✓ Threshold manager ready for bank-grade parity phases")