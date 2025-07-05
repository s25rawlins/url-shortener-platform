"""Redirector service main application."""

import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
import uvicorn

# Import shared modules
import sys
sys.path.append('/app')
from shared.models import HealthCheck
from shared.database import get_db_session, get_database_manager
from shared.redis_client import get_redis_manager
from shared.observability import get_observability_manager, trace_function
from shared.utils import get_client_ip, parse_user_agent_info

from .service import RedirectorService
from .kafka_producer import KafkaProducer


# Global services
redirector_service: RedirectorService = None
kafka_producer: KafkaProducer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    global redirector_service, kafka_producer
    
    # Initialize observability
    obs_manager = get_observability_manager("redirector")
    obs_manager.instrument_fastapi(app)
    
    # Initialize services
    redirector_service = RedirectorService()
    kafka_producer = KafkaProducer()
    await kafka_producer.start()
    
    obs_manager.get_logger().info("Redirector service started")
    
    yield
    
    # Cleanup
    if kafka_producer:
        await kafka_producer.stop()
    
    db_manager = get_database_manager()
    await db_manager.close()
    
    redis_manager = get_redis_manager()
    await redis_manager.close()
    
    obs_manager.get_logger().info("Redirector service stopped")


# Create FastAPI app
app = FastAPI(
    title="URL Redirector Service",
    description="Service for URL redirection and click tracking",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/healthz", response_model=HealthCheck)
async def health_check():
    """Health check endpoint."""
    dependencies = {}
    
    # Check database
    try:
        db_manager = get_database_manager()
        db_healthy = await db_manager.health_check()
        dependencies["database"] = "healthy" if db_healthy else "unhealthy"
    except Exception:
        dependencies["database"] = "unhealthy"
    
    # Check Redis
    try:
        redis_manager = get_redis_manager()
        redis_healthy = await redis_manager.health_check()
        dependencies["redis"] = "healthy" if redis_healthy else "unhealthy"
    except Exception:
        dependencies["redis"] = "unhealthy"
    
    # Check Kafka
    try:
        kafka_healthy = await kafka_producer.health_check() if kafka_producer else False
        dependencies["kafka"] = "healthy" if kafka_healthy else "unhealthy"
    except Exception:
        dependencies["kafka"] = "unhealthy"
    
    return HealthCheck(
        service="redirector",
        dependencies=dependencies
    )


@app.get("/{short_code}")
@trace_function("redirector.redirect_url")
async def redirect_url(
    short_code: str,
    request: Request,
    db: AsyncSession = Depends(get_db_session)
):
    """Redirect to original URL and track click event."""
    try:
        # Get URL from database/cache
        url_record = await redirector_service.get_url_for_redirect(db, short_code)
        
        if not url_record:
            raise HTTPException(status_code=404, detail="Short URL not found")
        
        if not url_record.is_active:
            raise HTTPException(status_code=410, detail="Short URL is inactive")
        
        # Check if URL has expired
        if await redirector_service.check_url_expired(url_record):
            raise HTTPException(status_code=410, detail="Short URL has expired")
        
        # Extract request information
        client_ip = get_client_ip(request)
        user_agent = request.headers.get("X-Original-User-Agent") or request.headers.get("User-Agent", "")
        referer = request.headers.get("X-Original-Referer") or request.headers.get("Referer", "")
        
        # Parse user agent
        ua_info = parse_user_agent_info(user_agent)
        
        # Create click event
        click_event_data = {
            "url_id": str(url_record.id),
            "short_code": short_code,
            "ip_address": client_ip,
            "user_agent": user_agent,
            "referer": referer,
            "device_type": ua_info.get("device_type"),
            "browser": ua_info.get("browser"),
            "os": ua_info.get("os"),
            "is_bot": ua_info.get("is_bot", False)
        }
        
        # Send click event to Kafka (fire and forget)
        if kafka_producer:
            await kafka_producer.send_click_event(click_event_data)
        
        # Return redirect response
        return RedirectResponse(
            url=url_record.original_url,
            status_code=302,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/preview/{short_code}")
@trace_function("redirector.preview_url")
async def preview_url(
    short_code: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Preview URL information without redirecting."""
    try:
        url_record = await redirector_service.get_url_for_redirect(db, short_code)
        
        if not url_record:
            raise HTTPException(status_code=404, detail="Short URL not found")
        
        return {
            "short_code": url_record.short_code,
            "original_url": url_record.original_url,
            "created_at": url_record.created_at.isoformat(),
            "expires_at": url_record.expires_at.isoformat() if url_record.expires_at else None,
            "is_active": url_record.is_active,
            "is_expired": await redirector_service.check_url_expired(url_record)
        }
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/track-click")
@trace_function("redirector.track_click")
async def track_click_manual(
    click_data: dict,
    request: Request
):
    """Manually track a click event (for client-side tracking)."""
    try:
        # Validate required fields
        if not click_data.get("short_code"):
            raise HTTPException(status_code=400, detail="short_code is required")
        
        # Add request information
        click_data.update({
            "ip_address": get_client_ip(request),
            "user_agent": request.headers.get("User-Agent", ""),
            "referer": request.headers.get("Referer", "")
        })
        
        # Send to Kafka
        if kafka_producer:
            await kafka_producer.send_click_event(click_data)
        
        return {"message": "Click tracked successfully"}
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    host = os.getenv("REDIRECTOR_HOST", "0.0.0.0")
    port = int(os.getenv("REDIRECTOR_PORT", "8002"))
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
        access_log=True,
        log_config=None  # Use our custom logging
    )
