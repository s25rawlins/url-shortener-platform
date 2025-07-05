import time
from typing import Optional
from fastapi import Request, HTTPException
import sys
sys.path.append('/app')
from shared.redis_client import get_redis_manager, CacheKeys
from shared.utils import get_client_ip
from shared.observability import trace_function


class RateLimiter:
    def __init__(self, requests_per_minute: int = 100, window_seconds: int = 60):
        self.requests_per_minute = requests_per_minute
        self.window_seconds = window_seconds
        self.redis_manager = get_redis_manager()
    
    @trace_function("rate_limiter.check_rate_limit")
    async def check_rate_limit(self, request: Request) -> None:
        client_ip = get_client_ip(request)
        if not client_ip:
            client_ip = "unknown"
        
        current_time = int(time.time())
        window_start = current_time - self.window_seconds
        rate_limit_key = CacheKeys.rate_limit(f"{client_ip}:{window_start // self.window_seconds}")
        
        try:
            current_count = await self.redis_manager.get(rate_limit_key)
            current_count = int(current_count) if current_count else 0
            
            if current_count >= self.requests_per_minute:
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Please try again later.",
                    headers={"Retry-After": str(self.window_seconds)}
                )
            
            await self.redis_manager.increment(rate_limit_key)
            await self.redis_manager.expire(rate_limit_key, self.window_seconds)
            
        except HTTPException:
            raise
        except Exception:
            pass
    
    async def get_rate_limit_status(self, client_ip: str) -> dict:
        current_time = int(time.time())
        window_start = current_time - self.window_seconds
        rate_limit_key = CacheKeys.rate_limit(f"{client_ip}:{window_start // self.window_seconds}")
        
        try:
            current_count = await self.redis_manager.get(rate_limit_key)
            current_count = int(current_count) if current_count else 0
            
            return {
                "requests_made": current_count,
                "requests_limit": self.requests_per_minute,
                "requests_remaining": max(0, self.requests_per_minute - current_count),
                "window_seconds": self.window_seconds,
                "reset_time": window_start + self.window_seconds
            }
        except Exception:
            return {
                "requests_made": 0,
                "requests_limit": self.requests_per_minute,
                "requests_remaining": self.requests_per_minute,
                "window_seconds": self.window_seconds,
                "reset_time": current_time + self.window_seconds
            }


class AdvancedRateLimiter:
    def __init__(self):
        self.redis_manager = get_redis_manager()
        
        self.tiers = {
            "burst": {"requests": 10, "window": 10},
            "minute": {"requests": 100, "window": 60},
            "hour": {"requests": 1000, "window": 3600},
        }
    
    async def check_rate_limit(self, request: Request) -> None:
        client_ip = get_client_ip(request) or "unknown"
        current_time = int(time.time())
        
        for tier_name, tier_config in self.tiers.items():
            window_start = current_time - tier_config["window"]
            key = CacheKeys.rate_limit(f"{client_ip}:{tier_name}:{window_start // tier_config['window']}")
            
            try:
                current_count = await self.redis_manager.get(key)
                current_count = int(current_count) if current_count else 0
                
                if current_count >= tier_config["requests"]:
                    raise HTTPException(
                        status_code=429,
                        detail=f"Rate limit exceeded for {tier_name} tier. Please try again later.",
                        headers={"Retry-After": str(tier_config["window"])}
                    )
                
                await self.redis_manager.increment(key)
                await self.redis_manager.expire(key, tier_config["window"])
                
            except HTTPException:
                raise
            except Exception:
                continue
