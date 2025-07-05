"""Tests for gateway rate limiter."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from fastapi import HTTPException
from services.gateway.app.rate_limiter import RateLimiter


class TestRateLimiter:
    """Test RateLimiter class."""

    @pytest.fixture
    def rate_limiter(self):
        """Create RateLimiter instance for testing."""
        return RateLimiter()

    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = Mock()
        request.client.host = "192.168.1.1"
        request.headers = {}
        return request

    @pytest.mark.asyncio
    async def test_check_rate_limit_allowed(self, rate_limiter, mock_request):
        """Test rate limit check when request is allowed."""
        with patch.object(rate_limiter.redis_manager, 'get', return_value=None), \
             patch.object(rate_limiter.redis_manager, 'set', return_value=None):
            
            # Should not raise exception
            await rate_limiter.check_rate_limit(mock_request)

    @pytest.mark.asyncio
    async def test_check_rate_limit_exceeded(self, rate_limiter, mock_request):
        """Test rate limit check when limit is exceeded."""
        with patch.object(rate_limiter.redis_manager, 'get', return_value=b'100'), \
             patch.object(rate_limiter.redis_manager, 'incr', return_value=101):
            
            with pytest.raises(HTTPException) as exc_info:
                await rate_limiter.check_rate_limit(mock_request)
            
            assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_check_rate_limit_increment(self, rate_limiter, mock_request):
        """Test rate limit increment for existing key."""
        with patch.object(rate_limiter.redis_manager, 'get', return_value=b'50'), \
             patch.object(rate_limiter.redis_manager, 'incr', return_value=51):
            
            # Should not raise exception
            await rate_limiter.check_rate_limit(mock_request)

    @pytest.mark.asyncio
    async def test_get_client_identifier_ip(self, rate_limiter, mock_request):
        """Test getting client identifier from IP."""
        identifier = await rate_limiter.get_client_identifier(mock_request)
        assert identifier == "192.168.1.1"

    @pytest.mark.asyncio
    async def test_get_client_identifier_forwarded(self, rate_limiter, mock_request):
        """Test getting client identifier from X-Forwarded-For header."""
        mock_request.headers = {"X-Forwarded-For": "10.0.0.1, 192.168.1.1"}
        
        identifier = await rate_limiter.get_client_identifier(mock_request)
        assert identifier == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_get_client_identifier_real_ip(self, rate_limiter, mock_request):
        """Test getting client identifier from X-Real-IP header."""
        mock_request.headers = {"X-Real-IP": "10.0.0.1"}
        
        identifier = await rate_limiter.get_client_identifier(mock_request)
        assert identifier == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_get_client_identifier_fallback(self, rate_limiter):
        """Test getting client identifier fallback."""
        mock_request = Mock()
        mock_request.headers = {}
        mock_request.client = None
        
        identifier = await rate_limiter.get_client_identifier(mock_request)
        assert identifier == "unknown"
