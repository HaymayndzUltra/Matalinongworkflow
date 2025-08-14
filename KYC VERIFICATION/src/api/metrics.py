from typing import Optional
from prometheus_client import Counter, Histogram, Gauge, REGISTRY

# Request-level metrics
REQUEST_COUNTER = Counter(
    "kyc_requests_total",
    "Total HTTP requests",
    labelnames=("endpoint", "method", "status"),
)


# Risk and decision metrics
DECISION_COUNTER = Counter(
    "kyc_decisions_total",
    "Count of decisions by type",
    labelnames=("decision",),
)

RISK_SCORE_HIST = Histogram(
    "kyc_risk_score",
    "Distribution of risk scores (0-100)",
    buckets=(0, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100),
)

# Drift monitoring and fairness audit
RISK_DRIFT_SCORE = Gauge(
    "kyc_risk_drift_score",
    "Simple drift score based on moving mean difference (0..100)",
)

FAIRNESS_AUDIT_DUE = Gauge(
    "kyc_fairness_audit_due",
    "Indicator (0/1) if a scheduled fairness audit window is due",
)

REQUEST_LATENCY = Histogram(
    "kyc_request_latency_seconds",
    "Request latency in seconds",
    labelnames=("endpoint", "method"),
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 20, 60),
)

# Vendor orchestrator metrics
VENDOR_BREAKER_STATE = Gauge(
    "kyc_vendor_breaker_state",
    "Vendor circuit breaker state (0=healthy,1=degraded,2=open,3=maintenance)",
    labelnames=("vendor",),
)

VENDOR_SUCCESS_RATE = Gauge(
    "kyc_vendor_success_rate",
    "Vendor success rate (0..1)",
    labelnames=("vendor",),
)

VENDOR_P95_LATENCY_MS = Gauge(
    "kyc_vendor_p95_latency_ms",
    "Vendor p95 latency (ms)",
    labelnames=("vendor",),
)


def _status_to_code(state: str) -> int:
    table = {
        "healthy": 0,
        "degraded": 1,
        "circuit_open": 2,
        "maintenance": 3,
        "unhealthy": 1,  # treat as degraded numerically
    }
    return table.get(state.lower(), 1)


def update_vendor_metrics(orchestrator: Optional[object]) -> None:
    """Update vendor gauges from orchestrator state if available."""
    if orchestrator is None:
        return
    # Orchestrator attributes are accessed duck-typed to avoid import cycles
    breakers = getattr(orchestrator, "circuit_breakers", {})
    metrics = getattr(orchestrator, "metrics", {})

    for vendor_id, breaker in breakers.items():
        state = getattr(breaker, "state", None)
        state_value = _status_to_code(getattr(state, "value", str(state) or "degraded"))
        VENDOR_BREAKER_STATE.labels(vendor=vendor_id).set(state_value)

    for vendor_id, m in metrics.items():
        success_rate = getattr(m, "success_rate", 0.0)
        p95 = getattr(m, "p95_latency", 0.0)
        VENDOR_SUCCESS_RATE.labels(vendor=vendor_id).set(success_rate)
        VENDOR_P95_LATENCY_MS.labels(vendor=vendor_id).set(p95)


__all__ = [
    "REQUEST_COUNTER",
    "REQUEST_LATENCY",
    "VENDOR_BREAKER_STATE",
    "VENDOR_SUCCESS_RATE",
    "VENDOR_P95_LATENCY_MS",
    "DECISION_COUNTER",
    "RISK_SCORE_HIST",
    "RISK_DRIFT_SCORE",
    "FAIRNESS_AUDIT_DUE",
    "update_vendor_metrics",
    "REGISTRY",
]
