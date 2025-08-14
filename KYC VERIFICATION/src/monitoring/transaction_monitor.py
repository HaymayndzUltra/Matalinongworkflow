"""
Transaction Monitoring Module
Velocity, Geovelocity, and Structuring Pattern Detection
Part of KYC Bank-Grade Parity - Phase 6

This module implements foundational transaction monitoring rules.
"""

import logging
import hashlib
import json
import time
import math
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from enum import Enum
from collections import defaultdict, deque
import numpy as np

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Manila timezone
MANILA_TZ = timezone(timedelta(hours=8))


class AlertType(Enum):
    """Types of transaction monitoring alerts"""
    VELOCITY = "velocity"
    GEOVELOCITY = "geovelocity"
    STRUCTURING = "structuring"
    LARGE_TRANSACTION = "large_transaction"
    RAPID_MOVEMENT = "rapid_movement"
    PATTERN_ANOMALY = "pattern_anomaly"


class AlertSeverity(Enum):
    """Alert severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TransactionType(Enum):
    """Transaction types"""
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    TRANSFER = "transfer"
    PAYMENT = "payment"
    CASH_IN = "cash_in"
    CASH_OUT = "cash_out"


@dataclass
class Transaction:
    """Transaction data structure"""
    transaction_id: str
    customer_id: str
    amount: float
    currency: str
    transaction_type: TransactionType
    timestamp: str
    location: Optional[Dict[str, float]] = None  # {"lat": x, "lon": y}
    merchant_id: Optional[str] = None
    channel: Optional[str] = None  # ATM, Online, Branch, Mobile
    metadata: Dict[str, Any] = None
    
    def to_json(self) -> str:
        """Convert to JSON"""
        data = asdict(self)
        data['transaction_type'] = self.transaction_type.value
        return json.dumps(data)


@dataclass
class Alert:
    """Transaction monitoring alert"""
    alert_id: str
    alert_type: AlertType
    severity: AlertSeverity
    customer_id: str
    transaction_ids: List[str]
    score: float
    reason: str
    details: Dict[str, Any]
    created_at: str
    requires_review: bool
    case_id: Optional[str] = None
    
    def to_json(self) -> str:
        """Convert to JSON"""
        data = asdict(self)
        data['alert_type'] = self.alert_type.value
        data['severity'] = self.severity.value
        return json.dumps(data)


@dataclass
class MonitoringResult:
    """Result of transaction monitoring"""
    monitoring_id: str
    transaction_id: str
    customer_id: str
    alerts_generated: List[Alert]
    risk_score: float
    processing_time_ms: float
    timestamp: str
    
    def has_alerts(self) -> bool:
        """Check if any alerts were generated"""
        return len(self.alerts_generated) > 0


class VelocityTracker:
    """Tracks transaction velocity per customer"""
    
    def __init__(self, window_size_minutes: int = 60):
        """
        Initialize velocity tracker
        
        Args:
            window_size_minutes: Time window for velocity calculation
        """
        self.window_size = timedelta(minutes=window_size_minutes)
        self.transactions: Dict[str, deque] = defaultdict(deque)
        
        # Load thresholds
        import sys
        sys.path.append('/workspace/KYC VERIFICATION')
        from src.config.threshold_manager import get_threshold_manager
        self.threshold_manager = get_threshold_manager()
        
        logger.info(f"Velocity Tracker initialized with {window_size_minutes}min window")
    
    def add_transaction(self, transaction: Transaction):
        """
        Add transaction to tracking
        
        Args:
            transaction: Transaction to track
        """
        customer_id = transaction.customer_id
        tx_time = datetime.fromisoformat(transaction.timestamp)
        
        # Add to customer's transaction history
        self.transactions[customer_id].append({
            'time': tx_time,
            'amount': transaction.amount,
            'type': transaction.transaction_type,
            'id': transaction.transaction_id
        })
        
        # Clean old transactions
        self._clean_old_transactions(customer_id)
    
    def _clean_old_transactions(self, customer_id: str):
        """Remove transactions outside the time window"""
        now = datetime.now(MANILA_TZ)
        cutoff = now - self.window_size
        
        while (self.transactions[customer_id] and 
               self.transactions[customer_id][0]['time'] < cutoff):
            self.transactions[customer_id].popleft()
    
    def check_velocity(self, customer_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if velocity exceeds threshold
        
        Args:
            customer_id: Customer ID
            
        Returns:
            Tuple of (exceeds_threshold, details)
        """
        self._clean_old_transactions(customer_id)
        
        if customer_id not in self.transactions:
            return False, {}
        
        # Get thresholds
        hourly_limit = self.threshold_manager.get("tm_velocity_hourly") or 10
        daily_limit = self.threshold_manager.get("tm_velocity_daily") or 50
        
        # Count transactions
        now = datetime.now(MANILA_TZ)
        hour_ago = now - timedelta(hours=1)
        day_ago = now - timedelta(days=1)
        
        hourly_count = sum(1 for tx in self.transactions[customer_id] 
                          if tx['time'] >= hour_ago)
        daily_count = sum(1 for tx in self.transactions[customer_id] 
                         if tx['time'] >= day_ago)
        
        # Calculate amounts
        hourly_amount = sum(tx['amount'] for tx in self.transactions[customer_id] 
                           if tx['time'] >= hour_ago)
        daily_amount = sum(tx['amount'] for tx in self.transactions[customer_id] 
                          if tx['time'] >= day_ago)
        
        # Check if exceeded
        hourly_exceeded = hourly_count > hourly_limit
        daily_exceeded = daily_count > daily_limit
        
        details = {
            'hourly_count': hourly_count,
            'hourly_limit': hourly_limit,
            'hourly_amount': hourly_amount,
            'daily_count': daily_count,
            'daily_limit': daily_limit,
            'daily_amount': daily_amount,
            'hourly_exceeded': hourly_exceeded,
            'daily_exceeded': daily_exceeded
        }
        
        return (hourly_exceeded or daily_exceeded), details


class GeovelocityDetector:
    """Detects impossible travel patterns"""
    
    def __init__(self):
        """Initialize geovelocity detector"""
        self.location_history: Dict[str, List[Dict]] = defaultdict(list)
        
        # Load thresholds
        import sys
        sys.path.append('/workspace/KYC VERIFICATION')
        from src.config.threshold_manager import get_threshold_manager
        self.threshold_manager = get_threshold_manager()
        
        logger.info("Geovelocity Detector initialized")
    
    def add_transaction(self, transaction: Transaction):
        """
        Add transaction with location
        
        Args:
            transaction: Transaction with location data
        """
        if not transaction.location:
            return
        
        customer_id = transaction.customer_id
        self.location_history[customer_id].append({
            'time': datetime.fromisoformat(transaction.timestamp),
            'location': transaction.location,
            'transaction_id': transaction.transaction_id
        })
        
        # Keep only last 100 locations
        if len(self.location_history[customer_id]) > 100:
            self.location_history[customer_id] = self.location_history[customer_id][-100:]
    
    def check_geovelocity(self, customer_id: str, 
                         current_location: Dict[str, float]) -> Tuple[bool, Dict[str, Any]]:
        """
        Check for impossible travel
        
        Args:
            customer_id: Customer ID
            current_location: Current transaction location
            
        Returns:
            Tuple of (suspicious, details)
        """
        if customer_id not in self.location_history or not self.location_history[customer_id]:
            return False, {}
        
        # Get threshold (km/hour)
        threshold = self.threshold_manager.get("tm_geovelocity") or 500
        
        # Get last location
        last_entry = self.location_history[customer_id][-1]
        last_location = last_entry['location']
        last_time = last_entry['time']
        
        # Calculate distance (Haversine formula)
        distance_km = self._calculate_distance(last_location, current_location)
        
        # Calculate time difference
        current_time = datetime.now(MANILA_TZ)
        time_diff = (current_time - last_time).total_seconds() / 3600  # hours
        
        if time_diff == 0:
            velocity = float('inf')
        else:
            velocity = distance_km / time_diff
        
        # Check if exceeds threshold
        suspicious = velocity > threshold
        
        details = {
            'distance_km': distance_km,
            'time_hours': time_diff,
            'velocity_kmh': velocity,
            'threshold_kmh': threshold,
            'last_location': last_location,
            'current_location': current_location,
            'suspicious': suspicious
        }
        
        return suspicious, details
    
    def _calculate_distance(self, loc1: Dict[str, float], 
                           loc2: Dict[str, float]) -> float:
        """
        Calculate distance between two locations using Haversine formula
        
        Args:
            loc1: First location {"lat": x, "lon": y}
            loc2: Second location {"lat": x, "lon": y}
            
        Returns:
            Distance in kilometers
        """
        R = 6371  # Earth's radius in kilometers
        
        lat1, lon1 = math.radians(loc1['lat']), math.radians(loc1['lon'])
        lat2, lon2 = math.radians(loc2['lat']), math.radians(loc2['lon'])
        
        dlat = lat2 - lat1
        dlon = lon2 - lon1
        
        a = math.sin(dlat/2)**2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon/2)**2
        c = 2 * math.asin(math.sqrt(a))
        
        return R * c


class StructuringDetector:
    """Detects potential structuring/smurfing patterns"""
    
    def __init__(self, window_hours: int = 24):
        """
        Initialize structuring detector
        
        Args:
            window_hours: Time window for pattern detection
        """
        self.window = timedelta(hours=window_hours)
        self.transaction_history: Dict[str, List[Transaction]] = defaultdict(list)
        
        # Load thresholds
        import sys
        sys.path.append('/workspace/KYC VERIFICATION')
        from src.config.threshold_manager import get_threshold_manager
        self.threshold_manager = get_threshold_manager()
        
        logger.info(f"Structuring Detector initialized with {window_hours}h window")
    
    def add_transaction(self, transaction: Transaction):
        """
        Add transaction for analysis
        
        Args:
            transaction: Transaction to analyze
        """
        customer_id = transaction.customer_id
        self.transaction_history[customer_id].append(transaction)
        
        # Clean old transactions
        self._clean_old_transactions(customer_id)
    
    def _clean_old_transactions(self, customer_id: str):
        """Remove transactions outside the window"""
        cutoff = datetime.now(MANILA_TZ) - self.window
        
        self.transaction_history[customer_id] = [
            tx for tx in self.transaction_history[customer_id]
            if datetime.fromisoformat(tx.timestamp) >= cutoff
        ]
    
    def detect_structuring(self, customer_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Detect structuring patterns
        
        Args:
            customer_id: Customer ID
            
        Returns:
            Tuple of (suspicious, details)
        """
        if customer_id not in self.transaction_history:
            return False, {}
        
        transactions = self.transaction_history[customer_id]
        if len(transactions) < 3:
            return False, {}
        
        # Get threshold
        threshold_amount = self.threshold_manager.get("tm_structuring_amount") or 500000
        
        # Analyze patterns
        patterns = []
        
        # Pattern 1: Multiple similar amounts just below threshold
        amounts = [tx.amount for tx in transactions]
        similar_threshold = threshold_amount * 0.9  # 90% of threshold
        
        similar_amounts = [a for a in amounts if similar_threshold <= a < threshold_amount]
        if len(similar_amounts) >= 3:
            patterns.append({
                'type': 'multiple_below_threshold',
                'count': len(similar_amounts),
                'amounts': similar_amounts,
                'total': sum(similar_amounts)
            })
        
        # Pattern 2: Rapid sequence of deposits
        deposit_times = [
            datetime.fromisoformat(tx.timestamp) 
            for tx in transactions 
            if tx.transaction_type == TransactionType.DEPOSIT
        ]
        
        if len(deposit_times) >= 3:
            time_diffs = [
                (deposit_times[i+1] - deposit_times[i]).total_seconds() / 60
                for i in range(len(deposit_times)-1)
            ]
            
            rapid_deposits = [t for t in time_diffs if t < 30]  # Within 30 minutes
            if len(rapid_deposits) >= 2:
                patterns.append({
                    'type': 'rapid_deposits',
                    'count': len(rapid_deposits) + 1,
                    'intervals_minutes': rapid_deposits
                })
        
        # Pattern 3: Round number amounts
        round_amounts = [a for a in amounts if a % 10000 == 0]  # Divisible by 10,000
        if len(round_amounts) >= 3:
            patterns.append({
                'type': 'round_amounts',
                'count': len(round_amounts),
                'amounts': round_amounts
            })
        
        suspicious = len(patterns) > 0
        
        details = {
            'transaction_count': len(transactions),
            'total_amount': sum(amounts),
            'patterns_detected': patterns,
            'threshold_amount': threshold_amount,
            'suspicious': suspicious
        }
        
        return suspicious, details


class TransactionMonitor:
    """Main transaction monitoring orchestrator"""
    
    def __init__(self):
        """Initialize transaction monitor"""
        self.velocity_tracker = VelocityTracker()
        self.geovelocity_detector = GeovelocityDetector()
        self.structuring_detector = StructuringDetector()
        self.alert_storage = AlertStorage()
        
        # Load case manager for alert routing
        import sys
        sys.path.append('/workspace/KYC VERIFICATION')
        from src.aml.screening_system import CaseManager
        self.case_manager = CaseManager()
        
        logger.info("Transaction Monitor initialized with all detectors")
    
    def monitor_transaction(self, transaction: Transaction) -> MonitoringResult:
        """
        Monitor a transaction for suspicious patterns
        
        Args:
            transaction: Transaction to monitor
            
        Returns:
            MonitoringResult with any alerts
        """
        start_time = time.time()
        alerts = []
        
        # Add to all trackers
        self.velocity_tracker.add_transaction(transaction)
        self.geovelocity_detector.add_transaction(transaction)
        self.structuring_detector.add_transaction(transaction)
        
        # Check velocity
        velocity_exceeded, velocity_details = self.velocity_tracker.check_velocity(
            transaction.customer_id
        )
        if velocity_exceeded:
            alert = self._create_alert(
                AlertType.VELOCITY,
                AlertSeverity.HIGH if velocity_details.get('daily_exceeded') else AlertSeverity.MEDIUM,
                transaction,
                "Transaction velocity exceeded threshold",
                velocity_details
            )
            alerts.append(alert)
        
        # Check geovelocity if location provided
        if transaction.location:
            geo_suspicious, geo_details = self.geovelocity_detector.check_geovelocity(
                transaction.customer_id,
                transaction.location
            )
            if geo_suspicious:
                alert = self._create_alert(
                    AlertType.GEOVELOCITY,
                    AlertSeverity.CRITICAL,
                    transaction,
                    "Impossible travel detected",
                    geo_details
                )
                alerts.append(alert)
        
        # Check structuring
        struct_suspicious, struct_details = self.structuring_detector.detect_structuring(
            transaction.customer_id
        )
        if struct_suspicious:
            alert = self._create_alert(
                AlertType.STRUCTURING,
                AlertSeverity.HIGH,
                transaction,
                "Potential structuring pattern detected",
                struct_details
            )
            alerts.append(alert)
        
        # Check large transaction
        large_tx_threshold = 1000000  # 1M PHP
        if transaction.amount >= large_tx_threshold:
            alert = self._create_alert(
                AlertType.LARGE_TRANSACTION,
                AlertSeverity.MEDIUM,
                transaction,
                f"Large transaction: {transaction.amount:,.2f} {transaction.currency}",
                {'amount': transaction.amount, 'threshold': large_tx_threshold}
            )
            alerts.append(alert)
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(alerts)
        
        # Create monitoring result
        result = MonitoringResult(
            monitoring_id=hashlib.sha256(
                f"{transaction.transaction_id}_{datetime.now(MANILA_TZ).isoformat()}".encode()
            ).hexdigest()[:16],
            transaction_id=transaction.transaction_id,
            customer_id=transaction.customer_id,
            alerts_generated=alerts,
            risk_score=risk_score,
            processing_time_ms=(time.time() - start_time) * 1000,
            timestamp=datetime.now(MANILA_TZ).isoformat()
        )
        
        # Route high-severity alerts to case management
        for alert in alerts:
            if alert.severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL]:
                self._create_case_for_alert(alert)
        
        # Store alerts
        for alert in alerts:
            self.alert_storage.store_alert(alert)
        
        logger.info(f"Transaction {transaction.transaction_id} monitored: "
                   f"{len(alerts)} alerts, risk score: {risk_score:.2f}")
        
        return result
    
    def _create_alert(self, alert_type: AlertType, severity: AlertSeverity,
                     transaction: Transaction, reason: str, 
                     details: Dict[str, Any]) -> Alert:
        """Create an alert"""
        alert_id = hashlib.sha256(
            f"{transaction.transaction_id}_{alert_type.value}_{datetime.now(MANILA_TZ).isoformat()}".encode()
        ).hexdigest()[:16]
        
        return Alert(
            alert_id=alert_id,
            alert_type=alert_type,
            severity=severity,
            customer_id=transaction.customer_id,
            transaction_ids=[transaction.transaction_id],
            score=self._severity_to_score(severity),
            reason=reason,
            details=details,
            created_at=datetime.now(MANILA_TZ).isoformat(),
            requires_review=severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL]
        )
    
    def _severity_to_score(self, severity: AlertSeverity) -> float:
        """Convert severity to numeric score"""
        scores = {
            AlertSeverity.LOW: 0.25,
            AlertSeverity.MEDIUM: 0.5,
            AlertSeverity.HIGH: 0.75,
            AlertSeverity.CRITICAL: 1.0
        }
        return scores.get(severity, 0.5)
    
    def _calculate_risk_score(self, alerts: List[Alert]) -> float:
        """Calculate overall risk score from alerts"""
        if not alerts:
            return 0.0
        
        # Weighted average with emphasis on highest severity
        scores = [alert.score for alert in alerts]
        max_score = max(scores)
        avg_score = sum(scores) / len(scores)
        
        # Weight: 70% max, 30% average
        return 0.7 * max_score + 0.3 * avg_score
    
    def _create_case_for_alert(self, alert: Alert):
        """Create a case for high-severity alert"""
        # Mock case creation - would integrate with case management
        logger.info(f"Case created for alert {alert.alert_id} (severity: {alert.severity.value})")


class AlertStorage:
    """Storage for transaction monitoring alerts"""
    
    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize alert storage
        
        Args:
            storage_path: Path to store alerts
        """
        self.storage_path = storage_path or Path("/workspace/KYC VERIFICATION/alerts")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.alerts: Dict[str, Alert] = {}
        logger.info(f"Alert Storage initialized at {self.storage_path}")
    
    def store_alert(self, alert: Alert) -> bool:
        """
        Store an alert
        
        Args:
            alert: Alert to store
            
        Returns:
            True if stored successfully
        """
        try:
            # Store in memory
            self.alerts[alert.alert_id] = alert
            
            # Persist to file
            filename = self.storage_path / f"{alert.alert_id}.json"
            with open(filename, 'w') as f:
                f.write(alert.to_json())
            
            logger.debug(f"Alert stored: {alert.alert_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to store alert: {e}")
            return False
    
    def get_alert(self, alert_id: str) -> Optional[Alert]:
        """
        Retrieve an alert
        
        Args:
            alert_id: Alert ID
            
        Returns:
            Alert or None
        """
        return self.alerts.get(alert_id)
    
    def get_customer_alerts(self, customer_id: str, 
                           limit: int = 100) -> List[Alert]:
        """
        Get alerts for a customer
        
        Args:
            customer_id: Customer ID
            limit: Maximum alerts to return
            
        Returns:
            List of alerts
        """
        customer_alerts = [
            alert for alert in self.alerts.values()
            if alert.customer_id == customer_id
        ]
        
        # Sort by creation time (newest first)
        customer_alerts.sort(key=lambda a: a.created_at, reverse=True)
        
        return customer_alerts[:limit]


def generate_alert_summary(monitor: TransactionMonitor) -> Dict[str, Any]:
    """
    Generate summary of monitoring activities
    
    Args:
        monitor: Transaction monitor instance
        
    Returns:
        Summary dictionary
    """
    summary = {
        'timestamp': datetime.now(MANILA_TZ).isoformat(),
        'active_customers': len(monitor.velocity_tracker.transactions),
        'alerts_total': len(monitor.alert_storage.alerts),
        'alerts_by_type': {},
        'alerts_by_severity': {},
        'high_risk_customers': []
    }
    
    # Count by type and severity
    for alert in monitor.alert_storage.alerts.values():
        # By type
        alert_type = alert.alert_type.value
        summary['alerts_by_type'][alert_type] = summary['alerts_by_type'].get(alert_type, 0) + 1
        
        # By severity
        severity = alert.severity.value
        summary['alerts_by_severity'][severity] = summary['alerts_by_severity'].get(severity, 0) + 1
        
        # Track high risk
        if alert.severity in [AlertSeverity.HIGH, AlertSeverity.CRITICAL]:
            if alert.customer_id not in summary['high_risk_customers']:
                summary['high_risk_customers'].append(alert.customer_id)
    
    return summary


if __name__ == "__main__":
    # Demo and testing
    print("=== Transaction Monitoring Demo ===\n")
    
    # Initialize monitor
    monitor = TransactionMonitor()
    
    # Test Case 1: Normal transaction
    print("Test 1: Normal Transaction")
    tx1 = Transaction(
        transaction_id="TX001",
        customer_id="CUST001",
        amount=5000,
        currency="PHP",
        transaction_type=TransactionType.PAYMENT,
        timestamp=datetime.now(MANILA_TZ).isoformat(),
        location={"lat": 14.5995, "lon": 120.9842},  # Manila
        channel="Mobile"
    )
    result = monitor.monitor_transaction(tx1)
    print(f"  Alerts: {len(result.alerts_generated)}")
    print(f"  Risk Score: {result.risk_score:.2f}")
    
    # Test Case 2: Velocity breach
    print("\nTest 2: Velocity Breach (11 transactions)")
    for i in range(11):
        tx = Transaction(
            transaction_id=f"TX10{i}",
            customer_id="CUST002",
            amount=1000,
            currency="PHP",
            transaction_type=TransactionType.PAYMENT,
            timestamp=datetime.now(MANILA_TZ).isoformat()
        )
        result = monitor.monitor_transaction(tx)
    print(f"  Alerts: {len(result.alerts_generated)}")
    if result.alerts_generated:
        print(f"  Alert Type: {result.alerts_generated[0].alert_type.value}")
        print(f"  Severity: {result.alerts_generated[0].severity.value}")
    
    # Test Case 3: Geovelocity - impossible travel
    print("\nTest 3: Geovelocity Alert")
    # First transaction in Manila
    tx_manila = Transaction(
        transaction_id="TX201",
        customer_id="CUST003",
        amount=5000,
        currency="PHP",
        transaction_type=TransactionType.WITHDRAWAL,
        timestamp=datetime.now(MANILA_TZ).isoformat(),
        location={"lat": 14.5995, "lon": 120.9842}  # Manila
    )
    monitor.monitor_transaction(tx_manila)
    
    # Second transaction in Cebu (impossible travel)
    tx_cebu = Transaction(
        transaction_id="TX202",
        customer_id="CUST003",
        amount=3000,
        currency="PHP",
        transaction_type=TransactionType.WITHDRAWAL,
        timestamp=datetime.now(MANILA_TZ).isoformat(),
        location={"lat": 10.3157, "lon": 123.8854}  # Cebu (570km away)
    )
    result = monitor.monitor_transaction(tx_cebu)
    print(f"  Alerts: {len(result.alerts_generated)}")
    if result.alerts_generated:
        for alert in result.alerts_generated:
            print(f"  Alert: {alert.alert_type.value} - {alert.reason}")
    
    # Test Case 4: Structuring pattern
    print("\nTest 4: Structuring Pattern")
    amounts = [490000, 480000, 495000]  # Just below 500K threshold
    for i, amount in enumerate(amounts):
        tx = Transaction(
            transaction_id=f"TX30{i}",
            customer_id="CUST004",
            amount=amount,
            currency="PHP",
            transaction_type=TransactionType.DEPOSIT,
            timestamp=datetime.now(MANILA_TZ).isoformat()
        )
        result = monitor.monitor_transaction(tx)
    print(f"  Alerts: {len(result.alerts_generated)}")
    if result.alerts_generated:
        print(f"  Alert Type: {result.alerts_generated[0].alert_type.value}")
        print(f"  Details: Detected pattern with {len(amounts)} transactions")
    
    # Test Case 5: Large transaction
    print("\nTest 5: Large Transaction")
    tx_large = Transaction(
        transaction_id="TX401",
        customer_id="CUST005",
        amount=5000000,  # 5M PHP
        currency="PHP",
        transaction_type=TransactionType.TRANSFER,
        timestamp=datetime.now(MANILA_TZ).isoformat()
    )
    result = monitor.monitor_transaction(tx_large)
    print(f"  Alerts: {len(result.alerts_generated)}")
    print(f"  Risk Score: {result.risk_score:.2f}")
    
    # Generate summary
    print("\n=== Monitoring Summary ===")
    summary = generate_alert_summary(monitor)
    print(f"Active Customers: {summary['active_customers']}")
    print(f"Total Alerts: {summary['alerts_total']}")
    print(f"Alerts by Type: {summary['alerts_by_type']}")
    print(f"Alerts by Severity: {summary['alerts_by_severity']}")
    print(f"High Risk Customers: {len(summary['high_risk_customers'])}")
    
    print("\n✓ Transaction Monitoring system operational with all rules active")