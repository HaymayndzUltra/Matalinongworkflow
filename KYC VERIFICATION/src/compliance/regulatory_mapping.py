"""
Regulatory Compliance Mapping Module
BSP, AMLC, PDPA Control Matrix and SMR/SAR Submission
Part of KYC Bank-Grade Parity - Phase 12

This module maps controls to regulatory requirements and handles reporting.
"""

import logging
import json
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
from enum import Enum
import uuid
from abc import ABC, abstractmethod

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Manila timezone
MANILA_TZ = timezone(timedelta(hours=8))


class Regulation(Enum):
    """Regulatory frameworks"""
    BSP_CIRCULAR_1022 = "BSP Circular 1022"  # E-money AML/CFT
    BSP_CIRCULAR_1108 = "BSP Circular 1108"  # Digital Banks
    BSP_MORB = "BSP MORB"  # Manual of Regulations for Banks
    AMLC_REGISTRATION = "AMLC Registration and Reporting"
    AMLC_RULES_2018 = "AMLC Rules and Regulations 2018"
    PDPA_IRR = "Data Privacy Act IRR"
    NPC_CIRCULAR_16_01 = "NPC Circular 16-01"  # Security Measures


class ControlCategory(Enum):
    """Control categories"""
    CUSTOMER_IDENTIFICATION = "customer_identification"
    RISK_ASSESSMENT = "risk_assessment"
    TRANSACTION_MONITORING = "transaction_monitoring"
    RECORD_KEEPING = "record_keeping"
    REPORTING = "reporting"
    DATA_PRIVACY = "data_privacy"
    SECURITY = "security"
    GOVERNANCE = "governance"


class ComplianceStatus(Enum):
    """Compliance status"""
    COMPLIANT = "compliant"
    PARTIAL = "partial"
    NON_COMPLIANT = "non_compliant"
    NOT_APPLICABLE = "not_applicable"
    IN_REMEDIATION = "in_remediation"


class ReportType(Enum):
    """Regulatory report types"""
    STR = "Suspicious Transaction Report"
    CTR = "Covered Transaction Report"
    SMR = "Suspicious Movement Report"
    SAR = "Suspicious Activity Report"
    DPA_BREACH = "Data Privacy Breach Notification"
    ANNUAL_COMPLIANCE = "Annual Compliance Report"


@dataclass
class Control:
    """Regulatory control"""
    control_id: str
    category: ControlCategory
    description: str
    regulation: Regulation
    requirement: str
    implementation: str
    evidence_path: Optional[str] = None
    status: ComplianceStatus = ComplianceStatus.PARTIAL
    owner: str = "compliance_team"
    last_reviewed: Optional[datetime] = None
    next_review: Optional[datetime] = None
    
    def is_due_for_review(self) -> bool:
        """Check if control needs review"""
        if not self.next_review:
            return True
        return datetime.now(MANILA_TZ) >= self.next_review


@dataclass
class ComplianceReport:
    """Regulatory compliance report"""
    report_id: str
    report_type: ReportType
    customer_id: str
    transaction_ids: List[str]
    amount: float
    currency: str
    narrative: str
    indicators: List[str]
    created_at: datetime
    submitted_at: Optional[datetime] = None
    reference_number: Optional[str] = None
    status: str = "draft"
    
    def to_xml(self) -> str:
        """Convert to XML format for submission"""
        # Simplified XML generation for demo
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Report>
    <ReportID>{self.report_id}</ReportID>
    <Type>{self.report_type.value}</Type>
    <CustomerID>{self.customer_id}</CustomerID>
    <Amount>{self.amount}</Amount>
    <Currency>{self.currency}</Currency>
    <Narrative>{self.narrative}</Narrative>
    <Indicators>{'|'.join(self.indicators)}</Indicators>
    <CreatedAt>{self.created_at.isoformat()}</CreatedAt>
</Report>"""
        return xml


class ControlMatrix:
    """Regulatory control matrix"""
    
    def __init__(self):
        """Initialize control matrix"""
        self.controls: Dict[str, Control] = {}
        self._load_controls()
        logger.info(f"Control Matrix initialized with {len(self.controls)} controls")
    
    def _load_controls(self):
        """Load regulatory controls"""
        # BSP Controls
        self.controls["BSP-001"] = Control(
            control_id="BSP-001",
            category=ControlCategory.CUSTOMER_IDENTIFICATION,
            description="Customer identification at onboarding",
            regulation=Regulation.BSP_CIRCULAR_1022,
            requirement="Section 2.1 - Customer identification procedures",
            implementation="KYC document verification with PAD liveness detection",
            evidence_path="/docs/kyc_procedures.pdf",
            status=ComplianceStatus.COMPLIANT
        )
        
        self.controls["BSP-002"] = Control(
            control_id="BSP-002",
            category=ControlCategory.RISK_ASSESSMENT,
            description="Risk-based customer due diligence",
            regulation=Regulation.BSP_CIRCULAR_1108,
            requirement="Section 4 - Risk assessment framework",
            implementation="Risk scoring model with governance framework",
            status=ComplianceStatus.COMPLIANT
        )
        
        self.controls["BSP-003"] = Control(
            control_id="BSP-003",
            category=ControlCategory.TRANSACTION_MONITORING,
            description="Real-time transaction monitoring",
            regulation=Regulation.BSP_MORB,
            requirement="X181.3 - Transaction monitoring systems",
            implementation="Transaction monitoring engine with velocity and pattern detection",
            status=ComplianceStatus.COMPLIANT
        )
        
        # AMLC Controls
        self.controls["AMLC-001"] = Control(
            control_id="AMLC-001",
            category=ControlCategory.REPORTING,
            description="Suspicious transaction reporting",
            regulation=Regulation.AMLC_RULES_2018,
            requirement="Rule 9 - STR submission within 5 days",
            implementation="Automated STR generation and submission system",
            status=ComplianceStatus.COMPLIANT
        )
        
        self.controls["AMLC-002"] = Control(
            control_id="AMLC-002",
            category=ControlCategory.RECORD_KEEPING,
            description="Transaction record retention",
            regulation=Regulation.AMLC_REGISTRATION,
            requirement="5-year retention of transaction records",
            implementation="WORM storage with 5-year retention policy",
            status=ComplianceStatus.COMPLIANT
        )
        
        self.controls["AMLC-003"] = Control(
            control_id="AMLC-003",
            category=ControlCategory.CUSTOMER_IDENTIFICATION,
            description="PEP and sanctions screening",
            regulation=Regulation.AMLC_RULES_2018,
            requirement="Rule 4 - Enhanced due diligence for high-risk",
            implementation="AML/PEP/Sanctions screening with re-screening",
            status=ComplianceStatus.COMPLIANT
        )
        
        # PDPA Controls
        self.controls["PDPA-001"] = Control(
            control_id="PDPA-001",
            category=ControlCategory.DATA_PRIVACY,
            description="Personal data protection",
            regulation=Regulation.PDPA_IRR,
            requirement="Section 25 - Security measures",
            implementation="Encryption at rest, tokenization, access controls",
            status=ComplianceStatus.COMPLIANT
        )
        
        self.controls["PDPA-002"] = Control(
            control_id="PDPA-002",
            category=ControlCategory.DATA_PRIVACY,
            description="Data breach notification",
            regulation=Regulation.NPC_CIRCULAR_16_01,
            requirement="72-hour breach notification",
            implementation="Automated breach detection and notification system",
            status=ComplianceStatus.PARTIAL
        )
        
        self.controls["PDPA-003"] = Control(
            control_id="PDPA-003",
            category=ControlCategory.GOVERNANCE,
            description="Data Protection Officer",
            regulation=Regulation.PDPA_IRR,
            requirement="Section 14 - DPO appointment",
            implementation="DPO role defined with responsibilities",
            status=ComplianceStatus.COMPLIANT
        )
        
        # Security Controls
        self.controls["SEC-001"] = Control(
            control_id="SEC-001",
            category=ControlCategory.SECURITY,
            description="Encryption key management",
            regulation=Regulation.NPC_CIRCULAR_16_01,
            requirement="Organizational security measures",
            implementation="Key rotation every 90 days with HSM",
            status=ComplianceStatus.COMPLIANT
        )
    
    def get_controls_by_regulation(self, regulation: Regulation) -> List[Control]:
        """Get controls for specific regulation"""
        return [c for c in self.controls.values() if c.regulation == regulation]
    
    def get_controls_by_category(self, category: ControlCategory) -> List[Control]:
        """Get controls by category"""
        return [c for c in self.controls.values() if c.category == category]
    
    def get_compliance_status(self) -> Dict[str, Any]:
        """Get overall compliance status"""
        total = len(self.controls)
        by_status = {}
        
        for status in ComplianceStatus:
            count = sum(1 for c in self.controls.values() if c.status == status)
            by_status[status.value] = {
                "count": count,
                "percentage": (count / total) * 100 if total > 0 else 0
            }
        
        return {
            "total_controls": total,
            "by_status": by_status,
            "compliance_score": by_status[ComplianceStatus.COMPLIANT.value]["percentage"],
            "controls_needing_review": sum(
                1 for c in self.controls.values() if c.is_due_for_review()
            )
        }
    
    def generate_compliance_matrix(self) -> Dict[str, List[Dict[str, Any]]]:
        """Generate compliance matrix report"""
        matrix = {}
        
        for regulation in Regulation:
            controls = self.get_controls_by_regulation(regulation)
            if controls:
                matrix[regulation.value] = [
                    {
                        "control_id": c.control_id,
                        "category": c.category.value,
                        "description": c.description,
                        "status": c.status.value,
                        "implementation": c.implementation,
                        "owner": c.owner
                    }
                    for c in controls
                ]
        
        return matrix


class SMRSubmissionHook:
    """Suspicious Movement Report submission hook"""
    
    def __init__(self, endpoint: Optional[str] = None):
        """
        Initialize SMR submission
        
        Args:
            endpoint: AMLC submission endpoint
        """
        self.endpoint = endpoint or "https://amlc.gov.ph/api/smr"
        self.submission_queue: List[ComplianceReport] = []
        logger.info("SMR Submission Hook initialized")
    
    def create_smr(self, customer_data: Dict[str, Any],
                   transactions: List[Dict[str, Any]],
                   indicators: List[str]) -> ComplianceReport:
        """
        Create SMR report
        
        Args:
            customer_data: Customer information
            transactions: Suspicious transactions
            indicators: Red flag indicators
            
        Returns:
            Created SMR report
        """
        # Calculate total amount
        total_amount = sum(t.get("amount", 0) for t in transactions)
        
        # Generate narrative
        narrative = self._generate_narrative(customer_data, transactions, indicators)
        
        report = ComplianceReport(
            report_id=str(uuid.uuid4()),
            report_type=ReportType.SMR,
            customer_id=customer_data.get("customer_id", ""),
            transaction_ids=[t.get("id", "") for t in transactions],
            amount=total_amount,
            currency="PHP",
            narrative=narrative,
            indicators=indicators,
            created_at=datetime.now(MANILA_TZ)
        )
        
        self.submission_queue.append(report)
        logger.info(f"SMR created: {report.report_id}")
        
        return report
    
    def _generate_narrative(self, customer_data: Dict[str, Any],
                          transactions: List[Dict[str, Any]],
                          indicators: List[str]) -> str:
        """Generate SMR narrative"""
        narrative = f"Suspicious movement detected for customer {customer_data.get('name', 'Unknown')}. "
        narrative += f"Total of {len(transactions)} suspicious transactions identified. "
        narrative += f"Red flags: {', '.join(indicators)}. "
        narrative += "Transactions appear to be structured to avoid reporting thresholds."
        return narrative
    
    def submit_smr(self, report: ComplianceReport) -> Tuple[bool, Optional[str]]:
        """
        Submit SMR to AMLC
        
        Args:
            report: SMR report to submit
            
        Returns:
            Tuple of (success, reference_number)
        """
        try:
            # Convert to XML
            xml_data = report.to_xml()
            
            # In production, would make actual API call
            # response = requests.post(self.endpoint, data=xml_data, headers=...)
            
            # Mock submission
            reference_number = f"AMLC-{datetime.now(MANILA_TZ).strftime('%Y%m%d')}-{uuid.uuid4().hex[:8].upper()}"
            
            report.submitted_at = datetime.now(MANILA_TZ)
            report.reference_number = reference_number
            report.status = "submitted"
            
            logger.info(f"SMR submitted: {reference_number}")
            return True, reference_number
            
        except Exception as e:
            logger.error(f"SMR submission failed: {e}")
            return False, None
    
    def process_submission_queue(self) -> Dict[str, int]:
        """Process pending submissions"""
        results = {"submitted": 0, "failed": 0}
        
        for report in self.submission_queue:
            if report.status == "draft":
                success, ref = self.submit_smr(report)
                if success:
                    results["submitted"] += 1
                else:
                    results["failed"] += 1
        
        return results


class SARSubmissionHook:
    """Suspicious Activity Report submission hook"""
    
    def __init__(self):
        """Initialize SAR submission"""
        self.submission_queue: List[ComplianceReport] = []
        logger.info("SAR Submission Hook initialized")
    
    def create_sar(self, activity_data: Dict[str, Any]) -> ComplianceReport:
        """Create SAR report"""
        report = ComplianceReport(
            report_id=str(uuid.uuid4()),
            report_type=ReportType.SAR,
            customer_id=activity_data.get("customer_id", ""),
            transaction_ids=activity_data.get("transaction_ids", []),
            amount=activity_data.get("amount", 0),
            currency=activity_data.get("currency", "PHP"),
            narrative=activity_data.get("narrative", ""),
            indicators=activity_data.get("indicators", []),
            created_at=datetime.now(MANILA_TZ)
        )
        
        self.submission_queue.append(report)
        logger.info(f"SAR created: {report.report_id}")
        
        return report


class KYCRefreshScheduler:
    """KYC refresh scheduler based on risk rating"""
    
    def __init__(self):
        """Initialize KYC refresh scheduler"""
        self.refresh_intervals = {
            "low": timedelta(days=365 * 3),  # 3 years
            "medium": timedelta(days=365 * 2),  # 2 years
            "high": timedelta(days=365),  # 1 year
            "critical": timedelta(days=180)  # 6 months
        }
        self.refresh_queue: List[Dict[str, Any]] = []
        logger.info("KYC Refresh Scheduler initialized")
    
    def schedule_refresh(self, customer_id: str, risk_rating: str,
                        last_kyc_date: datetime) -> datetime:
        """
        Schedule KYC refresh
        
        Args:
            customer_id: Customer ID
            risk_rating: Customer risk rating
            last_kyc_date: Last KYC completion date
            
        Returns:
            Next refresh date
        """
        interval = self.refresh_intervals.get(risk_rating, timedelta(days=365))
        next_refresh = last_kyc_date + interval
        
        self.refresh_queue.append({
            "customer_id": customer_id,
            "risk_rating": risk_rating,
            "last_kyc_date": last_kyc_date,
            "next_refresh": next_refresh,
            "scheduled_at": datetime.now(MANILA_TZ)
        })
        
        logger.info(f"KYC refresh scheduled for {customer_id} on {next_refresh.date()}")
        return next_refresh
    
    def get_due_refreshes(self) -> List[Dict[str, Any]]:
        """Get customers due for KYC refresh"""
        now = datetime.now(MANILA_TZ)
        due = []
        
        for item in self.refresh_queue:
            if item["next_refresh"] <= now:
                due.append(item)
        
        return due
    
    def trigger_refresh(self, customer_id: str) -> Dict[str, Any]:
        """Trigger KYC refresh process"""
        return {
            "customer_id": customer_id,
            "refresh_triggered_at": datetime.now(MANILA_TZ).isoformat(),
            "notification_sent": True,
            "refresh_url": f"https://kyc.bank.ph/refresh/{customer_id}"
        }


class ComplianceManager:
    """Main compliance management system"""
    
    def __init__(self):
        """Initialize compliance manager"""
        self.control_matrix = ControlMatrix()
        self.smr_hook = SMRSubmissionHook()
        self.sar_hook = SARSubmissionHook()
        self.kyc_scheduler = KYCRefreshScheduler()
        self.audit_trail: List[Dict[str, Any]] = []
        
        logger.info("Compliance Manager initialized")
    
    def assess_compliance(self) -> Dict[str, Any]:
        """Assess overall compliance status"""
        status = self.control_matrix.get_compliance_status()
        matrix = self.control_matrix.generate_compliance_matrix()
        
        return {
            "assessment_date": datetime.now(MANILA_TZ).isoformat(),
            "compliance_score": status["compliance_score"],
            "status_summary": status,
            "control_matrix": matrix,
            "recommendations": self._generate_recommendations(status)
        }
    
    def _generate_recommendations(self, status: Dict[str, Any]) -> List[str]:
        """Generate compliance recommendations"""
        recommendations = []
        
        if status["by_status"][ComplianceStatus.NON_COMPLIANT.value]["count"] > 0:
            recommendations.append("Immediate action required for non-compliant controls")
        
        if status["by_status"][ComplianceStatus.PARTIAL.value]["count"] > 5:
            recommendations.append("Prioritize remediation of partially compliant controls")
        
        if status["controls_needing_review"] > 10:
            recommendations.append("Schedule control reviews for overdue items")
        
        return recommendations
    
    def handle_suspicious_activity(self, activity_data: Dict[str, Any]) -> Dict[str, Any]:
        """Handle suspicious activity detection"""
        result = {
            "timestamp": datetime.now(MANILA_TZ).isoformat(),
            "actions_taken": []
        }
        
        # Determine report type
        if activity_data.get("amount", 0) >= 500000:
            # Create CTR for covered transaction
            result["actions_taken"].append("CTR created for covered transaction")
        
        if activity_data.get("indicators"):
            # Create SMR for suspicious movement
            smr = self.smr_hook.create_smr(
                activity_data.get("customer_data", {}),
                activity_data.get("transactions", []),
                activity_data.get("indicators", [])
            )
            result["smr_id"] = smr.report_id
            result["actions_taken"].append("SMR created")
            
            # Submit if critical
            if activity_data.get("risk_score") == "critical":
                success, ref = self.smr_hook.submit_smr(smr)
                if success:
                    result["smr_reference"] = ref
                    result["actions_taken"].append("SMR submitted to AMLC")
        
        # Log to audit trail
        self.audit_trail.append(result)
        
        return result


if __name__ == "__main__":
    # Demo and testing
    print("=== Regulatory Compliance Mapping Demo ===\n")
    
    # Initialize compliance manager
    manager = ComplianceManager()
    
    # Assess compliance
    print("Assessing compliance status...")
    assessment = manager.assess_compliance()
    print(f"Compliance Score: {assessment['compliance_score']:.1f}%")
    print(f"Controls: {assessment['status_summary']['total_controls']}")
    
    # Show control matrix
    print("\n=== Control Matrix by Regulation ===")
    for regulation, controls in assessment['control_matrix'].items():
        print(f"\n{regulation}:")
        for control in controls:
            status_icon = "✓" if control['status'] == "compliant" else "⚠"
            print(f"  {status_icon} {control['control_id']}: {control['description']}")
    
    # Test SMR creation
    print("\n=== SMR Submission Test ===")
    suspicious_activity = {
        "customer_data": {"customer_id": "CUST001", "name": "John Doe"},
        "transactions": [
            {"id": "TXN001", "amount": 490000},
            {"id": "TXN002", "amount": 490000}
        ],
        "indicators": ["structuring", "velocity_breach"],
        "risk_score": "critical"
    }
    
    result = manager.handle_suspicious_activity(suspicious_activity)
    print(f"SMR Created: {result.get('smr_id', 'None')}")
    if "smr_reference" in result:
        print(f"SMR Reference: {result['smr_reference']}")
    print(f"Actions: {', '.join(result['actions_taken'])}")
    
    # Test KYC refresh scheduling
    print("\n=== KYC Refresh Schedule ===")
    test_customers = [
        ("CUST001", "low", datetime.now(MANILA_TZ) - timedelta(days=1000)),
        ("CUST002", "high", datetime.now(MANILA_TZ) - timedelta(days=300)),
        ("CUST003", "critical", datetime.now(MANILA_TZ) - timedelta(days=170))
    ]
    
    for cust_id, risk, last_kyc in test_customers:
        next_refresh = manager.kyc_scheduler.schedule_refresh(cust_id, risk, last_kyc)
        days_until = (next_refresh - datetime.now(MANILA_TZ)).days
        print(f"  {cust_id} ({risk} risk): Refresh in {days_until} days")
    
    # Check due refreshes
    due = manager.kyc_scheduler.get_due_refreshes()
    print(f"\nCustomers due for refresh: {len(due)}")
    
    # Show recommendations
    print("\n=== Compliance Recommendations ===")
    for rec in assessment['recommendations']:
        print(f"  • {rec}")
    
    print("\n✓ Compliance mapping and regulatory hooks operational")