"""Redirector service business logic."""

from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

import sys
sys.path.append('/app')
from shared.database import URL
from shared.redis_client import get_redis_manager, CacheKeys, with_fallback
from shared.observability import trace_function, trace_operation


class RedirectorService:
    """Service for URL redirection operations."""
    
    def __init__(self):
        self.redis_manager = get_redis_manager()
    
    @trace_function("redirector_service.get_url_for_redirect")
    async def get_url_for_redirect(self, db: AsyncSession, short_code: str) -> Optional[URL]:
        """Get URL for redirection with caching optimized for read performance."""
        cache_key = CacheKeys.url_by_code(short_code)
        
        async def get_from_cache():
            cached_data = await self.redis_manager.get_json(cache_key)
            if cached_data:
                # Convert back to URL object
                url_record = URL()
                for key, value in cached_data.items():
                    if key == 'created_at' and value:
                        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    elif key == 'updated_at' and value:
                        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    elif key == 'expires_at' and value:
                        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
                    setattr(url_record, key, value)
                return url_record
            return None
        
        async def get_from_db():
            with trace_operation("database.get_url_for_redirect"):
                result = await db.execute(
                    select(URL).where(
                        (URL.short_code == short_code) & 
                        (URL.is_active == True)
                    )
                )
                url_record = result.scalar_one_or_none()
                
                if url_record:
                    # Cache for longer since redirects are read-heavy
                    await self._cache_url(url_record, expire=7200)  # 2 hours
                
                return url_record
        
        return await with_fallback(get_from_cache, get_from_db, cache_key, expire=7200)
    
    @trace_function("redirector_service.check_url_expired")
    async def check_url_expired(self, url_record: URL) -> bool:
        """Check if URL has expired."""
        if not url_record.expires_at:
            return False
        
        return datetime.utcnow() > url_record.expires_at.replace(tzinfo=None)
    
    async def _cache_url(self, url_record: URL, expire: int = 3600) -> None:
        """Cache URL record in Redis."""
        cache_key = CacheKeys.url_by_code(url_record.short_code)
        
        # Convert to dict for JSON serialization
        url_data = {
            "id": str(url_record.id),
            "original_url": url_record.original_url,
            "short_code": url_record.short_code,
            "created_at": url_record.created_at.isoformat() if url_record.created_at else None,
            "updated_at": url_record.updated_at.isoformat() if url_record.updated_at else None,
            "expires_at": url_record.expires_at.isoformat() if url_record.expires_at else None,
            "is_active": url_record.is_active,
            "created_by": url_record.created_by,
            "metadata": url_record.metadata
        }
        
        await self.redis_manager.set_json(cache_key, url_data, expire=expire)
    
    @trace_function("redirector_service.increment_click_counter")
    async def increment_click_counter(self, short_code: str) -> None:
        """Increment click counter in Redis for real-time stats."""
        counter_key = f"clicks:{short_code}:count"
        daily_key = f"clicks:{short_code}:{datetime.utcnow().strftime('%Y-%m-%d')}"
        
        # Increment counters
        await self.redis_manager.increment(counter_key)
        await self.redis_manager.increment(daily_key)
        
        # Set expiration for daily counter (keep for 30 days)
        await self.redis_manager.expire(daily_key, 30 * 24 * 3600)
    
    @trace_function("redirector_service.get_click_count")
    async def get_click_count(self, short_code: str) -> int:
        """Get current click count from Redis."""
        counter_key = f"clicks:{short_code}:count"
        count = await self.redis_manager.get(counter_key)
        return int(count) if count else 0
    
    @trace_function("redirector_service.is_bot_request")
    async def is_bot_request(self, user_agent: str) -> bool:
        """Check if request is from a bot/crawler."""
        if not user_agent:
            return False
        
        user_agent_lower = user_agent.lower()
        bot_indicators = [
            'bot', 'crawler', 'spider', 'scraper', 'curl', 'wget',
            'python-requests', 'http', 'facebookexternalhit', 'twitterbot',
            'linkedinbot', 'whatsapp', 'telegram', 'slack', 'discord'
        ]
        
        return any(indicator in user_agent_lower for indicator in bot_indicators)
    
    @trace_function("redirector_service.should_track_click")
    async def should_track_click(self, click_data: dict) -> bool:
        """Determine if click should be tracked based on various criteria."""
        # Don't track bot requests
        if click_data.get("is_bot", False):
            return False
        
        # Don't track if no IP address (suspicious)
        if not click_data.get("ip_address"):
            return False
        
        # Check for suspicious patterns
        user_agent = click_data.get("user_agent", "")
        if await self.is_bot_request(user_agent):
            return False
        
        return True
    
    @trace_function("redirector_service.enrich_click_data")
    async def enrich_click_data(self, click_data: dict) -> dict:
        """Enrich click data with additional information."""
        enriched_data = click_data.copy()
        
        # Add timestamp if not present
        if "clicked_at" not in enriched_data:
            enriched_data["clicked_at"] = datetime.utcnow().isoformat()
        
        # Add geolocation (placeholder - would use actual GeoIP service)
        ip_address = click_data.get("ip_address")
        if ip_address:
            # In production, use MaxMind GeoIP or similar service
            enriched_data["country"] = None  # get_country_from_ip(ip_address)
            enriched_data["city"] = None     # get_city_from_ip(ip_address)
        
        # Add additional metadata
        enriched_data["metadata"] = {
            "service": "redirector",
            "version": "1.0.0",
            "processed_at": datetime.utcnow().isoformat()
        }
        
        return enriched_data
