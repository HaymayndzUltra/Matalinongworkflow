"""
Human Review Console & Case Management Module
RBAC, Dual Control, Audit Trails, and Reviewer Calibration
Part of KYC Bank-Grade Parity - Phase 7

This module implements the human review console for case management.
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
from collections import defaultdict
import numpy as np
from abc import ABC, abstractmethod

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Manila timezone
MANILA_TZ = timezone(timedelta(hours=8))


class Role(Enum):
    """User roles in the review system"""
    REVIEWER_L1 = "reviewer_l1"
    REVIEWER_L2 = "reviewer_l2"
    SUPERVISOR = "supervisor"
    MANAGER = "manager"
    ADMIN = "admin"
    AUDITOR = "auditor"


class CaseStatus(Enum):
    """Case status"""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    ESCALATED = "escalated"
    RESOLVED = "resolved"
    REJECTED = "rejected"
    ON_HOLD = "on_hold"


class ReviewDecision(Enum):
    """Review decisions"""
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"
    REQUEST_INFO = "request_info"
    DEFER = "defer"


class QueueType(Enum):
    """Types of review queues"""
    STANDARD = "standard"
    HIGH_RISK = "high_risk"
    ESCALATION = "escalation"
    QUALITY_CHECK = "quality_check"


@dataclass
class User:
    """System user"""
    user_id: str
    username: str
    role: Role
    permissions: List[str]
    active: bool
    created_at: str
    last_login: Optional[str] = None
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has permission"""
        return permission in self.permissions


@dataclass
class ReviewCase:
    """Case for review"""
    case_id: str
    customer_id: str
    case_type: str
    priority: str
    status: CaseStatus
    queue_type: QueueType
    assigned_to: Optional[str]
    created_at: str
    sla_deadline: str
    evidence: Dict[str, Any]
    risk_score: float
    alerts: List[str]
    requires_dual_control: bool
    review_history: List[Dict[str, Any]]
    resolution: Optional[ReviewDecision] = None
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    notes: List[str] = None


@dataclass
class ReviewAction:
    """Action taken during review"""
    action_id: str
    case_id: str
    user_id: str
    action_type: str
    decision: Optional[ReviewDecision]
    notes: str
    evidence_reviewed: List[str]
    timestamp: str
    ip_address: Optional[str] = None
    session_id: Optional[str] = None


@dataclass
class CalibrationResult:
    """Reviewer calibration result"""
    reviewer_id: str
    period: str
    total_reviews: int
    agreement_rate: float
    kappa_score: float
    false_positive_rate: float
    false_negative_rate: float
    avg_review_time_seconds: float
    needs_retraining: bool


class RBACManager:
    """Role-Based Access Control manager"""
    
    def __init__(self):
        """Initialize RBAC manager"""
        self.users: Dict[str, User] = {}
        self.sessions: Dict[str, Dict[str, Any]] = {}
        self._setup_default_permissions()
        logger.info("RBAC Manager initialized")
    
    def _setup_default_permissions(self):
        """Setup default role permissions"""
        self.role_permissions = {
            Role.REVIEWER_L1: [
                "view_cases", "review_standard_cases", "add_notes"
            ],
            Role.REVIEWER_L2: [
                "view_cases", "review_standard_cases", "review_high_risk_cases",
                "add_notes", "escalate_cases"
            ],
            Role.SUPERVISOR: [
                "view_cases", "review_all_cases", "reassign_cases",
                "override_decisions", "view_metrics"
            ],
            Role.MANAGER: [
                "view_cases", "review_all_cases", "reassign_cases",
                "override_decisions", "view_metrics", "manage_users",
                "configure_queues"
            ],
            Role.ADMIN: ["*"],  # All permissions
            Role.AUDITOR: [
                "view_cases", "view_audit_logs", "export_reports"
            ]
        }
    
    def create_user(self, username: str, role: Role) -> User:
        """
        Create a new user
        
        Args:
            username: Username
            role: User role
            
        Returns:
            Created user
        """
        user_id = hashlib.sha256(f"{username}_{datetime.now(MANILA_TZ).isoformat()}".encode()).hexdigest()[:12]
        
        permissions = self.role_permissions.get(role, [])
        
        user = User(
            user_id=user_id,
            username=username,
            role=role,
            permissions=permissions,
            active=True,
            created_at=datetime.now(MANILA_TZ).isoformat()
        )
        
        self.users[user_id] = user
        logger.info(f"User created: {username} ({role.value})")
        return user
    
    def authenticate(self, username: str, password: str) -> Optional[str]:
        """
        Authenticate user (mock implementation)
        
        Args:
            username: Username
            password: Password
            
        Returns:
            Session ID if authenticated
        """
        # Mock authentication - in production would verify against secure store
        for user in self.users.values():
            if user.username == username and user.active:
                session_id = hashlib.sha256(
                    f"{user.user_id}_{datetime.now(MANILA_TZ).isoformat()}".encode()
                ).hexdigest()[:16]
                
                self.sessions[session_id] = {
                    "user_id": user.user_id,
                    "created_at": datetime.now(MANILA_TZ).isoformat(),
                    "last_activity": datetime.now(MANILA_TZ).isoformat()
                }
                
                user.last_login = datetime.now(MANILA_TZ).isoformat()
                logger.info(f"User authenticated: {username}")
                return session_id
        
        logger.warning(f"Authentication failed for: {username}")
        return None
    
    def check_permission(self, session_id: str, permission: str) -> bool:
        """
        Check if session has permission
        
        Args:
            session_id: Session ID
            permission: Permission to check
            
        Returns:
            True if permitted
        """
        if session_id not in self.sessions:
            return False
        
        user_id = self.sessions[session_id]["user_id"]
        user = self.users.get(user_id)
        
        if not user or not user.active:
            return False
        
        # Admin has all permissions
        if user.role == Role.ADMIN or "*" in user.permissions:
            return True
        
        return permission in user.permissions


class DualControlManager:
    """Manages dual control requirements"""
    
    def __init__(self):
        """Initialize dual control manager"""
        self.pending_approvals: Dict[str, Dict[str, Any]] = {}
        
        # Load config
        import sys
        sys.path.append('/workspace/KYC VERIFICATION')
        from src.config.threshold_manager import get_threshold_manager
        self.threshold_manager = get_threshold_manager()
        
        logger.info("Dual Control Manager initialized")
    
    def requires_dual_control(self, case: ReviewCase) -> bool:
        """
        Check if case requires dual control
        
        Args:
            case: Review case
            
        Returns:
            True if dual control required
        """
        # High-risk cases require dual control
        if case.queue_type == QueueType.HIGH_RISK:
            return True
        
        # High risk score cases
        risk_threshold = self.threshold_manager.get("review_dual_control_risk_threshold") or 0.8
        if case.risk_score >= risk_threshold:
            return True
        
        # Explicit flag
        return case.requires_dual_control
    
    def initiate_dual_control(self, case_id: str, first_reviewer: str,
                            decision: ReviewDecision, notes: str) -> str:
        """
        Initiate dual control approval
        
        Args:
            case_id: Case ID
            first_reviewer: First reviewer ID
            decision: Proposed decision
            notes: Review notes
            
        Returns:
            Approval request ID
        """
        approval_id = hashlib.sha256(
            f"{case_id}_{first_reviewer}_{datetime.now(MANILA_TZ).isoformat()}".encode()
        ).hexdigest()[:16]
        
        self.pending_approvals[approval_id] = {
            "case_id": case_id,
            "first_reviewer": first_reviewer,
            "decision": decision,
            "notes": notes,
            "created_at": datetime.now(MANILA_TZ).isoformat(),
            "status": "pending",
            "second_reviewer": None,
            "final_decision": None
        }
        
        logger.info(f"Dual control initiated for case {case_id}")
        return approval_id
    
    def complete_dual_control(self, approval_id: str, second_reviewer: str,
                             confirm_decision: bool, additional_notes: str = "") -> bool:
        """
        Complete dual control approval
        
        Args:
            approval_id: Approval request ID
            second_reviewer: Second reviewer ID
            confirm_decision: Whether to confirm the decision
            additional_notes: Additional notes
            
        Returns:
            True if approved
        """
        if approval_id not in self.pending_approvals:
            logger.error(f"Approval {approval_id} not found")
            return False
        
        approval = self.pending_approvals[approval_id]
        
        # Ensure different reviewers
        if second_reviewer == approval["first_reviewer"]:
            logger.error("Same reviewer cannot complete dual control")
            return False
        
        approval["second_reviewer"] = second_reviewer
        approval["confirmed"] = confirm_decision
        approval["additional_notes"] = additional_notes
        approval["completed_at"] = datetime.now(MANILA_TZ).isoformat()
        approval["status"] = "approved" if confirm_decision else "rejected"
        
        logger.info(f"Dual control completed for approval {approval_id}: {approval['status']}")
        return confirm_decision


class ReviewQueue:
    """Manages review queues"""
    
    def __init__(self, queue_type: QueueType):
        """
        Initialize review queue
        
        Args:
            queue_type: Type of queue
        """
        self.queue_type = queue_type
        self.cases: List[ReviewCase] = []
        self.assignments: Dict[str, List[str]] = defaultdict(list)  # reviewer_id -> case_ids
        logger.info(f"Review Queue initialized: {queue_type.value}")
    
    def add_case(self, case: ReviewCase):
        """Add case to queue"""
        self.cases.append(case)
        logger.debug(f"Case {case.case_id} added to {self.queue_type.value} queue")
    
    def assign_case(self, case_id: str, reviewer_id: str) -> bool:
        """
        Assign case to reviewer
        
        Args:
            case_id: Case ID
            reviewer_id: Reviewer ID
            
        Returns:
            True if assigned successfully
        """
        for case in self.cases:
            if case.case_id == case_id:
                case.assigned_to = reviewer_id
                case.status = CaseStatus.IN_REVIEW
                self.assignments[reviewer_id].append(case_id)
                logger.info(f"Case {case_id} assigned to {reviewer_id}")
                return True
        return False
    
    def get_next_case(self, reviewer_id: str) -> Optional[ReviewCase]:
        """
        Get next case for reviewer
        
        Args:
            reviewer_id: Reviewer ID
            
        Returns:
            Next case or None
        """
        # Find unassigned cases
        for case in self.cases:
            if case.assigned_to is None and case.status == CaseStatus.PENDING:
                self.assign_case(case.case_id, reviewer_id)
                return case
        
        return None
    
    def get_queue_metrics(self) -> Dict[str, Any]:
        """Get queue metrics"""
        total = len(self.cases)
        pending = sum(1 for c in self.cases if c.status == CaseStatus.PENDING)
        in_review = sum(1 for c in self.cases if c.status == CaseStatus.IN_REVIEW)
        resolved = sum(1 for c in self.cases if c.status == CaseStatus.RESOLVED)
        
        # Calculate SLA compliance
        now = datetime.now(MANILA_TZ)
        overdue = sum(1 for c in self.cases 
                     if c.status != CaseStatus.RESOLVED and 
                     datetime.fromisoformat(c.sla_deadline) < now)
        
        return {
            "queue_type": self.queue_type.value,
            "total_cases": total,
            "pending": pending,
            "in_review": in_review,
            "resolved": resolved,
            "overdue": overdue,
            "sla_compliance": (total - overdue) / total if total > 0 else 1.0
        }


class AuditLogger:
    """Audit logging for all review actions"""
    
    def __init__(self, log_path: Optional[Path] = None):
        """
        Initialize audit logger
        
        Args:
            log_path: Path to store audit logs
        """
        self.log_path = log_path or Path("/workspace/KYC VERIFICATION/audit_logs")
        self.log_path.mkdir(parents=True, exist_ok=True)
        self.actions: List[ReviewAction] = []
        logger.info("Audit Logger initialized")
    
    def log_action(self, action: ReviewAction):
        """
        Log a review action
        
        Args:
            action: Review action to log
        """
        self.actions.append(action)
        
        # Write to file
        log_file = self.log_path / f"audit_{datetime.now(MANILA_TZ).strftime('%Y%m%d')}.jsonl"
        
        try:
            with open(log_file, 'a') as f:
                f.write(json.dumps(asdict(action)) + '\n')
            logger.debug(f"Audit logged: {action.action_type} for case {action.case_id}")
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
    
    def get_case_audit_trail(self, case_id: str) -> List[ReviewAction]:
        """
        Get audit trail for a case
        
        Args:
            case_id: Case ID
            
        Returns:
            List of actions for the case
        """
        return [a for a in self.actions if a.case_id == case_id]


class ReviewerCalibration:
    """Manages reviewer calibration and quality checks"""
    
    def __init__(self):
        """Initialize calibration system"""
        self.review_samples: Dict[str, List[Dict]] = defaultdict(list)
        self.calibration_results: Dict[str, CalibrationResult] = {}
        logger.info("Reviewer Calibration system initialized")
    
    def add_review_sample(self, reviewer_id: str, case_id: str,
                         decision: ReviewDecision, ground_truth: Optional[ReviewDecision] = None):
        """
        Add review sample for calibration
        
        Args:
            reviewer_id: Reviewer ID
            case_id: Case ID
            decision: Reviewer's decision
            ground_truth: Expert/consensus decision
        """
        sample = {
            "case_id": case_id,
            "decision": decision.value,
            "ground_truth": ground_truth.value if ground_truth else None,
            "timestamp": datetime.now(MANILA_TZ).isoformat()
        }
        
        self.review_samples[reviewer_id].append(sample)
    
    def calculate_irr(self, reviewer_id: str) -> float:
        """
        Calculate Inter-Rater Reliability (Cohen's Kappa)
        
        Args:
            reviewer_id: Reviewer ID
            
        Returns:
            Kappa score
        """
        samples = self.review_samples.get(reviewer_id, [])
        
        if len(samples) < 20:  # Need minimum samples
            return 0.0
        
        # Get samples with ground truth
        paired_samples = [(s["decision"], s["ground_truth"]) 
                         for s in samples if s["ground_truth"]]
        
        if len(paired_samples) < 10:
            return 0.0
        
        # Calculate agreement
        agreements = sum(1 for r, g in paired_samples if r == g)
        total = len(paired_samples)
        
        observed_agreement = agreements / total
        
        # Calculate expected agreement (simplified)
        # In production, would use proper Cohen's Kappa calculation
        expected_agreement = 0.25  # Assuming 4 decision types
        
        if expected_agreement == 1:
            return 1.0
        
        kappa = (observed_agreement - expected_agreement) / (1 - expected_agreement)
        
        return max(0, min(1, kappa))
    
    def calibrate_reviewer(self, reviewer_id: str) -> CalibrationResult:
        """
        Perform calibration for a reviewer
        
        Args:
            reviewer_id: Reviewer ID
            
        Returns:
            Calibration result
        """
        samples = self.review_samples.get(reviewer_id, [])
        
        if not samples:
            return CalibrationResult(
                reviewer_id=reviewer_id,
                period=datetime.now(MANILA_TZ).strftime("%Y-%m"),
                total_reviews=0,
                agreement_rate=0.0,
                kappa_score=0.0,
                false_positive_rate=0.0,
                false_negative_rate=0.0,
                avg_review_time_seconds=0.0,
                needs_retraining=True
            )
        
        # Calculate metrics
        kappa = self.calculate_irr(reviewer_id)
        
        # Calculate agreement rate
        with_truth = [s for s in samples if s["ground_truth"]]
        agreement_rate = sum(1 for s in with_truth 
                            if s["decision"] == s["ground_truth"]) / len(with_truth) if with_truth else 0
        
        # Calculate FPR/FNR (simplified)
        false_positives = sum(1 for s in with_truth 
                             if s["decision"] == "approve" and s["ground_truth"] == "reject")
        false_negatives = sum(1 for s in with_truth 
                             if s["decision"] == "reject" and s["ground_truth"] == "approve")
        
        fpr = false_positives / len(with_truth) if with_truth else 0
        fnr = false_negatives / len(with_truth) if with_truth else 0
        
        # Determine if retraining needed (κ < 0.8)
        needs_retraining = kappa < 0.8
        
        result = CalibrationResult(
            reviewer_id=reviewer_id,
            period=datetime.now(MANILA_TZ).strftime("%Y-%m"),
            total_reviews=len(samples),
            agreement_rate=agreement_rate,
            kappa_score=kappa,
            false_positive_rate=fpr,
            false_negative_rate=fnr,
            avg_review_time_seconds=45.0,  # Mock value
            needs_retraining=needs_retraining
        )
        
        self.calibration_results[reviewer_id] = result
        
        if needs_retraining:
            logger.warning(f"Reviewer {reviewer_id} needs retraining (κ={kappa:.2f})")
        
        return result


class ReviewConsole:
    """Main review console orchestrator"""
    
    def __init__(self):
        """Initialize review console"""
        self.rbac = RBACManager()
        self.dual_control = DualControlManager()
        self.audit_logger = AuditLogger()
        self.calibration = ReviewerCalibration()
        
        # Initialize queues
        self.queues = {
            QueueType.STANDARD: ReviewQueue(QueueType.STANDARD),
            QueueType.HIGH_RISK: ReviewQueue(QueueType.HIGH_RISK),
            QueueType.ESCALATION: ReviewQueue(QueueType.ESCALATION),
            QueueType.QUALITY_CHECK: ReviewQueue(QueueType.QUALITY_CHECK)
        }
        
        logger.info("Review Console initialized with all components")
    
    def create_case(self, customer_id: str, case_type: str, 
                   risk_score: float, evidence: Dict[str, Any],
                   alerts: List[str]) -> ReviewCase:
        """
        Create a new review case
        
        Args:
            customer_id: Customer ID
            case_type: Type of case
            risk_score: Risk score
            evidence: Evidence dictionary
            alerts: List of alert IDs
            
        Returns:
            Created case
        """
        case_id = f"RC-{datetime.now(MANILA_TZ).strftime('%Y%m%d')}-{len(self.queues[QueueType.STANDARD].cases)+1:04d}"
        
        # Determine queue and priority
        if risk_score >= 0.8:
            queue_type = QueueType.HIGH_RISK
            priority = "critical"
            sla_hours = 4
            requires_dual = True
        elif risk_score >= 0.6:
            queue_type = QueueType.STANDARD
            priority = "high"
            sla_hours = 24
            requires_dual = False
        else:
            queue_type = QueueType.STANDARD
            priority = "medium"
            sla_hours = 48
            requires_dual = False
        
        sla_deadline = datetime.now(MANILA_TZ) + timedelta(hours=sla_hours)
        
        case = ReviewCase(
            case_id=case_id,
            customer_id=customer_id,
            case_type=case_type,
            priority=priority,
            status=CaseStatus.PENDING,
            queue_type=queue_type,
            assigned_to=None,
            created_at=datetime.now(MANILA_TZ).isoformat(),
            sla_deadline=sla_deadline.isoformat(),
            evidence=evidence,
            risk_score=risk_score,
            alerts=alerts,
            requires_dual_control=requires_dual,
            review_history=[],
            notes=[]
        )
        
        # Add to appropriate queue
        self.queues[queue_type].add_case(case)
        
        logger.info(f"Case created: {case_id} (queue: {queue_type.value}, priority: {priority})")
        return case
    
    def review_case(self, session_id: str, case_id: str, 
                   decision: ReviewDecision, notes: str,
                   evidence_reviewed: List[str]) -> bool:
        """
        Review a case
        
        Args:
            session_id: Reviewer session
            case_id: Case ID
            decision: Review decision
            notes: Review notes
            evidence_reviewed: List of evidence items reviewed
            
        Returns:
            True if review completed
        """
        # Check permission
        if not self.rbac.check_permission(session_id, "review_standard_cases"):
            logger.error("Permission denied for case review")
            return False
        
        # Get user
        user_id = self.rbac.sessions[session_id]["user_id"]
        
        # Find case
        case = None
        for queue in self.queues.values():
            for c in queue.cases:
                if c.case_id == case_id:
                    case = c
                    break
        
        if not case:
            logger.error(f"Case {case_id} not found")
            return False
        
        # Check if dual control required
        if self.dual_control.requires_dual_control(case):
            # Initiate dual control
            approval_id = self.dual_control.initiate_dual_control(
                case_id, user_id, decision, notes
            )
            logger.info(f"Dual control required for case {case_id}, approval ID: {approval_id}")
            
            # Add to review history
            case.review_history.append({
                "reviewer": user_id,
                "decision": decision.value,
                "notes": notes,
                "timestamp": datetime.now(MANILA_TZ).isoformat(),
                "status": "pending_dual_control",
                "approval_id": approval_id
            })
            
            return False  # Not complete until dual control
        
        # Complete review
        case.resolution = decision
        case.resolved_at = datetime.now(MANILA_TZ).isoformat()
        case.resolved_by = user_id
        case.status = CaseStatus.RESOLVED
        
        # Add to review history
        case.review_history.append({
            "reviewer": user_id,
            "decision": decision.value,
            "notes": notes,
            "timestamp": datetime.now(MANILA_TZ).isoformat(),
            "status": "completed"
        })
        
        # Log action
        action = ReviewAction(
            action_id=hashlib.sha256(
                f"{case_id}_{user_id}_{datetime.now(MANILA_TZ).isoformat()}".encode()
            ).hexdigest()[:16],
            case_id=case_id,
            user_id=user_id,
            action_type="case_review",
            decision=decision,
            notes=notes,
            evidence_reviewed=evidence_reviewed,
            timestamp=datetime.now(MANILA_TZ).isoformat()
        )
        self.audit_logger.log_action(action)
        
        # Add calibration sample
        self.calibration.add_review_sample(user_id, case_id, decision)
        
        logger.info(f"Case {case_id} reviewed by {user_id}: {decision.value}")
        return True
    
    def get_dashboard_metrics(self) -> Dict[str, Any]:
        """Get dashboard metrics"""
        metrics = {
            "timestamp": datetime.now(MANILA_TZ).isoformat(),
            "queues": {},
            "reviewers": {},
            "sla_compliance": {},
            "calibration": {}
        }
        
        # Queue metrics
        for queue_type, queue in self.queues.items():
            metrics["queues"][queue_type.value] = queue.get_queue_metrics()
        
        # Reviewer metrics
        active_reviewers = set()
        for queue in self.queues.values():
            for reviewer_id in queue.assignments.keys():
                active_reviewers.add(reviewer_id)
        
        metrics["reviewers"]["active"] = len(active_reviewers)
        metrics["reviewers"]["total"] = len(self.rbac.users)
        
        # Calibration status
        needs_retraining = []
        for reviewer_id in active_reviewers:
            result = self.calibration.calibrate_reviewer(reviewer_id)
            if result.needs_retraining:
                needs_retraining.append(reviewer_id)
        
        metrics["calibration"]["needs_retraining"] = len(needs_retraining)
        metrics["calibration"]["average_kappa"] = np.mean([
            r.kappa_score for r in self.calibration.calibration_results.values()
        ]) if self.calibration.calibration_results else 0
        
        return metrics


if __name__ == "__main__":
    # Demo and testing
    print("=== Human Review Console Demo ===\n")
    
    # Initialize console
    console = ReviewConsole()
    
    # Create users
    print("Creating users...")
    reviewer1 = console.rbac.create_user("john.doe", Role.REVIEWER_L1)
    reviewer2 = console.rbac.create_user("jane.smith", Role.REVIEWER_L2)
    supervisor = console.rbac.create_user("bob.manager", Role.SUPERVISOR)
    
    # Authenticate users
    session1 = console.rbac.authenticate("john.doe", "password")
    session2 = console.rbac.authenticate("jane.smith", "password")
    
    print(f"  Created 3 users")
    print(f"  Sessions created: {session1 is not None and session2 is not None}")
    
    # Create test cases
    print("\nCreating test cases...")
    
    # Standard risk case
    case1 = console.create_case(
        customer_id="CUST001",
        case_type="kyc_review",
        risk_score=0.4,
        evidence={"document": "passport", "selfie": "verified"},
        alerts=[]
    )
    
    # High risk case (requires dual control)
    case2 = console.create_case(
        customer_id="CUST002",
        case_type="aml_alert",
        risk_score=0.85,
        evidence={"alert_type": "pep_hit", "score": 0.9},
        alerts=["ALERT001"]
    )
    
    print(f"  Case 1: {case1.case_id} (queue: {case1.queue_type.value})")
    print(f"  Case 2: {case2.case_id} (queue: {case2.queue_type.value}, dual control: {case2.requires_dual_control})")
    
    # Review standard case
    print("\nReviewing standard case...")
    success = console.review_case(
        session1, case1.case_id,
        ReviewDecision.APPROVE,
        "All documents verified",
        ["passport", "selfie"]
    )
    print(f"  Review completed: {success}")
    
    # Review high-risk case (will trigger dual control)
    print("\nReviewing high-risk case...")
    success = console.review_case(
        session2, case2.case_id,
        ReviewDecision.REJECT,
        "PEP hit confirmed, high risk",
        ["pep_database", "adverse_media"]
    )
    print(f"  Dual control initiated: {not success}")
    
    # Complete dual control
    if console.dual_control.pending_approvals:
        approval_id = list(console.dual_control.pending_approvals.keys())[0]
        confirmed = console.dual_control.complete_dual_control(
            approval_id, supervisor.user_id, True, "Confirmed rejection"
        )
        print(f"  Dual control completed: {confirmed}")
    
    # Check calibration
    print("\nReviewer Calibration:")
    for reviewer_id in [reviewer1.user_id, reviewer2.user_id]:
        # Add some ground truth samples
        console.calibration.add_review_sample(
            reviewer_id, "TEST001", ReviewDecision.APPROVE, ReviewDecision.APPROVE
        )
        console.calibration.add_review_sample(
            reviewer_id, "TEST002", ReviewDecision.REJECT, ReviewDecision.APPROVE
        )
        
        result = console.calibration.calibrate_reviewer(reviewer_id)
        print(f"  Reviewer {reviewer_id[:8]}... κ={result.kappa_score:.2f}")
    
    # Get dashboard metrics
    print("\nDashboard Metrics:")
    metrics = console.get_dashboard_metrics()
    print(f"  Active Reviewers: {metrics['reviewers']['active']}")
    print(f"  Queue Status:")
    for queue_type, queue_metrics in metrics['queues'].items():
        print(f"    {queue_type}: {queue_metrics['total_cases']} cases, "
              f"SLA: {queue_metrics['sla_compliance']:.1%}")
    
    print("\n✓ Human Review Console operational with RBAC and dual control")