import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import httpx
import uvicorn

import sys
sys.path.append('/app')
from shared.models import URLCreate, URLResponse, HealthCheck, ErrorResponse
from shared.observability import get_observability_manager, trace_function
from shared.redis_client import get_redis_manager
from shared.utils import get_client_ip

from .rate_limiter import RateLimiter
from .middleware import RequestTracingMiddleware, ErrorHandlingMiddleware

http_client: httpx.AsyncClient = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global http_client
    
    obs_manager = get_observability_manager("gateway")
    obs_manager.instrument_fastapi(app)
    
    http_client = httpx.AsyncClient(
        timeout=httpx.Timeout(30.0),
        limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
    )
    
    obs_manager.get_logger().info("Gateway service started")
    
    yield
    
    if http_client:
        await http_client.aclose()
    
    obs_manager.get_logger().info("Gateway service stopped")


app = FastAPI(
    title="URL Shortener Gateway",
    description="API Gateway for URL shortener platform",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RequestTracingMiddleware)
app.add_middleware(ErrorHandlingMiddleware)

rate_limiter = RateLimiter(
    requests_per_minute=int(os.getenv("RATE_LIMIT_REQUESTS", "100")),
    window_seconds=int(os.getenv("RATE_LIMIT_WINDOW", "60"))
)

SHORTENER_URL = os.getenv("SHORTENER_URL", "http://shortener:8001")
REDIRECTOR_URL = os.getenv("REDIRECTOR_URL", "http://redirector:8002")
ANALYTICS_URL = os.getenv("ANALYTICS_URL", "http://analytics:8003")


@app.get("/healthz", response_model=HealthCheck)
async def health_check():
    dependencies = {}
    
    try:
        redis_manager = get_redis_manager()
        redis_healthy = await redis_manager.health_check()
        dependencies["redis"] = "healthy" if redis_healthy else "unhealthy"
    except Exception:
        dependencies["redis"] = "unhealthy"
    
    for service_name, service_url in [
        ("shortener", SHORTENER_URL),
        ("redirector", REDIRECTOR_URL),
        ("analytics", ANALYTICS_URL)
    ]:
        try:
            response = await http_client.get(f"{service_url}/healthz", timeout=5.0)
            dependencies[service_name] = "healthy" if response.status_code == 200 else "unhealthy"
        except Exception:
            dependencies[service_name] = "unhealthy"
    
    return HealthCheck(
        service="gateway",
        dependencies=dependencies
    )


@app.post("/api/v1/shorten", response_model=URLResponse)
@trace_function("gateway.shorten_url")
async def shorten_url(
    url_data: URLCreate,
    request: Request,
    _: None = Depends(rate_limiter.check_rate_limit)
):
    try:
        response = await http_client.post(
            f"{SHORTENER_URL}/shorten",
            json=url_data.model_dump(),
            headers={"X-Forwarded-For": get_client_ip(request) or "unknown"}
        )
        
        if response.status_code == 200:
            return URLResponse(**response.json())
        elif response.status_code == 400:
            raise HTTPException(status_code=400, detail=response.json().get("detail", "Bad request"))
        elif response.status_code == 409:
            raise HTTPException(status_code=409, detail="Short code already exists")
        else:
            raise HTTPException(status_code=500, detail="Internal server error")
            
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Shortener service unavailable")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/{short_code}")
@trace_function("gateway.redirect_url")
async def redirect_url(
    short_code: str,
    request: Request,
    _: None = Depends(rate_limiter.check_rate_limit)
):
    try:
        client_ip = get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "")
        referer = request.headers.get("Referer", "")
        
        response = await http_client.get(
            f"{REDIRECTOR_URL}/{short_code}",
            headers={
                "X-Forwarded-For": client_ip or "unknown",
                "X-Original-User-Agent": user_agent,
                "X-Original-Referer": referer,
            },
            follow_redirects=False
        )
        
        if response.status_code == 302:
            location = response.headers.get("Location")
            if location:
                return RedirectResponse(url=location, status_code=302)
            else:
                raise HTTPException(status_code=500, detail="Invalid redirect response")
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Short URL not found")
        elif response.status_code == 410:
            raise HTTPException(status_code=410, detail="Short URL has expired")
        else:
            raise HTTPException(status_code=500, detail="Internal server error")
            
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Redirector service unavailable")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/analytics/{short_code}")
@trace_function("gateway.get_analytics")
async def get_analytics(
    short_code: str,
    request: Request,
    _: None = Depends(rate_limiter.check_rate_limit)
):
    try:
        response = await http_client.get(
            f"{ANALYTICS_URL}/analytics/{short_code}",
            headers={"X-Forwarded-For": get_client_ip(request) or "unknown"}
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Short URL not found")
        else:
            raise HTTPException(status_code=500, detail="Internal server error")
            
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Analytics service unavailable")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/v1/urls/{short_code}")
@trace_function("gateway.get_url_info")
async def get_url_info(
    short_code: str,
    request: Request,
    _: None = Depends(rate_limiter.check_rate_limit)
):
    try:
        response = await http_client.get(
            f"{SHORTENER_URL}/urls/{short_code}",
            headers={"X-Forwarded-For": get_client_ip(request) or "unknown"}
        )
        
        if response.status_code == 200:
            return URLResponse(**response.json())
        elif response.status_code == 404:
            raise HTTPException(status_code=404, detail="Short URL not found")
        else:
            raise HTTPException(status_code=500, detail="Internal server error")
            
    except httpx.RequestError:
        raise HTTPException(status_code=503, detail="Shortener service unavailable")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=500, detail="Internal server error")


if __name__ == "__main__":
    host = os.getenv("GATEWAY_HOST", "0.0.0.0")
    port = int(os.getenv("GATEWAY_PORT", "8000"))
    
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
        access_log=True,
        log_config=None  # Use our custom logging
    )
