import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import uvicorn

import sys
sys.path.append('/app')
from shared.models import URLCreate, URLResponse, HealthCheck
from shared.database import get_db_session, get_database_manager
from shared.redis_client import get_redis_manager
from shared.observability import get_observability_manager, trace_function
from shared.utils import create_short_url

from .service import URLService


@asynccontextmanager
async def lifespan(app: FastAPI):
    obs_manager = get_observability_manager("shortener")
    obs_manager.instrument_fastapi(app)
    
    obs_manager.get_logger().info("Shortener service started")
    
    yield
    
    db_manager = get_database_manager()
    await db_manager.close()
    
    redis_manager = get_redis_manager()
    await redis_manager.close()
    
    obs_manager.get_logger().info("Shortener service stopped")


app = FastAPI(
    title="URL Shortener Service",
    description="Service for creating and managing short URLs",
    version="1.0.0",
    lifespan=lifespan
)

url_service = URLService()


@app.get("/healthz", response_model=HealthCheck)
async def health_check():
    dependencies = {}
    
    try:
        db_manager = get_database_manager()
        db_healthy = await db_manager.health_check()
        dependencies["database"] = "healthy" if db_healthy else "unhealthy"
    except Exception:
        dependencies["database"] = "unhealthy"
    
    try:
        redis_manager = get_redis_manager()
        redis_healthy = await redis_manager.health_check()
        dependencies["redis"] = "healthy" if redis_healthy else "unhealthy"
    except Exception:
        dependencies["redis"] = "unhealthy"
    
    return HealthCheck(
        service="shortener",
        dependencies=dependencies
    )


@app.post("/shorten", response_model=URLResponse)
@trace_function("shortener.create_short_url")
async def create_short_url_endpoint(
    url_data: URLCreate,
    db: AsyncSession = Depends(get_db_session)
):
    try:
        url_record = await url_service.create_short_url(db, url_data)
        
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        short_url = create_short_url(base_url, url_record.short_code)
        
        return URLResponse(
            id=url_record.id,
            original_url=url_record.original_url,
            short_code=url_record.short_code,
            short_url=short_url,
            created_at=url_record.created_at,
            expires_at=url_record.expires_at,
            is_active=url_record.is_active,
            metadata=url_record.metadata
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        if "duplicate key" in str(e).lower():
            raise HTTPException(status_code=409, detail="Short code already exists")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/urls/{short_code}", response_model=URLResponse)
@trace_function("shortener.get_url_info")
async def get_url_info(
    short_code: str,
    db: AsyncSession = Depends(get_db_session)
):
    try:
        url_record = await url_service.get_url_by_code(db, short_code)
        
        if not url_record:
            raise HTTPException(status_code=404, detail="Short URL not found")
        
        base_url = os.getenv("BASE_URL", "http://localhost:8000")
        short_url = create_short_url(base_url, url_record.short_code)
        
        return URLResponse(
            id=url_record.id,
            original_url=url_record.original_url,
            short_code=url_record.short_code,
            short_url=short_url,
            created_at=url_record.created_at,
            expires_at=url_record.expires_at,
            is_active=url_record.is_active,
            metadata=url_record.metadata
        )
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.put("/urls/{short_code}/deactivate")
@trace_function("shortener.deactivate_url")
async def deactivate_url(
    short_code: str,
    db: AsyncSession = Depends(get_db_session)
):
    try:
        success = await url_service.deactivate_url(db, short_code)
        
        if not success:
            raise HTTPException(status_code=404, detail="Short URL not found")
        
        return {"message": "URL deactivated successfully"}
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/urls/{short_code}/stats")
@trace_function("shortener.get_url_stats")
async def get_url_stats(
    short_code: str,
    db: AsyncSession = Depends(get_db_session)
):
    try:
        stats = await url_service.get_url_stats(db, short_code)
        
        if not stats:
            raise HTTPException(status_code=404, detail="Short URL not found")
        
        return stats
    
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    host = os.getenv("SHORTENER_HOST", "0.0.0.0")
    port = int(os.getenv("SHORTENER_PORT", "8001"))
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
        access_log=True,
        log_config=None  # Use our custom logging
    )
