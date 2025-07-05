"""Kafka producer for sending click events."""

import os
import json
import asyncio
from typing import Dict, Any, Optional
from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

import sys
sys.path.append('/app')
from shared.observability import trace_function, get_observability_manager


class KafkaProducer:
    """Async Kafka producer for click events."""
    
    def __init__(self):
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
        self.topic = os.getenv("KAFKA_TOPIC_CLICKS", "url_clicks")
        self.producer: Optional[AIOKafkaProducer] = None
        self.logger = get_observability_manager("redirector").get_logger()
        
    async def start(self):
        """Start the Kafka producer."""
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                # Producer configuration for reliability
                acks='all',  # Wait for all replicas to acknowledge
                retries=3,
                retry_backoff_ms=1000,
                request_timeout_ms=30000,
                # Batching for performance
                batch_size=16384,
                linger_ms=10,
                # Compression
                compression_type='gzip'
            )
            
            await self.producer.start()
            self.logger.info("Kafka producer started successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to start Kafka producer: {e}")
            self.producer = None
    
    async def stop(self):
        """Stop the Kafka producer."""
        if self.producer:
            try:
                await self.producer.stop()
                self.logger.info("Kafka producer stopped")
            except Exception as e:
                self.logger.error(f"Error stopping Kafka producer: {e}")
    
    @trace_function("kafka_producer.send_click_event")
    async def send_click_event(self, click_data: Dict[str, Any]) -> bool:
        """Send click event to Kafka topic."""
        if not self.producer:
            self.logger.warning("Kafka producer not available, skipping click event")
            return False
        
        try:
            # Use short_code as partition key for better distribution
            partition_key = click_data.get("short_code", "unknown")
            
            # Add metadata
            enriched_data = {
                **click_data,
                "event_type": "click",
                "service": "redirector",
                "timestamp": click_data.get("clicked_at"),
                "version": "1.0.0"
            }
            
            # Send to Kafka
            future = await self.producer.send(
                topic=self.topic,
                value=enriched_data,
                key=partition_key
            )
            
            # Wait for acknowledgment (with timeout)
            record_metadata = await asyncio.wait_for(future, timeout=5.0)
            
            self.logger.debug(
                f"Click event sent successfully",
                topic=record_metadata.topic,
                partition=record_metadata.partition,
                offset=record_metadata.offset,
                short_code=click_data.get("short_code")
            )
            
            return True
            
        except asyncio.TimeoutError:
            self.logger.error(f"Timeout sending click event to Kafka")
            return False
        except KafkaError as e:
            self.logger.error(f"Kafka error sending click event: {e}")
            return False
        except Exception as e:
            self.logger.error(f"Unexpected error sending click event: {e}")
            return False
    
    @trace_function("kafka_producer.send_batch_events")
    async def send_batch_events(self, events: list[Dict[str, Any]]) -> int:
        """Send multiple click events in batch."""
        if not self.producer:
            self.logger.warning("Kafka producer not available, skipping batch events")
            return 0
        
        successful_sends = 0
        
        try:
            # Send all events
            futures = []
            for event in events:
                partition_key = event.get("short_code", "unknown")
                enriched_data = {
                    **event,
                    "event_type": "click",
                    "service": "redirector",
                    "timestamp": event.get("clicked_at"),
                    "version": "1.0.0"
                }
                
                future = await self.producer.send(
                    topic=self.topic,
                    value=enriched_data,
                    key=partition_key
                )
                futures.append(future)
            
            # Wait for all acknowledgments
            results = await asyncio.gather(*futures, return_exceptions=True)
            
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    self.logger.error(f"Failed to send event {i}: {result}")
                else:
                    successful_sends += 1
            
            self.logger.info(f"Batch send completed: {successful_sends}/{len(events)} successful")
            
        except Exception as e:
            self.logger.error(f"Error in batch send: {e}")
        
        return successful_sends
    
    async def health_check(self) -> bool:
        """Check if Kafka producer is healthy."""
        if not self.producer:
            return False
        
        try:
            # Try to get cluster metadata as a health check
            metadata = await self.producer.client.fetch_metadata()
            return len(metadata.brokers) > 0
        except Exception:
            return False
    
    @trace_function("kafka_producer.flush")
    async def flush(self) -> bool:
        """Flush any pending messages."""
        if not self.producer:
            return False
        
        try:
            await self.producer.flush()
            return True
        except Exception as e:
            self.logger.error(f"Error flushing Kafka producer: {e}")
            return False


class KafkaProducerPool:
    """Pool of Kafka producers for high-throughput scenarios."""
    
    def __init__(self, pool_size: int = 3):
        self.pool_size = pool_size
        self.producers: list[KafkaProducer] = []
        self.current_index = 0
        self.logger = get_observability_manager("redirector").get_logger()
    
    async def start(self):
        """Start all producers in the pool."""
        for i in range(self.pool_size):
            producer = KafkaProducer()
            await producer.start()
            self.producers.append(producer)
        
        self.logger.info(f"Started Kafka producer pool with {self.pool_size} producers")
    
    async def stop(self):
        """Stop all producers in the pool."""
        for producer in self.producers:
            await producer.stop()
        self.producers.clear()
        self.logger.info("Stopped Kafka producer pool")
    
    def get_producer(self) -> KafkaProducer:
        """Get next producer from pool (round-robin)."""
        if not self.producers:
            return None
        
        producer = self.producers[self.current_index]
        self.current_index = (self.current_index + 1) % len(self.producers)
        return producer
    
    async def send_click_event(self, click_data: Dict[str, Any]) -> bool:
        """Send click event using pool."""
        producer = self.get_producer()
        if producer:
            return await producer.send_click_event(click_data)
        return False
    
    async def health_check(self) -> bool:
        """Check if at least one producer is healthy."""
        if not self.producers:
            return False
        
        for producer in self.producers:
            if await producer.health_check():
                return True
        
        return False
