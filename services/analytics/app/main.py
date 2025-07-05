"""Analytics service main application."""

import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
import uvicorn

# Import shared modules
import sys
sys.path.append('/app')
from shared.models import HealthCheck, AnalyticsResponse
from shared.database import get_db_session, get_database_manager
from shared.observability import get_observability_manager, trace_function

from .service import AnalyticsService
from .kafka_consumer import KafkaConsumer


# Global services
analytics_service: AnalyticsService = None
kafka_consumer: KafkaConsumer = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    global analytics_service, kafka_consumer
    
    # Initialize observability
    obs_manager = get_observability_manager("analytics")
    obs_manager.instrument_fastapi(app)
    
    # Initialize services
    analytics_service = AnalyticsService()
    kafka_consumer = KafkaConsumer(analytics_service)
    
    # Start Kafka consumer in background
    consumer_task = asyncio.create_task(kafka_consumer.start_consuming())
    
    obs_manager.get_logger().info("Analytics service started")
    
    yield
    
    # Cleanup
    consumer_task.cancel()
    try:
        await consumer_task
    except asyncio.CancelledError:
        pass
    
    if kafka_consumer:
        await kafka_consumer.stop()
    
    db_manager = get_database_manager()
    await db_manager.close()
    
    obs_manager.get_logger().info("Analytics service stopped")


# Create FastAPI app
app = FastAPI(
    title="URL Analytics Service",
    description="Service for processing and serving URL analytics",
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
    
    # Check Kafka consumer
    try:
        kafka_healthy = kafka_consumer.is_running() if kafka_consumer else False
        dependencies["kafka"] = "healthy" if kafka_healthy else "unhealthy"
    except Exception:
        dependencies["kafka"] = "unhealthy"
    
    return HealthCheck(
        service="analytics",
        dependencies=dependencies
    )


@app.get("/analytics/{short_code}", response_model=AnalyticsResponse)
@trace_function("analytics.get_url_analytics")
async def get_url_analytics(
    short_code: str,
    db: AsyncSession = Depends(get_db_session)
):
    """Get comprehensive analytics for a short URL."""
    try:
        analytics_data = await analytics_service.get_url_analytics(db, short_code)
        
        if not analytics_data:
            raise HTTPException(status_code=404, detail="Short URL not found")
        
        return analytics_data
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/analytics/{short_code}/summary")
@trace_function("analytics.get_analytics_summary")
async def get_analytics_summary(
    short_code: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db_session)
):
    """Get analytics summary for specified time period."""
    try:
        if days < 1 or days > 365:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 365")
        
        summary = await analytics_service.get_analytics_summary(db, short_code, days)
        
        if not summary:
            raise HTTPException(status_code=404, detail="Short URL not found")
        
        return summary
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/analytics/{short_code}/daily")
@trace_function("analytics.get_daily_stats")
async def get_daily_stats(
    short_code: str,
    days: int = 30,
    db: AsyncSession = Depends(get_db_session)
):
    """Get daily click statistics."""
    try:
        if days < 1 or days > 365:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 365")
        
        daily_stats = await analytics_service.get_daily_stats(db, short_code, days)
        
        return {"short_code": short_code, "daily_stats": daily_stats}
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/analytics/{short_code}/countries")
@trace_function("analytics.get_country_stats")
async def get_country_stats(
    short_code: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db_session)
):
    """Get top countries by clicks."""
    try:
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")
        
        country_stats = await analytics_service.get_country_stats(db, short_code, limit)
        
        return {"short_code": short_code, "countries": country_stats}
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/analytics/{short_code}/devices")
@trace_function("analytics.get_device_stats")
async def get_device_stats(
    short_code: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db_session)
):
    """Get top devices by clicks."""
    try:
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")
        
        device_stats = await analytics_service.get_device_stats(db, short_code, limit)
        
        return {"short_code": short_code, "devices": device_stats}
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/analytics/{short_code}/referers")
@trace_function("analytics.get_referer_stats")
async def get_referer_stats(
    short_code: str,
    limit: int = 10,
    db: AsyncSession = Depends(get_db_session)
):
    """Get top referers by clicks."""
    try:
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")
        
        referer_stats = await analytics_service.get_referer_stats(db, short_code, limit)
        
        return {"short_code": short_code, "referers": referer_stats}
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/analytics/process-batch")
@trace_function("analytics.process_batch")
async def process_batch_events(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session)
):
    """Manually trigger batch processing of events."""
    try:
        background_tasks.add_task(analytics_service.process_pending_events, db)
        return {"message": "Batch processing started"}
    
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/analytics/stats/global")
@trace_function("analytics.get_global_stats")
async def get_global_stats(
    db: AsyncSession = Depends(get_db_session)
):
    """Get global platform statistics."""
    try:
        global_stats = await analytics_service.get_global_stats(db)
        return global_stats
    
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/analytics/stats/top-urls")
@trace_function("analytics.get_top_urls")
async def get_top_urls(
    limit: int = 10,
    days: int = 30,
    db: AsyncSession = Depends(get_db_session)
):
    """Get top URLs by clicks."""
    try:
        if limit < 1 or limit > 100:
            raise HTTPException(status_code=400, detail="Limit must be between 1 and 100")
        
        if days < 1 or days > 365:
            raise HTTPException(status_code=400, detail="Days must be between 1 and 365")
        
        top_urls = await analytics_service.get_top_urls(db, limit, days)
        return {"top_urls": top_urls}
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    host = os.getenv("ANALYTICS_HOST", "0.0.0.0")
    port = int(os.getenv("ANALYTICS_PORT", "8003"))
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
        access_log=True,
        log_config=None  # Use our custom logging
    )
