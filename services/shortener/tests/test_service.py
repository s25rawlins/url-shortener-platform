"""Tests for URL shortener service."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

import sys
sys.path.append('/app')
from services.shortener.app.service import URLService
from services.shared.database import URL
from services.shared.models import URLCreate


class TestURLService:
    """Test URLService class."""

    @pytest.fixture
    def url_service(self):
        """Create URLService instance for testing."""
        return URLService()

    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        return AsyncMock(spec=AsyncSession)

    @pytest.fixture
    def sample_url_create(self):
        """Create sample URLCreate instance."""
        return URLCreate(
            original_url="https://example.com",
            custom_code=None,
            expires_at=None,
            metadata={"source": "test"}
        )

    @pytest.fixture
    def sample_url_record(self):
        """Create sample URL record."""
        url_record = URL()
        url_record.id = uuid4()
        url_record.original_url = "https://example.com"
        url_record.short_code = "abc123"
        url_record.created_at = datetime.utcnow()
        url_record.is_active = True
        url_record.metadata = {"source": "test"}
        return url_record


class TestCreateShortURL(TestURLService):
    """Test create_short_url method."""

    @pytest.mark.asyncio
    async def test_create_short_url_success(self, url_service, mock_db_session, sample_url_create):
        """Test successful URL creation."""
        # Mock dependencies
        with patch('services.shortener.app.service.is_valid_url', return_value=True), \
             patch('services.shortener.app.service.normalize_url', return_value="https://example.com"), \
             patch('services.shortener.app.service.sanitize_metadata', return_value={"source": "test"}), \
             patch.object(url_service, '_generate_unique_short_code', return_value="abc123"), \
             patch.object(url_service, '_cache_url', return_value=None):
            
            # Mock database operations
            mock_db_session.add = Mock()
            mock_db_session.commit = AsyncMock()
            mock_db_session.refresh = AsyncMock()
            
            result = await url_service.create_short_url(mock_db_session, sample_url_create)
            
            # Assertions
            assert result.original_url == "https://example.com"
            assert result.short_code == "abc123"
            assert result.metadata == {"source": "test"}
            mock_db_session.add.assert_called_once()
            mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_short_url_invalid_url(self, url_service, mock_db_session):
        """Test URL creation with invalid URL."""
        invalid_url_create = URLCreate(original_url="https://invalid-url")
        
        with patch('services.shortener.app.service.is_valid_url', return_value=False):
            with pytest.raises(ValueError, match="Invalid URL format"):
                await url_service.create_short_url(mock_db_session, invalid_url_create)

    @pytest.mark.asyncio
    async def test_create_short_url_with_custom_code(self, url_service, mock_db_session):
        """Test URL creation with custom code."""
        url_create = URLCreate(
            original_url="https://example.com",
            custom_code="mycustom"
        )
        
        with patch('services.shortener.app.service.is_valid_url', return_value=True), \
             patch('services.shortener.app.service.normalize_url', return_value="https://example.com"), \
             patch('services.shortener.app.service.validate_custom_code', return_value=(True, "Valid")), \
             patch('services.shortener.app.service.sanitize_metadata', return_value={}), \
             patch.object(url_service, '_cache_url', return_value=None):
            
            mock_db_session.add = Mock()
            mock_db_session.commit = AsyncMock()
            mock_db_session.refresh = AsyncMock()
            
            result = await url_service.create_short_url(mock_db_session, url_create)
            
            assert result.short_code == "mycustom"

    @pytest.mark.asyncio
    async def test_create_short_url_invalid_custom_code(self, url_service, mock_db_session):
        """Test URL creation with invalid custom code."""
        url_create = URLCreate(
            original_url="https://example.com",
            custom_code="invalid-code"
        )
        
        with patch('services.shortener.app.service.is_valid_url', return_value=True), \
             patch('services.shortener.app.service.normalize_url', return_value="https://example.com"), \
             patch('services.shortener.app.service.validate_custom_code', return_value=(False, "Invalid code")):
            
            with pytest.raises(ValueError, match="Invalid code"):
                await url_service.create_short_url(mock_db_session, url_create)

    @pytest.mark.asyncio
    async def test_create_short_url_duplicate_code(self, url_service, mock_db_session, sample_url_create):
        """Test URL creation with duplicate short code."""
        with patch('services.shortener.app.service.is_valid_url', return_value=True), \
             patch('services.shortener.app.service.normalize_url', return_value="https://example.com"), \
             patch('services.shortener.app.service.sanitize_metadata', return_value={}), \
             patch.object(url_service, '_generate_unique_short_code', return_value="abc123"):
            
            mock_db_session.add = Mock()
            mock_db_session.commit = AsyncMock(side_effect=IntegrityError("", "", ""))
            mock_db_session.rollback = AsyncMock()
            
            with pytest.raises(ValueError, match="Short code already exists"):
                await url_service.create_short_url(mock_db_session, sample_url_create)
            
            mock_db_session.rollback.assert_called_once()


class TestGetURLByCode(TestURLService):
    """Test get_url_by_code method."""

    @pytest.mark.asyncio
    async def test_get_url_by_code_from_cache(self, url_service, mock_db_session):
        """Test getting URL from cache."""
        cached_data = {
            "id": str(uuid4()),
            "original_url": "https://example.com",
            "short_code": "abc123",
            "created_at": "2023-01-01T00:00:00",
            "is_active": True,
            "metadata": {}
        }
        
        with patch.object(url_service.redis_manager, 'get_json', return_value=cached_data):
            result = await url_service.get_url_by_code(mock_db_session, "abc123")
            
            assert result is not None
            assert result.short_code == "abc123"
            assert result.original_url == "https://example.com"

    @pytest.mark.asyncio
    async def test_get_url_by_code_from_database(self, url_service, mock_db_session, sample_url_record):
        """Test getting URL from database when not in cache."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = sample_url_record
        mock_db_session.execute.return_value = mock_result
        
        with patch.object(url_service.redis_manager, 'get_json', return_value=None), \
             patch.object(url_service, '_cache_url', return_value=None):
            
            result = await url_service.get_url_by_code(mock_db_session, "abc123")
            
            assert result == sample_url_record
            mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_url_by_code_not_found(self, url_service, mock_db_session):
        """Test getting non-existent URL."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        with patch.object(url_service.redis_manager, 'get_json', return_value=None):
            result = await url_service.get_url_by_code(mock_db_session, "nonexistent")
            
            assert result is None


class TestDeactivateURL(TestURLService):
    """Test deactivate_url method."""

    @pytest.mark.asyncio
    async def test_deactivate_url_success(self, url_service, mock_db_session):
        """Test successful URL deactivation."""
        mock_result = Mock()
        mock_result.rowcount = 1
        mock_db_session.execute.return_value = mock_result
        mock_db_session.commit = AsyncMock()
        
        with patch.object(url_service.redis_manager, 'delete', return_value=None):
            result = await url_service.deactivate_url(mock_db_session, "abc123")
            
            assert result is True
            mock_db_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_deactivate_url_not_found(self, url_service, mock_db_session):
        """Test deactivating non-existent URL."""
        mock_result = Mock()
        mock_result.rowcount = 0
        mock_db_session.execute.return_value = mock_result
        
        result = await url_service.deactivate_url(mock_db_session, "nonexistent")
        
        assert result is False


class TestGetURLStats(TestURLService):
    """Test get_url_stats method."""

    @pytest.mark.asyncio
    async def test_get_url_stats_success(self, url_service, mock_db_session):
        """Test getting URL statistics."""
        mock_row = Mock()
        mock_row.id = uuid4()
        mock_row.short_code = "abc123"
        mock_row.original_url = "https://example.com"
        mock_row.created_at = datetime.utcnow()
        mock_row.is_active = True
        mock_row.total_clicks = 100
        mock_row.unique_clicks = 80
        mock_row.unique_visitors = 60
        mock_row.last_clicked_at = datetime.utcnow()
        
        mock_result = Mock()
        mock_result.fetchone.return_value = mock_row
        mock_db_session.execute.return_value = mock_result
        
        result = await url_service.get_url_stats(mock_db_session, "abc123")
        
        assert result is not None
        assert result["short_code"] == "abc123"
        assert result["total_clicks"] == 100
        assert result["unique_clicks"] == 80

    @pytest.mark.asyncio
    async def test_get_url_stats_not_found(self, url_service, mock_db_session):
        """Test getting stats for non-existent URL."""
        mock_result = Mock()
        mock_result.fetchone.return_value = None
        mock_db_session.execute.return_value = mock_result
        
        result = await url_service.get_url_stats(mock_db_session, "nonexistent")
        
        assert result is None


class TestGenerateUniqueShortCode(TestURLService):
    """Test _generate_unique_short_code method."""

    @pytest.mark.asyncio
    async def test_generate_unique_short_code_success(self, url_service, mock_db_session):
        """Test generating unique short code."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None  # Code doesn't exist
        mock_db_session.execute.return_value = mock_result
        
        with patch('services.shortener.app.service.generate_short_code', return_value="abc123"):
            result = await url_service._generate_unique_short_code(mock_db_session)
            
            assert result == "abc123"

    @pytest.mark.asyncio
    async def test_generate_unique_short_code_retry(self, url_service, mock_db_session):
        """Test generating unique short code with retries."""
        # First call returns existing code, second call returns unique code
        mock_result1 = Mock()
        mock_result1.scalar_one_or_none.return_value = uuid4()  # Code exists
        mock_result2 = Mock()
        mock_result2.scalar_one_or_none.return_value = None  # Code doesn't exist
        
        mock_db_session.execute.side_effect = [mock_result1, mock_result2]
        
        with patch('services.shortener.app.service.generate_short_code', side_effect=["abc123", "def456"]):
            result = await url_service._generate_unique_short_code(mock_db_session)
            
            assert result == "def456"

    @pytest.mark.asyncio
    async def test_generate_unique_short_code_max_retries(self, url_service, mock_db_session):
        """Test generating unique short code exceeding max retries."""
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = uuid4()  # Code always exists
        mock_db_session.execute.return_value = mock_result
        
        with patch('services.shortener.app.service.generate_short_code', return_value="abc123"):
            with pytest.raises(ValueError, match="Unable to generate unique short code"):
                await url_service._generate_unique_short_code(mock_db_session)


class TestCacheURL(TestURLService):
    """Test _cache_url method."""

    @pytest.mark.asyncio
    async def test_cache_url_success(self, url_service, sample_url_record):
        """Test caching URL record."""
        with patch.object(url_service.redis_manager, 'set_json', return_value=None) as mock_set_json:
            await url_service._cache_url(sample_url_record)
            
            mock_set_json.assert_called_once()
            call_args = mock_set_json.call_args
            assert "url:abc123" in call_args[0][0]  # Cache key
            assert call_args[1]["expire"] == 3600  # Expiration


class TestCheckURLExpired(TestURLService):
    """Test check_url_expired method."""

    @pytest.mark.asyncio
    async def test_check_url_expired_no_expiration(self, url_service, sample_url_record):
        """Test checking URL with no expiration date."""
        sample_url_record.expires_at = None
        
        result = await url_service.check_url_expired(sample_url_record)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_check_url_expired_not_expired(self, url_service, sample_url_record):
        """Test checking URL that hasn't expired."""
        sample_url_record.expires_at = datetime.utcnow() + timedelta(hours=1)
        
        result = await url_service.check_url_expired(sample_url_record)
        
        assert result is False

    @pytest.mark.asyncio
    async def test_check_url_expired_expired(self, url_service, sample_url_record):
        """Test checking URL that has expired."""
        sample_url_record.expires_at = datetime.utcnow() - timedelta(hours=1)
        
        result = await url_service.check_url_expired(sample_url_record)
        
        assert result is True


class TestBulkCreateURLs(TestURLService):
    """Test bulk_create_urls method."""

    @pytest.mark.asyncio
    async def test_bulk_create_urls_success(self, url_service, mock_db_session):
        """Test bulk creating URLs."""
        urls_data = [
            URLCreate(original_url="https://example1.com"),
            URLCreate(original_url="https://example2.com"),
        ]
        
        mock_url_record = Mock()
        with patch.object(url_service, 'create_short_url', return_value=mock_url_record):
            result = await url_service.bulk_create_urls(mock_db_session, urls_data)
            
            assert len(result) == 2
            assert all(url == mock_url_record for url in result)

    @pytest.mark.asyncio
    async def test_bulk_create_urls_with_errors(self, url_service, mock_db_session):
        """Test bulk creating URLs with some errors."""
        urls_data = [
            URLCreate(original_url="https://example1.com"),
            URLCreate(original_url="https://example2.com"),
        ]
        
        mock_url_record = Mock()
        with patch.object(url_service, 'create_short_url', side_effect=[mock_url_record, Exception("Error")]):
            result = await url_service.bulk_create_urls(mock_db_session, urls_data)
            
            assert len(result) == 1  # Only successful creation
            assert result[0] == mock_url_record


class TestSearchURLs(TestURLService):
    """Test search_urls method."""

    @pytest.mark.asyncio
    async def test_search_urls_success(self, url_service, mock_db_session, sample_url_record):
        """Test searching URLs."""
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = [sample_url_record]
        mock_db_session.execute.return_value = mock_result
        
        result = await url_service.search_urls(mock_db_session, "example", limit=10, offset=0)
        
        assert len(result) == 1
        assert result[0] == sample_url_record
        mock_db_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_search_urls_no_results(self, url_service, mock_db_session):
        """Test searching URLs with no results."""
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db_session.execute.return_value = mock_result
        
        result = await url_service.search_urls(mock_db_session, "nonexistent")
        
        assert len(result) == 0
