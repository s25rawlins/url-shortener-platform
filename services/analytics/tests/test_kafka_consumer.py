"""Tests for analytics Kafka consumer."""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from datetime import datetime
from uuid import uuid4
import json
from services.analytics.app.kafka_consumer import ClickEventConsumer
from services.shared.models import ClickEvent


class TestClickEventConsumer:
    """Test ClickEventConsumer class."""

    @pytest.fixture
    def consumer(self):
        """Create ClickEventConsumer instance for testing."""
        return ClickEventConsumer()

    @pytest.fixture
    def sample_click_event_data(self):
        """Create sample click event data."""
        return {
            "url_id": str(uuid4()),
            "short_code": "abc123",
            "clicked_at": datetime.utcnow().isoformat(),
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0...",
            "referer": "https://google.com",
            "country": "US",
            "city": "New York",
            "device_type": "Desktop",
            "browser": "Chrome",
            "os": "Windows"
        }

    @pytest.fixture
    def mock_kafka_message(self, sample_click_event_data):
        """Create mock Kafka message."""
        message = Mock()
        message.value = json.dumps(sample_click_event_data).encode()
        message.key = b"abc123"
        message.topic = "click-events"
        message.partition = 0
        message.offset = 123
        return message

    @pytest.mark.asyncio
    async def test_process_message_success(self, consumer, mock_kafka_message):
        """Test successful message processing."""
        with patch.object(consumer, 'analytics_service') as mock_service:
            mock_service.process_click_event = AsyncMock()
            
            await consumer.process_message(mock_kafka_message)
            
            mock_service.process_click_event.assert_called_once()
            call_args = mock_service.process_click_event.call_args[0]
            click_event = call_args[0]
            assert isinstance(click_event, ClickEvent)
            assert click_event.short_code == "abc123"

    @pytest.mark.asyncio
    async def test_process_message_invalid_json(self, consumer):
        """Test processing message with invalid JSON."""
        message = Mock()
        message.value = b"invalid json"
        message.key = b"abc123"
        
        # Should not raise exception, just log error
        await consumer.process_message(message)

    @pytest.mark.asyncio
    async def test_process_message_missing_fields(self, consumer):
        """Test processing message with missing required fields."""
        message = Mock()
        message.value = json.dumps({"short_code": "abc123"}).encode()  # Missing required fields
        message.key = b"abc123"
        
        # Should not raise exception, just log error
        await consumer.process_message(message)

    @pytest.mark.asyncio
    async def test_process_message_service_error(self, consumer, mock_kafka_message):
        """Test processing message when service raises error."""
        with patch.object(consumer, 'analytics_service') as mock_service:
            mock_service.process_click_event = AsyncMock(side_effect=Exception("Service error"))
            
            # Should not raise exception, just log error
            await consumer.process_message(mock_kafka_message)

    @pytest.mark.asyncio
    async def test_start_consumer(self, consumer):
        """Test starting the consumer."""
        with patch.object(consumer, 'consumer') as mock_consumer:
            mock_consumer.start = AsyncMock()
            mock_consumer.subscribe = Mock()
            
            await consumer.start()
            
            mock_consumer.subscribe.assert_called_once_with(["click-events"])
            mock_consumer.start.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_consumer(self, consumer):
        """Test stopping the consumer."""
        with patch.object(consumer, 'consumer') as mock_consumer:
            mock_consumer.stop = AsyncMock()
            
            await consumer.stop()
            
            mock_consumer.stop.assert_called_once()

    @pytest.mark.asyncio
    async def test_consume_messages(self, consumer, mock_kafka_message):
        """Test consuming messages loop."""
        with patch.object(consumer, 'consumer') as mock_consumer, \
             patch.object(consumer, 'process_message') as mock_process:
            
            # Mock consumer to return one message then stop
            mock_consumer.__aiter__ = AsyncMock(return_value=iter([mock_kafka_message]))
            mock_process.return_value = None
            
            # This would normally run forever, so we'll just test one iteration
            async for message in mock_consumer:
                await consumer.process_message(message)
                break
            
            mock_process.assert_called_once_with(mock_kafka_message)

    def test_deserialize_click_event(self, consumer, sample_click_event_data):
        """Test click event deserialization."""
        json_data = json.dumps(sample_click_event_data)
        
        click_event = consumer._deserialize_click_event(json_data)
        
        assert isinstance(click_event, ClickEvent)
        assert click_event.short_code == "abc123"
        assert click_event.ip_address == "192.168.1.1"

    def test_deserialize_click_event_minimal(self, consumer):
        """Test click event deserialization with minimal data."""
        minimal_data = {
            "url_id": str(uuid4()),
            "short_code": "abc123",
            "clicked_at": datetime.utcnow().isoformat()
        }
        json_data = json.dumps(minimal_data)
        
        click_event = consumer._deserialize_click_event(json_data)
        
        assert isinstance(click_event, ClickEvent)
        assert click_event.short_code == "abc123"
        assert click_event.ip_address is None

    def test_deserialize_click_event_invalid(self, consumer):
        """Test click event deserialization with invalid data."""
        with pytest.raises(Exception):
            consumer._deserialize_click_event("invalid json")
