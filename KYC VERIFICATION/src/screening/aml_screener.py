"""
Sanctions & AML Screening Module
Phase 9: Multi-vendor sanctions/PEP/adverse media screening
Explainable hits with entity resolution and continuous monitoring
"""

import json
import logging
import hashlib
import requests
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, date, timedelta
from pathlib import Path
import difflib
from fuzzywuzzy import fuzz, process
import re

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ScreeningType(Enum):
    """Types of screening checks"""
    SANCTIONS = "sanctions"
    PEP = "pep"  # Politically Exposed Person
    ADVERSE_MEDIA = "adverse_media"
    WATCHLIST = "watchlist"
    INTERNAL_LIST = "internal_list"
    OFAC = "ofac"  # Office of Foreign Assets Control
    UN = "un"  # United Nations
    EU = "eu"  # European Union
    INTERPOL = "interpol"

class MatchType(Enum):
    """Types of name matches"""
    EXACT = "exact"
    FUZZY = "fuzzy"
    PHONETIC = "phonetic"
    PARTIAL = "partial"
    ALIAS = "alias"

class RiskLevel(Enum):
    """Risk levels for matches"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMAL = "minimal"

@dataclass
class ScreeningHit:
    """Individual screening hit"""
    hit_id: str
    source: ScreeningType
    match_type: MatchType
    match_score: float
    entity_name: str
    matched_name: str
    risk_level: RiskLevel
    reasons: List[str]
    metadata: Dict[str, Any]
    is_false_positive: bool = False

@dataclass
class SanctionedEntity:
    """Sanctioned entity information"""
    entity_id: str
    primary_name: str
    aliases: List[str]
    date_of_birth: Optional[str]
    nationality: Optional[str]
    addresses: List[str]
    identifiers: Dict[str, str]  # passport, national_id, etc.
    sanction_programs: List[str]
    listing_date: str
    source: str

@dataclass
class PEPEntity:
    """Politically Exposed Person entity"""
    entity_id: str
    name: str
    position: str
    country: str
    risk_level: RiskLevel
    start_date: Optional[str]
    end_date: Optional[str]
    is_current: bool
    relationships: List[Dict[str, str]]  # family, associates

@dataclass
class AdverseMediaHit:
    """Adverse media finding"""
    article_id: str
    headline: str
    source: str
    published_date: str
    risk_categories: List[str]  # fraud, corruption, terrorism, etc.
    relevance_score: float
    summary: str
    url: Optional[str]

@dataclass
class ScreeningResult:
    """Complete screening result"""
    request_id: str
    subject_name: str
    subject_data: Dict[str, Any]
    total_hits: int
    sanctions_hits: List[ScreeningHit]
    pep_hits: List[ScreeningHit]
    adverse_media_hits: List[AdverseMediaHit]
    overall_risk: RiskLevel
    requires_review: bool
    auto_clearable: bool
    explanations: List[str]
    vendor_responses: Dict[str, Any]
    screening_timestamp: datetime
    processing_time_ms: float

class AMLScreener:
    """AML and sanctions screening engine"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize AML screener"""
        self.config = self._load_config(config_path)
        self.sanctions_db = self._load_sanctions_database()
        self.pep_db = self._load_pep_database()
        self.vendor_configs = self._load_vendor_configs()
        self.false_positive_cache = {}
        
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load AML screening configuration"""
        default_config = {
            "screening_vendors": {
                "primary": "internal",
                "secondary": ["vendor_a", "vendor_b"],
                "use_multiple": True,
                "consensus_required": False
            },
            "matching": {
                "exact_match_threshold": 1.0,
                "fuzzy_match_threshold": 0.85,
                "phonetic_match_threshold": 0.80,
                "partial_match_threshold": 0.75,
                "use_aliases": True,
                "use_transliteration": True
            },
            "risk_scoring": {
                "sanctions_weight": 0.4,
                "pep_weight": 0.3,
                "adverse_media_weight": 0.3,
                "auto_clear_threshold": 0.2,
                "manual_review_threshold": 0.5
            },
            "sources": {
                "ofac": {"enabled": True, "weight": 1.0},
                "un": {"enabled": True, "weight": 1.0},
                "eu": {"enabled": True, "weight": 0.9},
                "interpol": {"enabled": True, "weight": 1.0},
                "local_watchlist": {"enabled": True, "weight": 0.8}
            },
            "false_positive_handling": {
                "enable_cache": True,
                "cache_duration_days": 90,
                "require_approval": True,
                "audit_trail": True
            },
            "continuous_monitoring": {
                "enabled": True,
                "frequency_days": 30,
                "alert_on_new_hits": True
            }
        }
        
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def _load_sanctions_database(self) -> List[SanctionedEntity]:
        """Load sanctions database"""
        # In production, this would connect to actual sanctions databases
        # This is a mock implementation
        sanctions = [
            SanctionedEntity(
                entity_id="OFAC-001",
                primary_name="John Doe Sanctioned",
                aliases=["J. Doe", "Johnny Sanctioned"],
                date_of_birth="1970-01-01",
                nationality="XX",
                addresses=["123 Blocked Street"],
                identifiers={"passport": "X1234567"},
                sanction_programs=["SDN"],
                listing_date="2020-01-01",
                source="OFAC"
            ),
            # Add more mock entities as needed
        ]
        
        return sanctions
    
    def _load_pep_database(self) -> List[PEPEntity]:
        """Load PEP database"""
        # Mock PEP database
        peps = [
            PEPEntity(
                entity_id="PEP-001",
                name="Maria Political",
                position="Former Minister",
                country="PH",
                risk_level=RiskLevel.MEDIUM,
                start_date="2015-01-01",
                end_date="2020-12-31",
                is_current=False,
                relationships=[
                    {"type": "spouse", "name": "Juan Political"},
                    {"type": "child", "name": "Ana Political"}
                ]
            ),
            # Add more mock PEPs
        ]
        
        return peps
    
    def _load_vendor_configs(self) -> Dict[str, Dict]:
        """Load vendor API configurations"""
        return {
            "vendor_a": {
                "api_url": "https://api.vendor-a.com/screen",
                "api_key": "dummy_key_a",
                "timeout": 30,
                "retry_count": 3
            },
            "vendor_b": {
                "api_url": "https://api.vendor-b.com/aml-check",
                "api_key": "dummy_key_b",
                "timeout": 30,
                "retry_count": 3
            }
        }
    
    def screen_individual(self, individual_data: Dict[str, Any]) -> ScreeningResult:
        """
        Screen an individual against sanctions, PEP, and adverse media
        
        Args:
            individual_data: Individual information to screen
            
        Returns:
            Complete screening result
        """
        start_time = datetime.now()
        request_id = self._generate_request_id()
        
        logger.info(f"🔍 Starting AML screening for: {individual_data.get('name', 'Unknown')}")
        
        # Prepare screening data
        subject_name = individual_data.get("name", "")
        subject_dob = individual_data.get("date_of_birth")
        subject_nationality = individual_data.get("nationality")
        subject_id_numbers = individual_data.get("id_numbers", {})
        
        # Check false positive cache
        cache_key = self._generate_cache_key(individual_data)
        if cache_key in self.false_positive_cache:
            cached_result = self.false_positive_cache[cache_key]
            if self._is_cache_valid(cached_result):
                logger.info("Using cached screening result")
                return cached_result["result"]
        
        # Perform internal screening
        sanctions_hits = self._screen_sanctions(
            subject_name, subject_dob, subject_nationality, subject_id_numbers
        )
        
        pep_hits = self._screen_pep(
            subject_name, subject_nationality
        )
        
        # Perform vendor screening if configured
        vendor_responses = {}
        if self.config["screening_vendors"]["use_multiple"]:
            vendor_responses = self._screen_via_vendors(individual_data)
            
            # Merge vendor hits with internal hits
            vendor_sanctions, vendor_peps, vendor_media = self._parse_vendor_responses(vendor_responses)
            sanctions_hits.extend(vendor_sanctions)
            pep_hits.extend(vendor_peps)
        
        # Screen for adverse media
        adverse_media_hits = self._screen_adverse_media(subject_name)
        
        # Calculate overall risk
        overall_risk = self._calculate_overall_risk(
            sanctions_hits, pep_hits, adverse_media_hits
        )
        
        # Determine if review is required
        requires_review = overall_risk.value in ["high", "critical"]
        auto_clearable = overall_risk.value in ["minimal", "low"] and len(sanctions_hits) == 0
        
        # Generate explanations
        explanations = self._generate_explanations(
            sanctions_hits, pep_hits, adverse_media_hits, overall_risk
        )
        
        processing_time = (datetime.now() - start_time).total_seconds() * 1000
        
        result = ScreeningResult(
            request_id=request_id,
            subject_name=subject_name,
            subject_data=individual_data,
            total_hits=len(sanctions_hits) + len(pep_hits) + len(adverse_media_hits),
            sanctions_hits=sanctions_hits,
            pep_hits=pep_hits,
            adverse_media_hits=adverse_media_hits,
            overall_risk=overall_risk,
            requires_review=requires_review,
            auto_clearable=auto_clearable,
            explanations=explanations,
            vendor_responses=vendor_responses,
            screening_timestamp=datetime.now(),
            processing_time_ms=processing_time
        )
        
        # Cache result if auto-clearable
        if auto_clearable and self.config["false_positive_handling"]["enable_cache"]:
            self.false_positive_cache[cache_key] = {
                "result": result,
                "timestamp": datetime.now()
            }
        
        logger.info(f"✅ AML screening complete: Risk={overall_risk.value}, "
                   f"Hits={result.total_hits}, Review={requires_review}")
        
        return result
    
    def _screen_sanctions(self, name: str, dob: Optional[str], 
                         nationality: Optional[str],
                         id_numbers: Dict[str, str]) -> List[ScreeningHit]:
        """Screen against sanctions lists"""
        hits = []
        
        for entity in self.sanctions_db:
            # Check name match
            name_score, match_type = self._match_names(name, entity.primary_name)
            
            # Check aliases
            if name_score < self.config["matching"]["fuzzy_match_threshold"]:
                for alias in entity.aliases:
                    alias_score, alias_type = self._match_names(name, alias)
                    if alias_score > name_score:
                        name_score = alias_score
                        match_type = MatchType.ALIAS
            
            # Check if match exceeds threshold
            if name_score >= self.config["matching"]["partial_match_threshold"]:
                # Additional verification with DOB and nationality
                confidence_boost = 0
                
                if dob and entity.date_of_birth:
                    if dob == entity.date_of_birth:
                        confidence_boost += 0.2
                
                if nationality and entity.nationality:
                    if nationality == entity.nationality:
                        confidence_boost += 0.1
                
                # Check ID numbers
                for id_type, id_value in id_numbers.items():
                    if id_type in entity.identifiers:
                        if entity.identifiers[id_type] == id_value:
                            confidence_boost += 0.3
                            break
                
                final_score = min(1.0, name_score + confidence_boost)
                
                if final_score >= self.config["matching"]["partial_match_threshold"]:
                    hit = ScreeningHit(
                        hit_id=f"SANC-{entity.entity_id}-{hashlib.md5(name.encode()).hexdigest()[:8]}",
                        source=ScreeningType.SANCTIONS,
                        match_type=match_type,
                        match_score=final_score,
                        entity_name=entity.primary_name,
                        matched_name=name,
                        risk_level=RiskLevel.CRITICAL if final_score > 0.9 else RiskLevel.HIGH,
                        reasons=[
                            f"Name match: {match_type.value} ({name_score:.2f})",
                            f"Sanction programs: {', '.join(entity.sanction_programs)}",
                            f"Listed since: {entity.listing_date}"
                        ],
                        metadata={
                            "entity_id": entity.entity_id,
                            "source_list": entity.source,
                            "sanction_programs": entity.sanction_programs
                        }
                    )
                    hits.append(hit)
        
        return hits
    
    def _screen_pep(self, name: str, nationality: Optional[str]) -> List[ScreeningHit]:
        """Screen against PEP database"""
        hits = []
        
        for pep in self.pep_db:
            # Match name
            name_score, match_type = self._match_names(name, pep.name)
            
            if name_score >= self.config["matching"]["fuzzy_match_threshold"]:
                # Boost score if nationality matches
                if nationality and pep.country == nationality:
                    name_score = min(1.0, name_score + 0.1)
                
                # Check relationships for family members
                for relation in pep.relationships:
                    rel_score, rel_type = self._match_names(name, relation["name"])
                    if rel_score >= self.config["matching"]["fuzzy_match_threshold"]:
                        hit = ScreeningHit(
                            hit_id=f"PEP-REL-{pep.entity_id}-{hashlib.md5(name.encode()).hexdigest()[:8]}",
                            source=ScreeningType.PEP,
                            match_type=MatchType.PARTIAL,
                            match_score=rel_score,
                            entity_name=relation["name"],
                            matched_name=name,
                            risk_level=RiskLevel.MEDIUM,
                            reasons=[
                                f"Related to PEP: {pep.name}",
                                f"Relationship: {relation['type']}",
                                f"PEP Position: {pep.position}"
                            ],
                            metadata={
                                "pep_id": pep.entity_id,
                                "relationship_type": relation["type"],
                                "pep_name": pep.name
                            }
                        )
                        hits.append(hit)
                
                # Direct PEP match
                if name_score >= self.config["matching"]["fuzzy_match_threshold"]:
                    hit = ScreeningHit(
                        hit_id=f"PEP-{pep.entity_id}-{hashlib.md5(name.encode()).hexdigest()[:8]}",
                        source=ScreeningType.PEP,
                        match_type=match_type,
                        match_score=name_score,
                        entity_name=pep.name,
                        matched_name=name,
                        risk_level=pep.risk_level,
                        reasons=[
                            f"PEP Match: {pep.position}",
                            f"Country: {pep.country}",
                            f"Current: {'Yes' if pep.is_current else 'No'}"
                        ],
                        metadata={
                            "pep_id": pep.entity_id,
                            "position": pep.position,
                            "is_current": pep.is_current
                        }
                    )
                    hits.append(hit)
        
        return hits
    
    def _screen_adverse_media(self, name: str) -> List[AdverseMediaHit]:
        """Screen for adverse media"""
        # In production, this would call news APIs or adverse media databases
        # Mock implementation
        adverse_hits = []
        
        # Simulate adverse media search
        mock_articles = [
            {
                "headline": "Investigation into Financial Irregularities",
                "source": "Financial Times",
                "date": "2023-06-15",
                "categories": ["fraud", "financial_crime"],
                "relevance": 0.3
            }
        ]
        
        for article in mock_articles:
            # Simple name matching in headline/content
            if any(part.lower() in article["headline"].lower() for part in name.split()):
                hit = AdverseMediaHit(
                    article_id=hashlib.md5(article["headline"].encode()).hexdigest()[:12],
                    headline=article["headline"],
                    source=article["source"],
                    published_date=article["date"],
                    risk_categories=article["categories"],
                    relevance_score=article["relevance"],
                    summary=f"Article mentions potential {', '.join(article['categories'])}",
                    url=None
                )
                adverse_hits.append(hit)
        
        return adverse_hits
    
    def _screen_via_vendors(self, individual_data: Dict[str, Any]) -> Dict[str, Any]:
        """Screen via external vendor APIs"""
        vendor_responses = {}
        
        for vendor_name in self.config["screening_vendors"]["secondary"]:
            if vendor_name in self.vendor_configs:
                try:
                    response = self._call_vendor_api(vendor_name, individual_data)
                    vendor_responses[vendor_name] = response
                except Exception as e:
                    logger.error(f"Vendor {vendor_name} screening failed: {e}")
                    vendor_responses[vendor_name] = {"error": str(e)}
        
        return vendor_responses
    
    def _call_vendor_api(self, vendor_name: str, data: Dict[str, Any]) -> Dict:
        """Call vendor screening API"""
        # Mock vendor API call
        # In production, this would make actual HTTP requests
        
        logger.info(f"Calling vendor API: {vendor_name}")
        
        # Simulate API response
        mock_response = {
            "status": "completed",
            "matches": [],
            "risk_score": 0.1,
            "screening_id": hashlib.md5(f"{vendor_name}{data}".encode()).hexdigest()[:16]
        }
        
        return mock_response
    
    def _parse_vendor_responses(self, vendor_responses: Dict[str, Any]) -> Tuple[List[ScreeningHit], List[ScreeningHit], List[AdverseMediaHit]]:
        """Parse and consolidate vendor responses"""
        sanctions = []
        peps = []
        media = []
        
        for vendor, response in vendor_responses.items():
            if "error" not in response and "matches" in response:
                for match in response.get("matches", []):
                    # Parse vendor-specific format
                    # This would be customized per vendor
                    pass
        
        return sanctions, peps, media
    
    def _match_names(self, name1: str, name2: str) -> Tuple[float, MatchType]:
        """Match two names and return score and match type"""
        # Normalize names
        name1_norm = self._normalize_name(name1)
        name2_norm = self._normalize_name(name2)
        
        # Exact match
        if name1_norm == name2_norm:
            return 1.0, MatchType.EXACT
        
        # Fuzzy match
        fuzzy_score = fuzz.token_sort_ratio(name1_norm, name2_norm) / 100.0
        
        # Partial match
        partial_score = fuzz.partial_ratio(name1_norm, name2_norm) / 100.0
        
        # Phonetic match (simplified)
        phonetic_score = self._phonetic_match(name1_norm, name2_norm)
        
        # Return best score
        scores = [
            (fuzzy_score, MatchType.FUZZY),
            (partial_score, MatchType.PARTIAL),
            (phonetic_score, MatchType.PHONETIC)
        ]
        
        best_score, match_type = max(scores, key=lambda x: x[0])
        
        return best_score, match_type
    
    def _normalize_name(self, name: str) -> str:
        """Normalize name for matching"""
        # Remove special characters and extra spaces
        normalized = re.sub(r'[^\w\s]', '', name)
        normalized = ' '.join(normalized.split())
        return normalized.upper()
    
    def _phonetic_match(self, name1: str, name2: str) -> float:
        """Simple phonetic matching"""
        # In production, use algorithms like Soundex, Metaphone, or Double Metaphone
        # This is a simplified version
        
        # Remove vowels for basic phonetic comparison
        def remove_vowels(s):
            return re.sub(r'[AEIOU]', '', s)
        
        name1_phonetic = remove_vowels(name1)
        name2_phonetic = remove_vowels(name2)
        
        if name1_phonetic == name2_phonetic:
            return 0.9
        
        # Calculate similarity
        return difflib.SequenceMatcher(None, name1_phonetic, name2_phonetic).ratio()
    
    def _calculate_overall_risk(self, sanctions_hits: List[ScreeningHit],
                               pep_hits: List[ScreeningHit],
                               adverse_hits: List[AdverseMediaHit]) -> RiskLevel:
        """Calculate overall risk level from all hits"""
        if not sanctions_hits and not pep_hits and not adverse_hits:
            return RiskLevel.MINIMAL
        
        # Sanctions are highest risk
        if sanctions_hits:
            max_sanction_score = max(h.match_score for h in sanctions_hits)
            if max_sanction_score > 0.9:
                return RiskLevel.CRITICAL
            elif max_sanction_score > 0.7:
                return RiskLevel.HIGH
        
        # PEP risk
        if pep_hits:
            max_pep_score = max(h.match_score for h in pep_hits)
            current_pep = any(h.metadata.get("is_current", False) for h in pep_hits)
            
            if current_pep and max_pep_score > 0.8:
                return RiskLevel.HIGH
            elif max_pep_score > 0.7:
                return RiskLevel.MEDIUM
        
        # Adverse media risk
        if adverse_hits:
            high_risk_categories = ["terrorism", "fraud", "corruption", "money_laundering"]
            has_high_risk = any(
                any(cat in hit.risk_categories for cat in high_risk_categories)
                for hit in adverse_hits
            )
            
            if has_high_risk:
                return RiskLevel.MEDIUM
        
        return RiskLevel.LOW
    
    def _generate_explanations(self, sanctions_hits: List[ScreeningHit],
                              pep_hits: List[ScreeningHit],
                              adverse_hits: List[AdverseMediaHit],
                              overall_risk: RiskLevel) -> List[str]:
        """Generate human-readable explanations"""
        explanations = []
        
        if sanctions_hits:
            explanations.append(f"Found {len(sanctions_hits)} potential sanctions match(es)")
            best_match = max(sanctions_hits, key=lambda h: h.match_score)
            explanations.append(f"Highest sanctions match: {best_match.entity_name} "
                              f"({best_match.match_score:.0%} confidence)")
        
        if pep_hits:
            explanations.append(f"Found {len(pep_hits)} PEP match(es)")
            current_peps = [h for h in pep_hits if h.metadata.get("is_current", False)]
            if current_peps:
                explanations.append(f"{len(current_peps)} current PEP position(s) identified")
        
        if adverse_hits:
            explanations.append(f"Found {len(adverse_hits)} adverse media article(s)")
            categories = set()
            for hit in adverse_hits:
                categories.update(hit.risk_categories)
            if categories:
                explanations.append(f"Risk categories: {', '.join(categories)}")
        
        if overall_risk == RiskLevel.MINIMAL:
            explanations.append("No significant AML/sanctions risks identified")
        elif overall_risk == RiskLevel.CRITICAL:
            explanations.append("CRITICAL: Immediate review required - potential sanctions match")
        
        return explanations
    
    def _generate_request_id(self) -> str:
        """Generate unique request ID"""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        random_part = hashlib.md5(str(datetime.now().timestamp()).encode()).hexdigest()[:8]
        return f"AML-{timestamp}-{random_part}"
    
    def _generate_cache_key(self, individual_data: Dict[str, Any]) -> str:
        """Generate cache key for individual"""
        key_parts = [
            individual_data.get("name", ""),
            individual_data.get("date_of_birth", ""),
            individual_data.get("nationality", "")
        ]
        return hashlib.sha256("".join(key_parts).encode()).hexdigest()
    
    def _is_cache_valid(self, cached_entry: Dict) -> bool:
        """Check if cached entry is still valid"""
        if not self.config["false_positive_handling"]["enable_cache"]:
            return False
        
        cache_duration = self.config["false_positive_handling"]["cache_duration_days"]
        cache_timestamp = cached_entry.get("timestamp")
        
        if cache_timestamp:
            age_days = (datetime.now() - cache_timestamp).days
            return age_days < cache_duration
        
        return False
    
    def mark_false_positive(self, hit_id: str, reason: str, 
                           approved_by: str) -> bool:
        """
        Mark a hit as false positive
        
        Args:
            hit_id: Hit identifier
            reason: Reason for marking as false positive
            approved_by: Approver ID
            
        Returns:
            Success status
        """
        if not self.config["false_positive_handling"]["require_approval"]:
            logger.warning("False positive marking requires approval")
            return False
        
        # Log the false positive
        logger.info(f"Marking hit {hit_id} as false positive. "
                   f"Reason: {reason}, Approved by: {approved_by}")
        
        # Update cache or database
        # In production, this would update a persistent store
        
        return True
    
    def monitor_continuous(self, individual_id: str, 
                          individual_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Set up continuous monitoring for an individual
        
        Args:
            individual_id: Unique individual identifier
            individual_data: Individual information
            
        Returns:
            Monitoring setup confirmation
        """
        if not self.config["continuous_monitoring"]["enabled"]:
            return {"status": "disabled", "message": "Continuous monitoring is not enabled"}
        
        # In production, this would register the individual for periodic re-screening
        monitoring_config = {
            "individual_id": individual_id,
            "frequency_days": self.config["continuous_monitoring"]["frequency_days"],
            "alert_on_new_hits": self.config["continuous_monitoring"]["alert_on_new_hits"],
            "last_screened": datetime.now().isoformat(),
            "next_screening": (
                datetime.now() + 
                timedelta(days=self.config["continuous_monitoring"]["frequency_days"])
            ).isoformat()
        }
        
        logger.info(f"Continuous monitoring enabled for {individual_id}")
        
        return {
            "status": "active",
            "config": monitoring_config
        }

# Export main components
__all__ = [
    "AMLScreener",
    "ScreeningResult",
    "ScreeningHit",
    "SanctionedEntity",
    "PEPEntity",
    "AdverseMediaHit",
    "ScreeningType",
    "MatchType",
    "RiskLevel"
]