import os
import json
from typing import Optional, Any, Dict
import redis.asyncio as redis
from redis.asyncio import Redis
import logging

logger = logging.getLogger(__name__)


class RedisManager:
    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self.pool = redis.ConnectionPool.from_url(
            redis_url,
            max_connections=20,
            retry_on_timeout=True,
            socket_keepalive=True,
            socket_keepalive_options={},
        )
        self._client: Optional[Redis] = None

    @property
    def client(self) -> Redis:
        if self._client is None:
            self._client = Redis(connection_pool=self.pool)
        return self._client

    async def get(self, key: str) -> Optional[str]:
        try:
            value = await self.client.get(key)
            return value.decode('utf-8') if value else None
        except Exception as e:
            logger.error(f"Redis GET error for key {key}: {e}")
            return None

    async def set(self, key: str, value: str, expire: Optional[int] = None) -> bool:
        try:
            result = await self.client.set(key, value, ex=expire)
            return bool(result)
        except Exception as e:
            logger.error(f"Redis SET error for key {key}: {e}")
            return False

    async def get_json(self, key: str) -> Optional[Dict[str, Any]]:
        try:
            value = await self.get(key)
            return json.loads(value) if value else None
        except (json.JSONDecodeError, Exception) as e:
            logger.error(f"Redis GET JSON error for key {key}: {e}")
            return None

    async def set_json(self, key: str, value: Dict[str, Any], expire: Optional[int] = None) -> bool:
        try:
            json_str = json.dumps(value, default=str)
            return await self.set(key, json_str, expire)
        except Exception as e:
            logger.error(f"Redis SET JSON error for key {key}: {e}")
            return False

    async def delete(self, key: str) -> bool:
        try:
            result = await self.client.delete(key)
            return bool(result)
        except Exception as e:
            logger.error(f"Redis DELETE error for key {key}: {e}")
            return False

    async def exists(self, key: str) -> bool:
        try:
            result = await self.client.exists(key)
            return bool(result)
        except Exception as e:
            logger.error(f"Redis EXISTS error for key {key}: {e}")
            return False

    async def increment(self, key: str, amount: int = 1) -> Optional[int]:
        try:
            result = await self.client.incrby(key, amount)
            return int(result)
        except Exception as e:
            logger.error(f"Redis INCREMENT error for key {key}: {e}")
            return None

    async def expire(self, key: str, seconds: int) -> bool:
        try:
            result = await self.client.expire(key, seconds)
            return bool(result)
        except Exception as e:
            logger.error(f"Redis EXPIRE error for key {key}: {e}")
            return False

    async def health_check(self) -> bool:
        try:
            await self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return False

    async def close(self):
        if self._client:
            await self._client.close()
        await self.pool.disconnect()


# Global Redis manager instance
_redis_manager: Optional[RedisManager] = None


def get_redis_manager() -> RedisManager:
    global _redis_manager
    if _redis_manager is None:
        redis_url = os.getenv("REDIS_URL")
        if not redis_url:
            raise ValueError("REDIS_URL environment variable is required")
        _redis_manager = RedisManager(redis_url)
    return _redis_manager


class CacheKeys:
    @staticmethod
    def url_by_code(short_code: str) -> str:
        return f"url:code:{short_code}"
    
    @staticmethod
    def url_by_id(url_id: str) -> str:
        return f"url:id:{url_id}"
    
    @staticmethod
    def analytics_summary(short_code: str, date: str) -> str:
        return f"analytics:{short_code}:{date}"
    
    @staticmethod
    def rate_limit(identifier: str) -> str:
        return f"rate_limit:{identifier}"
    
    @staticmethod
    def health_check(service: str) -> str:
        return f"health:{service}"


async def with_fallback(cache_operation, fallback_operation, cache_key: str, expire: Optional[int] = 300):
    redis_manager = get_redis_manager()
    
    try:
        cached_result = await cache_operation()
        if cached_result is not None:
            return cached_result
    except Exception as e:
        logger.warning(f"Cache operation failed for key {cache_key}: {e}")
    
    try:
        result = await fallback_operation()
        if result is not None:
            if isinstance(result, dict):
                await redis_manager.set_json(cache_key, result, expire)
            else:
                await redis_manager.set(cache_key, str(result), expire)
        return result
    except Exception as e:
        logger.error(f"Fallback operation failed for key {cache_key}: {e}")
        raise
