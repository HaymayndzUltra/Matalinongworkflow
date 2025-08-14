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
from typing import Dict, Any, Optional, Union
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
            
            # Retention
            ThresholdConfig("retention_days", ThresholdCategory.RETENTION, 2555, 365, 3650, "days",
                          "Data retention period", "RETENTION_POLICY_DAYS"),
            
            # Operational
            ThresholdConfig("rate_limit_per_minute", ThresholdCategory.OPERATIONAL, 1000, 10, 10000, "requests",
                          "API rate limit", "RATE_LIMIT_PER_MINUTE"),
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