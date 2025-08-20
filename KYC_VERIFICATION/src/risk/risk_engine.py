"""
Risk Scoring & Decisioning Module
Phase 8: ML ensemble with feature aggregation from all phases
Policy-driven thresholds with explainable decisions (approve/review/deny)
"""

import json
import logging
import numpy as np
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from pathlib import Path
import pickle
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.preprocessing import StandardScaler
try:
    import xgboost as xgb  # type: ignore
    XGB_AVAILABLE = True
except Exception:
    xgb = None  # type: ignore
    XGB_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DecisionType(Enum):
    """Decision outcomes"""
    APPROVE = "approve"
    REVIEW = "review"
    DENY = "deny"
    ESCALATE = "escalate"

class RiskCategory(Enum):
    """Risk categories"""
    DOCUMENT_QUALITY = "document_quality"
    DOCUMENT_AUTHENTICITY = "document_authenticity"
    IDENTITY_VERIFICATION = "identity_verification"
    BEHAVIORAL_RISK = "behavioral_risk"
    DEVICE_RISK = "device_risk"
    VELOCITY_RISK = "velocity_risk"
    COMPLIANCE_RISK = "compliance_risk"

@dataclass
class RiskFeature:
    """Individual risk feature"""
    name: str
    value: float
    category: RiskCategory
    weight: float = 1.0
    normalized_value: float = 0.0

@dataclass
class RiskScore:
    """Risk scoring result"""
    overall_score: float
    category_scores: Dict[RiskCategory, float]
    confidence: float
    model_scores: Dict[str, float]  # Individual model predictions
    feature_importance: List[Tuple[str, float]]

@dataclass
class Decision:
    """Final decision with explanations"""
    decision_type: DecisionType
    risk_score: float
    confidence: float
    reasons: List[str]
    recommendations: List[str]
    policy_violations: List[str]
    review_required_fields: List[str]
    metadata: Dict[str, Any]

@dataclass
class RiskPolicy:
    """Risk policy configuration"""
    name: str
    enabled: bool
    priority: int
    conditions: Dict[str, Any]
    action: DecisionType
    message: str

class RiskEngine:
    """Risk scoring and decisioning engine"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize risk engine"""
        self.config = self._load_config(config_path)
        self.policies = self._load_policies()
        self.models = self._initialize_models()
        self.scaler = StandardScaler()
        self.feature_weights = self._load_feature_weights()
        
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load risk engine configuration"""
        default_config = {
            "thresholds": {
                "approve": 0.3,    # Risk score below this = approve
                "review": 0.7,     # Risk score below this = review
                "deny": 0.9        # Risk score above this = deny
            },
            "ensemble": {
                "use_ensemble": True,
                "models": ["random_forest", "xgboost", "gradient_boost"],
                "voting": "weighted",  # or "majority"
                "weights": [0.4, 0.35, 0.25]
            },
            "feature_categories": {
                "document_quality": 0.15,
                "document_authenticity": 0.25,
                "identity_verification": 0.25,
                "behavioral_risk": 0.15,
                "device_risk": 0.10,
                "velocity_risk": 0.05,
                "compliance_risk": 0.05
            },
            "explainability": {
                "min_reasons": 3,
                "max_reasons": 5,
                "include_recommendations": True,
                "include_feature_importance": True
            },
            "overrides": {
                "allow_manual_override": True,
                "require_supervisor_approval": True,
                "audit_all_overrides": True
            }
        }
        
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def _load_policies(self) -> List[RiskPolicy]:
        """Load risk policies"""
        policies = [
            RiskPolicy(
                name="expired_document",
                enabled=True,
                priority=1,
                conditions={"document_expired": True},
                action=DecisionType.DENY,
                message="Document has expired"
            ),
            RiskPolicy(
                name="failed_biometric",
                enabled=True,
                priority=1,
                conditions={"biometric_match": False},
                action=DecisionType.DENY,
                message="Biometric verification failed"
            ),
            RiskPolicy(
                name="tor_usage",
                enabled=True,
                priority=2,
                conditions={"tor_detected": True},
                action=DecisionType.REVIEW,
                message="TOR network detected"
            ),
            RiskPolicy(
                name="document_tampered",
                enabled=True,
                priority=1,
                conditions={"forensic_tamper_detected": True},
                action=DecisionType.DENY,
                message="Document tampering detected"
            ),
            RiskPolicy(
                name="velocity_anomaly",
                enabled=True,
                priority=3,
                conditions={"velocity_impossible": True},
                action=DecisionType.REVIEW,
                message="Impossible travel detected"
            ),
            RiskPolicy(
                name="device_emulator",
                enabled=True,
                priority=2,
                conditions={"emulator_detected": True},
                action=DecisionType.REVIEW,
                message="Emulator or virtual device detected"
            ),
            RiskPolicy(
                name="high_risk_country",
                enabled=True,
                priority=3,
                conditions={"country_risk_high": True},
                action=DecisionType.ESCALATE,
                message="High-risk jurisdiction"
            ),
            RiskPolicy(
                name="duplicate_submission",
                enabled=True,
                priority=1,
                conditions={"duplicate_document": True},
                action=DecisionType.DENY,
                message="Duplicate document submission"
            ),
            RiskPolicy(
                name="underage",
                enabled=True,
                priority=1,
                conditions={"age_below_minimum": True},
                action=DecisionType.DENY,
                message="Below minimum age requirement"
            ),
            RiskPolicy(
                name="name_mismatch",
                enabled=True,
                priority=2,
                conditions={"name_similarity_low": True},
                action=DecisionType.REVIEW,
                message="Name inconsistency detected"
            )
        ]
        
        # Sort by priority
        return sorted(policies, key=lambda p: p.priority)
    
    def _initialize_models(self) -> Dict[str, Any]:
        """Initialize ML models for ensemble"""
        models = {}
        
        if self.config["ensemble"]["use_ensemble"]:
            # Random Forest
            models["random_forest"] = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                min_samples_split=5,
                random_state=42
            )
            
            # XGBoost (optional)
            if XGB_AVAILABLE:
                models["xgboost"] = xgb.XGBClassifier(
                    n_estimators=100,
                    max_depth=6,
                    learning_rate=0.1,
                    random_state=42
                )
            
            # Gradient Boosting
            models["gradient_boost"] = GradientBoostingClassifier(
                n_estimators=100,
                max_depth=5,
                learning_rate=0.1,
                random_state=42
            )
        
        # Try to load pre-trained models
        self._load_pretrained_models(models)
        
        return models
    
    def _load_pretrained_models(self, models: Dict[str, Any]):
        """Load pre-trained models if available"""
        model_dir = Path("models")
        
        if model_dir.exists():
            for model_name in models.keys():
                model_path = model_dir / f"{model_name}.pkl"
                if model_path.exists():
                    try:
                        with open(model_path, 'rb') as f:
                            models[model_name] = pickle.load(f)
                        logger.info(f"Loaded pre-trained model: {model_name}")
                    except Exception as e:
                        logger.warning(f"Failed to load model {model_name}: {e}")
    
    def _load_feature_weights(self) -> Dict[str, float]:
        """Load feature importance weights"""
        return {
            # Document quality features
            "blur_score": 0.05,
            "glare_score": 0.03,
            "resolution_adequate": 0.04,
            "orientation_correct": 0.02,
            
            # Classification features
            "classification_confidence": 0.08,
            "template_match_score": 0.06,
            
            # Extraction features
            "ocr_confidence": 0.07,
            "mrz_valid": 0.08,
            "fields_extracted_ratio": 0.05,
            
            # Forensics features
            "ela_score": 0.10,
            "noise_consistency": 0.08,
            "no_tampering": 0.12,
            
            # Biometric features
            "face_match_score": 0.15,
            "liveness_score": 0.12,
            
            # Validation features
            "checksum_valid": 0.06,
            "expiry_valid": 0.08,
            "format_valid": 0.05,
            
            # Device features
            "device_trust_score": 0.08,
            "no_vpn_tor": 0.05,
            "no_emulator": 0.06,
            
            # Behavioral features
            "velocity_normal": 0.04,
            "device_consistent": 0.03,
            "location_consistent": 0.03
        }
    
    def calculate_risk(self, verification_data: Dict[str, Any]) -> Tuple[RiskScore, Decision]:
        """
        Calculate risk score and make decision
        
        Args:
            verification_data: Aggregated data from all verification phases
            
        Returns:
            Risk score and decision
        """
        logger.info("🎯 Starting risk assessment...")
        
        # Extract features from verification data
        features = self._extract_features(verification_data)
        
        # Check policies first (can override ML decision)
        policy_decision = self._check_policies(verification_data)
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(features)
        
        # Make decision
        decision = self._make_decision(risk_score, policy_decision, verification_data)
        
        # Add explanations
        decision = self._add_explanations(decision, risk_score, features)
        
        logger.info(f"✅ Risk assessment complete: "
                   f"Score={risk_score.overall_score:.3f}, "
                   f"Decision={decision.decision_type.value}")
        
        return risk_score, decision
    
    def _extract_features(self, data: Dict[str, Any]) -> List[RiskFeature]:
        """Extract risk features from verification data"""
        features = []
        
        # Document quality features
        if "quality" in data:
            quality = data["quality"]
            features.extend([
                RiskFeature(
                    name="blur_score",
                    value=1 - quality.get("blur_score", 0),
                    category=RiskCategory.DOCUMENT_QUALITY
                ),
                RiskFeature(
                    name="glare_score",
                    value=quality.get("glare_score", 0),
                    category=RiskCategory.DOCUMENT_QUALITY
                ),
                RiskFeature(
                    name="resolution_adequate",
                    value=1.0 if quality.get("resolution_adequate", False) else 0.0,
                    category=RiskCategory.DOCUMENT_QUALITY
                )
            ])
        
        # Classification features
        if "classification" in data:
            classification = data["classification"]
            features.append(
                RiskFeature(
                    name="classification_confidence",
                    value=classification.get("confidence", 0),
                    category=RiskCategory.DOCUMENT_QUALITY
                )
            )
        
        # Extraction features
        if "extraction" in data:
            extraction = data["extraction"]
            total_fields = len(extraction.get("expected_fields", []))
            extracted_fields = len(extraction.get("extracted_fields", []))
            
            features.extend([
                RiskFeature(
                    name="ocr_confidence",
                    value=extraction.get("ocr_confidence", 0),
                    category=RiskCategory.DOCUMENT_QUALITY
                ),
                RiskFeature(
                    name="fields_extracted_ratio",
                    value=extracted_fields / max(total_fields, 1),
                    category=RiskCategory.DOCUMENT_QUALITY
                ),
                RiskFeature(
                    name="mrz_valid",
                    value=1.0 if extraction.get("mrz_valid", False) else 0.0,
                    category=RiskCategory.DOCUMENT_AUTHENTICITY
                )
            ])
        
        # Forensics features
        if "forensics" in data:
            forensics = data["forensics"]
            features.extend([
                RiskFeature(
                    name="no_tampering",
                    value=1.0 if forensics.get("is_authentic", False) else 0.0,
                    category=RiskCategory.DOCUMENT_AUTHENTICITY,
                    weight=2.0  # Higher weight for authenticity
                ),
                RiskFeature(
                    name="ela_score",
                    value=1 - forensics.get("manipulation_score", 0),
                    category=RiskCategory.DOCUMENT_AUTHENTICITY
                )
            ])
        
        # Biometric features
        if "biometrics" in data:
            biometrics = data["biometrics"]
            features.extend([
                RiskFeature(
                    name="face_match_score",
                    value=biometrics.get("similarity_score", 0),
                    category=RiskCategory.IDENTITY_VERIFICATION,
                    weight=2.0
                ),
                RiskFeature(
                    name="liveness_score",
                    value=biometrics.get("liveness_confidence", 0),
                    category=RiskCategory.IDENTITY_VERIFICATION,
                    weight=1.5
                )
            ])
        
        # Validation features
        if "validation" in data:
            validation = data["validation"]
            features.extend([
                RiskFeature(
                    name="checksum_valid",
                    value=1.0 if validation.get("checksum_valid", False) else 0.0,
                    category=RiskCategory.DOCUMENT_AUTHENTICITY
                ),
                RiskFeature(
                    name="expiry_valid",
                    value=1.0 if validation.get("expiry_status", "") != "expired" else 0.0,
                    category=RiskCategory.COMPLIANCE_RISK
                )
            ])
        
        # Device intelligence features
        if "device" in data:
            device = data["device"]
            features.extend([
                RiskFeature(
                    name="device_trust_score",
                    value=1 - device.get("risk_score", 0),
                    category=RiskCategory.DEVICE_RISK
                ),
                RiskFeature(
                    name="no_vpn_tor",
                    value=0.0 if device.get("vpn_detected", False) or device.get("tor_detected", False) else 1.0,
                    category=RiskCategory.DEVICE_RISK
                ),
                RiskFeature(
                    name="no_emulator",
                    value=0.0 if device.get("emulator_detected", False) else 1.0,
                    category=RiskCategory.DEVICE_RISK
                )
            ])
        
        # Behavioral features
        if "velocity" in data:
            velocity = data["velocity"]
            features.append(
                RiskFeature(
                    name="velocity_normal",
                    value=0.0 if velocity.get("anomaly_detected", False) else 1.0,
                    category=RiskCategory.VELOCITY_RISK
                )
            )
        
        # Normalize features
        features = self._normalize_features(features)
        
        return features
    
    def _normalize_features(self, features: List[RiskFeature]) -> List[RiskFeature]:
        """Normalize feature values to 0-1 range"""
        for feature in features:
            # Ensure value is in [0, 1] range
            feature.normalized_value = max(0.0, min(1.0, feature.value))
        
        return features
    
    def _check_policies(self, data: Dict[str, Any]) -> Optional[Decision]:
        """Check policy rules for immediate decisions"""
        for policy in self.policies:
            if not policy.enabled:
                continue
            
            # Check if policy conditions are met
            conditions_met = True
            
            for condition, expected_value in policy.conditions.items():
                actual_value = self._get_nested_value(data, condition)
                
                if actual_value != expected_value:
                    conditions_met = False
                    break
            
            if conditions_met:
                logger.info(f"Policy triggered: {policy.name}")
                
                return Decision(
                    decision_type=policy.action,
                    risk_score=1.0 if policy.action == DecisionType.DENY else 0.5,
                    confidence=1.0,
                    reasons=[policy.message],
                    recommendations=[],
                    policy_violations=[policy.name],
                    review_required_fields=[],
                    metadata={"triggered_policy": policy.name}
                )
        
        return None
    
    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """Get value from nested dictionary using dot notation"""
        keys = path.split('.')
        value = data
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return None
        
        return value
    
    def _calculate_risk_score(self, features: List[RiskFeature]) -> RiskScore:
        """Calculate risk score using ensemble model"""
        # Group features by category
        category_features = {}
        for feature in features:
            if feature.category not in category_features:
                category_features[feature.category] = []
            category_features[feature.category].append(feature)
        
        # Calculate category scores
        category_scores = {}
        category_weights = self.config["feature_categories"]
        
        for category, cat_features in category_features.items():
            if cat_features:
                # Weighted average of features in category
                total_weight = sum(f.weight for f in cat_features)
                weighted_sum = sum(
                    (1 - f.normalized_value) * f.weight  # Invert: high value = low risk
                    for f in cat_features
                )
                category_scores[category] = weighted_sum / max(total_weight, 1)
            else:
                category_scores[category] = 0.0
        
        # Calculate overall score
        overall_score = 0.0
        for category, score in category_scores.items():
            weight = category_weights.get(category.value, 0.1)
            overall_score += score * weight
        
        # Get model predictions if available
        model_scores = {}
        if self.config["ensemble"]["use_ensemble"] and self.models:
            model_scores = self._get_ensemble_predictions(features)
            
            # Combine rule-based and ML scores
            if model_scores:
                ml_score = np.mean(list(model_scores.values()))
                overall_score = 0.6 * overall_score + 0.4 * ml_score
        
        # Calculate feature importance
        feature_importance = self._calculate_feature_importance(features)
        
        # Calculate confidence based on data completeness
        confidence = len(features) / len(self.feature_weights)
        
        return RiskScore(
            overall_score=min(1.0, overall_score),
            category_scores=category_scores,
            confidence=confidence,
            model_scores=model_scores,
            feature_importance=feature_importance[:10]  # Top 10 features
        )
    
    def _get_ensemble_predictions(self, features: List[RiskFeature]) -> Dict[str, float]:
        """Get predictions from ensemble models"""
        model_scores = {}
        
        # Convert features to array
        feature_names = list(self.feature_weights.keys())
        feature_dict = {f.name: f.normalized_value for f in features}
        
        X = np.array([[
            feature_dict.get(name, 0.0) for name in feature_names
        ]])
        
        # Get predictions from each model
        for model_name, model in self.models.items():
            try:
                # Check if model is trained
                if hasattr(model, 'n_classes_'):
                    # Model is trained, get prediction
                    prob = model.predict_proba(X)[0]
                    # Assuming binary classification (risk/no-risk)
                    model_scores[model_name] = prob[1] if len(prob) > 1 else prob[0]
                else:
                    # Model not trained, use random prediction for demo
                    model_scores[model_name] = np.random.random() * 0.3  # Low risk for demo
            except Exception as e:
                logger.warning(f"Model {model_name} prediction failed: {e}")
                model_scores[model_name] = 0.5  # Neutral score
        
        return model_scores
    
    def _calculate_feature_importance(self, features: List[RiskFeature]) -> List[Tuple[str, float]]:
        """Calculate feature importance for explainability"""
        importance = []
        
        for feature in features:
            weight = self.feature_weights.get(feature.name, 0.05)
            impact = abs(0.5 - feature.normalized_value) * weight * feature.weight
            importance.append((feature.name, impact))
        
        # Sort by importance
        importance.sort(key=lambda x: x[1], reverse=True)
        
        return importance
    
    def _make_decision(self, risk_score: RiskScore, 
                       policy_decision: Optional[Decision],
                       data: Dict[str, Any]) -> Decision:
        """Make final decision based on risk score and policies"""
        # If policy triggered, use that decision
        if policy_decision:
            policy_decision.risk_score = risk_score.overall_score
            return policy_decision
        
        # Otherwise, use threshold-based decision
        thresholds = self.config["thresholds"]
        
        if risk_score.overall_score < thresholds["approve"]:
            decision_type = DecisionType.APPROVE
        elif risk_score.overall_score < thresholds["review"]:
            decision_type = DecisionType.REVIEW
        elif risk_score.overall_score < thresholds["deny"]:
            decision_type = DecisionType.DENY
        else:
            decision_type = DecisionType.ESCALATE
        
        # Identify fields requiring review
        review_fields = self._identify_review_fields(risk_score, data)
        
        return Decision(
            decision_type=decision_type,
            risk_score=risk_score.overall_score,
            confidence=risk_score.confidence,
            reasons=[],
            recommendations=[],
            policy_violations=[],
            review_required_fields=review_fields,
            metadata={
                "threshold_used": decision_type.value,
                "category_scores": {
                    k.value: v for k, v in risk_score.category_scores.items()
                }
            }
        )
    
    def _identify_review_fields(self, risk_score: RiskScore, data: Dict[str, Any]) -> List[str]:
        """Identify fields that need manual review"""
        review_fields = []
        
        # Check category scores
        for category, score in risk_score.category_scores.items():
            if score > 0.6:  # High risk in category
                if category == RiskCategory.DOCUMENT_QUALITY:
                    review_fields.append("document_image")
                elif category == RiskCategory.DOCUMENT_AUTHENTICITY:
                    review_fields.append("security_features")
                elif category == RiskCategory.IDENTITY_VERIFICATION:
                    review_fields.append("biometric_match")
                elif category == RiskCategory.DEVICE_RISK:
                    review_fields.append("device_fingerprint")
        
        # Check specific data issues
        if data.get("extraction", {}).get("fields_missing", []):
            review_fields.extend(data["extraction"]["fields_missing"])
        
        return list(set(review_fields))  # Remove duplicates
    
    def _add_explanations(self, decision: Decision, 
                         risk_score: RiskScore,
                         features: List[RiskFeature]) -> Decision:
        """Add human-readable explanations to decision"""
        # Add reasons based on risk categories
        high_risk_categories = [
            (cat, score) for cat, score in risk_score.category_scores.items()
            if score > 0.5
        ]
        
        high_risk_categories.sort(key=lambda x: x[1], reverse=True)
        
        for category, score in high_risk_categories[:self.config["explainability"]["max_reasons"]]:
            if category == RiskCategory.DOCUMENT_QUALITY:
                decision.reasons.append(f"Document quality issues detected (risk: {score:.2f})")
            elif category == RiskCategory.DOCUMENT_AUTHENTICITY:
                decision.reasons.append(f"Document authenticity concerns (risk: {score:.2f})")
            elif category == RiskCategory.IDENTITY_VERIFICATION:
                decision.reasons.append(f"Identity verification issues (risk: {score:.2f})")
            elif category == RiskCategory.DEVICE_RISK:
                decision.reasons.append(f"Suspicious device characteristics (risk: {score:.2f})")
            elif category == RiskCategory.VELOCITY_RISK:
                decision.reasons.append(f"Unusual activity patterns detected (risk: {score:.2f})")
        
        # Add feature-specific reasons
        low_score_features = [f for f in features if f.normalized_value < 0.3]
        for feature in low_score_features[:2]:
            if feature.name == "face_match_score":
                decision.reasons.append("Low face matching confidence")
            elif feature.name == "no_tampering":
                decision.reasons.append("Potential document tampering detected")
            elif feature.name == "liveness_score":
                decision.reasons.append("Liveness check failed or inconclusive")
        
        # Add recommendations
        if decision.decision_type == DecisionType.REVIEW:
            decision.recommendations.extend([
                "Manual review of document authenticity recommended",
                "Verify extracted information against external sources",
                "Request additional documentation if necessary"
            ])
        elif decision.decision_type == DecisionType.DENY:
            decision.recommendations.extend([
                "Request new document submission",
                "Ensure document is original and unaltered",
                "Verify identity through alternative means"
            ])
        elif decision.decision_type == DecisionType.APPROVE:
            decision.recommendations.append("Proceed with account creation")
        
        # Ensure minimum reasons
        if len(decision.reasons) < self.config["explainability"]["min_reasons"]:
            decision.reasons.append(f"Overall risk score: {risk_score.overall_score:.2f}")
            decision.reasons.append(f"Confidence level: {risk_score.confidence:.2f}")
        
        return decision
    
    def override_decision(self, original_decision: Decision,
                         new_decision_type: DecisionType,
                         override_reason: str,
                         supervisor_id: str) -> Decision:
        """
        Override automated decision with manual review
        
        Args:
            original_decision: Original automated decision
            new_decision_type: New decision type
            override_reason: Reason for override
            supervisor_id: ID of supervisor approving override
            
        Returns:
            Updated decision with override information
        """
        if not self.config["overrides"]["allow_manual_override"]:
            raise ValueError("Manual overrides are not allowed")
        
        # Create new decision with override
        overridden = Decision(
            decision_type=new_decision_type,
            risk_score=original_decision.risk_score,
            confidence=original_decision.confidence,
            reasons=original_decision.reasons + [f"Manual override: {override_reason}"],
            recommendations=original_decision.recommendations,
            policy_violations=original_decision.policy_violations,
            review_required_fields=[],
            metadata={
                **original_decision.metadata,
                "override": {
                    "original_decision": original_decision.decision_type.value,
                    "override_reason": override_reason,
                    "supervisor_id": supervisor_id,
                    "override_timestamp": datetime.now().isoformat(),
                    "requires_audit": True
                }
            }
        )
        
        # Log override for audit
        logger.warning(f"Decision overridden: {original_decision.decision_type.value} -> "
                      f"{new_decision_type.value} by {supervisor_id}")
        
        return overridden

# Export main components
__all__ = [
    "RiskEngine",
    "RiskScore",
    "Decision",
    "DecisionType",
    "RiskCategory",
    "RiskFeature",
    "RiskPolicy"
]