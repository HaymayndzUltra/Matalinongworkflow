"""
Vendor Orchestrator Module
Phase 10: Multi-vendor orchestration with circuit breakers, failover, retry logic
SLA monitoring, cost optimization, and vendor performance tracking
"""

import json
import logging
import time
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
from collections import deque, defaultdict
import random
from pathlib import Path
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VendorStatus(Enum):
    """Vendor availability status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    CIRCUIT_OPEN = "circuit_open"
    MAINTENANCE = "maintenance"

class RequestPriority(Enum):
    """Request priority levels"""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4

class VendorCapability(Enum):
    """Vendor service capabilities"""
    OCR = "ocr"
    FACE_MATCH = "face_match"
    LIVENESS = "liveness"
    DOCUMENT_VERIFY = "document_verify"
    AML_SCREEN = "aml_screen"
    ADDRESS_VERIFY = "address_verify"
    PHONE_VERIFY = "phone_verify"

@dataclass
class VendorConfig:
    """Vendor configuration"""
    vendor_id: str
    name: str
    base_url: str
    api_key: str
    capabilities: List[VendorCapability]
    priority: int  # Lower is higher priority
    cost_per_request: float
    timeout_seconds: int
    max_retries: int
    rate_limit: int  # requests per minute
    sla_target_ms: int
    circuit_breaker_threshold: float
    circuit_breaker_timeout: int

@dataclass
class CircuitBreaker:
    """Circuit breaker for vendor"""
    vendor_id: str
    failure_count: int = 0
    success_count: int = 0
    last_failure_time: Optional[datetime] = None
    state: VendorStatus = VendorStatus.HEALTHY
    open_until: Optional[datetime] = None
    
    def record_success(self):
        """Record successful request"""
        self.success_count += 1
        self.failure_count = max(0, self.failure_count - 1)
        
        if self.state == VendorStatus.CIRCUIT_OPEN:
            if self.success_count >= 3:  # Required successes to close circuit
                self.state = VendorStatus.HEALTHY
                self.open_until = None
                logger.info(f"Circuit closed for vendor {self.vendor_id}")
    
    def record_failure(self):
        """Record failed request"""
        self.failure_count += 1
        self.success_count = 0
        self.last_failure_time = datetime.now()
    
    def should_open(self, threshold: float) -> bool:
        """Check if circuit should open"""
        if self.failure_count >= threshold:
            return True
        
        # Check failure rate in time window
        if self.failure_count > 5 and self.last_failure_time:
            time_since_failure = (datetime.now() - self.last_failure_time).seconds
            if time_since_failure < 60:  # Within 1 minute
                return True
        
        return False
    
    def open_circuit(self, timeout_seconds: int):
        """Open the circuit breaker"""
        self.state = VendorStatus.CIRCUIT_OPEN
        self.open_until = datetime.now() + timedelta(seconds=timeout_seconds)
        logger.warning(f"Circuit opened for vendor {self.vendor_id} until {self.open_until}")
    
    def is_open(self) -> bool:
        """Check if circuit is currently open"""
        if self.state == VendorStatus.CIRCUIT_OPEN:
            if self.open_until and datetime.now() > self.open_until:
                # Allow half-open state for testing
                self.state = VendorStatus.DEGRADED
                return False
            return True
        return False

@dataclass
class VendorMetrics:
    """Vendor performance metrics"""
    vendor_id: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0
    response_times: deque = field(default_factory=lambda: deque(maxlen=100))
    error_types: Dict[str, int] = field(default_factory=dict)
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    
    def record_request(self, success: bool, latency_ms: float, error_type: Optional[str] = None):
        """Record request metrics"""
        self.total_requests += 1
        self.total_latency_ms += latency_ms
        self.response_times.append(latency_ms)
        
        if success:
            self.successful_requests += 1
            self.last_success = datetime.now()
        else:
            self.failed_requests += 1
            self.last_failure = datetime.now()
            if error_type:
                self.error_types[error_type] = self.error_types.get(error_type, 0) + 1
    
    @property
    def success_rate(self) -> float:
        """Calculate success rate"""
        if self.total_requests == 0:
            return 1.0
        return self.successful_requests / self.total_requests
    
    @property
    def average_latency(self) -> float:
        """Calculate average latency"""
        if self.total_requests == 0:
            return 0
        return self.total_latency_ms / self.total_requests
    
    @property
    def p95_latency(self) -> float:
        """Calculate 95th percentile latency"""
        if not self.response_times:
            return 0
        sorted_times = sorted(self.response_times)
        index = int(len(sorted_times) * 0.95)
        return sorted_times[min(index, len(sorted_times) - 1)]

@dataclass
class VendorResponse:
    """Vendor API response"""
    vendor_id: str
    success: bool
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    latency_ms: float
    timestamp: datetime
    retry_count: int

class VendorOrchestrator:
    """Orchestrates multi-vendor API calls with reliability"""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize vendor orchestrator"""
        self.config = self._load_config(config_path)
        self.vendors = self._load_vendors()
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        self.metrics: Dict[str, VendorMetrics] = {}
        self.rate_limiters: Dict[str, deque] = {}
        
        # Initialize circuit breakers and metrics
        for vendor in self.vendors.values():
            self.circuit_breakers[vendor.vendor_id] = CircuitBreaker(vendor.vendor_id)
            self.metrics[vendor.vendor_id] = VendorMetrics(vendor.vendor_id)
            self.rate_limiters[vendor.vendor_id] = deque(maxlen=vendor.rate_limit)
    
    def _load_config(self, config_path: Optional[str]) -> Dict:
        """Load orchestrator configuration"""
        default_config = {
            "strategy": {
                "primary_vendor": "vendor_a",
                "failover_enabled": True,
                "parallel_requests": False,
                "consensus_required": False,
                "min_consensus_vendors": 2
            },
            "circuit_breaker": {
                "enabled": True,
                "failure_threshold": 5,
                "timeout_seconds": 60,
                "half_open_requests": 3
            },
            "retry": {
                "max_retries": 3,
                "backoff_base": 2,
                "backoff_max": 30
            },
            "performance": {
                "sla_alert_threshold": 0.95,
                "latency_alert_p95": 5000,
                "cost_optimization": True
            },
            "monitoring": {
                "metrics_interval_seconds": 60,
                "health_check_interval": 30,
                "alert_channels": ["email", "slack"]
            }
        }
        
        if config_path and Path(config_path).exists():
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                default_config.update(user_config)
        
        return default_config
    
    def _load_vendors(self) -> Dict[str, VendorConfig]:
        """Load vendor configurations"""
        vendors = {
            "vendor_a": VendorConfig(
                vendor_id="vendor_a",
                name="Primary Vendor A",
                base_url="https://api.vendor-a.com",
                api_key="key_a",
                capabilities=[
                    VendorCapability.OCR,
                    VendorCapability.FACE_MATCH,
                    VendorCapability.DOCUMENT_VERIFY
                ],
                priority=1,
                cost_per_request=0.10,
                timeout_seconds=30,
                max_retries=3,
                rate_limit=100,
                sla_target_ms=2000,
                circuit_breaker_threshold=5,
                circuit_breaker_timeout=60
            ),
            "vendor_b": VendorConfig(
                vendor_id="vendor_b",
                name="Secondary Vendor B",
                base_url="https://api.vendor-b.com",
                api_key="key_b",
                capabilities=[
                    VendorCapability.OCR,
                    VendorCapability.FACE_MATCH,
                    VendorCapability.LIVENESS,
                    VendorCapability.AML_SCREEN
                ],
                priority=2,
                cost_per_request=0.08,
                timeout_seconds=25,
                max_retries=3,
                rate_limit=150,
                sla_target_ms=1500,
                circuit_breaker_threshold=5,
                circuit_breaker_timeout=60
            ),
            "vendor_c": VendorConfig(
                vendor_id="vendor_c",
                name="Tertiary Vendor C",
                base_url="https://api.vendor-c.com",
                api_key="key_c",
                capabilities=[
                    VendorCapability.AML_SCREEN,
                    VendorCapability.ADDRESS_VERIFY,
                    VendorCapability.PHONE_VERIFY
                ],
                priority=3,
                cost_per_request=0.05,
                timeout_seconds=20,
                max_retries=2,
                rate_limit=200,
                sla_target_ms=1000,
                circuit_breaker_threshold=10,
                circuit_breaker_timeout=30
            )
        }
        
        return vendors
    
    async def execute_request(self, capability: VendorCapability,
                             request_data: Dict[str, Any],
                             priority: RequestPriority = RequestPriority.NORMAL) -> VendorResponse:
        """
        Execute request with vendor orchestration
        
        Args:
            capability: Required vendor capability
            request_data: Request payload
            priority: Request priority
            
        Returns:
            Vendor response with data or error
        """
        start_time = time.time()
        
        # Get capable vendors sorted by priority
        capable_vendors = self._get_capable_vendors(capability)
        
        if not capable_vendors:
            return VendorResponse(
                vendor_id="none",
                success=False,
                data=None,
                error=f"No vendors available for capability: {capability.value}",
                latency_ms=0,
                timestamp=datetime.now(),
                retry_count=0
            )
        
        # Try vendors in priority order with failover
        last_error = None
        
        for vendor in capable_vendors:
            # Check circuit breaker
            if self._is_vendor_available(vendor.vendor_id):
                try:
                    response = await self._call_vendor(
                        vendor,
                        capability,
                        request_data,
                        priority
                    )
                    
                    if response.success:
                        return response
                    else:
                        last_error = response.error
                        
                except Exception as e:
                    logger.error(f"Error calling vendor {vendor.vendor_id}: {e}")
                    last_error = str(e)
                    
                    # Record failure for circuit breaker
                    self.circuit_breakers[vendor.vendor_id].record_failure()
                    
                    # Check if circuit should open
                    if self.circuit_breakers[vendor.vendor_id].should_open(
                        vendor.circuit_breaker_threshold
                    ):
                        self.circuit_breakers[vendor.vendor_id].open_circuit(
                            vendor.circuit_breaker_timeout
                        )
        
        # All vendors failed
        elapsed_ms = (time.time() - start_time) * 1000
        
        return VendorResponse(
            vendor_id="failover_exhausted",
            success=False,
            data=None,
            error=f"All vendors failed. Last error: {last_error}",
            latency_ms=elapsed_ms,
            timestamp=datetime.now(),
            retry_count=0
        )
    
    async def _call_vendor(self, vendor: VendorConfig,
                          capability: VendorCapability,
                          request_data: Dict[str, Any],
                          priority: RequestPriority) -> VendorResponse:
        """
        Call specific vendor with retry logic
        
        Args:
            vendor: Vendor configuration
            capability: Required capability
            request_data: Request payload
            priority: Request priority
            
        Returns:
            Vendor response
        """
        # Check rate limit
        if not self._check_rate_limit(vendor.vendor_id):
            await asyncio.sleep(1)  # Wait if rate limited
        
        retry_count = 0
        backoff = 1
        
        while retry_count <= vendor.max_retries:
            start_time = time.time()
            
            try:
                # Make API call
                response_data = await self._make_api_call(
                    vendor,
                    capability,
                    request_data
                )
                
                elapsed_ms = (time.time() - start_time) * 1000
                
                # Record success
                self.circuit_breakers[vendor.vendor_id].record_success()
                self.metrics[vendor.vendor_id].record_request(True, elapsed_ms)
                
                # Check SLA
                if elapsed_ms > vendor.sla_target_ms:
                    logger.warning(f"Vendor {vendor.vendor_id} exceeded SLA: "
                                 f"{elapsed_ms:.0f}ms > {vendor.sla_target_ms}ms")
                
                return VendorResponse(
                    vendor_id=vendor.vendor_id,
                    success=True,
                    data=response_data,
                    error=None,
                    latency_ms=elapsed_ms,
                    timestamp=datetime.now(),
                    retry_count=retry_count
                )
                
            except asyncio.TimeoutError:
                error_type = "timeout"
                error_msg = f"Request timeout after {vendor.timeout_seconds}s"
                
            except Exception as e:
                error_type = type(e).__name__
                error_msg = str(e)
            
            # Record failure
            elapsed_ms = (time.time() - start_time) * 1000
            self.circuit_breakers[vendor.vendor_id].record_failure()
            self.metrics[vendor.vendor_id].record_request(False, elapsed_ms, error_type)
            
            # Retry with exponential backoff
            retry_count += 1
            if retry_count <= vendor.max_retries:
                wait_time = min(backoff, self.config["retry"]["backoff_max"])
                logger.info(f"Retrying vendor {vendor.vendor_id} in {wait_time}s "
                          f"(attempt {retry_count}/{vendor.max_retries})")
                await asyncio.sleep(wait_time)
                backoff *= self.config["retry"]["backoff_base"]
            
        # All retries exhausted
        return VendorResponse(
            vendor_id=vendor.vendor_id,
            success=False,
            data=None,
            error=error_msg,
            latency_ms=elapsed_ms,
            timestamp=datetime.now(),
            retry_count=retry_count
        )
    
    async def _make_api_call(self, vendor: VendorConfig,
                           capability: VendorCapability,
                           request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Make actual API call to vendor
        
        Args:
            vendor: Vendor configuration
            capability: Required capability
            request_data: Request payload
            
        Returns:
            Response data
        """
        # Map capability to endpoint
        endpoint_map = {
            VendorCapability.OCR: "/ocr",
            VendorCapability.FACE_MATCH: "/face/match",
            VendorCapability.LIVENESS: "/face/liveness",
            VendorCapability.DOCUMENT_VERIFY: "/document/verify",
            VendorCapability.AML_SCREEN: "/aml/screen",
            VendorCapability.ADDRESS_VERIFY: "/address/verify",
            VendorCapability.PHONE_VERIFY: "/phone/verify"
        }
        
        endpoint = endpoint_map.get(capability, "/")
        url = f"{vendor.base_url}{endpoint}"
        
        headers = {
            "Authorization": f"Bearer {vendor.api_key}",
            "Content-Type": "application/json"
        }
        
        # Simulate API call (in production, use actual HTTP client)
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=request_data,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=vendor.timeout_seconds)
            ) as response:
                if response.status == 200:
                    return await response.json()
                else:
                    raise Exception(f"API error: {response.status}")
    
    def _get_capable_vendors(self, capability: VendorCapability) -> List[VendorConfig]:
        """Get vendors capable of handling the request"""
        capable = []
        
        for vendor in self.vendors.values():
            if capability in vendor.capabilities:
                # Check if vendor is healthy
                if self._is_vendor_available(vendor.vendor_id):
                    capable.append(vendor)
        
        # Sort by priority (lower is better)
        capable.sort(key=lambda v: v.priority)
        
        # Apply cost optimization if enabled
        if self.config["performance"]["cost_optimization"]:
            capable = self._optimize_by_cost(capable)
        
        return capable
    
    def _is_vendor_available(self, vendor_id: str) -> bool:
        """Check if vendor is available"""
        circuit_breaker = self.circuit_breakers.get(vendor_id)
        
        if not circuit_breaker:
            return True
        
        # Check circuit breaker state
        if circuit_breaker.is_open():
            return False
        
        # Check vendor metrics
        metrics = self.metrics.get(vendor_id)
        if metrics and metrics.success_rate < 0.5 and metrics.total_requests > 10:
            return False
        
        return True
    
    def _check_rate_limit(self, vendor_id: str) -> bool:
        """Check if request is within rate limit"""
        rate_limiter = self.rate_limiters.get(vendor_id)
        vendor = self.vendors.get(vendor_id)
        
        if not rate_limiter or not vendor:
            return True
        
        # Clean old entries
        current_time = time.time()
        while rate_limiter and rate_limiter[0] < current_time - 60:
            rate_limiter.popleft()
        
        # Check if under limit
        if len(rate_limiter) < vendor.rate_limit:
            rate_limiter.append(current_time)
            return True
        
        return False
    
    def _optimize_by_cost(self, vendors: List[VendorConfig]) -> List[VendorConfig]:
        """Optimize vendor selection by cost"""
        # Balance between cost and performance
        scored_vendors = []
        
        for vendor in vendors:
            metrics = self.metrics.get(vendor.vendor_id)
            
            if metrics:
                # Calculate score based on cost and performance
                cost_score = 1 / (vendor.cost_per_request + 0.01)
                performance_score = metrics.success_rate
                latency_score = 1 / (metrics.average_latency / 1000 + 1)
                
                total_score = (
                    cost_score * 0.4 +
                    performance_score * 0.4 +
                    latency_score * 0.2
                )
            else:
                # Default score for new vendors
                total_score = 1 / (vendor.cost_per_request + 0.01)
            
            scored_vendors.append((vendor, total_score))
        
        # Sort by score (higher is better)
        scored_vendors.sort(key=lambda x: x[1], reverse=True)
        
        return [vendor for vendor, _ in scored_vendors]
    
    def get_vendor_health(self) -> Dict[str, Dict[str, Any]]:
        """Get health status of all vendors"""
        health_status = {}
        
        for vendor_id, vendor in self.vendors.items():
            circuit_breaker = self.circuit_breakers.get(vendor_id)
            metrics = self.metrics.get(vendor_id)
            
            status = {
                "name": vendor.name,
                "status": circuit_breaker.state.value if circuit_breaker else "unknown",
                "available": self._is_vendor_available(vendor_id),
                "capabilities": [c.value for c in vendor.capabilities],
                "metrics": {}
            }
            
            if metrics:
                status["metrics"] = {
                    "total_requests": metrics.total_requests,
                    "success_rate": f"{metrics.success_rate:.2%}",
                    "average_latency_ms": f"{metrics.average_latency:.0f}",
                    "p95_latency_ms": f"{metrics.p95_latency:.0f}",
                    "last_success": metrics.last_success.isoformat() if metrics.last_success else None,
                    "last_failure": metrics.last_failure.isoformat() if metrics.last_failure else None
                }
            
            if circuit_breaker and circuit_breaker.state == VendorStatus.CIRCUIT_OPEN:
                status["circuit_open_until"] = circuit_breaker.open_until.isoformat()
            
            health_status[vendor_id] = status
        
        return health_status
    
    def get_cost_report(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Generate cost report for date range"""
        total_cost = 0
        vendor_costs = {}
        
        for vendor_id, vendor in self.vendors.items():
            metrics = self.metrics.get(vendor_id)
            
            if metrics:
                vendor_cost = metrics.total_requests * vendor.cost_per_request
                total_cost += vendor_cost
                
                vendor_costs[vendor_id] = {
                    "vendor_name": vendor.name,
                    "requests": metrics.total_requests,
                    "cost_per_request": vendor.cost_per_request,
                    "total_cost": vendor_cost,
                    "success_rate": metrics.success_rate
                }
        
        return {
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "total_cost": total_cost,
            "vendor_breakdown": vendor_costs,
            "cost_optimization_enabled": self.config["performance"]["cost_optimization"]
        }

    # --- Convenience sync wrappers expected by API layer ---
    def verify_with_issuer(
        self,
        document_type: str,
        document_number: str,
        personal_info: Dict[str, Any],
        adapter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Synchronous convenience method for issuer verification expected by /issuer/verify endpoint.
        Returns a normalized dict: {verified, match_score, issuer_response}.
        """
        # In this demo implementation, we do not call real issuers. We simulate a result
        # and return a stable structure for the API response model.
        normalized_number = (document_number or "").strip().upper()
        heuristic_ok = bool(normalized_number) and len(normalized_number) >= 6
        match_score = 0.85 if heuristic_ok else 0.3
        verified = heuristic_ok and normalized_number[0].isalpha()

        issuer_response: Dict[str, Any] = {
            "document_type": document_type,
            "document_number": document_number,
            "personal_info": personal_info or {},
            "adapter": adapter or "default_adapter",
            "notes": "Demo verification (stub)",
        }

        return {
            "verified": bool(verified),
            "match_score": float(match_score),
            "issuer_response": issuer_response,
        }
    
    async def health_check(self) -> Dict[str, bool]:
        """Perform health check on all vendors"""
        health_results = {}
        
        for vendor_id, vendor in self.vendors.items():
            try:
                # Simple health check request
                response = await self._make_api_call(
                    vendor,
                    VendorCapability.OCR,  # Use any capability
                    {"health_check": True}
                )
                health_results[vendor_id] = True
            except:
                health_results[vendor_id] = False
        
        return health_results

# Export main components
__all__ = [
    "VendorOrchestrator",
    "VendorConfig",
    "VendorResponse",
    "VendorCapability",
    "VendorStatus",
    "RequestPriority",
    "CircuitBreaker",
    "VendorMetrics"
]