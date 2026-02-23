#!/usr/bin/env python3
"""
PostgreSQL Connection Test Script
Tests connectivity and basic operations with the PostgreSQL database
"""

import sys
import psycopg2
from datetime import datetime

# Configuration
POSTGRES_HOST = "192.168.178.61"
POSTGRES_PORT = 5432
POSTGRES_DATABASE = "turbonomic_data"
POSTGRES_USER = "manfred"
POSTGRES_PASSWORD = "Test7283"

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

def test_connection():
    """Test basic connection to PostgreSQL"""
    print_info("Testing PostgreSQL connection...")
    try:
        conn = psycopg2.connect(
            host=POSTGRES_HOST,
            port=POSTGRES_PORT,
            database=POSTGRES_DATABASE,
            user=POSTGRES_USER,
            password=POSTGRES_PASSWORD,
            connect_timeout=10
        )
        print_success(f"Connected to PostgreSQL at {POSTGRES_HOST}:{POSTGRES_PORT}")
        return conn
    except Exception as e:
        print_error(f"Failed to connect to PostgreSQL: {e}")
        return None

def test_database_version(conn):
    """Test database version"""
    print_info("Checking PostgreSQL version...")
    try:
        cur = conn.cursor()
        cur.execute("SELECT version();")
        version = cur.fetchone()[0]
        print_success(f"PostgreSQL version: {version}")
        cur.close()
        return True
    except Exception as e:
        print_error(f"Failed to get version: {e}")
        return False

def test_database_exists(conn):
    """Test if database exists"""
    print_info("Checking if database exists...")
    try:
        cur = conn.cursor()
        cur.execute("SELECT current_database();")
        db_name = cur.fetchone()[0]
        print_success(f"Connected to database: {db_name}")
        cur.close()
        return True
    except Exception as e:
        print_error(f"Failed to check database: {e}")
        return False

def test_schema_exists(conn):
    """Test if kafka schema exists"""
    print_info("Checking if kafka schema exists...")
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT schema_name 
            FROM information_schema.schemata 
            WHERE schema_name = 'kafka';
        """)
        result = cur.fetchone()
        if result:
            print_success("Schema 'kafka' exists")
            cur.close()
            return True
        else:
            print_error("Schema 'kafka' does not exist")
            cur.close()
            return False
    except Exception as e:
        print_error(f"Failed to check schema: {e}")
        return False

def test_table_exists(conn):
    """Test if kafka_messages table exists"""
    print_info("Checking if kafka_messages table exists...")
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'kafka' 
            AND table_name = 'kafka_messages';
        """)
        result = cur.fetchone()
        if result:
            print_success("Table 'kafka.kafka_messages' exists")
            cur.close()
            return True
        else:
            print_error("Table 'kafka.kafka_messages' does not exist")
            cur.close()
            return False
    except Exception as e:
        print_error(f"Failed to check table: {e}")
        return False

def test_table_structure(conn):
    """Test table structure"""
    print_info("Checking table structure...")
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'kafka' 
            AND table_name = 'kafka_messages'
            ORDER BY ordinal_position;
        """)
        columns = cur.fetchall()
        print_success(f"Table has {len(columns)} columns:")
        for col in columns:
            print(f"  - {col[0]}: {col[1]} (nullable: {col[2]})")
        cur.close()
        return True
    except Exception as e:
        print_error(f"Failed to check table structure: {e}")
        return False

def test_insert_and_query(conn):
    """Test insert and query operations"""
    print_info("Testing insert and query operations...")
    try:
        cur = conn.cursor()
        
        # Insert test record
        test_data = {
            'message_key': 'test-connection-key',
            'message_value': '{"test": "connection", "timestamp": "' + datetime.now().isoformat() + '"}',
            'topic': 'test.connection',
            'partition': 0,
            'offset': 999999,
            'timestamp': datetime.now(),
            'consumed_at': datetime.now()
        }
        
        cur.execute("""
            INSERT INTO kafka.kafka_messages
            (message_key, message_value, topic, partition, "offset", timestamp, consumed_at)
            VALUES (%(message_key)s, %(message_value)s::jsonb, %(topic)s, %(partition)s,
                    %(offset)s, %(timestamp)s, %(consumed_at)s)
            ON CONFLICT (topic, partition, "offset") DO NOTHING
            RETURNING id;
        """, test_data)
        
        result = cur.fetchone()
        if result:
            record_id = result[0]
            print_success(f"Test record inserted with ID: {record_id}")
            
            # Query the record back
            cur.execute("""
                SELECT id, message_key, message_value, topic, partition, "offset"
                FROM kafka.kafka_messages
                WHERE id = %s;
            """, (record_id,))
            
            record = cur.fetchone()
            if record:
                print_success("Test record retrieved successfully:")
                print(f"  - ID: {record[0]}")
                print(f"  - Key: {record[1]}")
                print(f"  - Value: {record[2]}")
                print(f"  - Topic: {record[3]}")
                print(f"  - Partition: {record[4]}")
                print(f"  - Offset: {record[5]}")
            
            # Clean up test record
            cur.execute("DELETE FROM kafka.kafka_messages WHERE id = %s;", (record_id,))
            print_success("Test record cleaned up")
        else:
            print_warning("Test record already exists (conflict)")
        
        conn.commit()
        cur.close()
        return True
    except Exception as e:
        conn.rollback()
        print_error(f"Failed insert/query test: {e}")
        return False

def test_message_count(conn):
    """Test message count"""
    print_info("Checking message count...")
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM kafka.kafka_messages;")
        count = cur.fetchone()[0]
        print_success(f"Total messages in database: {count}")
        cur.close()
        return True
    except Exception as e:
        print_error(f"Failed to count messages: {e}")
        return False

def test_indexes(conn):
    """Test if indexes exist"""
    print_info("Checking indexes...")
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT indexname 
            FROM pg_indexes 
            WHERE schemaname = 'kafka' 
            AND tablename = 'kafka_messages';
        """)
        indexes = cur.fetchall()
        print_success(f"Found {len(indexes)} indexes:")
        for idx in indexes:
            print(f"  - {idx[0]}")
        cur.close()
        return True
    except Exception as e:
        print_error(f"Failed to check indexes: {e}")
        return False

def main():
    """Main test function"""
    print("=" * 70)
    print("PostgreSQL Connection Test")
    print("=" * 70)
    print(f"Host: {POSTGRES_HOST}:{POSTGRES_PORT}")
    print(f"Database: {POSTGRES_DATABASE}")
    print(f"User: {POSTGRES_USER}")
    print("=" * 70)
    print()
    
    # Run tests
    conn = test_connection()
    if not conn:
        print_error("Cannot proceed without database connection")
        sys.exit(1)
    
    tests = [
        ("Database Version", lambda: test_database_version(conn)),
        ("Database Exists", lambda: test_database_exists(conn)),
        ("Schema Exists", lambda: test_schema_exists(conn)),
        ("Table Exists", lambda: test_table_exists(conn)),
        ("Table Structure", lambda: test_table_structure(conn)),
        ("Insert and Query", lambda: test_insert_and_query(conn)),
        ("Message Count", lambda: test_message_count(conn)),
        ("Indexes", lambda: test_indexes(conn)),
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
    
    # Close connection
    conn.close()
    print_info("Connection closed")
    
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
        print_success("All tests passed! PostgreSQL is ready for use.")
        sys.exit(0)
    else:
        print_error(f"{total - passed} test(s) failed. Please check the configuration.")
        sys.exit(1)

if __name__ == '__main__':
    main()

# Made with Bob
