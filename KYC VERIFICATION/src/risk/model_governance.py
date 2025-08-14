"""
Risk Model Governance Module
Model Registry, Versioning, and Fairness Monitoring
Part of KYC Bank-Grade Parity - Phase 4

This module implements governance controls for risk scoring models.
"""

import logging
import hashlib
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from enum import Enum
import numpy as np
from abc import ABC, abstractmethod

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Manila timezone
MANILA_TZ = timezone(timedelta(hours=8))


class ModelStatus(Enum):
    """Model deployment status"""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    CHALLENGER = "challenger"
    RETIRED = "retired"
    REJECTED = "rejected"


class ModelType(Enum):
    """Types of risk models"""
    FRAUD_DETECTION = "fraud_detection"
    CREDIT_SCORING = "credit_scoring"
    AML_RISK = "aml_risk"
    IDENTITY_VERIFICATION = "identity_verification"
    TRANSACTION_RISK = "transaction_risk"


@dataclass
class ModelMetadata:
    """Model metadata and lineage"""
    model_id: str
    name: str
    version: str
    model_type: ModelType
    status: ModelStatus
    created_at: str
    created_by: str
    description: str
    algorithm: str
    training_data: Dict[str, Any]
    performance_metrics: Dict[str, float]
    hyperparameters: Dict[str, Any]
    parent_model_id: Optional[str] = None
    approval_status: Optional[str] = None
    approved_by: Optional[str] = None
    deployment_date: Optional[str] = None
    
    def to_json(self) -> str:
        """Convert to JSON for storage"""
        data = asdict(self)
        data['model_type'] = self.model_type.value
        data['status'] = self.status.value
        return json.dumps(data)


@dataclass
class ModelPerformance:
    """Model performance metrics"""
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    auc_roc: float
    false_positive_rate: float
    false_negative_rate: float
    processing_time_ms: float
    sample_count: int
    timestamp: str


@dataclass
class FairnessMetrics:
    """Fairness and bias metrics"""
    demographic_parity: float
    equal_opportunity: float
    disparate_impact: float
    group_fairness_scores: Dict[str, float]
    bias_detected: bool
    affected_groups: List[str]
    recommendations: List[str]


class ModelRegistry:
    """Central registry for all risk models"""
    
    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize model registry
        
        Args:
            storage_path: Path to store model metadata
        """
        self.storage_path = storage_path or Path("/workspace/KYC VERIFICATION/models/registry")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.models: Dict[str, ModelMetadata] = {}
        self._load_registry()
        logger.info(f"Model Registry initialized with {len(self.models)} models")
    
    def _load_registry(self):
        """Load existing models from storage"""
        registry_file = self.storage_path / "registry.json"
        if registry_file.exists():
            try:
                with open(registry_file, 'r') as f:
                    data = json.load(f)
                    for model_id, model_data in data.items():
                        # Convert string enums back
                        model_data['model_type'] = ModelType(model_data['model_type'])
                        model_data['status'] = ModelStatus(model_data['status'])
                        self.models[model_id] = ModelMetadata(**model_data)
            except Exception as e:
                logger.error(f"Failed to load registry: {e}")
    
    def register_model(self, metadata: ModelMetadata) -> str:
        """
        Register a new model
        
        Args:
            metadata: Model metadata
            
        Returns:
            Model ID
        """
        # Generate model ID if not provided
        if not metadata.model_id:
            id_data = f"{metadata.name}_{metadata.version}_{datetime.now(MANILA_TZ).isoformat()}"
            metadata.model_id = hashlib.sha256(id_data.encode()).hexdigest()[:12]
        
        # Store model
        self.models[metadata.model_id] = metadata
        self._save_registry()
        
        logger.info(f"Model registered: {metadata.model_id} ({metadata.name} v{metadata.version})")
        return metadata.model_id
    
    def get_model(self, model_id: str) -> Optional[ModelMetadata]:
        """Get model by ID"""
        return self.models.get(model_id)
    
    def get_production_model(self, model_type: ModelType) -> Optional[ModelMetadata]:
        """Get current production model for a type"""
        for model in self.models.values():
            if model.model_type == model_type and model.status == ModelStatus.PRODUCTION:
                return model
        return None
    
    def get_challenger_models(self, model_type: ModelType) -> List[ModelMetadata]:
        """Get challenger models for a type"""
        challengers = []
        for model in self.models.values():
            if model.model_type == model_type and model.status == ModelStatus.CHALLENGER:
                challengers.append(model)
        return challengers
    
    def update_model_status(self, model_id: str, new_status: ModelStatus, 
                          approved_by: Optional[str] = None) -> bool:
        """
        Update model status
        
        Args:
            model_id: Model ID
            new_status: New status
            approved_by: Approver name (for production deployment)
            
        Returns:
            True if updated successfully
        """
        model = self.models.get(model_id)
        if not model:
            logger.error(f"Model {model_id} not found")
            return False
        
        # Validate status transition
        if not self._validate_status_transition(model.status, new_status):
            logger.error(f"Invalid status transition: {model.status} -> {new_status}")
            return False
        
        # Update status
        old_status = model.status
        model.status = new_status
        
        # Update approval info for production deployment
        if new_status == ModelStatus.PRODUCTION:
            model.approval_status = "approved"
            model.approved_by = approved_by or "system"
            model.deployment_date = datetime.now(MANILA_TZ).isoformat()
            
            # Retire previous production model
            self._retire_production_models(model.model_type, exclude_id=model_id)
        
        self._save_registry()
        logger.info(f"Model {model_id} status updated: {old_status} -> {new_status}")
        return True
    
    def _validate_status_transition(self, current: ModelStatus, 
                                   new: ModelStatus) -> bool:
        """Validate if status transition is allowed"""
        valid_transitions = {
            ModelStatus.DEVELOPMENT: [ModelStatus.STAGING, ModelStatus.REJECTED],
            ModelStatus.STAGING: [ModelStatus.PRODUCTION, ModelStatus.CHALLENGER, 
                                 ModelStatus.REJECTED, ModelStatus.DEVELOPMENT],
            ModelStatus.PRODUCTION: [ModelStatus.RETIRED],
            ModelStatus.CHALLENGER: [ModelStatus.PRODUCTION, ModelStatus.RETIRED, 
                                    ModelStatus.REJECTED],
            ModelStatus.RETIRED: [],
            ModelStatus.REJECTED: [ModelStatus.DEVELOPMENT]
        }
        
        return new in valid_transitions.get(current, [])
    
    def _retire_production_models(self, model_type: ModelType, exclude_id: str):
        """Retire existing production models of the same type"""
        for model in self.models.values():
            if (model.model_type == model_type and 
                model.status == ModelStatus.PRODUCTION and 
                model.model_id != exclude_id):
                model.status = ModelStatus.RETIRED
                logger.info(f"Retired model {model.model_id}")
    
    def _save_registry(self):
        """Save registry to storage"""
        try:
            registry_file = self.storage_path / "registry.json"
            data = {}
            for model_id, model in self.models.items():
                model_dict = asdict(model)
                model_dict['model_type'] = model.model_type.value
                model_dict['status'] = model.status.value
                data[model_id] = model_dict
            
            with open(registry_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")


class FairnessMonitor:
    """Monitor model fairness and detect bias"""
    
    def __init__(self, protected_attributes: Optional[List[str]] = None):
        """
        Initialize fairness monitor
        
        Args:
            protected_attributes: List of protected attributes to monitor
        """
        self.protected_attributes = protected_attributes or ["age", "gender", "location"]
        logger.info(f"Fairness Monitor initialized for attributes: {self.protected_attributes}")
    
    def calculate_fairness_metrics(self, predictions: np.ndarray, 
                                  actual: np.ndarray,
                                  groups: Dict[str, np.ndarray]) -> FairnessMetrics:
        """
        Calculate fairness metrics
        
        Args:
            predictions: Model predictions
            actual: Actual labels
            groups: Dictionary of group membership arrays
            
        Returns:
            FairnessMetrics object
        """
        # Calculate demographic parity
        demographic_parity = self._calculate_demographic_parity(predictions, groups)
        
        # Calculate equal opportunity
        equal_opportunity = self._calculate_equal_opportunity(predictions, actual, groups)
        
        # Calculate disparate impact
        disparate_impact = self._calculate_disparate_impact(predictions, groups)
        
        # Calculate per-group fairness
        group_scores = {}
        for group_name, group_mask in groups.items():
            group_predictions = predictions[group_mask]
            group_actual = actual[group_mask] if actual is not None else None
            
            if len(group_predictions) > 0:
                group_scores[group_name] = {
                    "selection_rate": np.mean(group_predictions),
                    "accuracy": np.mean(group_predictions == group_actual) if group_actual is not None else None
                }
        
        # Detect bias
        bias_detected = (
            demographic_parity < 0.8 or 
            equal_opportunity < 0.8 or 
            disparate_impact < 0.8
        )
        
        # Identify affected groups
        affected_groups = []
        base_rate = np.mean(predictions)
        for group_name, scores in group_scores.items():
            if abs(scores["selection_rate"] - base_rate) > 0.1:
                affected_groups.append(group_name)
        
        # Generate recommendations
        recommendations = []
        if bias_detected:
            if demographic_parity < 0.8:
                recommendations.append("Consider rebalancing training data")
            if equal_opportunity < 0.8:
                recommendations.append("Review feature engineering for fairness")
            if disparate_impact < 0.8:
                recommendations.append("Apply fairness-aware preprocessing")
        
        return FairnessMetrics(
            demographic_parity=demographic_parity,
            equal_opportunity=equal_opportunity,
            disparate_impact=disparate_impact,
            group_fairness_scores=group_scores,
            bias_detected=bias_detected,
            affected_groups=affected_groups,
            recommendations=recommendations
        )
    
    def _calculate_demographic_parity(self, predictions: np.ndarray, 
                                     groups: Dict[str, np.ndarray]) -> float:
        """Calculate demographic parity difference"""
        if not groups:
            return 1.0
        
        selection_rates = []
        for group_mask in groups.values():
            if np.sum(group_mask) > 0:
                selection_rates.append(np.mean(predictions[group_mask]))
        
        if len(selection_rates) < 2:
            return 1.0
        
        return min(selection_rates) / max(selection_rates) if max(selection_rates) > 0 else 0
    
    def _calculate_equal_opportunity(self, predictions: np.ndarray, 
                                    actual: np.ndarray,
                                    groups: Dict[str, np.ndarray]) -> float:
        """Calculate equal opportunity difference"""
        if actual is None or not groups:
            return 1.0
        
        tpr_values = []  # True positive rates
        for group_mask in groups.values():
            group_pred = predictions[group_mask]
            group_actual = actual[group_mask]
            
            if np.sum(group_actual) > 0:
                tpr = np.sum((group_pred == 1) & (group_actual == 1)) / np.sum(group_actual == 1)
                tpr_values.append(tpr)
        
        if len(tpr_values) < 2:
            return 1.0
        
        return min(tpr_values) / max(tpr_values) if max(tpr_values) > 0 else 0
    
    def _calculate_disparate_impact(self, predictions: np.ndarray,
                                   groups: Dict[str, np.ndarray]) -> float:
        """Calculate disparate impact ratio"""
        if not groups or len(groups) < 2:
            return 1.0
        
        # Assuming first group is privileged, others are unprivileged
        group_names = list(groups.keys())
        privileged_mask = groups[group_names[0]]
        unprivileged_mask = ~privileged_mask
        
        privileged_rate = np.mean(predictions[privileged_mask]) if np.sum(privileged_mask) > 0 else 0
        unprivileged_rate = np.mean(predictions[unprivileged_mask]) if np.sum(unprivileged_mask) > 0 else 0
        
        if privileged_rate == 0:
            return 0
        
        return unprivileged_rate / privileged_rate


class ChallengerSystem:
    """A/B testing system for challenger models"""
    
    def __init__(self, traffic_split: float = 0.1):
        """
        Initialize challenger system
        
        Args:
            traffic_split: Fraction of traffic for challenger model
        """
        self.traffic_split = traffic_split
        self.performance_history: Dict[str, List[ModelPerformance]] = {}
        logger.info(f"Challenger System initialized with {traffic_split*100}% traffic split")
    
    def route_request(self, production_model_id: str, 
                     challenger_model_ids: List[str]) -> str:
        """
        Route request to production or challenger model
        
        Args:
            production_model_id: Production model ID
            challenger_model_ids: List of challenger model IDs
            
        Returns:
            Selected model ID
        """
        if not challenger_model_ids:
            return production_model_id
        
        # Random routing based on traffic split
        import random
        if random.random() < self.traffic_split:
            # Route to challenger
            return random.choice(challenger_model_ids)
        else:
            # Route to production
            return production_model_id
    
    def record_performance(self, model_id: str, performance: ModelPerformance):
        """
        Record model performance
        
        Args:
            model_id: Model ID
            performance: Performance metrics
        """
        if model_id not in self.performance_history:
            self.performance_history[model_id] = []
        
        self.performance_history[model_id].append(performance)
        
        # Keep only recent history (last 1000 records)
        if len(self.performance_history[model_id]) > 1000:
            self.performance_history[model_id] = self.performance_history[model_id][-1000:]
    
    def compare_models(self, production_id: str, 
                       challenger_id: str) -> Dict[str, Any]:
        """
        Compare production and challenger model performance
        
        Args:
            production_id: Production model ID
            challenger_id: Challenger model ID
            
        Returns:
            Comparison results
        """
        prod_perf = self.performance_history.get(production_id, [])
        chal_perf = self.performance_history.get(challenger_id, [])
        
        if not prod_perf or not chal_perf:
            return {"status": "insufficient_data"}
        
        # Calculate average metrics
        prod_metrics = self._calculate_average_metrics(prod_perf)
        chal_metrics = self._calculate_average_metrics(chal_perf)
        
        # Compare metrics
        comparison = {
            "production_model": production_id,
            "challenger_model": challenger_id,
            "sample_size": {
                "production": len(prod_perf),
                "challenger": len(chal_perf)
            },
            "metrics_comparison": {
                "accuracy": {
                    "production": prod_metrics["accuracy"],
                    "challenger": chal_metrics["accuracy"],
                    "improvement": chal_metrics["accuracy"] - prod_metrics["accuracy"]
                },
                "f1_score": {
                    "production": prod_metrics["f1_score"],
                    "challenger": chal_metrics["f1_score"],
                    "improvement": chal_metrics["f1_score"] - prod_metrics["f1_score"]
                },
                "processing_time": {
                    "production": prod_metrics["processing_time"],
                    "challenger": chal_metrics["processing_time"],
                    "improvement": prod_metrics["processing_time"] - chal_metrics["processing_time"]
                }
            },
            "recommendation": self._generate_recommendation(prod_metrics, chal_metrics)
        }
        
        return comparison
    
    def _calculate_average_metrics(self, 
                                  performance_list: List[ModelPerformance]) -> Dict[str, float]:
        """Calculate average performance metrics"""
        if not performance_list:
            return {}
        
        metrics = {
            "accuracy": np.mean([p.accuracy for p in performance_list]),
            "precision": np.mean([p.precision for p in performance_list]),
            "recall": np.mean([p.recall for p in performance_list]),
            "f1_score": np.mean([p.f1_score for p in performance_list]),
            "auc_roc": np.mean([p.auc_roc for p in performance_list]),
            "processing_time": np.mean([p.processing_time_ms for p in performance_list])
        }
        
        return metrics
    
    def _generate_recommendation(self, prod_metrics: Dict[str, float],
                                chal_metrics: Dict[str, float]) -> str:
        """Generate recommendation based on comparison"""
        if not prod_metrics or not chal_metrics:
            return "Insufficient data for recommendation"
        
        # Check if challenger is significantly better
        accuracy_improvement = chal_metrics["accuracy"] - prod_metrics["accuracy"]
        f1_improvement = chal_metrics["f1_score"] - prod_metrics["f1_score"]
        
        if accuracy_improvement > 0.02 and f1_improvement > 0.02:
            return "Promote challenger to production"
        elif accuracy_improvement < -0.02 or f1_improvement < -0.02:
            return "Reject challenger model"
        else:
            return "Continue monitoring"


def create_governance_report(registry: ModelRegistry,
                            fairness_monitor: FairnessMonitor,
                            challenger_system: ChallengerSystem) -> Dict[str, Any]:
    """
    Create comprehensive governance report
    
    Args:
        registry: Model registry
        fairness_monitor: Fairness monitor
        challenger_system: Challenger system
        
    Returns:
        Governance report dictionary
    """
    report = {
        "timestamp": datetime.now(MANILA_TZ).isoformat(),
        "registry_summary": {
            "total_models": len(registry.models),
            "production_models": sum(1 for m in registry.models.values() 
                                   if m.status == ModelStatus.PRODUCTION),
            "challenger_models": sum(1 for m in registry.models.values() 
                                   if m.status == ModelStatus.CHALLENGER),
            "retired_models": sum(1 for m in registry.models.values() 
                                if m.status == ModelStatus.RETIRED)
        },
        "model_types": {},
        "fairness_status": "monitoring",
        "challenger_tests": len(challenger_system.performance_history)
    }
    
    # Group by model type
    for model_type in ModelType:
        type_models = [m for m in registry.models.values() if m.model_type == model_type]
        if type_models:
            report["model_types"][model_type.value] = {
                "count": len(type_models),
                "production": next((m.model_id for m in type_models 
                                  if m.status == ModelStatus.PRODUCTION), None),
                "challengers": [m.model_id for m in type_models 
                              if m.status == ModelStatus.CHALLENGER]
            }
    
    return report


if __name__ == "__main__":
    # Demo and testing
    print("=== Risk Model Governance Demo ===\n")
    
    # Initialize components
    registry = ModelRegistry()
    fairness_monitor = FairnessMonitor()
    challenger_system = ChallengerSystem(traffic_split=0.2)
    
    # Register a model
    model = ModelMetadata(
        model_id="",
        name="fraud_detector",
        version="1.0.0",
        model_type=ModelType.FRAUD_DETECTION,
        status=ModelStatus.DEVELOPMENT,
        created_at=datetime.now(MANILA_TZ).isoformat(),
        created_by="data_scientist",
        description="XGBoost fraud detection model",
        algorithm="XGBoost",
        training_data={"samples": 100000, "features": 50},
        performance_metrics={"accuracy": 0.95, "auc_roc": 0.92},
        hyperparameters={"max_depth": 10, "learning_rate": 0.01}
    )
    
    model_id = registry.register_model(model)
    print(f"Model registered: {model_id}")
    
    # Update to production
    registry.update_model_status(model_id, ModelStatus.PRODUCTION, "risk_manager")
    print(f"Model promoted to production")
    
    # Test fairness monitoring
    print("\nTesting Fairness Monitor:")
    predictions = np.random.randint(0, 2, 1000)
    actual = np.random.randint(0, 2, 1000)
    groups = {
        "group_a": np.random.random(1000) > 0.5,
        "group_b": np.random.random(1000) <= 0.5
    }
    
    fairness = fairness_monitor.calculate_fairness_metrics(predictions, actual, groups)
    print(f"  Demographic Parity: {fairness.demographic_parity:.3f}")
    print(f"  Equal Opportunity: {fairness.equal_opportunity:.3f}")
    print(f"  Bias Detected: {fairness.bias_detected}")
    
    # Test challenger system
    print("\nTesting Challenger System:")
    selected = challenger_system.route_request(model_id, [])
    print(f"  Routed to: {selected}")
    
    # Record some performance
    perf = ModelPerformance(
        accuracy=0.94,
        precision=0.92,
        recall=0.91,
        f1_score=0.915,
        auc_roc=0.93,
        false_positive_rate=0.08,
        false_negative_rate=0.09,
        processing_time_ms=15.5,
        sample_count=100,
        timestamp=datetime.now(MANILA_TZ).isoformat()
    )
    challenger_system.record_performance(model_id, perf)
    
    # Generate report
    report = create_governance_report(registry, fairness_monitor, challenger_system)
    print(f"\nGovernance Report:")
    print(f"  Total Models: {report['registry_summary']['total_models']}")
    print(f"  Production Models: {report['registry_summary']['production_models']}")
    
    print("\n✓ Model Governance system operational")