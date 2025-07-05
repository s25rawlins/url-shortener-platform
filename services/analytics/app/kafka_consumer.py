"""Kafka consumer for processing click events."""

import os
import json
import asyncio
from typing import Dict, Any
from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

import sys
sys.path.append('/app')
from shared.database import get_database_manager
from shared.observability import trace_function, get_observability_manager


class KafkaConsumer:
    """Async Kafka consumer for click events."""
    
    def __init__(self, analytics_service):
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
        self.topic = os.getenv("KAFKA_TOPIC_CLICKS", "url_clicks")
        self.consumer_group = os.getenv("KAFKA_CONSUMER_GROUP", "analytics_service")
        self.analytics_service = analytics_service
        self.consumer = None
        self.running = False
        self.logger = get_observability_manager("analytics").get_logger()
        
    async def start_consuming(self):
        """Start consuming messages from Kafka."""
        try:
            self.consumer = AIOKafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.consumer_group,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=True,
                auto_commit_interval_ms=1000,
                max_poll_records=100,
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000
            )
            
            await self.consumer.start()
            self.running = True
            self.logger.info(f"Kafka consumer started for topic: {self.topic}")
            
            try:
                async for message in self.consumer:
                    await self._process_message(message)
            except asyncio.CancelledError:
                self.logger.info("Kafka consumer cancelled")
            except Exception as e:
                self.logger.error(f"Error in Kafka consumer: {e}")
                
        except Exception as e:
            self.logger.error(f"Failed to start Kafka consumer: {e}")
        finally:
            await self.stop()
    
    async def stop(self):
        """Stop the Kafka consumer."""
        self.running = False
        if self.consumer:
            try:
                await self.consumer.stop()
                self.logger.info("Kafka consumer stopped")
            except Exception as e:
                self.logger.error(f"Error stopping Kafka consumer: {e}")
    
    @trace_function("kafka_consumer.process_message")
    async def _process_message(self, message):
        """Process a single Kafka message."""
        try:
            event_data = message.value
            
            # Validate required fields
            if not self._validate_event_data(event_data):
                self.logger.warning(f"Invalid event data: {event_data}")
                return
            
            # Process the click event
            db_manager = get_database_manager()
            async with db_manager.get_session() as db:
                success = await self.analytics_service.process_click_event(db, event_data)
                
                if success:
                    self.logger.debug(
                        f"Processed click event",
                        short_code=event_data.get("short_code"),
                        partition=message.partition,
                        offset=message.offset
                    )
                else:
                    self.logger.error(
                        f"Failed to process click event",
                        short_code=event_data.get("short_code"),
                        partition=message.partition,
                        offset=message.offset
                    )
                    
        except Exception as e:
            self.logger.error(
                f"Error processing message",
                error=str(e),
                partition=message.partition,
                offset=message.offset
            )
    
    def _validate_event_data(self, event_data: Dict[str, Any]) -> bool:
        """Validate event data structure."""
        required_fields = ["url_id", "short_code"]
        
        if not isinstance(event_data, dict):
            return False
        
        for field in required_fields:
            if field not in event_data:
                return False
        
        return True
    
    def is_running(self) -> bool:
        """Check if consumer is running."""
        return self.running
    
    async def health_check(self) -> bool:
        """Check if Kafka consumer is healthy."""
        return self.running and self.consumer is not None


class BatchKafkaConsumer:
    """Batch processing Kafka consumer for higher throughput."""
    
    def __init__(self, analytics_service, batch_size: int = 100):
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
        self.topic = os.getenv("KAFKA_TOPIC_CLICKS", "url_clicks")
        self.consumer_group = os.getenv("KAFKA_CONSUMER_GROUP", "analytics_service")
        self.analytics_service = analytics_service
        self.batch_size = batch_size
        self.consumer = None
        self.running = False
        self.logger = get_observability_manager("analytics").get_logger()
        self.pending_events = []
        
    async def start_consuming(self):
        """Start consuming messages in batches."""
        try:
            self.consumer = AIOKafkaConsumer(
                self.topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=self.consumer_group,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset='latest',
                enable_auto_commit=False,  # Manual commit for batch processing
                max_poll_records=self.batch_size,
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000
            )
            
            await self.consumer.start()
            self.running = True
            self.logger.info(f"Batch Kafka consumer started for topic: {self.topic}")
            
            try:
                async for message in self.consumer:
                    await self._add_to_batch(message)
                    
                    if len(self.pending_events) >= self.batch_size:
                        await self._process_batch()
                        
            except asyncio.CancelledError:
                # Process remaining events before stopping
                if self.pending_events:
                    await self._process_batch()
                self.logger.info("Batch Kafka consumer cancelled")
            except Exception as e:
                self.logger.error(f"Error in batch Kafka consumer: {e}")
                
        except Exception as e:
            self.logger.error(f"Failed to start batch Kafka consumer: {e}")
        finally:
            await self.stop()
    
    async def _add_to_batch(self, message):
        """Add message to pending batch."""
        try:
            event_data = message.value
            if self._validate_event_data(event_data):
                self.pending_events.append({
                    "data": event_data,
                    "message": message
                })
        except Exception as e:
            self.logger.error(f"Error adding message to batch: {e}")
    
    async def _process_batch(self):
        """Process a batch of events."""
        if not self.pending_events:
            return
        
        try:
            db_manager = get_database_manager()
            async with db_manager.get_session() as db:
                successful_count = 0
                
                for event_item in self.pending_events:
                    success = await self.analytics_service.process_click_event(
                        db, event_item["data"]
                    )
                    if success:
                        successful_count += 1
                
                # Commit offsets for successfully processed messages
                if successful_count > 0:
                    await self.consumer.commit()
                
                self.logger.info(
                    f"Processed batch",
                    total_events=len(self.pending_events),
                    successful=successful_count,
                    failed=len(self.pending_events) - successful_count
                )
                
        except Exception as e:
            self.logger.error(f"Error processing batch: {e}")
        finally:
            self.pending_events.clear()
    
    def _validate_event_data(self, event_data: Dict[str, Any]) -> bool:
        """Validate event data structure."""
        required_fields = ["url_id", "short_code"]
        
        if not isinstance(event_data, dict):
            return False
        
        for field in required_fields:
            if field not in event_data:
                return False
        
        return True
    
    async def stop(self):
        """Stop the batch Kafka consumer."""
        self.running = False
        if self.consumer:
            try:
                await self.consumer.stop()
                self.logger.info("Batch Kafka consumer stopped")
            except Exception as e:
                self.logger.error(f"Error stopping batch Kafka consumer: {e}")
    
    def is_running(self) -> bool:
        """Check if consumer is running."""
        return self.running
