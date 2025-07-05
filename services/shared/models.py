from datetime import datetime
from typing import Optional, Dict, Any, List
from uuid import UUID
from pydantic import BaseModel, HttpUrl, Field


class URLCreate(BaseModel):
    original_url: HttpUrl
    custom_code: Optional[str] = None
    expires_at: Optional[datetime] = None
    metadata: Optional[Dict[str, Any]] = None


class URLResponse(BaseModel):
    id: UUID
    original_url: str
    short_code: str
    short_url: str
    created_at: datetime
    expires_at: Optional[datetime] = None
    is_active: bool
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class ClickEvent(BaseModel):
    url_id: UUID
    short_code: str
    clicked_at: datetime
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    referer: Optional[str] = None
    country: Optional[str] = None
    city: Optional[str] = None
    device_type: Optional[str] = None
    browser: Optional[str] = None
    os: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

    class Config:
        from_attributes = True


class AnalyticsResponse(BaseModel):
    url_id: UUID
    short_code: str
    original_url: str
    total_clicks: int
    unique_clicks: int
    unique_visitors: int
    created_at: datetime
    last_clicked_at: Optional[datetime] = None
    daily_stats: List[Dict[str, Any]] = []
    top_countries: List[Dict[str, Any]] = []
    top_devices: List[Dict[str, Any]] = []
    top_browsers: List[Dict[str, Any]] = []
    top_referers: List[Dict[str, Any]] = []

    class Config:
        from_attributes = True


class HealthCheck(BaseModel):
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    service: str
    version: str = "1.0.0"
    dependencies: Dict[str, str] = {}


class ErrorResponse(BaseModel):
    error: str
    message: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    trace_id: Optional[str] = None
