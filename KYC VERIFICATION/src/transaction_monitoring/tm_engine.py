"""
Transaction Monitoring Engine
Velocity, Geovelocity, and Structuring Pattern Detection
Part of KYC Bank-Grade Parity - Phase 6

This module implements transaction monitoring rules for suspicious activity detection.
"""

import logging
import hashlib
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from enum import Enum
import math
from collections import defaultdict
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Manila timezone
MANILA_TZ = timezone(timedelta(hours=8))


class TransactionType(Enum):
    """Transaction types"""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    PAYMENT = "payment"
    CARD_PURCHASE = "card_purchase"
    ATM_WITHDRAWAL = "atm_withdrawal"


class AlertType(Enum):
    """Alert types for suspicious activities"""
    VELOCITY_BREACH = "velocity_breach"
    GEOVELOCITY_IMPOSSIBLE = "geovelocity_impossible"
    STRUCTURING_SUSPECTED = "structuring_suspected"
    RAPID_MOVEMENT = "rapid_movement"
    UNUSUAL_PATTERN = "unusual_pattern"
    HIGH_RISK_COUNTRY = "high_risk_country"
    ROUND_AMOUNT_PATTERN = "round_amount_pattern"
    TIME_PATTERN_ANOMALY = "time_pattern_anomaly"


class RiskScore(Enum):
    """Risk scoring levels"""
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Location:
    """Geographic location"""
    latitude: float
    longitude: float
    country: str
    city: str
    ip_address: Optional[str] = None
    
    def distance_to(self, other: 'Location') -> float:
        """Calculate distance in kilometers using Haversine formula"""
        R = 6371  # Earth's radius in kilometers
        
        lat1, lon1 = math.radians(self.latitude), math.radians(self.longitude)
        lat2, lon2 = math.radians(other.latitude), math.radians(other.longitude)
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c


@dataclass
class Transaction:
    """Transaction data structure"""
    transaction_id: str
    customer_id: str
    timestamp: datetime
    amount: float
    currency: str
    transaction_type: TransactionType
    location: Optional[Location]
    merchant: Optional[str] = None
    reference: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_json(self) -> str:
        """Convert to JSON"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        data['transaction_type'] = self.transaction_type.value
        if self.location:
            data['location'] = asdict(self.location)
        return json.dumps(data)


@dataclass
class Alert:
    """Alert generated from monitoring rules"""
    alert_id: str
    customer_id: str
    alert_type: AlertType
    risk_score: RiskScore
    transaction_ids: List[str]
    details: Dict[str, Any]
    created_at: datetime
    requires_review: bool
    auto_escalate: bool = False
    
    def to_case_format(self) -> Dict[str, Any]:
        """Convert to case management format"""
        return {
            "case_type": "transaction_monitoring",
            "alert_id": self.alert_id,
            "customer_id": self.customer_id,
            "alert_type": self.alert_type.value,
            "risk_score": self.risk_score.value,
            "priority": "critical" if self.risk_score == RiskScore.CRITICAL else 
                       "high" if self.risk_score == RiskScore.HIGH else "medium",
            "transaction_count": len(self.transaction_ids),
            "details": self.details,
            "created_at": self.created_at.isoformat(),
            "requires_review": self.requires_review
        }


class VelocityMonitor:
    """Monitor transaction velocity patterns"""
    
    def __init__(self):
        """Initialize velocity monitor"""
        # Load thresholds
        import sys
        sys.path.append('/workspace/KYC VERIFICATION')
        from src.config.threshold_manager import get_threshold_manager
        self.threshold_manager = get_threshold_manager()
        
        # Default thresholds (overridden by config)
        self.thresholds = {
            "daily_transaction_count": 20,
            "daily_transaction_amount": 500000,  # PHP
            "hourly_transaction_count": 10,
            "hourly_transaction_amount": 100000,
            "minute_transaction_count": 3
        }
        
        # Transaction history for velocity calculation
        self.transaction_history: Dict[str, List[Transaction]] = defaultdict(list)
        logger.info("Velocity Monitor initialized")
    
    def check_velocity(self, transaction: Transaction) -> Optional[Alert]:
        """
        Check if transaction violates velocity rules
        
        Args:
            transaction: Transaction to check
            
        Returns:
            Alert if velocity breach detected
        """
        customer_id = transaction.customer_id
        
        # Add to history
        self.transaction_history[customer_id].append(transaction)
        
        # Clean old transactions (keep last 24 hours)
        cutoff_time = transaction.timestamp - timedelta(hours=24)
        self.transaction_history[customer_id] = [
            t for t in self.transaction_history[customer_id]
            if t.timestamp >= cutoff_time
        ]
        
        history = self.transaction_history[customer_id]
        violations = []
        
        # Check daily velocity
        daily_txns = [t for t in history 
                     if t.timestamp >= transaction.timestamp - timedelta(days=1)]
        daily_count = len(daily_txns)
        daily_amount = sum(t.amount for t in daily_txns)
        
        if daily_count > self.thresholds["daily_transaction_count"]:
            violations.append(f"Daily count: {daily_count} > {self.thresholds['daily_transaction_count']}")
        
        if daily_amount > self.thresholds["daily_transaction_amount"]:
            violations.append(f"Daily amount: {daily_amount:.2f} > {self.thresholds['daily_transaction_amount']}")
        
        # Check hourly velocity
        hourly_txns = [t for t in history 
                      if t.timestamp >= transaction.timestamp - timedelta(hours=1)]
        hourly_count = len(hourly_txns)
        hourly_amount = sum(t.amount for t in hourly_txns)
        
        if hourly_count > self.thresholds["hourly_transaction_count"]:
            violations.append(f"Hourly count: {hourly_count} > {self.thresholds['hourly_transaction_count']}")
        
        if hourly_amount > self.thresholds["hourly_transaction_amount"]:
            violations.append(f"Hourly amount: {hourly_amount:.2f} > {self.thresholds['hourly_transaction_amount']}")
        
        # Check minute velocity (burst detection)
        minute_txns = [t for t in history 
                      if t.timestamp >= transaction.timestamp - timedelta(minutes=1)]
        minute_count = len(minute_txns)
        
        if minute_count > self.thresholds["minute_transaction_count"]:
            violations.append(f"Burst detected: {minute_count} txns in 1 minute")
        
        # Generate alert if violations found
        if violations:
            risk_score = RiskScore.CRITICAL if len(violations) >= 3 else \
                        RiskScore.HIGH if len(violations) >= 2 else RiskScore.MEDIUM
            
            return Alert(
                alert_id=hashlib.sha256(
                    f"{customer_id}_{transaction.transaction_id}_velocity".encode()
                ).hexdigest()[:16],
                customer_id=customer_id,
                alert_type=AlertType.VELOCITY_BREACH,
                risk_score=risk_score,
                transaction_ids=[t.transaction_id for t in hourly_txns],
                details={
                    "violations": violations,
                    "daily_stats": {"count": daily_count, "amount": daily_amount},
                    "hourly_stats": {"count": hourly_count, "amount": hourly_amount},
                    "minute_count": minute_count
                },
                created_at=datetime.now(MANILA_TZ),
                requires_review=True,
                auto_escalate=risk_score == RiskScore.CRITICAL
            )
        
        return None


class GeovelocityMonitor:
    """Monitor impossible travel patterns"""
    
    def __init__(self):
        """Initialize geovelocity monitor"""
        self.max_travel_speed_kmh = 1000  # Max reasonable speed (airplane)
        self.location_history: Dict[str, List[Tuple[datetime, Location]]] = defaultdict(list)
        logger.info("Geovelocity Monitor initialized")
    
    def check_geovelocity(self, transaction: Transaction) -> Optional[Alert]:
        """
        Check for impossible travel
        
        Args:
            transaction: Transaction with location
            
        Returns:
            Alert if impossible travel detected
        """
        if not transaction.location:
            return None
        
        customer_id = transaction.customer_id
        current_location = transaction.location
        current_time = transaction.timestamp
        
        # Get location history
        history = self.location_history[customer_id]
        
        # Add current location
        history.append((current_time, current_location))
        
        # Keep last 7 days
        cutoff = current_time - timedelta(days=7)
        self.location_history[customer_id] = [
            (t, loc) for t, loc in history if t >= cutoff
        ]
        
        # Check for impossible travel
        violations = []
        suspicious_pairs = []
        
        for prev_time, prev_location in history[:-1]:
            time_diff_hours = (current_time - prev_time).total_seconds() / 3600
            
            if time_diff_hours <= 0:
                continue
            
            distance_km = current_location.distance_to(prev_location)
            required_speed_kmh = distance_km / time_diff_hours
            
            # Check if speed is impossible
            if required_speed_kmh > self.max_travel_speed_kmh:
                violations.append({
                    "from": f"{prev_location.city}, {prev_location.country}",
                    "to": f"{current_location.city}, {current_location.country}",
                    "distance_km": round(distance_km, 2),
                    "time_hours": round(time_diff_hours, 2),
                    "required_speed_kmh": round(required_speed_kmh, 2),
                    "timestamp_from": prev_time.isoformat(),
                    "timestamp_to": current_time.isoformat()
                })
                suspicious_pairs.append((prev_time, current_time))
            
            # Check for rapid movement even if technically possible
            elif required_speed_kmh > 500 and time_diff_hours < 2:
                violations.append({
                    "type": "rapid_movement",
                    "from": f"{prev_location.city}, {prev_location.country}",
                    "to": f"{current_location.city}, {current_location.country}",
                    "distance_km": round(distance_km, 2),
                    "time_hours": round(time_diff_hours, 2)
                })
        
        if violations:
            # Determine if it's impossible travel or just rapid movement
            alert_type = AlertType.GEOVELOCITY_IMPOSSIBLE if any(
                v.get("required_speed_kmh", 0) > self.max_travel_speed_kmh 
                for v in violations
            ) else AlertType.RAPID_MOVEMENT
            
            risk_score = RiskScore.CRITICAL if alert_type == AlertType.GEOVELOCITY_IMPOSSIBLE else \
                        RiskScore.HIGH
            
            return Alert(
                alert_id=hashlib.sha256(
                    f"{customer_id}_{transaction.transaction_id}_geo".encode()
                ).hexdigest()[:16],
                customer_id=customer_id,
                alert_type=alert_type,
                risk_score=risk_score,
                transaction_ids=[transaction.transaction_id],
                details={
                    "violations": violations,
                    "current_location": {
                        "city": current_location.city,
                        "country": current_location.country,
                        "coordinates": [current_location.latitude, current_location.longitude]
                    }
                },
                created_at=datetime.now(MANILA_TZ),
                requires_review=True,
                auto_escalate=alert_type == AlertType.GEOVELOCITY_IMPOSSIBLE
            )
        
        return None


class StructuringDetector:
    """Detect structuring/smurfing patterns"""
    
    def __init__(self):
        """Initialize structuring detector"""
        self.reporting_threshold = 500000  # PHP reporting threshold
        self.structuring_threshold = 450000  # 90% of reporting threshold
        self.time_window_hours = 24
        self.min_transactions_for_pattern = 3
        logger.info("Structuring Detector initialized")
    
    def detect_structuring(self, transaction: Transaction,
                          recent_transactions: List[Transaction]) -> Optional[Alert]:
        """
        Detect potential structuring patterns
        
        Args:
            transaction: Current transaction
            recent_transactions: Recent transactions for customer
            
        Returns:
            Alert if structuring suspected
        """
        # Filter transactions within time window
        cutoff_time = transaction.timestamp - timedelta(hours=self.time_window_hours)
        relevant_txns = [
            t for t in recent_transactions 
            if t.timestamp >= cutoff_time and 
            t.transaction_type in [TransactionType.DEPOSIT, TransactionType.WITHDRAWAL]
        ]
        relevant_txns.append(transaction)
        
        if len(relevant_txns) < self.min_transactions_for_pattern:
            return None
        
        patterns_found = []
        
        # Pattern 1: Multiple transactions just below reporting threshold
        below_threshold_txns = [
            t for t in relevant_txns
            if self.structuring_threshold <= t.amount < self.reporting_threshold
        ]
        
        if len(below_threshold_txns) >= self.min_transactions_for_pattern:
            patterns_found.append({
                "type": "below_threshold_pattern",
                "count": len(below_threshold_txns),
                "total_amount": sum(t.amount for t in below_threshold_txns),
                "transactions": [t.transaction_id for t in below_threshold_txns]
            })
        
        # Pattern 2: Round amounts pattern
        round_amounts = [1000, 5000, 10000, 50000, 100000, 200000]
        round_txns = [
            t for t in relevant_txns
            if any(abs(t.amount - ra) < 100 for ra in round_amounts)
        ]
        
        if len(round_txns) >= self.min_transactions_for_pattern:
            patterns_found.append({
                "type": "round_amounts_pattern",
                "count": len(round_txns),
                "amounts": [t.amount for t in round_txns]
            })
        
        # Pattern 3: Rapid sequence of similar amounts
        amounts = [t.amount for t in relevant_txns]
        if len(amounts) >= self.min_transactions_for_pattern:
            amount_variance = np.var(amounts)
            amount_mean = np.mean(amounts)
            
            # Low variance relative to mean suggests similar amounts
            if amount_variance / (amount_mean ** 2) < 0.1:
                patterns_found.append({
                    "type": "similar_amounts_pattern",
                    "count": len(amounts),
                    "mean_amount": round(amount_mean, 2),
                    "variance": round(amount_variance, 2)
                })
        
        # Pattern 4: Time-based pattern (e.g., every hour)
        if len(relevant_txns) >= 4:
            time_diffs = []
            sorted_txns = sorted(relevant_txns, key=lambda t: t.timestamp)
            for i in range(1, len(sorted_txns)):
                diff_minutes = (sorted_txns[i].timestamp - sorted_txns[i-1].timestamp).total_seconds() / 60
                time_diffs.append(diff_minutes)
            
            if time_diffs:
                # Check if transactions occur at regular intervals
                time_variance = np.var(time_diffs)
                if time_variance < 100:  # Low variance in time intervals
                    patterns_found.append({
                        "type": "regular_interval_pattern",
                        "avg_interval_minutes": round(np.mean(time_diffs), 2),
                        "interval_variance": round(time_variance, 2)
                    })
        
        if patterns_found:
            # Calculate risk score based on patterns
            risk_score = RiskScore.CRITICAL if len(patterns_found) >= 3 else \
                        RiskScore.HIGH if len(patterns_found) >= 2 else RiskScore.MEDIUM
            
            return Alert(
                alert_id=hashlib.sha256(
                    f"{transaction.customer_id}_{transaction.transaction_id}_struct".encode()
                ).hexdigest()[:16],
                customer_id=transaction.customer_id,
                alert_type=AlertType.STRUCTURING_SUSPECTED,
                risk_score=risk_score,
                transaction_ids=[t.transaction_id for t in relevant_txns],
                details={
                    "patterns_detected": patterns_found,
                    "time_window_hours": self.time_window_hours,
                    "total_amount": sum(t.amount for t in relevant_txns),
                    "transaction_count": len(relevant_txns)
                },
                created_at=datetime.now(MANILA_TZ),
                requires_review=True,
                auto_escalate=len(patterns_found) >= 3
            )
        
        return None


class TransactionMonitoringEngine:
    """Main transaction monitoring engine"""
    
    def __init__(self):
        """Initialize monitoring engine"""
        self.velocity_monitor = VelocityMonitor()
        self.geovelocity_monitor = GeovelocityMonitor()
        self.structuring_detector = StructuringDetector()
        
        # Alert storage
        self.alerts: List[Alert] = []
        self.alert_history: Dict[str, List[Alert]] = defaultdict(list)
        
        # Metrics
        self.metrics = {
            "transactions_processed": 0,
            "alerts_generated": 0,
            "alerts_by_type": defaultdict(int),
            "processing_times": []
        }
        
        logger.info("Transaction Monitoring Engine initialized")
    
    def process_transaction(self, transaction: Transaction) -> List[Alert]:
        """
        Process transaction through all monitoring rules
        
        Args:
            transaction: Transaction to monitor
            
        Returns:
            List of generated alerts
        """
        start_time = time.time()
        alerts = []
        
        # Run velocity checks
        velocity_alert = self.velocity_monitor.check_velocity(transaction)
        if velocity_alert:
            alerts.append(velocity_alert)
        
        # Run geovelocity checks
        geo_alert = self.geovelocity_monitor.check_geovelocity(transaction)
        if geo_alert:
            alerts.append(geo_alert)
        
        # Run structuring detection
        customer_history = self.velocity_monitor.transaction_history.get(
            transaction.customer_id, []
        )
        struct_alert = self.structuring_detector.detect_structuring(
            transaction, customer_history
        )
        if struct_alert:
            alerts.append(struct_alert)
        
        # Store alerts
        for alert in alerts:
            self.alerts.append(alert)
            self.alert_history[transaction.customer_id].append(alert)
            self.metrics["alerts_by_type"][alert.alert_type.value] += 1
        
        # Update metrics
        self.metrics["transactions_processed"] += 1
        self.metrics["alerts_generated"] += len(alerts)
        self.metrics["processing_times"].append((time.time() - start_time) * 1000)
        
        # Log if alerts generated
        if alerts:
            logger.info(f"Generated {len(alerts)} alerts for transaction {transaction.transaction_id}")
            for alert in alerts:
                logger.info(f"  - {alert.alert_type.value}: Risk={alert.risk_score.value}")
        
        return alerts
    
    def get_customer_risk_profile(self, customer_id: str) -> Dict[str, Any]:
        """
        Get risk profile for customer
        
        Args:
            customer_id: Customer ID
            
        Returns:
            Risk profile dictionary
        """
        customer_alerts = self.alert_history.get(customer_id, [])
        
        if not customer_alerts:
            return {
                "customer_id": customer_id,
                "risk_level": "low",
                "alert_count": 0,
                "last_alert": None
            }
        
        # Calculate risk level based on recent alerts
        recent_alerts = [
            a for a in customer_alerts
            if a.created_at >= datetime.now(MANILA_TZ) - timedelta(days=30)
        ]
        
        critical_count = sum(1 for a in recent_alerts if a.risk_score == RiskScore.CRITICAL)
        high_count = sum(1 for a in recent_alerts if a.risk_score == RiskScore.HIGH)
        
        if critical_count > 0:
            risk_level = "critical"
        elif high_count >= 3:
            risk_level = "high"
        elif len(recent_alerts) >= 5:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        return {
            "customer_id": customer_id,
            "risk_level": risk_level,
            "alert_count": len(customer_alerts),
            "recent_alert_count": len(recent_alerts),
            "alert_breakdown": {
                alert_type.value: sum(1 for a in customer_alerts if a.alert_type == alert_type)
                for alert_type in AlertType
            },
            "last_alert": customer_alerts[-1].created_at.isoformat() if customer_alerts else None
        }
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Get monitoring metrics summary"""
        avg_processing_time = np.mean(self.metrics["processing_times"]) if self.metrics["processing_times"] else 0
        
        return {
            "transactions_processed": self.metrics["transactions_processed"],
            "alerts_generated": self.metrics["alerts_generated"],
            "alert_rate": self.metrics["alerts_generated"] / max(1, self.metrics["transactions_processed"]),
            "alerts_by_type": dict(self.metrics["alerts_by_type"]),
            "avg_processing_time_ms": round(avg_processing_time, 2),
            "active_alerts": len([a for a in self.alerts if a.requires_review])
        }
    
    def export_alerts_for_case_management(self) -> List[Dict[str, Any]]:
        """Export alerts in case management format"""
        return [alert.to_case_format() for alert in self.alerts if alert.requires_review]


def generate_test_transactions() -> List[Transaction]:
    """Generate test transactions for demo"""
    transactions = []
    base_time = datetime.now(MANILA_TZ)
    
    # Normal transaction
    transactions.append(Transaction(
        transaction_id="TXN001",
        customer_id="CUST001",
        timestamp=base_time - timedelta(hours=2),
        amount=5000,
        currency="PHP",
        transaction_type=TransactionType.DEPOSIT,
        location=Location(14.5995, 120.9842, "Philippines", "Manila")
    ))
    
    # Velocity breach pattern
    for i in range(15):
        transactions.append(Transaction(
            transaction_id=f"TXN10{i}",
            customer_id="CUST002",
            timestamp=base_time - timedelta(minutes=30-i),
            amount=50000,
            currency="PHP",
            transaction_type=TransactionType.WITHDRAWAL,
            location=Location(14.5995, 120.9842, "Philippines", "Manila")
        ))
    
    # Impossible travel
    transactions.append(Transaction(
        transaction_id="TXN201",
        customer_id="CUST003",
        timestamp=base_time - timedelta(hours=3),
        amount=10000,
        currency="PHP",
        transaction_type=TransactionType.CARD_PURCHASE,
        location=Location(14.5995, 120.9842, "Philippines", "Manila")
    ))
    
    transactions.append(Transaction(
        transaction_id="TXN202",
        customer_id="CUST003",
        timestamp=base_time - timedelta(hours=2),
        amount=15000,
        currency="PHP",
        transaction_type=TransactionType.CARD_PURCHASE,
        location=Location(40.7128, -74.0060, "USA", "New York")  # Impossible travel
    ))
    
    # Structuring pattern
    for i in range(5):
        transactions.append(Transaction(
            transaction_id=f"TXN30{i}",
            customer_id="CUST004",
            timestamp=base_time - timedelta(hours=5-i),
            amount=490000,  # Just below 500k threshold
            currency="PHP",
            transaction_type=TransactionType.DEPOSIT,
            location=Location(14.5995, 120.9842, "Philippines", "Manila")
        ))
    
    return transactions


if __name__ == "__main__":
    # Demo and testing
    print("=== Transaction Monitoring Engine Demo ===\n")
    
    # Initialize engine
    engine = TransactionMonitoringEngine()
    
    # Generate test transactions
    test_transactions = generate_test_transactions()
    
    print(f"Processing {len(test_transactions)} test transactions...\n")
    
    # Process transactions
    all_alerts = []
    for txn in test_transactions:
        alerts = engine.process_transaction(txn)
        all_alerts.extend(alerts)
    
    # Display results
    print(f"\n=== Monitoring Results ===")
    print(f"Total Transactions: {engine.metrics['transactions_processed']}")
    print(f"Total Alerts: {engine.metrics['alerts_generated']}")
    print(f"Alert Rate: {engine.metrics['alerts_generated']/engine.metrics['transactions_processed']:.1%}")
    
    print(f"\nAlerts by Type:")
    for alert_type, count in engine.metrics["alerts_by_type"].items():
        print(f"  - {alert_type}: {count}")
    
    # Show sample alerts
    print(f"\n=== Sample Alerts ===")
    for alert in all_alerts[:3]:
        print(f"\nAlert ID: {alert.alert_id}")
        print(f"  Customer: {alert.customer_id}")
        print(f"  Type: {alert.alert_type.value}")
        print(f"  Risk: {alert.risk_score.name}")
        print(f"  Transactions: {len(alert.transaction_ids)}")
        if "violations" in alert.details:
            print(f"  Violations: {alert.details['violations'][:2]}")
    
    # Show risk profiles
    print(f"\n=== Customer Risk Profiles ===")
    for customer_id in ["CUST002", "CUST003", "CUST004"]:
        profile = engine.get_customer_risk_profile(customer_id)
        print(f"\n{customer_id}:")
        print(f"  Risk Level: {profile['risk_level']}")
        print(f"  Total Alerts: {profile['alert_count']}")
    
    # Export for case management
    cases = engine.export_alerts_for_case_management()
    print(f"\n✓ Exported {len(cases)} alerts for case management")
    
    # Metrics summary
    metrics = engine.get_metrics_summary()
    print(f"\n=== Performance Metrics ===")
    print(f"Avg Processing Time: {metrics['avg_processing_time_ms']:.2f}ms")
    print(f"Active Alerts: {metrics['active_alerts']}")
    
    print("\n✓ Transaction Monitoring Engine operational")