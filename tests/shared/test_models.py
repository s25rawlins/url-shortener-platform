"""Tests for shared Pydantic models."""

import pytest
from datetime import datetime
from uuid import uuid4
from pydantic import ValidationError
from services.shared.models import (
    URLCreate,
    URLResponse,
    ClickEvent,
    AnalyticsResponse,
    HealthCheck,
    ErrorResponse,
)


class TestURLCreate:
    """Test URLCreate model."""

    def test_url_create_valid(self):
        """Test creating valid URLCreate instance."""
        url_data = URLCreate(original_url="https://example.com")
        assert str(url_data.original_url) == "https://example.com"
        assert url_data.custom_code is None
        assert url_data.expires_at is None
        assert url_data.metadata is None

    def test_url_create_with_custom_code(self):
        """Test URLCreate with custom code."""
        url_data = URLCreate(
            original_url="https://example.com",
            custom_code="mycode"
        )
        assert url_data.custom_code == "mycode"

    def test_url_create_with_expiration(self):
        """Test URLCreate with expiration date."""
        expires_at = datetime.now()
        url_data = URLCreate(
            original_url="https://example.com",
            expires_at=expires_at
        )
        assert url_data.expires_at == expires_at

    def test_url_create_with_metadata(self):
        """Test URLCreate with metadata."""
        metadata = {"source": "api", "user_id": "123"}
        url_data = URLCreate(
            original_url="https://example.com",
            metadata=metadata
        )
        assert url_data.metadata == metadata

    def test_url_create_invalid_url(self):
        """Test URLCreate with invalid URL."""
        with pytest.raises(ValidationError):
            URLCreate(original_url="not-a-url")

    def test_url_create_missing_url(self):
        """Test URLCreate without URL."""
        with pytest.raises(ValidationError):
            URLCreate()


class TestURLResponse:
    """Test URLResponse model."""

    def test_url_response_valid(self):
        """Test creating valid URLResponse instance."""
        url_id = uuid4()
        created_at = datetime.now()
        
        url_response = URLResponse(
            id=url_id,
            original_url="https://example.com",
            short_code="abc123",
            short_url="https://short.ly/abc123",
            created_at=created_at,
            is_active=True
        )
        
        assert url_response.id == url_id
        assert url_response.original_url == "https://example.com"
        assert url_response.short_code == "abc123"
        assert url_response.short_url == "https://short.ly/abc123"
        assert url_response.created_at == created_at
        assert url_response.is_active is True
        assert url_response.expires_at is None
        assert url_response.metadata is None

    def test_url_response_with_optional_fields(self):
        """Test URLResponse with optional fields."""
        url_id = uuid4()
        created_at = datetime.now()
        expires_at = datetime.now()
        metadata = {"source": "web"}
        
        url_response = URLResponse(
            id=url_id,
            original_url="https://example.com",
            short_code="abc123",
            short_url="https://short.ly/abc123",
            created_at=created_at,
            expires_at=expires_at,
            is_active=True,
            metadata=metadata
        )
        
        assert url_response.expires_at == expires_at
        assert url_response.metadata == metadata

    def test_url_response_missing_required_fields(self):
        """Test URLResponse with missing required fields."""
        with pytest.raises(ValidationError):
            URLResponse(
                original_url="https://example.com",
                short_code="abc123"
                # Missing required fields
            )


class TestClickEvent:
    """Test ClickEvent model."""

    def test_click_event_valid(self):
        """Test creating valid ClickEvent instance."""
        url_id = uuid4()
        clicked_at = datetime.now()
        
        click_event = ClickEvent(
            url_id=url_id,
            short_code="abc123",
            clicked_at=clicked_at
        )
        
        assert click_event.url_id == url_id
        assert click_event.short_code == "abc123"
        assert click_event.clicked_at == clicked_at
        assert click_event.ip_address is None
        assert click_event.user_agent is None

    def test_click_event_with_optional_fields(self):
        """Test ClickEvent with optional fields."""
        url_id = uuid4()
        clicked_at = datetime.now()
        metadata = {"campaign": "email"}
        
        click_event = ClickEvent(
            url_id=url_id,
            short_code="abc123",
            clicked_at=clicked_at,
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0...",
            referer="https://google.com",
            country="US",
            city="New York",
            device_type="Desktop",
            browser="Chrome",
            os="Windows",
            metadata=metadata
        )
        
        assert click_event.ip_address == "192.168.1.1"
        assert click_event.user_agent == "Mozilla/5.0..."
        assert click_event.referer == "https://google.com"
        assert click_event.country == "US"
        assert click_event.city == "New York"
        assert click_event.device_type == "Desktop"
        assert click_event.browser == "Chrome"
        assert click_event.os == "Windows"
        assert click_event.metadata == metadata

    def test_click_event_missing_required_fields(self):
        """Test ClickEvent with missing required fields."""
        with pytest.raises(ValidationError):
            ClickEvent(
                short_code="abc123"
                # Missing url_id and clicked_at
            )


class TestAnalyticsResponse:
    """Test AnalyticsResponse model."""

    def test_analytics_response_valid(self):
        """Test creating valid AnalyticsResponse instance."""
        url_id = uuid4()
        created_at = datetime.now()
        
        analytics = AnalyticsResponse(
            url_id=url_id,
            short_code="abc123",
            original_url="https://example.com",
            total_clicks=100,
            unique_clicks=80,
            unique_visitors=60,
            created_at=created_at
        )
        
        assert analytics.url_id == url_id
        assert analytics.short_code == "abc123"
        assert analytics.original_url == "https://example.com"
        assert analytics.total_clicks == 100
        assert analytics.unique_clicks == 80
        assert analytics.unique_visitors == 60
        assert analytics.created_at == created_at
        assert analytics.last_clicked_at is None
        assert analytics.daily_stats == []

    def test_analytics_response_with_optional_fields(self):
        """Test AnalyticsResponse with optional fields."""
        url_id = uuid4()
        created_at = datetime.now()
        last_clicked_at = datetime.now()
        daily_stats = [{"date": "2023-01-01", "clicks": 10}]
        top_countries = [{"country": "US", "clicks": 50}]
        
        analytics = AnalyticsResponse(
            url_id=url_id,
            short_code="abc123",
            original_url="https://example.com",
            total_clicks=100,
            unique_clicks=80,
            unique_visitors=60,
            created_at=created_at,
            last_clicked_at=last_clicked_at,
            daily_stats=daily_stats,
            top_countries=top_countries
        )
        
        assert analytics.last_clicked_at == last_clicked_at
        assert analytics.daily_stats == daily_stats
        assert analytics.top_countries == top_countries

    def test_analytics_response_missing_required_fields(self):
        """Test AnalyticsResponse with missing required fields."""
        with pytest.raises(ValidationError):
            AnalyticsResponse(
                short_code="abc123",
                original_url="https://example.com"
                # Missing required fields
            )


class TestHealthCheck:
    """Test HealthCheck model."""

    def test_health_check_default(self):
        """Test HealthCheck with default values."""
        health = HealthCheck(service="test-service")
        
        assert health.status == "healthy"
        assert health.service == "test-service"
        assert health.version == "1.0.0"
        assert health.dependencies == {}
        assert isinstance(health.timestamp, datetime)

    def test_health_check_custom_values(self):
        """Test HealthCheck with custom values."""
        timestamp = datetime.now()
        dependencies = {"database": "connected", "redis": "connected"}
        
        health = HealthCheck(
            status="degraded",
            timestamp=timestamp,
            service="custom-service",
            version="2.0.0",
            dependencies=dependencies
        )
        
        assert health.status == "degraded"
        assert health.timestamp == timestamp
        assert health.service == "custom-service"
        assert health.version == "2.0.0"
        assert health.dependencies == dependencies

    def test_health_check_missing_service(self):
        """Test HealthCheck without service name."""
        with pytest.raises(ValidationError):
            HealthCheck()


class TestErrorResponse:
    """Test ErrorResponse model."""

    def test_error_response_required_fields(self):
        """Test ErrorResponse with required fields."""
        error = ErrorResponse(
            error="ValidationError",
            message="Invalid input data"
        )
        
        assert error.error == "ValidationError"
        assert error.message == "Invalid input data"
        assert isinstance(error.timestamp, datetime)
        assert error.trace_id is None

    def test_error_response_with_trace_id(self):
        """Test ErrorResponse with trace ID."""
        timestamp = datetime.now()
        
        error = ErrorResponse(
            error="DatabaseError",
            message="Connection failed",
            timestamp=timestamp,
            trace_id="abc-123-def"
        )
        
        assert error.error == "DatabaseError"
        assert error.message == "Connection failed"
        assert error.timestamp == timestamp
        assert error.trace_id == "abc-123-def"

    def test_error_response_missing_required_fields(self):
        """Test ErrorResponse with missing required fields."""
        with pytest.raises(ValidationError):
            ErrorResponse(error="SomeError")  # Missing message
        
        with pytest.raises(ValidationError):
            ErrorResponse(message="Some message")  # Missing error


class TestModelSerialization:
    """Test model serialization and deserialization."""

    def test_url_create_json_serialization(self):
        """Test URLCreate JSON serialization."""
        url_data = URLCreate(
            original_url="https://example.com",
            custom_code="test123",
            metadata={"source": "api"}
        )
        
        json_data = url_data.model_dump()
        assert json_data["original_url"] == "https://example.com"
        assert json_data["custom_code"] == "test123"
        assert json_data["metadata"] == {"source": "api"}

    def test_url_response_json_serialization(self):
        """Test URLResponse JSON serialization."""
        url_id = uuid4()
        created_at = datetime.now()
        
        url_response = URLResponse(
            id=url_id,
            original_url="https://example.com",
            short_code="abc123",
            short_url="https://short.ly/abc123",
            created_at=created_at,
            is_active=True
        )
        
        json_data = url_response.model_dump()
        assert json_data["id"] == str(url_id)  # UUID serialized as string
        assert json_data["original_url"] == "https://example.com"
        assert json_data["is_active"] is True

    def test_click_event_json_serialization(self):
        """Test ClickEvent JSON serialization."""
        url_id = uuid4()
        clicked_at = datetime.now()
        
        click_event = ClickEvent(
            url_id=url_id,
            short_code="abc123",
            clicked_at=clicked_at,
            ip_address="192.168.1.1"
        )
        
        json_data = click_event.model_dump()
        assert json_data["url_id"] == str(url_id)
        assert json_data["short_code"] == "abc123"
        assert json_data["ip_address"] == "192.168.1.1"
