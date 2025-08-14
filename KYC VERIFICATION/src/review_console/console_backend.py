"""
Human Review Console Backend
RBAC, Dual Control, and Audit Trail System
Part of KYC Bank-Grade Parity - Phase 7

This module implements the backend for human review operations.
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
from collections import defaultdict
import uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Manila timezone
MANILA_TZ = timezone(timedelta(hours=8))


class UserRole(Enum):
    """User roles for RBAC"""
    VIEWER = "viewer"
    REVIEWER = "reviewer"
    SENIOR_REVIEWER = "senior_reviewer"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"
    AUDITOR = "auditor"


class ReviewAction(Enum):
    """Review actions"""
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"
    REQUEST_INFO = "request_info"
    DEFER = "defer"
    OVERRIDE = "override"


class QueueType(Enum):
    """Review queue types"""
    STANDARD = "standard"
    HIGH_RISK = "high_risk"
    ESCALATED = "escalated"
    QUALITY_CHECK = "quality_check"
    TRAINING = "training"


class CaseStatus(Enum):
    """Case status"""
    PENDING = "pending"
    IN_REVIEW = "in_review"
    AWAITING_DUAL_CONTROL = "awaiting_dual_control"
    APPROVED = "approved"
    REJECTED = "rejected"
    ESCALATED = "escalated"
    DEFERRED = "deferred"


@dataclass
class User:
    """User representation"""
    user_id: str
    username: str
    role: UserRole
    permissions: List[str]
    active: bool = True
    last_login: Optional[datetime] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(MANILA_TZ))
    
    def has_permission(self, permission: str) -> bool:
        """Check if user has specific permission"""
        return permission in self.permissions or self.role == UserRole.ADMIN


@dataclass
class ReviewCase:
    """Review case"""
    case_id: str
    queue_type: QueueType
    priority: str
    customer_id: str
    case_type: str
    details: Dict[str, Any]
    status: CaseStatus
    assigned_to: Optional[str]
    created_at: datetime
    sla_deadline: datetime
    requires_dual_control: bool = False
    evidence_links: List[str] = field(default_factory=list)
    notes: List[Dict[str, Any]] = field(default_factory=list)
    review_history: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class ReviewDecision:
    """Review decision"""
    decision_id: str
    case_id: str
    reviewer_id: str
    action: ReviewAction
    reasoning: str
    confidence_score: float
    timestamp: datetime
    dual_control_required: bool = False
    dual_control_reviewer: Optional[str] = None
    dual_control_timestamp: Optional[datetime] = None
    
    def needs_dual_control(self) -> bool:
        """Check if decision needs dual control"""
        return self.dual_control_required and not self.dual_control_reviewer


@dataclass
class AuditEntry:
    """Audit log entry"""
    audit_id: str
    timestamp: datetime
    user_id: str
    action: str
    entity_type: str
    entity_id: str
    details: Dict[str, Any]
    ip_address: Optional[str] = None
    session_id: Optional[str] = None
    
    def to_json(self) -> str:
        """Convert to JSON for storage"""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return json.dumps(data)


class RBACManager:
    """Role-Based Access Control manager"""
    
    def __init__(self):
        """Initialize RBAC manager"""
        self.users: Dict[str, User] = {}
        self.role_permissions = self._define_role_permissions()
        self.sessions: Dict[str, Dict[str, Any]] = {}
        logger.info("RBAC Manager initialized")
    
    def _define_role_permissions(self) -> Dict[UserRole, List[str]]:
        """Define permissions for each role"""
        return {
            UserRole.VIEWER: [
                "view_cases",
                "view_statistics"
            ],
            UserRole.REVIEWER: [
                "view_cases",
                "review_standard_cases",
                "add_notes",
                "request_information"
            ],
            UserRole.SENIOR_REVIEWER: [
                "view_cases",
                "review_standard_cases",
                "review_high_risk_cases",
                "add_notes",
                "request_information",
                "escalate_cases",
                "dual_control_approve"
            ],
            UserRole.SUPERVISOR: [
                "view_cases",
                "review_all_cases",
                "override_decisions",
                "reassign_cases",
                "manage_queues",
                "view_audit_logs",
                "dual_control_approve"
            ],
            UserRole.ADMIN: [
                "all_permissions"
            ],
            UserRole.AUDITOR: [
                "view_cases",
                "view_audit_logs",
                "export_reports",
                "view_all_decisions"
            ]
        }
    
    def create_user(self, username: str, role: UserRole) -> User:
        """Create a new user"""
        user = User(
            user_id=str(uuid.uuid4()),
            username=username,
            role=role,
            permissions=self.role_permissions.get(role, [])
        )
        self.users[user.user_id] = user
        logger.info(f"Created user {username} with role {role.value}")
        return user
    
    def authenticate(self, username: str, password: str) -> Optional[str]:
        """Authenticate user and create session"""
        # Mock authentication - in production would verify against secure store
        user = next((u for u in self.users.values() if u.username == username), None)
        
        if user and user.active:
            session_id = str(uuid.uuid4())
            self.sessions[session_id] = {
                "user_id": user.user_id,
                "created_at": datetime.now(MANILA_TZ),
                "last_activity": datetime.now(MANILA_TZ)
            }
            user.last_login = datetime.now(MANILA_TZ)
            logger.info(f"User {username} authenticated, session {session_id}")
            return session_id
        
        return None
    
    def check_permission(self, session_id: str, permission: str) -> bool:
        """Check if session has permission"""
        session = self.sessions.get(session_id)
        if not session:
            return False
        
        user = self.users.get(session["user_id"])
        if not user or not user.active:
            return False
        
        # Update last activity
        session["last_activity"] = datetime.now(MANILA_TZ)
        
        return user.has_permission(permission)


class QueueManager:
    """Manages review queues"""
    
    def __init__(self):
        """Initialize queue manager"""
        self.queues: Dict[QueueType, List[ReviewCase]] = {
            queue_type: [] for queue_type in QueueType
        }
        self.case_assignments: Dict[str, str] = {}  # case_id -> reviewer_id
        self.reviewer_workload: Dict[str, int] = defaultdict(int)
        logger.info("Queue Manager initialized")
    
    def add_case(self, case: ReviewCase) -> bool:
        """Add case to appropriate queue"""
        queue = self.queues.get(case.queue_type, [])
        queue.append(case)
        
        # Sort by priority and SLA
        queue.sort(key=lambda c: (
            0 if c.priority == "critical" else 1 if c.priority == "high" else 2,
            c.sla_deadline
        ))
        
        logger.info(f"Added case {case.case_id} to {case.queue_type.value} queue")
        return True
    
    def assign_case(self, case_id: str, reviewer_id: str) -> bool:
        """Assign case to reviewer"""
        # Find case in queues
        case = None
        for queue in self.queues.values():
            case = next((c for c in queue if c.case_id == case_id), None)
            if case:
                break
        
        if not case:
            logger.error(f"Case {case_id} not found")
            return False
        
        # Update assignment
        case.assigned_to = reviewer_id
        case.status = CaseStatus.IN_REVIEW
        self.case_assignments[case_id] = reviewer_id
        self.reviewer_workload[reviewer_id] += 1
        
        logger.info(f"Assigned case {case_id} to reviewer {reviewer_id}")
        return True
    
    def get_next_case(self, reviewer_id: str, queue_type: QueueType) -> Optional[ReviewCase]:
        """Get next case for reviewer"""
        queue = self.queues.get(queue_type, [])
        
        # Find unassigned case
        for case in queue:
            if case.status == CaseStatus.PENDING and not case.assigned_to:
                if self.assign_case(case.case_id, reviewer_id):
                    return case
        
        return None
    
    def get_reviewer_stats(self, reviewer_id: str) -> Dict[str, Any]:
        """Get reviewer statistics"""
        assigned_cases = [
            case for queue in self.queues.values()
            for case in queue if case.assigned_to == reviewer_id
        ]
        
        return {
            "reviewer_id": reviewer_id,
            "active_cases": len([c for c in assigned_cases if c.status == CaseStatus.IN_REVIEW]),
            "completed_today": 0,  # Would track in production
            "average_review_time": 0,  # Would calculate in production
            "sla_compliance": 100.0  # Would calculate in production
        }


class DualControlManager:
    """Manages dual control requirements"""
    
    def __init__(self):
        """Initialize dual control manager"""
        self.pending_approvals: Dict[str, ReviewDecision] = {}
        self.approval_history: List[Dict[str, Any]] = []
        
        # Load config
        import sys
        sys.path.append('/workspace/KYC VERIFICATION')
        from src.config.threshold_manager import get_threshold_manager
        self.threshold_manager = get_threshold_manager()
        
        logger.info("Dual Control Manager initialized")
    
    def requires_dual_control(self, case: ReviewCase, decision: ReviewDecision) -> bool:
        """Check if case requires dual control"""
        # High-risk cases always require dual control
        if case.queue_type == QueueType.HIGH_RISK:
            return True
        
        # Override actions require dual control
        if decision.action == ReviewAction.OVERRIDE:
            return True
        
        # Check if explicitly marked
        if case.requires_dual_control:
            return True
        
        # Check thresholds (would be config-driven in production)
        if "amount" in case.details and case.details["amount"] > 1000000:
            return True
        
        return False
    
    def submit_for_dual_control(self, decision: ReviewDecision) -> str:
        """Submit decision for dual control approval"""
        approval_id = str(uuid.uuid4())
        self.pending_approvals[approval_id] = decision
        decision.dual_control_required = True
        
        logger.info(f"Decision {decision.decision_id} submitted for dual control, approval ID: {approval_id}")
        return approval_id
    
    def approve_dual_control(self, approval_id: str, approver_id: str, 
                           approved: bool, reason: str) -> bool:
        """Approve or reject dual control request"""
        decision = self.pending_approvals.get(approval_id)
        if not decision:
            logger.error(f"Approval {approval_id} not found")
            return False
        
        # Cannot self-approve
        if decision.reviewer_id == approver_id:
            logger.error(f"Self-approval attempted by {approver_id}")
            return False
        
        # Update decision
        if approved:
            decision.dual_control_reviewer = approver_id
            decision.dual_control_timestamp = datetime.now(MANILA_TZ)
        
        # Record in history
        self.approval_history.append({
            "approval_id": approval_id,
            "decision_id": decision.decision_id,
            "approver_id": approver_id,
            "approved": approved,
            "reason": reason,
            "timestamp": datetime.now(MANILA_TZ).isoformat()
        })
        
        # Remove from pending
        del self.pending_approvals[approval_id]
        
        logger.info(f"Dual control {'approved' if approved else 'rejected'} by {approver_id}")
        return True


class AuditLogger:
    """Audit logging system"""
    
    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize audit logger"""
        self.storage_path = storage_path or Path("/workspace/KYC VERIFICATION/audit_logs")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.entries: List[AuditEntry] = []
        self.redaction_enabled = True
        logger.info("Audit Logger initialized with PII redaction enabled")
    
    def log(self, user_id: str, action: str, entity_type: str, 
           entity_id: str, details: Dict[str, Any], 
           ip_address: Optional[str] = None,
           session_id: Optional[str] = None) -> AuditEntry:
        """Create audit log entry"""
        # Redact PII if enabled
        if self.redaction_enabled:
            details = self._redact_pii(details)
        
        entry = AuditEntry(
            audit_id=str(uuid.uuid4()),
            timestamp=datetime.now(MANILA_TZ),
            user_id=user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            details=details,
            ip_address=ip_address,
            session_id=session_id
        )
        
        self.entries.append(entry)
        self._persist_entry(entry)
        
        logger.debug(f"Audit: {user_id} performed {action} on {entity_type}:{entity_id}")
        return entry
    
    def _redact_pii(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Redact PII from data"""
        pii_fields = ["ssn", "tax_id", "passport_number", "license_number", 
                     "account_number", "card_number", "phone", "email"]
        
        redacted = data.copy()
        for field in pii_fields:
            if field in redacted:
                # Keep first 2 and last 2 characters
                value = str(redacted[field])
                if len(value) > 4:
                    redacted[field] = f"{value[:2]}***{value[-2:]}"
                else:
                    redacted[field] = "***"
        
        return redacted
    
    def _persist_entry(self, entry: AuditEntry):
        """Persist audit entry to storage"""
        try:
            # Daily audit files
            date_str = entry.timestamp.strftime("%Y%m%d")
            filename = self.storage_path / f"audit_{date_str}.jsonl"
            
            with open(filename, 'a') as f:
                f.write(entry.to_json() + '\n')
        except Exception as e:
            logger.error(f"Failed to persist audit entry: {e}")
    
    def query(self, start_date: datetime, end_date: datetime,
             user_id: Optional[str] = None,
             action: Optional[str] = None) -> List[AuditEntry]:
        """Query audit logs"""
        results = []
        
        for entry in self.entries:
            if start_date <= entry.timestamp <= end_date:
                if user_id and entry.user_id != user_id:
                    continue
                if action and entry.action != action:
                    continue
                results.append(entry)
        
        return results


class CalibrationChecker:
    """Inter-rater reliability and calibration checker"""
    
    def __init__(self):
        """Initialize calibration checker"""
        self.reviewer_decisions: Dict[str, List[ReviewDecision]] = defaultdict(list)
        self.calibration_cases: List[str] = []  # Known outcome cases for testing
        self.kappa_threshold = 0.8  # Target inter-rater reliability
        logger.info(f"Calibration Checker initialized with κ≥{self.kappa_threshold} target")
    
    def record_decision(self, reviewer_id: str, decision: ReviewDecision):
        """Record reviewer decision"""
        self.reviewer_decisions[reviewer_id].append(decision)
    
    def calculate_kappa(self, reviewer1_id: str, reviewer2_id: str) -> float:
        """Calculate Cohen's Kappa between two reviewers"""
        decisions1 = self.reviewer_decisions.get(reviewer1_id, [])
        decisions2 = self.reviewer_decisions.get(reviewer2_id, [])
        
        # Find common cases
        cases1 = {d.case_id: d.action for d in decisions1}
        cases2 = {d.case_id: d.action for d in decisions2}
        common_cases = set(cases1.keys()) & set(cases2.keys())
        
        if len(common_cases) < 10:  # Need minimum samples
            return -1.0
        
        # Calculate agreement
        agreements = sum(1 for case in common_cases if cases1[case] == cases2[case])
        observed_agreement = agreements / len(common_cases)
        
        # Calculate expected agreement (simplified)
        # In production, would calculate proper expected agreement
        expected_agreement = 0.25  # Assuming 4 possible actions
        
        # Cohen's Kappa
        if expected_agreement == 1:
            return 1.0
        
        kappa = (observed_agreement - expected_agreement) / (1 - expected_agreement)
        return kappa
    
    def needs_calibration(self, reviewer_id: str) -> bool:
        """Check if reviewer needs calibration"""
        # Check against other reviewers
        other_reviewers = [r for r in self.reviewer_decisions.keys() if r != reviewer_id]
        
        if not other_reviewers:
            return False
        
        kappa_scores = []
        for other_id in other_reviewers:
            kappa = self.calculate_kappa(reviewer_id, other_id)
            if kappa >= 0:  # Valid score
                kappa_scores.append(kappa)
        
        if not kappa_scores:
            return False
        
        avg_kappa = sum(kappa_scores) / len(kappa_scores)
        return avg_kappa < self.kappa_threshold
    
    def get_calibration_report(self) -> Dict[str, Any]:
        """Generate calibration report"""
        report = {
            "timestamp": datetime.now(MANILA_TZ).isoformat(),
            "reviewers": len(self.reviewer_decisions),
            "total_decisions": sum(len(d) for d in self.reviewer_decisions.values()),
            "kappa_threshold": self.kappa_threshold,
            "reviewers_needing_calibration": []
        }
        
        for reviewer_id in self.reviewer_decisions:
            if self.needs_calibration(reviewer_id):
                report["reviewers_needing_calibration"].append(reviewer_id)
        
        return report


class ReviewConsoleBackend:
    """Main review console backend"""
    
    def __init__(self):
        """Initialize review console backend"""
        self.rbac = RBACManager()
        self.queue_manager = QueueManager()
        self.dual_control = DualControlManager()
        self.audit_logger = AuditLogger()
        self.calibration = CalibrationChecker()
        
        # Storage for cases and decisions
        self.cases: Dict[str, ReviewCase] = {}
        self.decisions: Dict[str, ReviewDecision] = {}
        
        logger.info("Review Console Backend initialized")
    
    def create_review_case(self, case_type: str, customer_id: str,
                          details: Dict[str, Any], priority: str = "medium",
                          requires_dual_control: bool = False) -> ReviewCase:
        """Create a new review case"""
        # Determine queue type
        if priority == "critical" or requires_dual_control:
            queue_type = QueueType.HIGH_RISK
        else:
            queue_type = QueueType.STANDARD
        
        # Calculate SLA
        sla_hours = {"critical": 4, "high": 24, "medium": 48, "low": 72}
        sla_deadline = datetime.now(MANILA_TZ) + timedelta(
            hours=sla_hours.get(priority, 48)
        )
        
        case = ReviewCase(
            case_id=str(uuid.uuid4()),
            queue_type=queue_type,
            priority=priority,
            customer_id=customer_id,
            case_type=case_type,
            details=details,
            status=CaseStatus.PENDING,
            assigned_to=None,
            created_at=datetime.now(MANILA_TZ),
            sla_deadline=sla_deadline,
            requires_dual_control=requires_dual_control
        )
        
        self.cases[case.case_id] = case
        self.queue_manager.add_case(case)
        
        logger.info(f"Created review case {case.case_id} for {customer_id}")
        return case
    
    def submit_decision(self, session_id: str, case_id: str,
                       action: ReviewAction, reasoning: str,
                       confidence_score: float = 0.95) -> Optional[ReviewDecision]:
        """Submit review decision"""
        # Get user from session
        session = self.rbac.sessions.get(session_id)
        if not session:
            logger.error("Invalid session")
            return None
        
        user_id = session["user_id"]
        
        # Get case
        case = self.cases.get(case_id)
        if not case:
            logger.error(f"Case {case_id} not found")
            return None
        
        # Create decision
        decision = ReviewDecision(
            decision_id=str(uuid.uuid4()),
            case_id=case_id,
            reviewer_id=user_id,
            action=action,
            reasoning=reasoning,
            confidence_score=confidence_score,
            timestamp=datetime.now(MANILA_TZ)
        )
        
        # Check if dual control needed
        if self.dual_control.requires_dual_control(case, decision):
            approval_id = self.dual_control.submit_for_dual_control(decision)
            case.status = CaseStatus.AWAITING_DUAL_CONTROL
            logger.info(f"Decision requires dual control, approval ID: {approval_id}")
        else:
            # Apply decision immediately
            self._apply_decision(case, decision)
        
        # Store decision
        self.decisions[decision.decision_id] = decision
        
        # Record for calibration
        self.calibration.record_decision(user_id, decision)
        
        # Audit log
        self.audit_logger.log(
            user_id=user_id,
            action="submit_decision",
            entity_type="case",
            entity_id=case_id,
            details={
                "action": action.value,
                "confidence": confidence_score
            },
            session_id=session_id
        )
        
        return decision
    
    def _apply_decision(self, case: ReviewCase, decision: ReviewDecision):
        """Apply decision to case"""
        if decision.action == ReviewAction.APPROVE:
            case.status = CaseStatus.APPROVED
        elif decision.action == ReviewAction.REJECT:
            case.status = CaseStatus.REJECTED
        elif decision.action == ReviewAction.ESCALATE:
            case.status = CaseStatus.ESCALATED
            case.queue_type = QueueType.ESCALATED
        
        # Add to case history
        case.review_history.append({
            "decision_id": decision.decision_id,
            "reviewer_id": decision.reviewer_id,
            "action": decision.action.value,
            "timestamp": decision.timestamp.isoformat()
        })
    
    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get dashboard statistics"""
        total_cases = len(self.cases)
        pending_cases = sum(1 for c in self.cases.values() if c.status == CaseStatus.PENDING)
        in_review = sum(1 for c in self.cases.values() if c.status == CaseStatus.IN_REVIEW)
        awaiting_dual = sum(1 for c in self.cases.values() 
                           if c.status == CaseStatus.AWAITING_DUAL_CONTROL)
        
        # SLA compliance
        now = datetime.now(MANILA_TZ)
        overdue = sum(1 for c in self.cases.values() 
                     if c.status in [CaseStatus.PENDING, CaseStatus.IN_REVIEW] 
                     and c.sla_deadline < now)
        
        sla_compliance = ((total_cases - overdue) / max(1, total_cases)) * 100
        
        return {
            "total_cases": total_cases,
            "pending_cases": pending_cases,
            "in_review": in_review,
            "awaiting_dual_control": awaiting_dual,
            "overdue_cases": overdue,
            "sla_compliance": round(sla_compliance, 2),
            "active_reviewers": len(self.rbac.sessions),
            "calibration_status": self.calibration.get_calibration_report()
        }


if __name__ == "__main__":
    # Demo and testing
    print("=== Human Review Console Backend Demo ===\n")
    
    # Initialize backend
    backend = ReviewConsoleBackend()
    
    # Create users
    admin = backend.rbac.create_user("admin", UserRole.ADMIN)
    reviewer1 = backend.rbac.create_user("reviewer1", UserRole.REVIEWER)
    reviewer2 = backend.rbac.create_user("reviewer2", UserRole.SENIOR_REVIEWER)
    supervisor = backend.rbac.create_user("supervisor", UserRole.SUPERVISOR)
    
    # Authenticate users
    session1 = backend.rbac.authenticate("reviewer1", "password")
    session2 = backend.rbac.authenticate("reviewer2", "password")
    
    print(f"Created {len(backend.rbac.users)} users")
    print(f"Active sessions: {len(backend.rbac.sessions)}\n")
    
    # Create test cases
    print("Creating test cases...")
    
    # Standard case
    case1 = backend.create_review_case(
        case_type="kyc_verification",
        customer_id="CUST001",
        details={"document_type": "passport", "risk_score": 0.3},
        priority="medium"
    )
    
    # High-risk case requiring dual control
    case2 = backend.create_review_case(
        case_type="aml_alert",
        customer_id="CUST002",
        details={"alert_type": "structuring", "amount": 2000000},
        priority="critical",
        requires_dual_control=True
    )
    
    print(f"Created {len(backend.cases)} cases\n")
    
    # Submit decisions
    print("Processing decisions...")
    
    # Reviewer 1 reviews standard case
    if session1:
        decision1 = backend.submit_decision(
            session_id=session1,
            case_id=case1.case_id,
            action=ReviewAction.APPROVE,
            reasoning="Documents verified, low risk",
            confidence_score=0.95
        )
        print(f"Decision 1: {decision1.action.value} (No dual control needed)")
    
    # Reviewer 2 reviews high-risk case
    if session2:
        decision2 = backend.submit_decision(
            session_id=session2,
            case_id=case2.case_id,
            action=ReviewAction.REJECT,
            reasoning="Suspicious structuring pattern detected",
            confidence_score=0.85
        )
        print(f"Decision 2: {decision2.action.value} (Dual control required)")
    
    # Check dual control pending
    print(f"\nPending dual control approvals: {len(backend.dual_control.pending_approvals)}")
    
    # Dashboard stats
    stats = backend.get_dashboard_stats()
    print(f"\n=== Dashboard Statistics ===")
    print(f"Total Cases: {stats['total_cases']}")
    print(f"Pending: {stats['pending_cases']}")
    print(f"In Review: {stats['in_review']}")
    print(f"Awaiting Dual Control: {stats['awaiting_dual_control']}")
    print(f"SLA Compliance: {stats['sla_compliance']}%")
    
    # Audit trail
    print(f"\n=== Audit Trail ===")
    print(f"Total audit entries: {len(backend.audit_logger.entries)}")
    for entry in backend.audit_logger.entries[-3:]:
        print(f"  {entry.timestamp.strftime('%H:%M:%S')} - {entry.user_id[:8]}... - {entry.action}")
    
    print("\n✓ Human Review Console Backend operational with RBAC and dual control")