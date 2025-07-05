"""Custom middleware for the gateway service."""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import sys
sys.path.append('/app')
from shared.observability import get_observability_manager, trace
from shared.models import ErrorResponse


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Middleware to add request tracing and correlation IDs."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID") or str(uuid.uuid4())
        request.state.correlation_id = correlation_id
        
        # Add to trace context
        span = trace.get_current_span()
        if span and span.is_recording():
            span.set_attribute("http.correlation_id", correlation_id)
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("http.user_agent", request.headers.get("User-Agent", ""))
        
        # Process request
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        
        # Add headers to response
        response.headers["X-Correlation-ID"] = correlation_id
        response.headers["X-Process-Time"] = str(process_time)
        
        # Add response attributes to span
        if span and span.is_recording():
            span.set_attribute("http.status_code", response.status_code)
            span.set_attribute("http.response_time_ms", process_time * 1000)
        
        return response


class ErrorHandlingMiddleware(BaseHTTPMiddleware):
    """Middleware for centralized error handling and logging."""
    
    def __init__(self, app):
        super().__init__(app)
        self.obs_manager = get_observability_manager("gateway")
        self.logger = self.obs_manager.get_logger()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
            return response
        except Exception as exc:
            # Log the error
            correlation_id = getattr(request.state, 'correlation_id', 'unknown')
            
            self.logger.error(
                f"Unhandled exception in gateway",
                correlation_id=correlation_id,
                method=request.method,
                url=str(request.url),
                error_type=type(exc).__name__,
                error_message=str(exc)
            )
            
            # Add error to trace
            span = trace.get_current_span()
            if span and span.is_recording():
                span.set_attribute("error", True)
                span.set_attribute("error.type", type(exc).__name__)
                span.set_attribute("error.message", str(exc))
            
            # Return error response
            error_response = ErrorResponse(
                error="internal_server_error",
                message="An internal server error occurred",
                trace_id=correlation_id
            )
            
            return JSONResponse(
                status_code=500,
                content=error_response.model_dump(),
                headers={"X-Correlation-ID": correlation_id}
            )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware to add security headers."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        
        return response


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect request metrics."""
    
    def __init__(self, app):
        super().__init__(app)
        self.obs_manager = get_observability_manager("gateway")
        self.meter = self.obs_manager.get_meter()
        
        # Create metrics
        self.request_counter = self.meter.create_counter(
            name="http_requests_total",
            description="Total number of HTTP requests",
            unit="1"
        )
        
        self.request_duration = self.meter.create_histogram(
            name="http_request_duration_seconds",
            description="HTTP request duration in seconds",
            unit="s"
        )
        
        self.active_requests = self.meter.create_up_down_counter(
            name="http_requests_active",
            description="Number of active HTTP requests",
            unit="1"
        )
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Track active requests
        labels = {
            "method": request.method,
            "endpoint": request.url.path
        }
        
        self.active_requests.add(1, labels)
        
        start_time = time.time()
        try:
            response = await call_next(request)
            
            # Update metrics
            labels["status_code"] = str(response.status_code)
            self.request_counter.add(1, labels)
            
            duration = time.time() - start_time
            self.request_duration.record(duration, labels)
            
            return response
        
        except Exception as exc:
            # Update metrics for errors
            labels["status_code"] = "500"
            self.request_counter.add(1, labels)
            
            duration = time.time() - start_time
            self.request_duration.record(duration, labels)
            
            raise
        
        finally:
            # Decrement active requests
            self.active_requests.add(-1, {
                "method": request.method,
                "endpoint": request.url.path
            })
