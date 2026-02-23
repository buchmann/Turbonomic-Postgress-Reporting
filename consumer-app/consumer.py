#!/usr/bin/env python3
"""
Kafka to PostgreSQL Consumer
Consumes messages from Kafka topic and stores them in PostgreSQL database
"""

import os
import sys
import json
import signal
import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from contextlib import contextmanager

from kafka import KafkaConsumer
from kafka.errors import KafkaError
import psycopg2
from psycopg2 import pool, sql
from psycopg2.extras import execute_batch

# Configure logging
logging.basicConfig(
    level=os.getenv('LOG_LEVEL', 'INFO'),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)


class Config:
    """Application configuration from environment variables"""
    
    # Kafka configuration
    KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'kafka:9092')
    KAFKA_TOPIC = os.getenv('KAFKA_TOPIC', 'turbonomic.exporter')
    KAFKA_GROUP_ID = os.getenv('KAFKA_GROUP_ID', 'turbonomic-postgres-consumer')
    KAFKA_AUTO_OFFSET_RESET = os.getenv('KAFKA_AUTO_OFFSET_RESET', 'earliest')
    KAFKA_MAX_POLL_RECORDS = int(os.getenv('KAFKA_MAX_POLL_RECORDS', '500'))
    KAFKA_SESSION_TIMEOUT_MS = int(os.getenv('KAFKA_SESSION_TIMEOUT_MS', '30000'))
    
    # PostgreSQL configuration
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', '192.168.178.61')
    POSTGRES_PORT = int(os.getenv('POSTGRES_PORT', '5432'))
    POSTGRES_DATABASE = os.getenv('POSTGRES_DATABASE', 'turbonomic_data')
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'manfred')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'Test7283')
    POSTGRES_MIN_CONN = int(os.getenv('POSTGRES_MIN_CONN', '1'))
    POSTGRES_MAX_CONN = int(os.getenv('POSTGRES_MAX_CONN', '10'))
    
    # Application configuration
    BATCH_SIZE = int(os.getenv('BATCH_SIZE', '100'))
    BATCH_TIMEOUT = int(os.getenv('BATCH_TIMEOUT', '5'))
    MAX_RETRIES = int(os.getenv('MAX_RETRIES', '3'))
    RETRY_BACKOFF = float(os.getenv('RETRY_BACKOFF', '2.0'))
    
    @classmethod
    def validate(cls):
        """Validate required configuration"""
        required = [
            'POSTGRES_HOST', 'POSTGRES_DATABASE', 
            'POSTGRES_USER', 'POSTGRES_PASSWORD'
        ]
        missing = [var for var in required if not getattr(cls, var)]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")


class PostgreSQLConnection:
    """PostgreSQL connection pool manager"""
    
    def __init__(self):
        self.pool = None
        self._initialize_pool()
    
    def _initialize_pool(self):
        """Initialize connection pool"""
        try:
            logger.info(f"Initializing PostgreSQL connection pool to {Config.POSTGRES_HOST}:{Config.POSTGRES_PORT}")
            self.pool = psycopg2.pool.ThreadedConnectionPool(
                Config.POSTGRES_MIN_CONN,
                Config.POSTGRES_MAX_CONN,
                host=Config.POSTGRES_HOST,
                port=Config.POSTGRES_PORT,
                database=Config.POSTGRES_DATABASE,
                user=Config.POSTGRES_USER,
                password=Config.POSTGRES_PASSWORD,
                connect_timeout=10
            )
            logger.info("PostgreSQL connection pool initialized successfully")
            
            # Test connection
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT version();")
                    version = cur.fetchone()[0]
                    logger.info(f"Connected to PostgreSQL: {version}")
                    
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL connection pool: {e}")
            raise
    
    @contextmanager
    def get_connection(self):
        """Get connection from pool"""
        conn = None
        try:
            conn = self.pool.getconn()
            yield conn
            conn.commit()
        except Exception as e:
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                self.pool.putconn(conn)
    
    def close(self):
        """Close all connections in pool"""
        if self.pool:
            self.pool.closeall()
            logger.info("PostgreSQL connection pool closed")


class KafkaToPostgresConsumer:
    """Main consumer class"""
    
    def __init__(self):
        self.consumer = None
        self.db = None
        self.running = False
        self.message_buffer: List[Dict[str, Any]] = []
        self.last_flush_time = time.time()
        
        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}, initiating graceful shutdown...")
        self.running = False
    
    def _initialize_kafka_consumer(self):
        """Initialize Kafka consumer"""
        try:
            logger.info(f"Initializing Kafka consumer for topic: {Config.KAFKA_TOPIC}")
            self.consumer = KafkaConsumer(
                Config.KAFKA_TOPIC,
                bootstrap_servers=Config.KAFKA_BOOTSTRAP_SERVERS.split(','),
                group_id=Config.KAFKA_GROUP_ID,
                auto_offset_reset=Config.KAFKA_AUTO_OFFSET_RESET,
                enable_auto_commit=False,
                max_poll_records=Config.KAFKA_MAX_POLL_RECORDS,
                session_timeout_ms=Config.KAFKA_SESSION_TIMEOUT_MS,
                value_deserializer=lambda m: m.decode('utf-8') if m else None,
                key_deserializer=lambda m: m.decode('utf-8') if m else None
            )
            logger.info("Kafka consumer initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Kafka consumer: {e}")
            raise
    
    def _parse_message_value(self, value: str) -> Optional[Dict[str, Any]]:
        """Parse message value as JSON"""
        if not value:
            return None
        
        try:
            return json.loads(value)
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse message as JSON: {e}")
            # Return as string wrapped in dict
            return {"raw_value": value}
    
    def _process_message(self, message) -> Dict[str, Any]:
        """Process a single Kafka message"""
        message_value = self._parse_message_value(message.value)
        
        return {
            'message_key': message.key,
            'message_value': json.dumps(message_value) if message_value else None,
            'topic': message.topic,
            'partition': message.partition,
            'offset': message.offset,
            'timestamp': datetime.fromtimestamp(message.timestamp / 1000.0) if message.timestamp else None,
            'consumed_at': datetime.now()
        }
    
    def _insert_batch(self, messages: List[Dict[str, Any]]) -> bool:
        """Insert batch of messages into PostgreSQL"""
        if not messages:
            return True
        
        insert_query = """
            INSERT INTO kafka.kafka_messages
            (message_key, message_value, topic, partition, "offset", timestamp, consumed_at)
            VALUES (%(message_key)s, %(message_value)s::jsonb, %(topic)s, %(partition)s,
                    %(offset)s, %(timestamp)s, %(consumed_at)s)
            ON CONFLICT (topic, partition, "offset") DO NOTHING
        """
        
        for attempt in range(Config.MAX_RETRIES):
            try:
                with self.db.get_connection() as conn:
                    with conn.cursor() as cur:
                        execute_batch(cur, insert_query, messages, page_size=100)
                        inserted_count = cur.rowcount
                        
                logger.info(f"Successfully inserted {inserted_count} messages (batch size: {len(messages)})")
                return True
                
            except Exception as e:
                logger.error(f"Failed to insert batch (attempt {attempt + 1}/{Config.MAX_RETRIES}): {e}")
                if attempt < Config.MAX_RETRIES - 1:
                    sleep_time = Config.RETRY_BACKOFF ** attempt
                    logger.info(f"Retrying in {sleep_time} seconds...")
                    time.sleep(sleep_time)
                else:
                    logger.error("Max retries reached, batch insert failed")
                    return False
        
        return False
    
    def _flush_buffer(self, force: bool = False):
        """Flush message buffer to database"""
        current_time = time.time()
        time_since_flush = current_time - self.last_flush_time
        
        should_flush = (
            force or
            len(self.message_buffer) >= Config.BATCH_SIZE or
            time_since_flush >= Config.BATCH_TIMEOUT
        )
        
        if should_flush and self.message_buffer:
            logger.info(f"Flushing buffer with {len(self.message_buffer)} messages")
            
            if self._insert_batch(self.message_buffer):
                # Commit Kafka offsets after successful insert
                try:
                    self.consumer.commit()
                    logger.debug("Kafka offsets committed")
                except Exception as e:
                    logger.error(f"Failed to commit Kafka offsets: {e}")
                
                self.message_buffer.clear()
                self.last_flush_time = current_time
            else:
                logger.error("Failed to flush buffer, keeping messages for retry")
    
    def run(self):
        """Main consumer loop"""
        try:
            # Validate configuration
            Config.validate()
            
            # Initialize connections
            self.db = PostgreSQLConnection()
            self._initialize_kafka_consumer()
            
            self.running = True
            logger.info("Starting message consumption...")
            
            message_count = 0
            
            while self.running:
                try:
                    # Poll for messages
                    messages = self.consumer.poll(timeout_ms=1000, max_records=Config.KAFKA_MAX_POLL_RECORDS)
                    
                    if not messages:
                        # No messages, check if we should flush based on timeout
                        self._flush_buffer()
                        continue
                    
                    # Process messages
                    for topic_partition, records in messages.items():
                        for message in records:
                            try:
                                processed_message = self._process_message(message)
                                self.message_buffer.append(processed_message)
                                message_count += 1
                                
                                if message_count % 100 == 0:
                                    logger.info(f"Processed {message_count} messages so far")
                                
                            except Exception as e:
                                logger.error(f"Error processing message: {e}")
                                continue
                    
                    # Flush buffer if needed
                    self._flush_buffer()
                    
                except KafkaError as e:
                    logger.error(f"Kafka error: {e}")
                    time.sleep(5)
                    continue
                    
        except KeyboardInterrupt:
            logger.info("Received keyboard interrupt")
        except Exception as e:
            logger.error(f"Fatal error in consumer: {e}", exc_info=True)
            raise
        finally:
            self._shutdown()
    
    def _shutdown(self):
        """Cleanup and shutdown"""
        logger.info("Shutting down consumer...")
        
        # Flush remaining messages
        if self.message_buffer:
            logger.info(f"Flushing {len(self.message_buffer)} remaining messages")
            self._flush_buffer(force=True)
        
        # Close Kafka consumer
        if self.consumer:
            try:
                self.consumer.close()
                logger.info("Kafka consumer closed")
            except Exception as e:
                logger.error(f"Error closing Kafka consumer: {e}")
        
        # Close database connections
        if self.db:
            try:
                self.db.close()
            except Exception as e:
                logger.error(f"Error closing database connections: {e}")
        
        logger.info("Consumer shutdown complete")


def main():
    """Main entry point"""
    logger.info("=" * 70)
    logger.info("Kafka to PostgreSQL Consumer")
    logger.info("=" * 70)
    logger.info(f"Kafka Bootstrap Servers: {Config.KAFKA_BOOTSTRAP_SERVERS}")
    logger.info(f"Kafka Topic: {Config.KAFKA_TOPIC}")
    logger.info(f"Kafka Group ID: {Config.KAFKA_GROUP_ID}")
    logger.info(f"PostgreSQL Host: {Config.POSTGRES_HOST}:{Config.POSTGRES_PORT}")
    logger.info(f"PostgreSQL Database: {Config.POSTGRES_DATABASE}")
    logger.info(f"Batch Size: {Config.BATCH_SIZE}")
    logger.info(f"Batch Timeout: {Config.BATCH_TIMEOUT}s")
    logger.info("=" * 70)
    
    consumer = KafkaToPostgresConsumer()
    consumer.run()


if __name__ == '__main__':
    main()

# Made with Bob
