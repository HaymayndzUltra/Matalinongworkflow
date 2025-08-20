import os
from typing import Optional

from fastapi import FastAPI

try:
    from opentelemetry import trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter  # type: ignore
        _HAS_OTLP = True
    except Exception:  # pragma: no cover
        OTLPSpanExporter = None  # type: ignore
        _HAS_OTLP = False
except Exception:  # pragma: no cover
    trace = None  # type: ignore
    FastAPIInstrumentor = None  # type: ignore


def setup_tracing(app: FastAPI) -> None:
    """Configure OpenTelemetry tracing for FastAPI if available.

    Uses OTLP exporter when OTEL_EXPORTER_OTLP_ENDPOINT is set and exporter is available,
    otherwise falls back to console exporter for local debugging.
    """
    if trace is None or FastAPIInstrumentor is None:
        return

    service_name = os.getenv("OTEL_SERVICE_NAME", "kyc-api")
    res = Resource.create({"service.name": service_name})
    provider = TracerProvider(resource=res)

    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    if endpoint and _HAS_OTLP:
        exporter = OTLPSpanExporter(endpoint=endpoint)
    else:
        exporter = ConsoleSpanExporter()

    span_processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(span_processor)
    trace.set_tracer_provider(provider)

    # Instrument FastAPI app
    FastAPIInstrumentor.instrument_app(app)
