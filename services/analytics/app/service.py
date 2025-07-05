"""Analytics service business logic."""

import asyncio
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text, func, desc
from uuid import UUID

import sys
sys.path.append('/app')
from shared.database import URL, ClickEvent, URLAnalytics
from shared.models import AnalyticsResponse
from shared.observability import trace_function, trace_operation


class AnalyticsService:
    """Service for analytics operations."""
    
    def __init__(self):
        self.batch_size = 100
        self.pending_events = []
    
    @trace_function("analytics_service.process_click_event")
    async def process_click_event(self, db: AsyncSession, event_data: Dict[str, Any]) -> bool:
        """Process a single click event."""
        try:
            # Create click event record
            click_event = ClickEvent(
                url_id=UUID(event_data["url_id"]),
                short_code=event_data["short_code"],
                clicked_at=datetime.fromisoformat(event_data.get("clicked_at", datetime.utcnow().isoformat())),
                ip_address=event_data.get("ip_address"),
                user_agent=event_data.get("user_agent"),
                referer=event_data.get("referer"),
                country=event_data.get("country"),
                city=event_data.get("city"),
                device_type=event_data.get("device_type"),
                browser=event_data.get("browser"),
                os=event_data.get("os"),
                metadata=event_data.get("metadata", {})
            )
            
            db.add(click_event)
            await db.commit()
            
            # Update daily analytics summary
            await self._update_daily_analytics(db, event_data)
            
            return True
            
        except Exception as e:
            await db.rollback()
            return False
    
    @trace_function("analytics_service.get_url_analytics")
    async def get_url_analytics(self, db: AsyncSession, short_code: str) -> Optional[AnalyticsResponse]:
        """Get comprehensive analytics for a URL."""
        with trace_operation("database.get_url_analytics"):
            # Get URL info
            url_result = await db.execute(
                select(URL).where(URL.short_code == short_code)
            )
            url_record = url_result.scalar_one_or_none()
            
            if not url_record:
                return None
            
            # Get click statistics
            click_stats = await db.execute(
                text("""
                    SELECT 
                        COUNT(*) as total_clicks,
                        COUNT(DISTINCT ip_address) as unique_visitors,
                        MAX(clicked_at) as last_clicked_at
                    FROM click_events 
                    WHERE short_code = :short_code
                """),
                {"short_code": short_code}
            )
            stats = click_stats.fetchone()
            
            # Get daily stats for last 30 days
            daily_stats = await self.get_daily_stats(db, short_code, 30)
            
            # Get top countries
            top_countries = await self.get_country_stats(db, short_code, 5)
            
            # Get top devices
            top_devices = await self.get_device_stats(db, short_code, 5)
            
            # Get top browsers
            top_browsers = await self.get_browser_stats(db, short_code, 5)
            
            # Get top referers
            top_referers = await self.get_referer_stats(db, short_code, 5)
            
            return AnalyticsResponse(
                url_id=url_record.id,
                short_code=url_record.short_code,
                original_url=url_record.original_url,
                total_clicks=stats.total_clicks or 0,
                unique_clicks=stats.total_clicks or 0,  # Simplified for now
                unique_visitors=stats.unique_visitors or 0,
                created_at=url_record.created_at,
                last_clicked_at=stats.last_clicked_at,
                daily_stats=daily_stats,
                top_countries=top_countries,
                top_devices=top_devices,
                top_browsers=top_browsers,
                top_referers=top_referers
            )
    
    @trace_function("analytics_service.get_analytics_summary")
    async def get_analytics_summary(self, db: AsyncSession, short_code: str, days: int = 30) -> Optional[Dict[str, Any]]:
        """Get analytics summary for specified time period."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        with trace_operation("database.get_analytics_summary"):
            result = await db.execute(
                text("""
                    SELECT 
                        COUNT(*) as total_clicks,
                        COUNT(DISTINCT ip_address) as unique_visitors,
                        COUNT(DISTINCT DATE(clicked_at)) as active_days
                    FROM click_events 
                    WHERE short_code = :short_code 
                    AND clicked_at >= :start_date
                """),
                {"short_code": short_code, "start_date": start_date}
            )
            
            summary = result.fetchone()
            if not summary or summary.total_clicks == 0:
                return None
            
            return {
                "short_code": short_code,
                "period_days": days,
                "total_clicks": summary.total_clicks,
                "unique_visitors": summary.unique_visitors,
                "active_days": summary.active_days,
                "avg_clicks_per_day": summary.total_clicks / days if days > 0 else 0
            }
    
    @trace_function("analytics_service.get_daily_stats")
    async def get_daily_stats(self, db: AsyncSession, short_code: str, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily click statistics."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        with trace_operation("database.get_daily_stats"):
            result = await db.execute(
                text("""
                    SELECT 
                        DATE(clicked_at) as date,
                        COUNT(*) as clicks,
                        COUNT(DISTINCT ip_address) as unique_visitors
                    FROM click_events 
                    WHERE short_code = :short_code 
                    AND clicked_at >= :start_date
                    GROUP BY DATE(clicked_at)
                    ORDER BY date DESC
                """),
                {"short_code": short_code, "start_date": start_date}
            )
            
            return [
                {
                    "date": row.date.isoformat(),
                    "clicks": row.clicks,
                    "unique_visitors": row.unique_visitors
                }
                for row in result.fetchall()
            ]
    
    @trace_function("analytics_service.get_country_stats")
    async def get_country_stats(self, db: AsyncSession, short_code: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top countries by clicks."""
        with trace_operation("database.get_country_stats"):
            result = await db.execute(
                text("""
                    SELECT 
                        country,
                        COUNT(*) as clicks,
                        COUNT(DISTINCT ip_address) as unique_visitors
                    FROM click_events 
                    WHERE short_code = :short_code 
                    AND country IS NOT NULL
                    GROUP BY country
                    ORDER BY clicks DESC
                    LIMIT :limit
                """),
                {"short_code": short_code, "limit": limit}
            )
            
            return [
                {
                    "country": row.country,
                    "clicks": row.clicks,
                    "unique_visitors": row.unique_visitors
                }
                for row in result.fetchall()
            ]
    
    @trace_function("analytics_service.get_device_stats")
    async def get_device_stats(self, db: AsyncSession, short_code: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top devices by clicks."""
        with trace_operation("database.get_device_stats"):
            result = await db.execute(
                text("""
                    SELECT 
                        device_type,
                        COUNT(*) as clicks,
                        COUNT(DISTINCT ip_address) as unique_visitors
                    FROM click_events 
                    WHERE short_code = :short_code 
                    AND device_type IS NOT NULL
                    GROUP BY device_type
                    ORDER BY clicks DESC
                    LIMIT :limit
                """),
                {"short_code": short_code, "limit": limit}
            )
            
            return [
                {
                    "device_type": row.device_type,
                    "clicks": row.clicks,
                    "unique_visitors": row.unique_visitors
                }
                for row in result.fetchall()
            ]
    
    @trace_function("analytics_service.get_browser_stats")
    async def get_browser_stats(self, db: AsyncSession, short_code: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top browsers by clicks."""
        with trace_operation("database.get_browser_stats"):
            result = await db.execute(
                text("""
                    SELECT 
                        browser,
                        COUNT(*) as clicks,
                        COUNT(DISTINCT ip_address) as unique_visitors
                    FROM click_events 
                    WHERE short_code = :short_code 
                    AND browser IS NOT NULL
                    GROUP BY browser
                    ORDER BY clicks DESC
                    LIMIT :limit
                """),
                {"short_code": short_code, "limit": limit}
            )
            
            return [
                {
                    "browser": row.browser,
                    "clicks": row.clicks,
                    "unique_visitors": row.unique_visitors
                }
                for row in result.fetchall()
            ]
    
    @trace_function("analytics_service.get_referer_stats")
    async def get_referer_stats(self, db: AsyncSession, short_code: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top referers by clicks."""
        with trace_operation("database.get_referer_stats"):
            result = await db.execute(
                text("""
                    SELECT 
                        referer,
                        COUNT(*) as clicks,
                        COUNT(DISTINCT ip_address) as unique_visitors
                    FROM click_events 
                    WHERE short_code = :short_code 
                    AND referer IS NOT NULL
                    AND referer != ''
                    GROUP BY referer
                    ORDER BY clicks DESC
                    LIMIT :limit
                """),
                {"short_code": short_code, "limit": limit}
            )
            
            return [
                {
                    "referer": row.referer,
                    "clicks": row.clicks,
                    "unique_visitors": row.unique_visitors
                }
                for row in result.fetchall()
            ]
    
    @trace_function("analytics_service.get_global_stats")
    async def get_global_stats(self, db: AsyncSession) -> Dict[str, Any]:
        """Get global platform statistics."""
        with trace_operation("database.get_global_stats"):
            # Total URLs
            url_count = await db.execute(
                select(func.count(URL.id))
            )
            total_urls = url_count.scalar()
            
            # Total clicks
            click_count = await db.execute(
                select(func.count(ClickEvent.id))
            )
            total_clicks = click_count.scalar()
            
            # Active URLs (clicked in last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            active_urls = await db.execute(
                text("""
                    SELECT COUNT(DISTINCT short_code) 
                    FROM click_events 
                    WHERE clicked_at >= :start_date
                """),
                {"start_date": thirty_days_ago}
            )
            active_url_count = active_urls.scalar()
            
            return {
                "total_urls": total_urls,
                "total_clicks": total_clicks,
                "active_urls_30d": active_url_count,
                "avg_clicks_per_url": total_clicks / total_urls if total_urls > 0 else 0
            }
    
    @trace_function("analytics_service.get_top_urls")
    async def get_top_urls(self, db: AsyncSession, limit: int = 10, days: int = 30) -> List[Dict[str, Any]]:
        """Get top URLs by clicks."""
        start_date = datetime.utcnow() - timedelta(days=days)
        
        with trace_operation("database.get_top_urls"):
            result = await db.execute(
                text("""
                    SELECT 
                        ce.short_code,
                        u.original_url,
                        COUNT(*) as clicks,
                        COUNT(DISTINCT ce.ip_address) as unique_visitors
                    FROM click_events ce
                    JOIN urls u ON ce.short_code = u.short_code
                    WHERE ce.clicked_at >= :start_date
                    GROUP BY ce.short_code, u.original_url
                    ORDER BY clicks DESC
                    LIMIT :limit
                """),
                {"start_date": start_date, "limit": limit}
            )
            
            return [
                {
                    "short_code": row.short_code,
                    "original_url": row.original_url,
                    "clicks": row.clicks,
                    "unique_visitors": row.unique_visitors
                }
                for row in result.fetchall()
            ]
    
    async def _update_daily_analytics(self, db: AsyncSession, event_data: Dict[str, Any]):
        """Update daily analytics summary."""
        try:
            date = datetime.fromisoformat(event_data.get("clicked_at", datetime.utcnow().isoformat())).date()
            
            # This would be more complex in production with proper aggregation
            # For now, we'll skip the daily summary updates
            pass
            
        except Exception:
            # Don't fail the main operation if analytics update fails
            pass
    
    async def process_pending_events(self, db: AsyncSession):
        """Process any pending events in batch."""
        if not self.pending_events:
            return
        
        events_to_process = self.pending_events[:self.batch_size]
        self.pending_events = self.pending_events[self.batch_size:]
        
        for event in events_to_process:
            await self.process_click_event(db, event)
