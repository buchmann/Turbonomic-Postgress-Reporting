#!/usr/bin/env python3
"""
Kafka Connection Test Script
Tests connectivity to Kafka broker and topic availability
"""

import sys
from kafka import KafkaConsumer, KafkaProducer
from kafka.admin import KafkaAdminClient, NewTopic
from kafka.errors import KafkaError

# Configuration
KAFKA_BOOTSTRAP_SERVERS = "kafka:9092"
KAFKA_TOPIC = "turbonomic.exporter"

# Colors for output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def print_success(message):
    print(f"{GREEN}✓ {message}{RESET}")

def print_error(message):
    print(f"{RED}✗ {message}{RESET}")

def print_info(message):
    print(f"{BLUE}ℹ {message}{RESET}")

def print_warning(message):
    print(f"{YELLOW}⚠ {message}{RESET}")

def test_broker_connection():
    """Test connection to Kafka broker"""
    print_info("Testing Kafka broker connection...")
    try:
        admin_client = KafkaAdminClient(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            request_timeout_ms=10000
        )
        print_success(f"Connected to Kafka broker at {KAFKA_BOOTSTRAP_SERVERS}")
        return admin_client
    except Exception as e:
        print_error(f"Failed to connect to Kafka broker: {e}")
        return None

def test_list_topics(admin_client):
    """List all available topics"""
    print_info("Listing available topics...")
    try:
        topics = admin_client.list_topics()
        print_success(f"Found {len(topics)} topics:")
        for topic in sorted(topics):
            print(f"  - {topic}")
        return topics
    except Exception as e:
        print_error(f"Failed to list topics: {e}")
        return []

def test_topic_exists(admin_client, topic_name):
    """Check if specific topic exists"""
    print_info(f"Checking if topic '{topic_name}' exists...")
    try:
        topics = admin_client.list_topics()
        if topic_name in topics:
            print_success(f"Topic '{topic_name}' exists")
            return True
        else:
            print_warning(f"Topic '{topic_name}' does not exist")
            return False
    except Exception as e:
        print_error(f"Failed to check topic: {e}")
        return False

def test_topic_metadata(admin_client, topic_name):
    """Get topic metadata"""
    print_info(f"Getting metadata for topic '{topic_name}'...")
    try:
        metadata = admin_client.describe_topics([topic_name])
        if metadata:
            topic_info = metadata[0]
            print_success(f"Topic metadata:")
            print(f"  - Topic: {topic_info['topic']}")
            print(f"  - Partitions: {len(topic_info['partitions'])}")
            for partition in topic_info['partitions']:
                print(f"    - Partition {partition['partition']}: Leader={partition['leader']}, Replicas={partition['replicas']}")
            return True
        else:
            print_warning(f"No metadata found for topic '{topic_name}'")
            return False
    except Exception as e:
        print_error(f"Failed to get topic metadata: {e}")
        return False

def test_consumer_connection(topic_name):
    """Test consumer connection"""
    print_info(f"Testing consumer connection to topic '{topic_name}'...")
    try:
        consumer = KafkaConsumer(
            topic_name,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            auto_offset_reset='earliest',
            enable_auto_commit=False,
            consumer_timeout_ms=5000,
            group_id='test-consumer-group'
        )
        print_success("Consumer connected successfully")
        
        # Get partition assignments
        partitions = consumer.assignment()
        if partitions:
            print_success(f"Assigned to {len(partitions)} partition(s):")
            for partition in partitions:
                print(f"  - Partition {partition.partition}")
        else:
            print_warning("No partitions assigned yet")
        
        consumer.close()
        return True
    except Exception as e:
        print_error(f"Failed to create consumer: {e}")
        return False

def test_consumer_group_status(admin_client):
    """Check consumer group status"""
    print_info("Checking consumer groups...")
    try:
        groups = admin_client.list_consumer_groups()
        if groups:
            print_success(f"Found {len(groups)} consumer group(s):")
            for group in groups:
                print(f"  - {group[0]} (protocol: {group[1]})")
        else:
            print_info("No consumer groups found")
        return True
    except Exception as e:
        print_error(f"Failed to list consumer groups: {e}")
        return False

def test_broker_info(admin_client):
    """Get broker information"""
    print_info("Getting broker information...")
    try:
        cluster_metadata = admin_client._client.cluster
        brokers = cluster_metadata.brokers()
        print_success(f"Found {len(brokers)} broker(s):")
        for broker in brokers:
            print(f"  - Broker {broker.nodeId}: {broker.host}:{broker.port}")
        return True
    except Exception as e:
        print_error(f"Failed to get broker info: {e}")
        return False

def test_produce_consume(topic_name):
    """Test producing and consuming a message"""
    print_info(f"Testing produce/consume on topic '{topic_name}'...")
    try:
        # Create producer
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            value_serializer=lambda v: v.encode('utf-8')
        )
        
        # Send test message
        test_message = '{"test": "connection", "source": "test-script"}'
        future = producer.send(topic_name, value=test_message)
        result = future.get(timeout=10)
        print_success(f"Test message sent to partition {result.partition}, offset {result.offset}")
        
        producer.close()
        
        # Try to consume the message
        consumer = KafkaConsumer(
            topic_name,
            bootstrap_servers=KAFKA_BOOTSTRAP_SERVERS,
            auto_offset_reset='latest',
            enable_auto_commit=False,
            consumer_timeout_ms=5000,
            group_id='test-consumer-group-temp'
        )
        
        # Seek to the message we just sent
        for partition in consumer.assignment():
            consumer.seek(partition, result.offset)
        
        # Try to read the message
        messages = consumer.poll(timeout_ms=5000)
        if messages:
            print_success("Successfully consumed test message")
        else:
            print_warning("Could not consume test message (this is OK if topic has retention)")
        
        consumer.close()
        return True
        
    except Exception as e:
        print_error(f"Failed produce/consume test: {e}")
        return False

def main():
    """Main test function"""
    print("=" * 70)
    print("Kafka Connection Test")
    print("=" * 70)
    print(f"Bootstrap Servers: {KAFKA_BOOTSTRAP_SERVERS}")
    print(f"Target Topic: {KAFKA_TOPIC}")
    print("=" * 70)
    print()
    
    # Run tests
    admin_client = test_broker_connection()
    if not admin_client:
        print_error("Cannot proceed without Kafka connection")
        sys.exit(1)
    
    tests = [
        ("Broker Information", lambda: test_broker_info(admin_client)),
        ("List Topics", lambda: test_list_topics(admin_client)),
        ("Topic Exists", lambda: test_topic_exists(admin_client, KAFKA_TOPIC)),
        ("Topic Metadata", lambda: test_topic_metadata(admin_client, KAFKA_TOPIC)),
        ("Consumer Connection", lambda: test_consumer_connection(KAFKA_TOPIC)),
        ("Consumer Groups", lambda: test_consumer_group_status(admin_client)),
    ]
    
    results = []
    for test_name, test_func in tests:
        print()
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print_error(f"Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))
    
    # Optional: Test produce/consume (commented out by default to avoid polluting topic)
    # print()
    # try:
    #     result = test_produce_consume(KAFKA_TOPIC)
    #     results.append(("Produce/Consume", result))
    # except Exception as e:
    #     print_error(f"Produce/Consume test failed: {e}")
    #     results.append(("Produce/Consume", False))
    
    # Close admin client
    admin_client.close()
    print_info("Admin client closed")
    
    # Summary
    print()
    print("=" * 70)
    print("Test Summary")
    print("=" * 70)
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = f"{GREEN}PASSED{RESET}" if result else f"{RED}FAILED{RESET}"
        print(f"{test_name}: {status}")
    
    print()
    print(f"Total: {passed}/{total} tests passed")
    print("=" * 70)
    
    if passed == total:
        print_success("All tests passed! Kafka is ready for use.")
        sys.exit(0)
    else:
        print_error(f"{total - passed} test(s) failed. Please check the configuration.")
        sys.exit(1)

if __name__ == '__main__':
    main()

# Made with Bob
