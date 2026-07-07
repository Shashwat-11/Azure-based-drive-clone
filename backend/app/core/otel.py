from __future__ import annotations

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased

from app.config.settings import settings
from app.core.logging_config import get_logger

logger = get_logger(__name__)

_tracer_provider: TracerProvider | None = None


def setup_otel() -> None:
    global _tracer_provider

    if not settings.OTEL_ENABLED:
        logger.info("otel_disabled")
        return

    resource = Resource.create({SERVICE_NAME: settings.APP_NAME})

    exporter = OTLPSpanExporter(
        endpoint="https://dc.services.visualstudio.com/v2/track"
        if settings.AZURE_APPINSIGHTS_CONNECTION_STRING else None,
    )

    processor = BatchSpanProcessor(exporter)
    _tracer_provider = TracerProvider(
        resource=resource,
        sampler=TraceIdRatioBased(settings.OTEL_SAMPLING_RATE),
    )
    _tracer_provider.add_span_processor(processor)
    trace.set_tracer_provider(_tracer_provider)
    logger.info("otel_initialized", sampling_rate=settings.OTEL_SAMPLING_RATE)


def shutdown_otel() -> None:
    global _tracer_provider
    if _tracer_provider is not None:
        _tracer_provider.shutdown()
        _tracer_provider = None
        logger.info("otel_shutdown")


def get_tracer(name: str = "drive-api") -> trace.Tracer:
    return trace.get_tracer(name)
