--------------------------------------------------------------------------------
-- PostgreSQL Database Initialization Script
-- Purpose: Create database, user, and schema for Kafka message storage
-- Database: turbonomic_data
-- User: manfred
--------------------------------------------------------------------------------

-- Connect as postgres superuser to create database and user
-- Run this script with: sudo -u postgres psql -f init-database.sql

-- Create database
CREATE DATABASE turbonomic_data
    WITH 
    ENCODING = 'UTF8'
    LC_COLLATE = 'en_US.UTF-8'
    LC_CTYPE = 'en_US.UTF-8'
    TEMPLATE = template0;

\echo 'Database turbonomic_data created successfully'

-- Create user
CREATE USER manfred WITH PASSWORD 'Test7283';

\echo 'User manfred created successfully'

-- Grant privileges on database
GRANT ALL PRIVILEGES ON DATABASE turbonomic_data TO manfred;

\echo 'Privileges granted to user manfred'

-- Connect to the new database
\c turbonomic_data

-- Create schema for kafka messages
CREATE SCHEMA IF NOT EXISTS kafka;

-- Grant schema privileges
GRANT ALL ON SCHEMA kafka TO manfred;
GRANT ALL ON SCHEMA public TO manfred;

\echo 'Schema kafka created and privileges granted'

-- Create kafka_messages table
CREATE TABLE kafka.kafka_messages (
    id BIGSERIAL PRIMARY KEY,
    message_key TEXT,
    message_value JSONB NOT NULL,
    topic VARCHAR(255) NOT NULL,
    partition INTEGER NOT NULL,
    "offset" BIGINT NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE,
    consumed_at TIMESTAMP WITH TIME ZONE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT unique_message UNIQUE (topic, partition, "offset")
);

\echo 'Table kafka.kafka_messages created successfully'

-- Create indexes for efficient querying
CREATE INDEX idx_kafka_messages_topic ON kafka.kafka_messages(topic);
CREATE INDEX idx_kafka_messages_timestamp ON kafka.kafka_messages(timestamp);
CREATE INDEX idx_kafka_messages_consumed_at ON kafka.kafka_messages(consumed_at);
CREATE INDEX idx_kafka_messages_partition_offset ON kafka.kafka_messages(partition, "offset");
CREATE INDEX idx_kafka_messages_value ON kafka.kafka_messages USING GIN (message_value);

\echo 'Indexes created successfully'

-- Grant table privileges to manfred
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA kafka TO manfred;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA kafka TO manfred;

-- Set default privileges for future tables
ALTER DEFAULT PRIVILEGES IN SCHEMA kafka GRANT ALL ON TABLES TO manfred;
ALTER DEFAULT PRIVILEGES IN SCHEMA kafka GRANT ALL ON SEQUENCES TO manfred;

\echo 'Table privileges granted to user manfred'

-- Create a view for easy querying of recent messages
CREATE VIEW kafka.recent_messages AS
SELECT
    id,
    message_key,
    message_value,
    topic,
    partition,
    "offset",
    timestamp,
    consumed_at,
    created_at
FROM kafka.kafka_messages
ORDER BY consumed_at DESC
LIMIT 1000;

GRANT SELECT ON kafka.recent_messages TO manfred;

\echo 'View kafka.recent_messages created successfully'

-- Create a function to get message count by topic
CREATE OR REPLACE FUNCTION kafka.get_message_count_by_topic()
RETURNS TABLE (
    topic_name VARCHAR(255),
    message_count BIGINT,
    earliest_message TIMESTAMP WITH TIME ZONE,
    latest_message TIMESTAMP WITH TIME ZONE
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        topic,
        COUNT(*) as message_count,
        MIN(consumed_at) as earliest_message,
        MAX(consumed_at) as latest_message
    FROM kafka.kafka_messages
    GROUP BY topic
    ORDER BY message_count DESC;
END;
$$ LANGUAGE plpgsql;

GRANT EXECUTE ON FUNCTION kafka.get_message_count_by_topic() TO manfred;

\echo 'Function kafka.get_message_count_by_topic() created successfully'

-- Create a function to clean old messages (optional, for maintenance)
CREATE OR REPLACE FUNCTION kafka.cleanup_old_messages(days_to_keep INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM kafka.kafka_messages
    WHERE consumed_at < NOW() - (days_to_keep || ' days')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

GRANT EXECUTE ON FUNCTION kafka.cleanup_old_messages(INTEGER) TO manfred;

\echo 'Function kafka.cleanup_old_messages() created successfully'

-- Insert a test record to verify everything works
INSERT INTO kafka.kafka_messages (
    message_key,
    message_value,
    topic,
    partition,
    "offset",
    timestamp,
    consumed_at
) VALUES (
    'test-key',
    '{"test": "message", "status": "initialization"}',
    'test.topic',
    0,
    0,
    NOW(),
    NOW()
);

\echo 'Test record inserted successfully'

-- Display table information
\echo ''
\echo '==================================================================='
\echo 'Database initialization completed successfully!'
\echo '==================================================================='
\echo ''
\echo 'Database: turbonomic_data'
\echo 'User: manfred'
\echo 'Schema: kafka'
\echo 'Main Table: kafka.kafka_messages'
\echo ''
\echo 'Available views:'
\echo '  - kafka.recent_messages (last 1000 messages)'
\echo ''
\echo 'Available functions:'
\echo '  - kafka.get_message_count_by_topic() - Get message statistics'
\echo '  - kafka.cleanup_old_messages(days) - Clean old messages'
\echo ''
\echo 'To verify the setup, run:'
\echo '  SELECT * FROM kafka.kafka_messages;'
\echo '  SELECT * FROM kafka.get_message_count_by_topic();'
\echo ''
\echo 'Next step: Run configure-postgres.sh to enable remote connections'
\echo '==================================================================='

-- Display table structure
\d+ kafka.kafka_messages

-- Made with Bob
