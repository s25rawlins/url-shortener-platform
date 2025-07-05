"""Tests for redirector Kafka producer."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime
from uuid import uuid4
from services.redirector.app.kafka_producer import ClickEventProducer
from services.shared.models import ClickEvent


class TestClickEventProducer:
    """Test ClickEventProducer class."""

    @pytest.fixture
    def producer(self):
        """Create ClickEventProducer instance for testing."""
        return ClickEventProducer()

    @pytest.fixture
    def sample_click_event(self):
        """Create sample ClickEvent."""
        return ClickEvent(
            url_id=uuid4(),
            short_code="abc123",
            clicked_at=datetime.utcnow(),
            ip_address="192.168.1.1",
            user_agent="Mozilla/5.0...",
            referer="https://google.com",
            country="US",
            city="New York",
            device_type="Desktop",
            browser="Chrome",
            os="Windows"
        )

    @pytest.mark.asyncio
    async def test_send_click_event_success(self, producer, sample_click_event):
        """Test successful click event sending."""
        with patch.object(producer, 'producer') as mock_producer:
            mock_producer.send_and_wait = AsyncMock()
            
            await producer.send_click_event(sample_click_event)
            
            mock_producer.send_and_wait.assert_called_once()
            call_args = mock_producer.send_and_wait.call_args[1]
            assert call_args["topic"] == "click-events"
            assert call_args["key"] == sample_click_event.short_code.encode()

    @pytest.mark.asyncio
    async def test_send_click_event_failure(self, producer, sample_click_event):
        """Test click event sending failure."""
        with patch.object(producer, 'producer') as mock_producer:
            mock_producer.send_and_wait = AsyncMock(side_effect=Exception("Kafka error"))
            
            # Should not raise exception, just log error
            await producer.send_click_event(sample_click_event)

    @pytest.mark.asyncio
    async def test_start_producer(self, producer):
        """Test starting the producer."""
        with patch.object(producer, 'producer') as mock_producer:
            mock_producer.start = AsyncMock()
            
            await producer.start()
            
            mock_producer.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_producer(self, producer):
        """Test stopping the producer."""
        with patch.object(producer, 'producer') as mock_producer:
            mock_producer.stop = AsyncMock()
            
            await producer.stop()
            
            mock_producer.stop.assert_called_once()

    def test_serialize_click_event(self, producer, sample_click_event):
        """Test click event serialization."""
        serialized = producer._serialize_click_event(sample_click_event)
        
        assert isinstance(serialized, bytes)
        # Should be valid JSON
        import json
        data = json.loads(serialized.decode())
        assert data["short_code"] == sample_click_event.short_code
        assert data["ip_address"] == sample_click_event.ip_address

    def test_serialize_click_event_minimal(self, producer):
        """Test click event serialization with minimal data."""
        click_event = ClickEvent(
            url_id=uuid4(),
            short_code="abc123",
            clicked_at=datetime.utcnow()
        )
        
        serialized = producer._serialize_click_event(click_event)
        
        assert isinstance(serialized, bytes)
        import json
        data = json.loads(serialized.decode())
        assert data["short_code"] == "abc123"
        assert data["ip_address"] is None
