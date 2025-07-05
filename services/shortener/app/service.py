"""URL shortener service business logic."""

import asyncio
from datetime import datetime
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, text
from sqlalchemy.exc import IntegrityError

import sys
sys.path.append('/app')
from shared.database import URL
from shared.models import URLCreate
from shared.redis_client import get_redis_manager, CacheKeys, with_fallback
from shared.utils import (
    generate_short_code, 
    is_valid_url, 
    normalize_url, 
    validate_custom_code,
    sanitize_metadata
)
from shared.observability import trace_function, trace_operation


class URLService:
    """Service for URL shortening operations."""
    
    def __init__(self):
        self.redis_manager = get_redis_manager()
        self.max_retries = 5
    
    @trace_function("url_service.create_short_url")
    async def create_short_url(self, db: AsyncSession, url_data: URLCreate) -> URL:
        """Create a new short URL."""
        # Validate and normalize URL
        original_url = str(url_data.original_url)
        if not is_valid_url(original_url):
            raise ValueError("Invalid URL format")
        
        original_url = normalize_url(original_url)
        
        # Handle custom code
        short_code = None
        if url_data.custom_code:
            is_valid, error_msg = validate_custom_code(url_data.custom_code)
            if not is_valid:
                raise ValueError(error_msg)
            short_code = url_data.custom_code
        
        # Sanitize metadata
        metadata = sanitize_metadata(url_data.metadata or {})
        
        # Generate short code if not provided
        if not short_code:
            short_code = await self._generate_unique_short_code(db)
        
        # Create URL record
        url_record = URL(
            original_url=original_url,
            short_code=short_code,
            expires_at=url_data.expires_at,
            metadata=metadata
        )
        
        try:
            db.add(url_record)
            await db.commit()
            await db.refresh(url_record)
            
            # Cache the URL
            await self._cache_url(url_record)
            
            return url_record
            
        except IntegrityError:
            await db.rollback()
            raise ValueError("Short code already exists")
    
    @trace_function("url_service.get_url_by_code")
    async def get_url_by_code(self, db: AsyncSession, short_code: str) -> Optional[URL]:
        """Get URL by short code with caching."""
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
            with trace_operation("database.get_url_by_code"):
                result = await db.execute(
                    select(URL).where(URL.short_code == short_code)
                )
                url_record = result.scalar_one_or_none()
                
                if url_record:
                    await self._cache_url(url_record)
                
                return url_record
        
        return await with_fallback(get_from_cache, get_from_db, cache_key, expire=3600)
    
    @trace_function("url_service.deactivate_url")
    async def deactivate_url(self, db: AsyncSession, short_code: str) -> bool:
        """Deactivate a URL."""
        with trace_operation("database.deactivate_url"):
            result = await db.execute(
                update(URL)
                .where(URL.short_code == short_code)
                .values(is_active=False)
            )
            
            if result.rowcount > 0:
                await db.commit()
                
                # Invalidate cache
                cache_key = CacheKeys.url_by_code(short_code)
                await self.redis_manager.delete(cache_key)
                
                return True
            
            return False
    
    @trace_function("url_service.get_url_stats")
    async def get_url_stats(self, db: AsyncSession, short_code: str) -> Optional[Dict[str, Any]]:
        """Get basic URL statistics."""
        with trace_operation("database.get_url_stats"):
            # Use the view created in init.sql
            result = await db.execute(
                text("""
                    SELECT 
                        id, short_code, original_url, created_at, is_active,
                        total_clicks, unique_clicks, unique_visitors, last_clicked_at
                    FROM url_stats 
                    WHERE short_code = :short_code
                """),
                {"short_code": short_code}
            )
            
            row = result.fetchone()
            if not row:
                return None
            
            return {
                "id": str(row.id),
                "short_code": row.short_code,
                "original_url": row.original_url,
                "created_at": row.created_at.isoformat(),
                "is_active": row.is_active,
                "total_clicks": row.total_clicks,
                "unique_clicks": row.unique_clicks,
                "unique_visitors": row.unique_visitors,
                "last_clicked_at": row.last_clicked_at.isoformat() if row.last_clicked_at else None
            }
    
    async def _generate_unique_short_code(self, db: AsyncSession) -> str:
        """Generate a unique short code."""
        for attempt in range(self.max_retries):
            short_code = generate_short_code(6 + attempt)  # Increase length on retries
            
            # Check if code exists in database
            with trace_operation("database.check_code_exists"):
                result = await db.execute(
                    select(URL.id).where(URL.short_code == short_code)
                )
                
                if not result.scalar_one_or_none():
                    return short_code
        
        raise ValueError("Unable to generate unique short code")
    
    async def _cache_url(self, url_record: URL) -> None:
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
        
        await self.redis_manager.set_json(cache_key, url_data, expire=3600)
    
    @trace_function("url_service.check_url_expired")
    async def check_url_expired(self, url_record: URL) -> bool:
        """Check if URL has expired."""
        if not url_record.expires_at:
            return False
        
        return datetime.utcnow() > url_record.expires_at.replace(tzinfo=None)
    
    @trace_function("url_service.bulk_create_urls")
    async def bulk_create_urls(self, db: AsyncSession, urls_data: list[URLCreate]) -> list[URL]:
        """Create multiple URLs in bulk."""
        url_records = []
        
        for url_data in urls_data:
            try:
                url_record = await self.create_short_url(db, url_data)
                url_records.append(url_record)
            except Exception as e:
                # Log error but continue with other URLs
                continue
        
        return url_records
    
    @trace_function("url_service.search_urls")
    async def search_urls(
        self, 
        db: AsyncSession, 
        query: str, 
        limit: int = 50, 
        offset: int = 0
    ) -> list[URL]:
        """Search URLs by original URL or short code."""
        with trace_operation("database.search_urls"):
            result = await db.execute(
                select(URL)
                .where(
                    (URL.original_url.ilike(f"%{query}%")) |
                    (URL.short_code.ilike(f"%{query}%"))
                )
                .order_by(URL.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            
            return result.scalars().all()
