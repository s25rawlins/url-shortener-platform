"""Shared observability utilities for OpenTelemetry, logging, and metrics."""

import os
import logging
import json
import time
from typing import Dict, Any, Optional
from contextlib import contextmanager
from functools import wraps

from opentelemetry import trace, metrics
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.kafka import KafkaInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor


class StructuredLogger:
    """Structured JSON logger with trace correlation."""
    
    def __init__(self, service_name: str, log_level: str = "INFO"):
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Remove existing handlers
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
        
        # Add structured handler
        handler = logging.StreamHandler()
        handler.setFormatter(self._get_formatter())
        self.logger.addHandler(handler)
    
    def _get_formatter(self):
        """Get JSON formatter with trace correlation."""
        class JSONFormatter(logging.Formatter):
            def format(self, record):
                log_entry = {
                    "timestamp": self.formatTime(record),
                    "level": record.levelname,
                    "service": record.name,
                    "message": record.getMessage(),
                    "module": record.module,
                    "function": record.funcName,
                    "line": record.lineno,
                }
                
                # Add trace context if available
                span = trace.get_current_span()
                if span and span.is_recording():
                    span_context = span.get_span_context()
                    log_entry.update({
                        "trace_id": format(span_context.trace_id, "032x"),
                        "span_id": format(span_context.span_id, "016x"),
                    })
                
                # Add extra fields
                if hasattr(record, 'extra'):
                    log_entry.update(record.extra)
                
                return json.dumps(log_entry)
        
        return JSONFormatter()
    
    def info(self, message: str, **kwargs):
        """Log info message with extra fields."""
        self.logger.info(message, extra=kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message with extra fields."""
        self.logger.error(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message with extra fields."""
        self.logger.warning(message, extra=kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message with extra fields."""
        self.logger.debug(message, extra=kwargs)


class ObservabilityManager:
    """Centralized observability setup and management."""
    
    def __init__(self, service_name: str, service_version: str = "1.0.0"):
        self.service_name = service_name
        self.service_version = service_version
        self.tracer = None
        self.meter = None
        self.logger = None
        self._initialized = False
    
    def initialize(self):
        """Initialize all observability components."""
        if self._initialized:
            return
        
        # Setup resource
        resource = Resource.create({
            "service.name": self.service_name,
            "service.version": self.service_version,
            "service.instance.id": os.getenv("HOSTNAME", "unknown"),
        })
        
        # Setup tracing
        self._setup_tracing(resource)
        
        # Setup metrics
        self._setup_metrics(resource)
        
        # Setup logging
        self._setup_logging()
        
        # Setup auto-instrumentation
        self._setup_auto_instrumentation()
        
        self._initialized = True
    
    def _setup_tracing(self, resource: Resource):
        """Setup OpenTelemetry tracing."""
        trace_provider = TracerProvider(resource=resource)
        
        # OTLP exporter
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otlp_endpoint:
            otlp_exporter = OTLPSpanExporter(
                endpoint=otlp_endpoint,
                insecure=os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "false").lower() == "true"
            )
            trace_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        
        trace.set_tracer_provider(trace_provider)
        self.tracer = trace.get_tracer(self.service_name, self.service_version)
    
    def _setup_metrics(self, resource: Resource):
        """Setup OpenTelemetry metrics."""
        otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
        if otlp_endpoint:
            metric_reader = PeriodicExportingMetricReader(
                OTLPMetricExporter(
                    endpoint=otlp_endpoint,
                    insecure=os.getenv("OTEL_EXPORTER_OTLP_INSECURE", "false").lower() == "true"
                ),
                export_interval_millis=30000,
            )
            metrics.set_meter_provider(MeterProvider(resource=resource, metric_readers=[metric_reader]))
        
        self.meter = metrics.get_meter(self.service_name, self.service_version)
    
    def _setup_logging(self):
        """Setup structured logging."""
        log_level = os.getenv("LOG_LEVEL", "INFO")
        self.logger = StructuredLogger(self.service_name, log_level)
    
    def _setup_auto_instrumentation(self):
        """Setup automatic instrumentation for common libraries."""
        # FastAPI instrumentation will be done per app
        SQLAlchemyInstrumentor().instrument()
        RedisInstrumentor().instrument()
        RequestsInstrumentor().instrument()
        HTTPXClientInstrumentor().instrument()
        
        # Kafka instrumentation if available
        try:
            KafkaInstrumentor().instrument()
        except Exception:
            pass  # Kafka might not be available in all services
    
    def instrument_fastapi(self, app):
        """Instrument FastAPI application."""
        FastAPIInstrumentor.instrument_app(app, tracer_provider=trace.get_tracer_provider())
    
    def get_tracer(self):
        """Get tracer instance."""
        if not self._initialized:
            self.initialize()
        return self.tracer
    
    def get_meter(self):
        """Get meter instance."""
        if not self._initialized:
            self.initialize()
        return self.meter
    
    def get_logger(self):
        """Get logger instance."""
        if not self._initialized:
            self.initialize()
        return self.logger


# Global observability manager
_observability_manager: Optional[ObservabilityManager] = None


def get_observability_manager(service_name: str) -> ObservabilityManager:
    """Get global observability manager instance."""
    global _observability_manager
    if _observability_manager is None:
        _observability_manager = ObservabilityManager(service_name)
        _observability_manager.initialize()
    return _observability_manager


def trace_function(operation_name: Optional[str] = None):
    """Decorator to trace function execution."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            span_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            with tracer.start_as_current_span(span_name) as span:
                try:
                    # Add function metadata
                    span.set_attribute("function.name", func.__name__)
                    span.set_attribute("function.module", func.__module__)
                    
                    result = await func(*args, **kwargs)
                    span.set_attribute("function.result", "success")
                    return result
                except Exception as e:
                    span.set_attribute("function.result", "error")
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracer = trace.get_tracer(__name__)
            span_name = operation_name or f"{func.__module__}.{func.__name__}"
            
            with tracer.start_as_current_span(span_name) as span:
                try:
                    # Add function metadata
                    span.set_attribute("function.name", func.__name__)
                    span.set_attribute("function.module", func.__module__)
                    
                    result = func(*args, **kwargs)
                    span.set_attribute("function.result", "success")
                    return result
                except Exception as e:
                    span.set_attribute("function.result", "error")
                    span.set_attribute("error.type", type(e).__name__)
                    span.set_attribute("error.message", str(e))
                    raise
        
        return async_wrapper if hasattr(func, '__code__') and func.__code__.co_flags & 0x80 else sync_wrapper
    return decorator


@contextmanager
def trace_operation(operation_name: str, attributes: Optional[Dict[str, Any]] = None):
    """Context manager for tracing operations."""
    tracer = trace.get_tracer(__name__)
    
    with tracer.start_as_current_span(operation_name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        
        start_time = time.time()
        try:
            yield span
            span.set_attribute("operation.duration_ms", (time.time() - start_time) * 1000)
            span.set_attribute("operation.result", "success")
        except Exception as e:
            span.set_attribute("operation.duration_ms", (time.time() - start_time) * 1000)
            span.set_attribute("operation.result", "error")
            span.set_attribute("error.type", type(e).__name__)
            span.set_attribute("error.message", str(e))
            raise


class MetricsCollector:
    """Helper class for collecting custom metrics."""
    
    def __init__(self, meter):
        self.meter = meter
        self._counters = {}
        self._histograms = {}
        self._gauges = {}
    
    def get_counter(self, name: str, description: str = ""):
        """Get or create a counter metric."""
        if name not in self._counters:
            self._counters[name] = self.meter.create_counter(
                name=name,
                description=description,
                unit="1"
            )
        return self._counters[name]
    
    def get_histogram(self, name: str, description: str = "", unit: str = "ms"):
        """Get or create a histogram metric."""
        if name not in self._histograms:
            self._histograms[name] = self.meter.create_histogram(
                name=name,
                description=description,
                unit=unit
            )
        return self._histograms[name]
    
    def get_gauge(self, name: str, description: str = ""):
        """Get or create a gauge metric."""
        if name not in self._gauges:
            self._gauges[name] = self.meter.create_up_down_counter(
                name=name,
                description=description,
                unit="1"
            )
        return self._gauges[name]
