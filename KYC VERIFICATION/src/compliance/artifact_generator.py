"""
Compliance Artifact Generator
Generates DPIA, ROPA, and retention matrix documents
"""

import json
import csv
import os
import re
import ast
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DataCategory(str, Enum):
    """Categories of personal data"""
    IDENTITY = "Identity Data"
    CONTACT = "Contact Data"
    BIOMETRIC = "Biometric Data"
    FINANCIAL = "Financial Data"
    GOVERNMENT = "Government ID Data"
    DEVICE = "Device/Technical Data"
    LOCATION = "Location Data"
    BEHAVIORAL = "Behavioral Data"
    SENSITIVE = "Sensitive Personal Data"


class ProcessingPurpose(str, Enum):
    """Purposes for data processing"""
    IDENTITY_VERIFICATION = "Identity Verification"
    FRAUD_PREVENTION = "Fraud Prevention"
    REGULATORY_COMPLIANCE = "Regulatory Compliance"
    RISK_ASSESSMENT = "Risk Assessment"
    AUDIT_LOGGING = "Audit and Logging"
    SERVICE_IMPROVEMENT = "Service Improvement"
    LEGAL_OBLIGATION = "Legal Obligation"


class LawfulBasis(str, Enum):
    """Lawful basis for processing under GDPR"""
    CONSENT = "Consent"
    CONTRACT = "Contract Performance"
    LEGAL_OBLIGATION = "Legal Obligation"
    VITAL_INTERESTS = "Vital Interests"
    PUBLIC_TASK = "Public Task"
    LEGITIMATE_INTERESTS = "Legitimate Interests"


@dataclass
class DataField:
    """Represents a data field in the system"""
    name: str
    category: DataCategory
    description: str
    is_pii: bool
    is_sensitive: bool
    source: str
    processing_activities: List[str]
    retention_period_days: int
    encryption_required: bool


@dataclass
class ProcessingActivity:
    """Represents a data processing activity"""
    name: str
    description: str
    purpose: ProcessingPurpose
    lawful_basis: LawfulBasis
    data_categories: List[DataCategory]
    data_subjects: List[str]
    recipients: List[str]
    international_transfers: bool
    transfer_countries: List[str]
    retention_period: str
    security_measures: List[str]


@dataclass
class PrivacyRisk:
    """Represents a privacy risk"""
    risk_id: str
    description: str
    likelihood: str  # Low, Medium, High
    impact: str  # Low, Medium, High
    risk_score: int  # 1-9
    mitigation_measures: List[str]
    residual_risk: str  # Low, Medium, High


class ComplianceArtifactGenerator:
    """Generates compliance artifacts from system analysis"""
    
    def __init__(self, project_path: str = "."):
        """Initialize the generator"""
        self.project_path = Path(project_path)
        self.artifacts_path = self.project_path / "artifacts"
        self.artifacts_path.mkdir(parents=True, exist_ok=True)
        
        # Data inventory
        self.data_fields: List[DataField] = []
        self.processing_activities: List[ProcessingActivity] = []
        self.privacy_risks: List[PrivacyRisk] = []
        
        # Initialize with known data
        self._initialize_data_inventory()
        self._initialize_processing_activities()
        self._initialize_privacy_risks()
    
    def _initialize_data_inventory(self):
        """Initialize known data fields from the KYC system"""
        self.data_fields = [
            # Identity Data
            DataField(
                name="full_name",
                category=DataCategory.IDENTITY,
                description="Full legal name of the individual",
                is_pii=True,
                is_sensitive=False,
                source="Document OCR, User Input",
                processing_activities=["extraction", "verification", "matching"],
                retention_period_days=2555,  # 7 years
                encryption_required=True
            ),
            DataField(
                name="birth_date",
                category=DataCategory.IDENTITY,
                description="Date of birth",
                is_pii=True,
                is_sensitive=False,
                source="Document OCR, MRZ",
                processing_activities=["extraction", "verification", "age_check"],
                retention_period_days=2555,
                encryption_required=True
            ),
            DataField(
                name="nationality",
                category=DataCategory.IDENTITY,
                description="Nationality/Citizenship",
                is_pii=True,
                is_sensitive=False,
                source="Document OCR, MRZ",
                processing_activities=["extraction", "verification"],
                retention_period_days=2555,
                encryption_required=False
            ),
            
            # Government ID Data
            DataField(
                name="id_number",
                category=DataCategory.GOVERNMENT,
                description="Government-issued ID number",
                is_pii=True,
                is_sensitive=True,
                source="Document OCR, MRZ, Barcode",
                processing_activities=["extraction", "verification", "issuer_check"],
                retention_period_days=2555,
                encryption_required=True
            ),
            DataField(
                name="passport_number",
                category=DataCategory.GOVERNMENT,
                description="Passport number",
                is_pii=True,
                is_sensitive=True,
                source="MRZ, NFC",
                processing_activities=["extraction", "verification"],
                retention_period_days=2555,
                encryption_required=True
            ),
            
            # Biometric Data
            DataField(
                name="face_image",
                category=DataCategory.BIOMETRIC,
                description="Facial image for biometric verification",
                is_pii=True,
                is_sensitive=True,
                source="Document Image, Selfie",
                processing_activities=["extraction", "face_matching", "liveness"],
                retention_period_days=90,  # Shorter retention for biometric
                encryption_required=True
            ),
            DataField(
                name="face_encoding",
                category=DataCategory.BIOMETRIC,
                description="Mathematical representation of facial features",
                is_pii=True,
                is_sensitive=True,
                source="Face Detection Algorithm",
                processing_activities=["face_matching", "deduplication"],
                retention_period_days=90,
                encryption_required=True
            ),
            
            # Contact Data
            DataField(
                name="email",
                category=DataCategory.CONTACT,
                description="Email address",
                is_pii=True,
                is_sensitive=False,
                source="User Input",
                processing_activities=["communication", "verification"],
                retention_period_days=2555,
                encryption_required=False
            ),
            DataField(
                name="phone_number",
                category=DataCategory.CONTACT,
                description="Phone number",
                is_pii=True,
                is_sensitive=False,
                source="User Input",
                processing_activities=["communication", "verification", "2fa"],
                retention_period_days=2555,
                encryption_required=False
            ),
            DataField(
                name="address",
                category=DataCategory.CONTACT,
                description="Physical address",
                is_pii=True,
                is_sensitive=False,
                source="Document OCR, User Input",
                processing_activities=["extraction", "verification", "geo_check"],
                retention_period_days=2555,
                encryption_required=True
            ),
            
            # Device/Technical Data
            DataField(
                name="ip_address",
                category=DataCategory.DEVICE,
                description="IP address of the device",
                is_pii=True,
                is_sensitive=False,
                source="Network Connection",
                processing_activities=["fraud_detection", "geo_location", "logging"],
                retention_period_days=180,
                encryption_required=False
            ),
            DataField(
                name="device_id",
                category=DataCategory.DEVICE,
                description="Unique device identifier",
                is_pii=True,
                is_sensitive=False,
                source="Device Fingerprinting",
                processing_activities=["fraud_detection", "device_tracking"],
                retention_period_days=365,
                encryption_required=False
            ),
            DataField(
                name="user_agent",
                category=DataCategory.DEVICE,
                description="Browser/app user agent string",
                is_pii=False,
                is_sensitive=False,
                source="HTTP Headers",
                processing_activities=["compatibility_check", "analytics"],
                retention_period_days=90,
                encryption_required=False
            ),
            
            # Location Data
            DataField(
                name="gps_coordinates",
                category=DataCategory.LOCATION,
                description="GPS coordinates",
                is_pii=True,
                is_sensitive=False,
                source="Device GPS, IP Geolocation",
                processing_activities=["geo_verification", "fraud_detection"],
                retention_period_days=30,
                encryption_required=True
            ),
            
            # Behavioral Data
            DataField(
                name="risk_score",
                category=DataCategory.BEHAVIORAL,
                description="Calculated risk score",
                is_pii=False,
                is_sensitive=False,
                source="Risk Engine",
                processing_activities=["risk_assessment", "decision_making"],
                retention_period_days=2555,
                encryption_required=False
            ),
            DataField(
                name="verification_attempts",
                category=DataCategory.BEHAVIORAL,
                description="Number and pattern of verification attempts",
                is_pii=False,
                is_sensitive=False,
                source="System Logs",
                processing_activities=["fraud_detection", "rate_limiting"],
                retention_period_days=365,
                encryption_required=False
            )
        ]
    
    def _initialize_processing_activities(self):
        """Initialize processing activities"""
        self.processing_activities = [
            ProcessingActivity(
                name="Document Capture and Quality Check",
                description="Capture and assess quality of identity documents",
                purpose=ProcessingPurpose.IDENTITY_VERIFICATION,
                lawful_basis=LawfulBasis.CONTRACT,
                data_categories=[DataCategory.IDENTITY, DataCategory.GOVERNMENT],
                data_subjects=["Customers", "Applicants"],
                recipients=["Internal Systems"],
                international_transfers=False,
                transfer_countries=[],
                retention_period="7 years from last activity",
                security_measures=["Encryption at rest", "Encryption in transit", "Access controls"]
            ),
            ProcessingActivity(
                name="OCR Data Extraction",
                description="Extract text data from identity documents using OCR",
                purpose=ProcessingPurpose.IDENTITY_VERIFICATION,
                lawful_basis=LawfulBasis.CONTRACT,
                data_categories=[DataCategory.IDENTITY, DataCategory.GOVERNMENT, DataCategory.CONTACT],
                data_subjects=["Customers"],
                recipients=["OCR Service Provider", "Internal Systems"],
                international_transfers=False,
                transfer_countries=[],
                retention_period="7 years",
                security_measures=["Data minimization", "Encryption", "Secure APIs"]
            ),
            ProcessingActivity(
                name="Biometric Face Matching",
                description="Compare face from document with selfie",
                purpose=ProcessingPurpose.FRAUD_PREVENTION,
                lawful_basis=LawfulBasis.LEGITIMATE_INTERESTS,
                data_categories=[DataCategory.BIOMETRIC],
                data_subjects=["Customers"],
                recipients=["Biometric Service Provider"],
                international_transfers=False,
                transfer_countries=[],
                retention_period="90 days after verification",
                security_measures=["Biometric template protection", "Secure deletion", "Access restrictions"]
            ),
            ProcessingActivity(
                name="AML Sanctions Screening",
                description="Screen against sanctions and PEP lists",
                purpose=ProcessingPurpose.REGULATORY_COMPLIANCE,
                lawful_basis=LawfulBasis.LEGAL_OBLIGATION,
                data_categories=[DataCategory.IDENTITY],
                data_subjects=["Customers", "Beneficial Owners"],
                recipients=["AML Service Providers", "Regulators (when required)"],
                international_transfers=True,
                transfer_countries=["United States", "United Kingdom"],
                retention_period="7 years from last transaction",
                security_measures=["Encrypted transmission", "Audit logging", "Data agreements"]
            ),
            ProcessingActivity(
                name="Risk Scoring",
                description="Calculate risk scores based on multiple factors",
                purpose=ProcessingPurpose.RISK_ASSESSMENT,
                lawful_basis=LawfulBasis.LEGITIMATE_INTERESTS,
                data_categories=[DataCategory.IDENTITY, DataCategory.DEVICE, DataCategory.BEHAVIORAL],
                data_subjects=["Customers"],
                recipients=["Internal Risk Engine"],
                international_transfers=False,
                transfer_countries=[],
                retention_period="7 years",
                security_measures=["Algorithm transparency", "Regular audits", "Fairness testing"]
            ),
            ProcessingActivity(
                name="Audit Logging",
                description="Log all system activities for audit trail",
                purpose=ProcessingPurpose.AUDIT_LOGGING,
                lawful_basis=LawfulBasis.LEGAL_OBLIGATION,
                data_categories=[DataCategory.IDENTITY, DataCategory.DEVICE, DataCategory.BEHAVIORAL],
                data_subjects=["Customers", "System Users"],
                recipients=["Auditors", "Regulators"],
                international_transfers=False,
                transfer_countries=[],
                retention_period="7 years minimum",
                security_measures=["WORM storage", "Hash chains", "Access controls", "Encryption"]
            ),
            ProcessingActivity(
                name="Issuer Verification",
                description="Verify document authenticity with issuing authority",
                purpose=ProcessingPurpose.IDENTITY_VERIFICATION,
                lawful_basis=LawfulBasis.CONTRACT,
                data_categories=[DataCategory.GOVERNMENT],
                data_subjects=["Customers"],
                recipients=["Government Agencies", "Issuer APIs"],
                international_transfers=False,
                transfer_countries=[],
                retention_period="7 years",
                security_measures=["Secure APIs", "Certificate pinning", "Data minimization"]
            ),
            ProcessingActivity(
                name="Device Intelligence",
                description="Analyze device characteristics for fraud detection",
                purpose=ProcessingPurpose.FRAUD_PREVENTION,
                lawful_basis=LawfulBasis.LEGITIMATE_INTERESTS,
                data_categories=[DataCategory.DEVICE, DataCategory.LOCATION],
                data_subjects=["Customers"],
                recipients=["Fraud Detection Service"],
                international_transfers=False,
                transfer_countries=[],
                retention_period="1 year",
                security_measures=["Device fingerprinting", "IP anonymization", "Secure storage"]
            )
        ]
    
    def _initialize_privacy_risks(self):
        """Initialize privacy risks and mitigations"""
        self.privacy_risks = [
            PrivacyRisk(
                risk_id="RISK-001",
                description="Unauthorized access to biometric data",
                likelihood="Low",
                impact="High",
                risk_score=6,
                mitigation_measures=[
                    "Encryption at rest and in transit",
                    "Multi-factor authentication for access",
                    "Regular access reviews",
                    "Biometric template protection"
                ],
                residual_risk="Low"
            ),
            PrivacyRisk(
                risk_id="RISK-002",
                description="Data breach exposing PII",
                likelihood="Medium",
                impact="High",
                risk_score=8,
                mitigation_measures=[
                    "End-to-end encryption",
                    "Network segmentation",
                    "Intrusion detection systems",
                    "Regular security audits",
                    "Incident response plan"
                ],
                residual_risk="Medium"
            ),
            PrivacyRisk(
                risk_id="RISK-003",
                description="Excessive data retention",
                likelihood="Medium",
                impact="Medium",
                risk_score=5,
                mitigation_measures=[
                    "Automated retention policies",
                    "Regular data purging",
                    "Retention period reviews",
                    "Data minimization practices"
                ],
                residual_risk="Low"
            ),
            PrivacyRisk(
                risk_id="RISK-004",
                description="Third-party data processor breach",
                likelihood="Low",
                impact="High",
                risk_score=6,
                mitigation_measures=[
                    "Vendor security assessments",
                    "Data processing agreements",
                    "Regular audits of processors",
                    "Contractual security requirements"
                ],
                residual_risk="Low"
            ),
            PrivacyRisk(
                risk_id="RISK-005",
                description="Algorithmic bias in risk scoring",
                likelihood="Medium",
                impact="Medium",
                risk_score=5,
                mitigation_measures=[
                    "Regular bias testing",
                    "Algorithm transparency",
                    "Human review for edge cases",
                    "Fairness metrics monitoring"
                ],
                residual_risk="Low"
            ),
            PrivacyRisk(
                risk_id="RISK-006",
                description="Cross-border data transfer compliance",
                likelihood="Low",
                impact="Medium",
                risk_score=4,
                mitigation_measures=[
                    "Standard Contractual Clauses",
                    "Adequacy decisions review",
                    "Transfer impact assessments",
                    "Local data residency options"
                ],
                residual_risk="Low"
            )
        ]
    
    def scan_codebase(self) -> Dict[str, Any]:
        """Scan codebase to extract data fields and processing information"""
        scan_results = {
            "files_scanned": 0,
            "pii_fields_found": [],
            "api_endpoints": [],
            "data_stores": [],
            "third_party_services": []
        }
        
        # Scan Python files
        for py_file in self.project_path.rglob("*.py"):
            if "test" in str(py_file) or "__pycache__" in str(py_file):
                continue
            
            scan_results["files_scanned"] += 1
            
            try:
                with open(py_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Find PII field references
                pii_patterns = [
                    r'["\'](full_name|name|email|phone|address|birth_date|id_number|passport)["\']',
                    r'\.get\(["\']?(full_name|email|phone|ssn|id_number)["\']?\)',
                ]
                
                for pattern in pii_patterns:
                    matches = re.findall(pattern, content, re.IGNORECASE)
                    scan_results["pii_fields_found"].extend(matches)
                
                # Find API endpoints
                endpoint_patterns = [
                    r'@app\.(get|post|put|delete)\(["\']([^"\']+)["\']',
                    r'router\.(get|post|put|delete)\(["\']([^"\']+)["\']',
                ]
                
                for pattern in endpoint_patterns:
                    matches = re.findall(pattern, content)
                    for method, path in matches:
                        scan_results["api_endpoints"].append(f"{method.upper()} {path}")
                
                # Find third-party service references
                service_patterns = [
                    r'(aws|s3|azure|gcs|google)',
                    r'(stripe|paypal|twilio)',
                    r'(sendgrid|mailgun)',
                ]
                
                for pattern in service_patterns:
                    if re.search(pattern, content, re.IGNORECASE):
                        scan_results["third_party_services"].append(pattern)
            
            except Exception as e:
                logger.warning(f"Error scanning {py_file}: {e}")
        
        # Remove duplicates
        scan_results["pii_fields_found"] = list(set(scan_results["pii_fields_found"]))
        scan_results["api_endpoints"] = list(set(scan_results["api_endpoints"]))
        scan_results["third_party_services"] = list(set(scan_results["third_party_services"]))
        
        return scan_results
    
    def generate_dpia(self) -> str:
        """Generate Data Protection Impact Assessment"""
        dpia_path = self.artifacts_path / "DPIA.md"
        
        # Scan codebase
        scan_results = self.scan_codebase()
        
        # Generate DPIA content
        content = []
        content.append("# Data Protection Impact Assessment (DPIA)")
        content.append(f"\n**Generated:** {datetime.now(timezone(timedelta(hours=8))).isoformat()}")
        content.append("**System:** KYC Identity Verification System")
        content.append("**Version:** 1.0.0")
        
        # Executive Summary
        content.append("\n## Executive Summary")
        content.append("\nThis Data Protection Impact Assessment evaluates the privacy risks associated with the KYC Identity Verification System. The system processes personal data including biometric information for identity verification and fraud prevention purposes.")
        
        # Processing Overview
        content.append("\n## 1. Processing Overview")
        content.append("\n### 1.1 Purpose of Processing")
        content.append("\nThe primary purposes of data processing are:")
        for activity in self.processing_activities:
            content.append(f"- **{activity.purpose.value}**: {activity.description}")
        
        content.append("\n### 1.2 Lawful Basis")
        content.append("\nProcessing is conducted under the following lawful bases:")
        basis_counts = {}
        for activity in self.processing_activities:
            basis = activity.lawful_basis.value
            basis_counts[basis] = basis_counts.get(basis, 0) + 1
        for basis, count in basis_counts.items():
            content.append(f"- **{basis}**: {count} processing activities")
        
        # Data Inventory
        content.append("\n## 2. Data Inventory")
        content.append("\n### 2.1 Categories of Personal Data")
        
        categories = {}
        for field in self.data_fields:
            if field.category not in categories:
                categories[field.category] = []
            categories[field.category].append(field)
        
        for category, fields in categories.items():
            content.append(f"\n#### {category.value}")
            content.append("\n| Field Name | Description | PII | Sensitive | Retention |")
            content.append("|------------|-------------|-----|-----------|-----------|")
            for field in fields:
                pii = "Yes" if field.is_pii else "No"
                sensitive = "Yes" if field.is_sensitive else "No"
                retention = f"{field.retention_period_days} days"
                content.append(f"| {field.name} | {field.description} | {pii} | {sensitive} | {retention} |")
        
        content.append("\n### 2.2 Data Sources")
        sources = set()
        for field in self.data_fields:
            for source in field.source.split(", "):
                sources.add(source)
        content.append("\n- " + "\n- ".join(sorted(sources)))
        
        # Data Flow
        content.append("\n## 3. Data Flow")
        content.append("\n### 3.1 Data Collection")
        content.append("```mermaid")
        content.append("graph LR")
        content.append("    A[User] -->|Upload| B[Document Capture]")
        content.append("    A -->|Selfie| C[Biometric Capture]")
        content.append("    B --> D[Quality Check]")
        content.append("    D --> E[OCR Extraction]")
        content.append("    E --> F[Data Validation]")
        content.append("    C --> G[Face Detection]")
        content.append("    F --> H[Risk Assessment]")
        content.append("    G --> H")
        content.append("    H --> I[Decision Engine]")
        content.append("```")
        
        # Recipients
        content.append("\n### 3.2 Data Recipients")
        recipients = set()
        for activity in self.processing_activities:
            recipients.update(activity.recipients)
        content.append("\n- " + "\n- ".join(sorted(recipients)))
        
        # International Transfers
        content.append("\n### 3.3 International Transfers")
        transfers = [a for a in self.processing_activities if a.international_transfers]
        if transfers:
            content.append("\nThe following activities involve international data transfers:")
            for activity in transfers:
                countries = ", ".join(activity.transfer_countries)
                content.append(f"- **{activity.name}**: {countries}")
        else:
            content.append("\nNo international data transfers identified.")
        
        # Risk Assessment
        content.append("\n## 4. Risk Assessment")
        content.append("\n### 4.1 Identified Risks")
        content.append("\n| Risk ID | Description | Likelihood | Impact | Score | Residual Risk |")
        content.append("|---------|-------------|------------|--------|-------|---------------|")
        for risk in self.privacy_risks:
            content.append(f"| {risk.risk_id} | {risk.description} | {risk.likelihood} | {risk.impact} | {risk.risk_score} | {risk.residual_risk} |")
        
        content.append("\n### 4.2 Risk Matrix")
        content.append("```")
        content.append("Impact    High  | 3 | 6 | 9 |")
        content.append("         Medium | 2 | 5 | 8 |")
        content.append("          Low   | 1 | 4 | 7 |")
        content.append("                +---+---+---+")
        content.append("                Low Med High")
        content.append("                Likelihood")
        content.append("```")
        
        # Mitigation Measures
        content.append("\n## 5. Mitigation Measures")
        for risk in self.privacy_risks:
            content.append(f"\n### {risk.risk_id}: {risk.description}")
            content.append("\n**Mitigation measures:**")
            for measure in risk.mitigation_measures:
                content.append(f"- {measure}")
        
        # Technical Measures
        content.append("\n## 6. Technical and Organizational Measures")
        content.append("\n### 6.1 Technical Measures")
        measures = set()
        for activity in self.processing_activities:
            measures.update(activity.security_measures)
        for measure in sorted(measures):
            content.append(f"- {measure}")
        
        content.append("\n### 6.2 Organizational Measures")
        content.append("- Privacy by Design principles")
        content.append("- Data Protection Officer appointment")
        content.append("- Regular privacy training")
        content.append("- Privacy policies and procedures")
        content.append("- Incident response plan")
        content.append("- Regular audits and assessments")
        
        # Data Subject Rights
        content.append("\n## 7. Data Subject Rights")
        content.append("\nThe system supports the following data subject rights:")
        content.append("- **Right to Access**: Data export functionality")
        content.append("- **Right to Rectification**: Data correction interfaces")
        content.append("- **Right to Erasure**: Data deletion procedures")
        content.append("- **Right to Restriction**: Processing limitation controls")
        content.append("- **Right to Portability**: Structured data export")
        content.append("- **Right to Object**: Opt-out mechanisms")
        
        # Compliance
        content.append("\n## 8. Compliance")
        content.append("\n### 8.1 Regulatory Compliance")
        content.append("- **GDPR**: General Data Protection Regulation (EU)")
        content.append("- **Data Privacy Act**: Republic Act 10173 (Philippines)")
        content.append("- **BSP Circular 808**: Guidelines on Information Security Management")
        content.append("- **PCI DSS**: Payment Card Industry Data Security Standard")
        
        content.append("\n### 8.2 Code Analysis Results")
        content.append(f"\n- Files scanned: {scan_results['files_scanned']}")
        content.append(f"- PII fields identified: {len(scan_results['pii_fields_found'])}")
        content.append(f"- API endpoints: {len(scan_results['api_endpoints'])}")
        
        # Recommendations
        content.append("\n## 9. Recommendations")
        content.append("\n1. **Immediate Actions:**")
        content.append("   - Implement automated data retention policies")
        content.append("   - Enhance biometric data protection")
        content.append("   - Complete privacy notices update")
        
        content.append("\n2. **Short-term (3 months):**")
        content.append("   - Conduct penetration testing")
        content.append("   - Implement privacy-preserving analytics")
        content.append("   - Enhance consent management")
        
        content.append("\n3. **Long-term (12 months):**")
        content.append("   - Achieve ISO 27001 certification")
        content.append("   - Implement homomorphic encryption")
        content.append("   - Establish privacy metrics dashboard")
        
        # Approval
        content.append("\n## 10. Approval and Review")
        content.append("\n| Role | Name | Date | Signature |")
        content.append("|------|------|------|-----------|")
        content.append("| Data Protection Officer | ____________ | ____________ | ____________ |")
        content.append("| Chief Technology Officer | ____________ | ____________ | ____________ |")
        content.append("| Legal Counsel | ____________ | ____________ | ____________ |")
        
        content.append("\n**Next Review Date:** 6 months from approval")
        
        # Write DPIA
        dpia_content = "\n".join(content)
        with open(dpia_path, 'w', encoding='utf-8') as f:
            f.write(dpia_content)
        
        logger.info(f"DPIA generated: {dpia_path}")
        return str(dpia_path)
    
    def generate_ropa(self) -> str:
        """Generate Record of Processing Activities (ROPA) in CSV format"""
        ropa_path = self.artifacts_path / "ROPA.csv"
        
        # Prepare CSV data
        headers = [
            "Activity Name",
            "Description",
            "Purpose",
            "Lawful Basis",
            "Data Categories",
            "Data Subjects",
            "Recipients",
            "International Transfers",
            "Transfer Countries",
            "Retention Period",
            "Security Measures",
            "Date Recorded",
            "Last Updated"
        ]
        
        rows = []
        for activity in self.processing_activities:
            row = [
                activity.name,
                activity.description,
                activity.purpose.value,
                activity.lawful_basis.value,
                "; ".join([cat.value for cat in activity.data_categories]),
                "; ".join(activity.data_subjects),
                "; ".join(activity.recipients),
                "Yes" if activity.international_transfers else "No",
                "; ".join(activity.transfer_countries) if activity.transfer_countries else "N/A",
                activity.retention_period,
                "; ".join(activity.security_measures),
                datetime.now(timezone(timedelta(hours=8))).date().isoformat(),
                datetime.now(timezone(timedelta(hours=8))).date().isoformat()
            ]
            rows.append(row)
        
        # Write CSV
        with open(ropa_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        
        logger.info(f"ROPA generated: {ropa_path}")
        return str(ropa_path)
    
    def generate_retention_matrix(self) -> str:
        """Generate Data Retention Matrix in CSV format"""
        retention_path = self.artifacts_path / "retention_matrix.csv"
        
        # Prepare CSV data
        headers = [
            "Data Category",
            "Data Field",
            "Description",
            "Retention Period (Days)",
            "Retention Period (Human)",
            "Legal Basis for Retention",
            "Deletion Method",
            "Archive Required",
            "Encryption Required",
            "Special Handling"
        ]
        
        rows = []
        for field in self.data_fields:
            # Convert days to human readable
            days = field.retention_period_days
            if days >= 365:
                years = days // 365
                human_period = f"{years} year{'s' if years > 1 else ''}"
            elif days >= 30:
                months = days // 30
                human_period = f"{months} month{'s' if months > 1 else ''}"
            else:
                human_period = f"{days} days"
            
            # Determine legal basis for retention
            if field.category == DataCategory.GOVERNMENT:
                legal_basis = "Regulatory requirement (AML/KYC)"
            elif field.category == DataCategory.BIOMETRIC:
                legal_basis = "Fraud prevention (limited retention)"
            elif days >= 2555:  # 7 years
                legal_basis = "Legal/Tax requirements"
            else:
                legal_basis = "Business purpose"
            
            # Determine deletion method
            if field.is_sensitive:
                deletion_method = "Secure overwrite (DOD 5220.22-M)"
            else:
                deletion_method = "Standard deletion"
            
            # Archive requirement
            archive_required = "Yes" if days >= 365 else "No"
            
            # Special handling
            special_handling = []
            if field.is_sensitive:
                special_handling.append("Sensitive data")
            if field.category == DataCategory.BIOMETRIC:
                special_handling.append("Biometric protection required")
            if field.encryption_required:
                special_handling.append("Encryption required")
            
            row = [
                field.category.value,
                field.name,
                field.description,
                str(field.retention_period_days),
                human_period,
                legal_basis,
                deletion_method,
                archive_required,
                "Yes" if field.encryption_required else "No",
                "; ".join(special_handling) if special_handling else "None"
            ]
            rows.append(row)
        
        # Sort by category and field name
        rows.sort(key=lambda x: (x[0], x[1]))
        
        # Write CSV
        with open(retention_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            writer.writerows(rows)
        
        logger.info(f"Retention Matrix generated: {retention_path}")
        return str(retention_path)
    
    def generate(
        self,
        artifact_type: str,
        include_data_flows: bool = True,
        include_minimization: bool = True,
        format: str = "default"
    ) -> Dict[str, Any]:
        """Generate specified compliance artifact"""
        
        if artifact_type.lower() == "dpia":
            file_path = self.generate_dpia()
            sections = [
                "Executive Summary",
                "Processing Overview",
                "Data Inventory",
                "Data Flow",
                "Risk Assessment",
                "Mitigation Measures",
                "Technical Measures",
                "Data Subject Rights",
                "Compliance",
                "Recommendations"
            ]
        
        elif artifact_type.lower() == "ropa":
            file_path = self.generate_ropa()
            sections = ["Processing Activities Record"]
        
        elif artifact_type.lower() == "retention_matrix":
            file_path = self.generate_retention_matrix()
            sections = ["Data Retention Schedule"]
        
        else:
            raise ValueError(f"Unknown artifact type: {artifact_type}")
        
        return {
            "file_path": file_path,
            "sections": sections,
            "generated_at": datetime.now(timezone(timedelta(hours=8))).isoformat()
        }
    
    def generate_all(self) -> Dict[str, str]:
        """Generate all compliance artifacts"""
        results = {}
        
        # Generate DPIA
        results["dpia"] = self.generate_dpia()
        
        # Generate ROPA
        results["ropa"] = self.generate_ropa()
        
        # Generate Retention Matrix
        results["retention_matrix"] = self.generate_retention_matrix()
        
        logger.info(f"All compliance artifacts generated in: {self.artifacts_path}")
        
        return results
