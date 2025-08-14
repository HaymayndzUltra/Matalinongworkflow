"""
AML/PEP/Adverse Media Screening System
Ongoing Customer Due Diligence with Re-screening
Part of KYC Bank-Grade Parity - Phase 5

This module implements screening against AML, PEP, and adverse media lists.
"""

import logging
import hashlib
import json
import time
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta, date
from pathlib import Path
from enum import Enum
import random
from abc import ABC, abstractmethod

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Manila timezone
MANILA_TZ = timezone(timedelta(hours=8))


class ScreeningType(Enum):
    """Types of screening"""
    AML = "aml"
    PEP = "pep"
    ADVERSE_MEDIA = "adverse_media"
    SANCTIONS = "sanctions"
    WATCHLIST = "watchlist"


class RiskLevel(Enum):
    """Customer risk levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"


class HitStatus(Enum):
    """Screening hit status"""
    NO_HIT = "no_hit"
    POTENTIAL_HIT = "potential_hit"
    CONFIRMED_HIT = "confirmed_hit"
    FALSE_POSITIVE = "false_positive"
    PENDING_REVIEW = "pending_review"


@dataclass
class ScreeningHit:
    """Individual screening hit"""
    hit_id: str
    screening_type: ScreeningType
    source_list: str
    matched_name: str
    match_score: float
    details: Dict[str, Any]
    risk_score: float
    created_at: str
    
    def to_json(self) -> str:
        """Convert to JSON"""
        data = asdict(self)
        data['screening_type'] = self.screening_type.value
        return json.dumps(data)


@dataclass
class ScreeningResult:
    """Complete screening result"""
    screening_id: str
    customer_id: str
    customer_name: str
    screening_types: List[ScreeningType]
    hits: List[ScreeningHit]
    overall_status: HitStatus
    risk_level: RiskLevel
    processing_time_ms: float
    timestamp: str
    next_screening_date: str
    case_id: Optional[str] = None
    
    def has_hits(self) -> bool:
        """Check if there are any hits"""
        return len(self.hits) > 0
    
    def get_hit_count_by_type(self) -> Dict[ScreeningType, int]:
        """Get hit count by screening type"""
        counts = {}
        for hit in self.hits:
            counts[hit.screening_type] = counts.get(hit.screening_type, 0) + 1
        return counts


@dataclass
class ScreeningCase:
    """Case created from screening hits"""
    case_id: str
    customer_id: str
    screening_result_id: str
    status: str
    priority: str
    assigned_to: Optional[str]
    created_at: str
    sla_deadline: str
    resolution: Optional[str] = None
    resolved_at: Optional[str] = None
    notes: List[str] = None


class CircuitBreaker:
    """Circuit breaker for external API calls"""
    
    def __init__(self, failure_threshold: int = 5, 
                 recovery_timeout: int = 60):
        """
        Initialize circuit breaker
        
        Args:
            failure_threshold: Number of failures before opening
            recovery_timeout: Seconds before attempting recovery
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "closed"  # closed, open, half-open
    
    def call(self, func, *args, **kwargs):
        """
        Call function with circuit breaker protection
        
        Args:
            func: Function to call
            *args, **kwargs: Function arguments
            
        Returns:
            Function result or None
        """
        if self.state == "open":
            if self._should_attempt_reset():
                self.state = "half-open"
            else:
                logger.warning("Circuit breaker is open, skipping call")
                return None
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e
    
    def _on_success(self):
        """Handle successful call"""
        self.failure_count = 0
        if self.state == "half-open":
            self.state = "closed"
            logger.info("Circuit breaker closed")
    
    def _on_failure(self):
        """Handle failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
            logger.warning(f"Circuit breaker opened after {self.failure_count} failures")
    
    def _should_attempt_reset(self) -> bool:
        """Check if should attempt reset"""
        if self.last_failure_time is None:
            return True
        
        return time.time() - self.last_failure_time >= self.recovery_timeout


class BaseScreeningProvider(ABC):
    """Base class for screening providers"""
    
    def __init__(self, api_endpoint: str, api_key: str):
        """
        Initialize screening provider
        
        Args:
            api_endpoint: API endpoint
            api_key: API key
        """
        self.api_endpoint = api_endpoint
        self.api_key = api_key
        self.circuit_breaker = CircuitBreaker()
        
        # Load config
        import sys
        sys.path.append('/workspace/KYC VERIFICATION')
        from src.config.threshold_manager import get_threshold_manager
        self.threshold_manager = get_threshold_manager()
    
    @abstractmethod
    def screen(self, customer_name: str, **kwargs) -> List[ScreeningHit]:
        """Screen customer against lists"""
        pass
    
    def _calculate_match_score(self, query_name: str, 
                              matched_name: str) -> float:
        """
        Calculate name match score
        
        Args:
            query_name: Query name
            matched_name: Matched name from list
            
        Returns:
            Match score (0-1)
        """
        # Simple character-based similarity (would use fuzzy matching in production)
        query_lower = query_name.lower()
        matched_lower = matched_name.lower()
        
        # Exact match
        if query_lower == matched_lower:
            return 1.0
        
        # Partial match
        if query_lower in matched_lower or matched_lower in query_lower:
            return 0.8
        
        # Token-based matching
        query_tokens = set(query_lower.split())
        matched_tokens = set(matched_lower.split())
        
        if query_tokens == matched_tokens:
            return 0.9
        
        intersection = query_tokens.intersection(matched_tokens)
        union = query_tokens.union(matched_tokens)
        
        if union:
            return len(intersection) / len(union)
        
        return 0.0


class AMLScreeningProvider(BaseScreeningProvider):
    """AML screening provider"""
    
    def __init__(self):
        """Initialize AML screening"""
        super().__init__(
            api_endpoint="https://api.aml-provider.com/screen",
            api_key="mock_aml_api_key"
        )
        logger.info("AML Screening Provider initialized")
    
    def screen(self, customer_name: str, **kwargs) -> List[ScreeningHit]:
        """
        Screen against AML lists
        
        Args:
            customer_name: Customer name
            **kwargs: Additional parameters
            
        Returns:
            List of screening hits
        """
        hits = []
        
        # Mock AML screening
        def mock_screen():
            # Simulate API call
            time.sleep(0.1)
            
            # Generate mock hits
            if "suspicious" in customer_name.lower():
                hit = ScreeningHit(
                    hit_id=hashlib.sha256(f"{customer_name}_aml".encode()).hexdigest()[:12],
                    screening_type=ScreeningType.AML,
                    source_list="OFAC SDN List",
                    matched_name=customer_name.upper(),
                    match_score=0.95,
                    details={
                        "list_entry_date": "2023-01-15",
                        "reason": "Money laundering suspicion",
                        "jurisdiction": "US"
                    },
                    risk_score=0.8,
                    created_at=datetime.now(MANILA_TZ).isoformat()
                )
                return [hit]
            
            return []
        
        # Use circuit breaker
        result = self.circuit_breaker.call(mock_screen)
        if result:
            hits.extend(result)
        
        return hits


class PEPScreeningProvider(BaseScreeningProvider):
    """PEP screening provider"""
    
    def __init__(self):
        """Initialize PEP screening"""
        super().__init__(
            api_endpoint="https://api.pep-provider.com/screen",
            api_key="mock_pep_api_key"
        )
        logger.info("PEP Screening Provider initialized")
    
    def screen(self, customer_name: str, **kwargs) -> List[ScreeningHit]:
        """
        Screen against PEP lists
        
        Args:
            customer_name: Customer name
            **kwargs: Additional parameters
            
        Returns:
            List of screening hits
        """
        hits = []
        
        # Mock PEP screening
        def mock_screen():
            time.sleep(0.1)
            
            # Check for PEP indicators
            pep_keywords = ["minister", "senator", "governor", "mayor"]
            name_lower = customer_name.lower()
            
            for keyword in pep_keywords:
                if keyword in name_lower:
                    hit = ScreeningHit(
                        hit_id=hashlib.sha256(f"{customer_name}_pep".encode()).hexdigest()[:12],
                        screening_type=ScreeningType.PEP,
                        source_list="Global PEP Database",
                        matched_name=customer_name,
                        match_score=0.85,
                        details={
                            "position": keyword.title(),
                            "country": "Philippines",
                            "pep_level": "Senior",
                            "start_date": "2020-01-01"
                        },
                        risk_score=0.7,
                        created_at=datetime.now(MANILA_TZ).isoformat()
                    )
                    return [hit]
            
            return []
        
        result = self.circuit_breaker.call(mock_screen)
        if result:
            hits.extend(result)
        
        return hits


class AdverseMediaScreeningProvider(BaseScreeningProvider):
    """Adverse media screening provider"""
    
    def __init__(self):
        """Initialize adverse media screening"""
        super().__init__(
            api_endpoint="https://api.media-screening.com/screen",
            api_key="mock_media_api_key"
        )
        logger.info("Adverse Media Screening Provider initialized")
    
    def screen(self, customer_name: str, **kwargs) -> List[ScreeningHit]:
        """
        Screen against adverse media
        
        Args:
            customer_name: Customer name
            **kwargs: Additional parameters
            
        Returns:
            List of screening hits
        """
        hits = []
        
        # Mock adverse media screening
        def mock_screen():
            time.sleep(0.1)
            
            # Simulate finding adverse media
            if random.random() < 0.1:  # 10% chance of adverse media
                hit = ScreeningHit(
                    hit_id=hashlib.sha256(f"{customer_name}_media".encode()).hexdigest()[:12],
                    screening_type=ScreeningType.ADVERSE_MEDIA,
                    source_list="Global News Database",
                    matched_name=customer_name,
                    match_score=0.75,
                    details={
                        "article_date": "2024-01-10",
                        "source": "Financial Times",
                        "headline": "Investigation into financial irregularities",
                        "url": "https://example.com/article"
                    },
                    risk_score=0.6,
                    created_at=datetime.now(MANILA_TZ).isoformat()
                )
                return [hit]
            
            return []
        
        result = self.circuit_breaker.call(mock_screen)
        if result:
            hits.extend(result)
        
        return hits


class ScreeningOrchestrator:
    """Orchestrates screening across multiple providers"""
    
    def __init__(self):
        """Initialize screening orchestrator"""
        self.providers = {
            ScreeningType.AML: AMLScreeningProvider(),
            ScreeningType.PEP: PEPScreeningProvider(),
            ScreeningType.ADVERSE_MEDIA: AdverseMediaScreeningProvider()
        }
        self.case_manager = CaseManager()
        logger.info("Screening Orchestrator initialized with 3 providers")
    
    def screen_customer(self, customer_id: str, customer_name: str,
                        screening_types: Optional[List[ScreeningType]] = None,
                        **kwargs) -> ScreeningResult:
        """
        Screen customer across multiple lists
        
        Args:
            customer_id: Customer ID
            customer_name: Customer name
            screening_types: Types to screen (default: all)
            **kwargs: Additional parameters
            
        Returns:
            ScreeningResult
        """
        start_time = time.time()
        
        # Default to all screening types
        if not screening_types:
            screening_types = list(ScreeningType)
        
        # Collect hits from all providers
        all_hits = []
        for screening_type in screening_types:
            if screening_type in self.providers:
                provider = self.providers[screening_type]
                hits = provider.screen(customer_name, **kwargs)
                all_hits.extend(hits)
        
        # Determine overall status
        if not all_hits:
            overall_status = HitStatus.NO_HIT
            risk_level = RiskLevel.LOW
        else:
            # Check hit scores
            max_score = max(hit.risk_score for hit in all_hits)
            if max_score >= 0.8:
                overall_status = HitStatus.CONFIRMED_HIT
                risk_level = RiskLevel.VERY_HIGH
            elif max_score >= 0.6:
                overall_status = HitStatus.POTENTIAL_HIT
                risk_level = RiskLevel.HIGH
            else:
                overall_status = HitStatus.PENDING_REVIEW
                risk_level = RiskLevel.MEDIUM
        
        # Calculate next screening date based on risk
        next_screening = self._calculate_next_screening_date(risk_level)
        
        # Create result
        result = ScreeningResult(
            screening_id=hashlib.sha256(
                f"{customer_id}_{datetime.now(MANILA_TZ).isoformat()}".encode()
            ).hexdigest()[:16],
            customer_id=customer_id,
            customer_name=customer_name,
            screening_types=screening_types,
            hits=all_hits,
            overall_status=overall_status,
            risk_level=risk_level,
            processing_time_ms=(time.time() - start_time) * 1000,
            timestamp=datetime.now(MANILA_TZ).isoformat(),
            next_screening_date=next_screening.isoformat()
        )
        
        # Create case if there are hits
        if result.has_hits() and overall_status != HitStatus.NO_HIT:
            case = self.case_manager.create_case(result)
            result.case_id = case.case_id
        
        logger.info(f"Screening completed for {customer_id}: {overall_status.value} "
                   f"({len(all_hits)} hits, {result.processing_time_ms:.1f}ms)")
        
        return result
    
    def _calculate_next_screening_date(self, risk_level: RiskLevel) -> datetime:
        """
        Calculate next screening date based on risk level
        
        Args:
            risk_level: Customer risk level
            
        Returns:
            Next screening date
        """
        now = datetime.now(MANILA_TZ)
        
        # Re-screening intervals based on risk
        intervals = {
            RiskLevel.LOW: timedelta(days=365),      # Annual
            RiskLevel.MEDIUM: timedelta(days=180),   # Semi-annual
            RiskLevel.HIGH: timedelta(days=90),      # Quarterly
            RiskLevel.VERY_HIGH: timedelta(days=30)  # Monthly
        }
        
        return now + intervals.get(risk_level, timedelta(days=180))


class CaseManager:
    """Manages cases created from screening hits"""
    
    def __init__(self, storage_path: Optional[Path] = None):
        """
        Initialize case manager
        
        Args:
            storage_path: Path to store cases
        """
        self.storage_path = storage_path or Path("/workspace/KYC VERIFICATION/cases")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.cases: Dict[str, ScreeningCase] = {}
        logger.info("Case Manager initialized")
    
    def create_case(self, screening_result: ScreeningResult) -> ScreeningCase:
        """
        Create case from screening result
        
        Args:
            screening_result: Screening result with hits
            
        Returns:
            Created case
        """
        # Generate case ID
        case_id = f"CASE-{datetime.now(MANILA_TZ).strftime('%Y%m%d')}-{len(self.cases)+1:04d}"
        
        # Determine priority based on risk level
        priority_map = {
            RiskLevel.VERY_HIGH: "critical",
            RiskLevel.HIGH: "high",
            RiskLevel.MEDIUM: "medium",
            RiskLevel.LOW: "low"
        }
        
        # Calculate SLA deadline
        sla_hours = {
            "critical": 4,
            "high": 24,
            "medium": 48,
            "low": 72
        }
        priority = priority_map[screening_result.risk_level]
        sla_deadline = datetime.now(MANILA_TZ) + timedelta(hours=sla_hours[priority])
        
        # Create case
        case = ScreeningCase(
            case_id=case_id,
            customer_id=screening_result.customer_id,
            screening_result_id=screening_result.screening_id,
            status="open",
            priority=priority,
            assigned_to=None,
            created_at=datetime.now(MANILA_TZ).isoformat(),
            sla_deadline=sla_deadline.isoformat(),
            notes=[]
        )
        
        # Store case
        self.cases[case_id] = case
        self._save_case(case)
        
        logger.info(f"Case created: {case_id} (priority: {priority})")
        return case
    
    def update_case(self, case_id: str, **updates) -> bool:
        """
        Update case
        
        Args:
            case_id: Case ID
            **updates: Fields to update
            
        Returns:
            True if updated successfully
        """
        case = self.cases.get(case_id)
        if not case:
            logger.error(f"Case {case_id} not found")
            return False
        
        # Update fields
        for key, value in updates.items():
            if hasattr(case, key):
                setattr(case, key, value)
        
        # Save updated case
        self._save_case(case)
        logger.info(f"Case {case_id} updated")
        return True
    
    def _save_case(self, case: ScreeningCase):
        """Save case to storage"""
        try:
            case_file = self.storage_path / f"{case.case_id}.json"
            with open(case_file, 'w') as f:
                json.dump(asdict(case), f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save case: {e}")


class ScreeningScheduler:
    """Schedules periodic re-screening"""
    
    def __init__(self, orchestrator: ScreeningOrchestrator):
        """
        Initialize screening scheduler
        
        Args:
            orchestrator: Screening orchestrator
        """
        self.orchestrator = orchestrator
        self.schedule: Dict[str, datetime] = {}
        logger.info("Screening Scheduler initialized")
    
    def get_customers_due_for_screening(self) -> List[str]:
        """
        Get customers due for re-screening
        
        Returns:
            List of customer IDs
        """
        now = datetime.now(MANILA_TZ)
        due_customers = []
        
        for customer_id, next_screening in self.schedule.items():
            if next_screening <= now:
                due_customers.append(customer_id)
        
        return due_customers
    
    def schedule_screening(self, customer_id: str, next_date: datetime):
        """
        Schedule next screening for customer
        
        Args:
            customer_id: Customer ID
            next_date: Next screening date
        """
        self.schedule[customer_id] = next_date
        logger.debug(f"Scheduled screening for {customer_id} on {next_date.date()}")
    
    def run_scheduled_screenings(self) -> List[ScreeningResult]:
        """
        Run all due screenings
        
        Returns:
            List of screening results
        """
        due_customers = self.get_customers_due_for_screening()
        results = []
        
        for customer_id in due_customers:
            # In production, would fetch customer details from database
            customer_name = f"Customer_{customer_id}"
            
            result = self.orchestrator.screen_customer(customer_id, customer_name)
            results.append(result)
            
            # Update schedule
            next_date = datetime.fromisoformat(result.next_screening_date)
            self.schedule_screening(customer_id, next_date)
        
        logger.info(f"Completed {len(results)} scheduled screenings")
        return results


if __name__ == "__main__":
    # Demo and testing
    print("=== AML/PEP/Adverse Media Screening Demo ===\n")
    
    # Initialize orchestrator
    orchestrator = ScreeningOrchestrator()
    
    # Test screening
    print("Testing screening for different customers:\n")
    
    # Clean customer
    result = orchestrator.screen_customer("CUST001", "John Smith")
    print(f"Customer: John Smith")
    print(f"  Status: {result.overall_status.value}")
    print(f"  Risk Level: {result.risk_level.value}")
    print(f"  Hits: {len(result.hits)}")
    print(f"  Processing: {result.processing_time_ms:.1f}ms")
    
    # Suspicious customer
    print("\nCustomer: Suspicious Person")
    result = orchestrator.screen_customer("CUST002", "Suspicious Person")
    print(f"  Status: {result.overall_status.value}")
    print(f"  Risk Level: {result.risk_level.value}")
    print(f"  Hits: {len(result.hits)}")
    if result.hits:
        for hit in result.hits:
            print(f"    - {hit.screening_type.value}: {hit.source_list} (score: {hit.match_score:.2f})")
    if result.case_id:
        print(f"  Case Created: {result.case_id}")
    
    # PEP customer
    print("\nCustomer: Senator Johnson")
    result = orchestrator.screen_customer("CUST003", "Senator Johnson")
    print(f"  Status: {result.overall_status.value}")
    print(f"  Risk Level: {result.risk_level.value}")
    print(f"  Hits: {len(result.hits)}")
    
    # Test scheduler
    print("\nTesting Scheduler:")
    scheduler = ScreeningScheduler(orchestrator)
    
    # Schedule some customers
    scheduler.schedule_screening("CUST001", datetime.now(MANILA_TZ))
    scheduler.schedule_screening("CUST002", datetime.now(MANILA_TZ) + timedelta(days=30))
    
    due = scheduler.get_customers_due_for_screening()
    print(f"  Customers due for screening: {len(due)}")
    
    print("\n✓ AML/PEP/Adverse Media Screening system operational")