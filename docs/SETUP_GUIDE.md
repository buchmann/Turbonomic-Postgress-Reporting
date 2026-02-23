# Complete Setup Guide - Kafka to PostgreSQL Consumer

This guide provides step-by-step instructions for setting up the complete Kafka to PostgreSQL consumer system.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [PostgreSQL Setup](#postgresql-setup)
3. [Build Docker Image](#build-docker-image)
4. [Deploy to Kubernetes](#deploy-to-kubernetes)
5. [Verification](#verification)
6. [Monitoring](#monitoring)
7. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required Access
- SSH access to Linux box at 192.168.178.61
- Root/sudo privileges on the Linux box
- Access to Kubernetes cluster with turbonomic namespace
- kubectl configured and working

### Required Software
- Linux box: Any modern Linux distribution (Ubuntu 20.04+, RHEL 8+, etc.)
- Kubernetes cluster: Version 1.20+
- Docker (for building the image)
- kubectl CLI tool

### Network Requirements
- Kubernetes pods must be able to reach 192.168.178.61:5432
- Kafka broker must be accessible at kafka:9092 from Kubernetes

---

## PostgreSQL Setup

### Step 1: Connect to PostgreSQL Server

```bash
ssh user@192.168.178.61
```

### Step 2: Install PostgreSQL

```bash
# Copy the installation script to the server
# (You can use scp, or copy-paste the content)

# Make the script executable
chmod +x install-postgres.sh

# Run the installation script
sudo ./install-postgres.sh
```

**Expected Output:**
```
[INFO] Starting PostgreSQL 15 installation...
[INFO] Detected OS: ubuntu 22.04
[INFO] Installing PostgreSQL on Ubuntu/Debian...
...
[INFO] PostgreSQL installation completed successfully!
```

### Step 3: Initialize Database

```bash
# Run the database initialization script
sudo -u postgres psql -f init-database.sql
```

**Expected Output:**
```
Database turbonomic_data created successfully
User manfred created successfully
Privileges granted to user manfred
...
Database initialization completed successfully!
```

### Step 4: Configure Remote Access

```bash
# Make the configuration script executable
chmod +x configure-postgres.sh

# Run the configuration script
sudo ./configure-postgres.sh
```

**Expected Output:**
```
[INFO] Starting PostgreSQL remote access configuration...
[STEP] Creating backup of configuration files...
[STEP] Configuring postgresql.conf for remote connections...
[STEP] Configuring pg_hba.conf for authentication...
[STEP] Configuring firewall...
[STEP] Restarting PostgreSQL service...
...
PostgreSQL remote access configuration completed successfully!
```

### Step 5: Test PostgreSQL Connection

From your local machine or Kubernetes cluster, test the connection:

```bash
# Install psycopg2 if not already installed
pip install psycopg2-binary

# Run the test script
python tests/test-postgres-connection.py
```

**Expected Output:**
```
======================================================================
PostgreSQL Connection Test
======================================================================
...
✓ Connected to PostgreSQL at 192.168.178.61:5432
✓ PostgreSQL version: PostgreSQL 15.x ...
...
All tests passed! PostgreSQL is ready for use.
```

---

## Build Docker Image

### Option 1: Build Locally

```bash
# Navigate to the consumer-app directory
cd consumer-app

# Build the Docker image
docker build -t kafka-postgres-consumer:latest .

# Tag for your registry (if using one)
docker tag kafka-postgres-consumer:latest your-registry/kafka-postgres-consumer:latest

# Push to registry (if using one)
docker push your-registry/kafka-postgres-consumer:latest
```

### Option 2: Build in Kubernetes Cluster

If your Kubernetes cluster has access to build images:

```bash
# Use a tool like kaniko or buildah
# Or use a CI/CD pipeline
```

### Option 3: Use Pre-built Image

If you have a pre-built image, update the deployment.yaml:

```yaml
spec:
  containers:
  - name: consumer
    image: your-registry/kafka-postgres-consumer:v1.0.0
```

---

## Deploy to Kubernetes

### Step 1: Verify Namespace

```bash
# Check if turbonomic namespace exists
kubectl get namespace turbonomic

# If it doesn't exist, create it
kubectl create namespace turbonomic
```

### Step 2: Create ConfigMap

```bash
# Apply the ConfigMap
kubectl apply -f kubernetes/configmap.yaml

# Verify
kubectl get configmap kafka-postgres-consumer-config -n turbonomic
kubectl describe configmap kafka-postgres-consumer-config -n turbonomic
```

### Step 3: Create Secret

```bash
# Apply the Secret
kubectl apply -f kubernetes/secret.yaml

# Verify (don't show values)
kubectl get secret kafka-postgres-consumer-secret -n turbonomic
```

**Alternative: Create Secret from Command Line**

```bash
kubectl create secret generic kafka-postgres-consumer-secret \
  --from-literal=POSTGRES_USER=manfred \
  --from-literal=POSTGRES_PASSWORD=Test7283 \
  --namespace=turbonomic \
  --dry-run=client -o yaml | kubectl apply -f -
```

### Step 4: Deploy Consumer

```bash
# Apply the Deployment
kubectl apply -f kubernetes/deployment.yaml

# Verify deployment
kubectl get deployment kafka-postgres-consumer -n turbonomic
kubectl get pods -n turbonomic -l app=kafka-postgres-consumer
```

**Expected Output:**
```
NAME                                      READY   STATUS    RESTARTS   AGE
kafka-postgres-consumer-xxxxxxxxxx-xxxxx   1/1     Running   0          30s
```

### Step 5: Check Pod Logs

```bash
# Get pod name
POD_NAME=$(kubectl get pods -n turbonomic -l app=kafka-postgres-consumer -o jsonpath='{.items[0].metadata.name}')

# View logs
kubectl logs -f $POD_NAME -n turbonomic
```

**Expected Output:**
```
======================================================================
Kafka to PostgreSQL Consumer
======================================================================
Kafka Bootstrap Servers: kafka:9092
Kafka Topic: turbonomic.exporter
...
INFO - PostgreSQL connection pool initialized successfully
INFO - Connected to PostgreSQL: PostgreSQL 15.x ...
INFO - Kafka consumer initialized successfully
INFO - Starting message consumption...
```

---

## Verification

### 1. Check Consumer Status

```bash
# Check if pod is running
kubectl get pods -n turbonomic -l app=kafka-postgres-consumer

# Check pod events
kubectl describe pod $POD_NAME -n turbonomic

# Check logs for errors
kubectl logs $POD_NAME -n turbonomic | grep -i error
```

### 2. Verify Kafka Consumption

```bash
# Check consumer group lag
kubectl exec -it $POD_NAME -n turbonomic -- bash

# Inside the pod (if kafka tools are available)
# Or check from Kafka broker
```

### 3. Verify Database Writes

Connect to PostgreSQL and check for messages:

```bash
# From your local machine
psql -h 192.168.178.61 -U manfred -d turbonomic_data

# Inside psql
SELECT COUNT(*) FROM kafka.kafka_messages;
SELECT * FROM kafka.recent_messages LIMIT 10;
SELECT * FROM kafka.get_message_count_by_topic();
```

**Expected Output:**
```
 topic_name          | message_count | earliest_message        | latest_message
---------------------+---------------+-------------------------+-------------------------
 turbonomic.exporter |          1234 | 2026-02-23 10:00:00+00  | 2026-02-23 11:00:00+00
```

### 4. Test End-to-End Flow

```bash
# Produce a test message to Kafka
kubectl exec -it kafka-0 -n turbonomic -- kafka-console-producer \
  --bootstrap-server kafka:9092 \
  --topic turbonomic.exporter

# Type a test message (JSON format)
{"test": "message", "timestamp": "2026-02-23T11:00:00Z"}

# Press Ctrl+D to exit

# Check if message appears in database
psql -h 192.168.178.61 -U manfred -d turbonomic_data \
  -c "SELECT * FROM kafka.kafka_messages ORDER BY consumed_at DESC LIMIT 1;"
```

---

## Monitoring

### View Consumer Logs

```bash
# Real-time logs
kubectl logs -f $POD_NAME -n turbonomic

# Last 100 lines
kubectl logs --tail=100 $POD_NAME -n turbonomic

# Logs from previous container (if crashed)
kubectl logs --previous $POD_NAME -n turbonomic
```

### Check Resource Usage

```bash
# CPU and Memory usage
kubectl top pod $POD_NAME -n turbonomic

# Detailed resource information
kubectl describe pod $POD_NAME -n turbonomic | grep -A 10 "Limits\|Requests"
```

### Monitor Database

```sql
-- Connect to PostgreSQL
psql -h 192.168.178.61 -U manfred -d turbonomic_data

-- Check message count
SELECT COUNT(*) FROM kafka.kafka_messages;

-- Check messages per hour
SELECT 
    DATE_TRUNC('hour', consumed_at) as hour,
    COUNT(*) as message_count
FROM kafka.kafka_messages
WHERE consumed_at > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour DESC;

-- Check database size
SELECT 
    pg_size_pretty(pg_database_size('turbonomic_data')) as database_size;

-- Check table size
SELECT 
    pg_size_pretty(pg_total_relation_size('kafka.kafka_messages')) as table_size;
```

### Set Up Alerts (Optional)

Create alerts for:
- Pod restarts
- High error rate in logs
- Consumer lag
- Database connection failures
- Disk space on PostgreSQL server

---

## Troubleshooting

### Pod Not Starting

**Check pod status:**
```bash
kubectl describe pod $POD_NAME -n turbonomic
```

**Common issues:**
- Image pull errors: Check image name and registry access
- ConfigMap/Secret not found: Verify they exist in the namespace
- Resource limits: Check if cluster has enough resources

### Cannot Connect to PostgreSQL

**Test connection from pod:**
```bash
kubectl exec -it $POD_NAME -n turbonomic -- bash
apt-get update && apt-get install -y postgresql-client
psql -h 192.168.178.61 -U manfred -d turbonomic_data
```

**Common issues:**
- Firewall blocking port 5432
- PostgreSQL not configured for remote connections
- Wrong credentials in Secret
- Network policy blocking traffic

### Cannot Connect to Kafka

**Test connection from pod:**
```bash
kubectl exec -it $POD_NAME -n turbonomic -- bash
apt-get update && apt-get install -y telnet
telnet kafka 9092
```

**Common issues:**
- Kafka service name incorrect
- Kafka not running
- Network policy blocking traffic
- Topic doesn't exist

### Messages Not Being Consumed

**Check consumer logs:**
```bash
kubectl logs $POD_NAME -n turbonomic | grep -i "error\|exception"
```

**Common issues:**
- Topic doesn't exist
- No messages in topic
- Consumer group offset at end of topic
- Deserialization errors

### Messages Not Being Stored

**Check database connection:**
```bash
# From pod logs
kubectl logs $POD_NAME -n turbonomic | grep -i "postgres\|database"
```

**Common issues:**
- Database connection failures
- Insert errors (check constraints)
- Duplicate messages (check unique constraint)
- Database full

### High Memory Usage

**Check pod memory:**
```bash
kubectl top pod $POD_NAME -n turbonomic
```

**Solutions:**
- Reduce BATCH_SIZE in ConfigMap
- Reduce KAFKA_MAX_POLL_RECORDS
- Increase memory limits in deployment

### Consumer Lag Increasing

**Check consumer group lag:**
```bash
# From Kafka broker
kafka-consumer-groups --bootstrap-server kafka:9092 \
  --group turbonomic-postgres-consumer --describe
```

**Solutions:**
- Increase number of replicas
- Increase BATCH_SIZE
- Optimize database inserts
- Check database performance

---

## Scaling

### Horizontal Scaling

```bash
# Scale to 3 replicas
kubectl scale deployment kafka-postgres-consumer -n turbonomic --replicas=3

# Verify
kubectl get pods -n turbonomic -l app=kafka-postgres-consumer
```

**Note:** Number of replicas should not exceed number of Kafka partitions.

### Vertical Scaling

Edit deployment.yaml and increase resources:

```yaml
resources:
  requests:
    memory: "512Mi"
    cpu: "500m"
  limits:
    memory: "1Gi"
    cpu: "1000m"
```

Apply changes:
```bash
kubectl apply -f kubernetes/deployment.yaml
```

---

## Maintenance

### Update Configuration

```bash
# Edit ConfigMap
kubectl edit configmap kafka-postgres-consumer-config -n turbonomic

# Restart pods to pick up changes
kubectl rollout restart deployment kafka-postgres-consumer -n turbonomic
```

### Update Consumer Image

```bash
# Update image in deployment
kubectl set image deployment/kafka-postgres-consumer \
  consumer=your-registry/kafka-postgres-consumer:v2.0.0 \
  -n turbonomic

# Check rollout status
kubectl rollout status deployment/kafka-postgres-consumer -n turbonomic
```

### Database Maintenance

```sql
-- Clean old messages (older than 30 days)
SELECT kafka.cleanup_old_messages(30);

-- Vacuum table
VACUUM ANALYZE kafka.kafka_messages;

-- Reindex
REINDEX TABLE kafka.kafka_messages;
```

---

## Backup and Recovery

### Backup PostgreSQL

```bash
# On PostgreSQL server
pg_dump -h localhost -U manfred -d turbonomic_data -F c -f turbonomic_data_backup.dump

# Or use pg_basebackup for full cluster backup
```

### Restore PostgreSQL

```bash
# On PostgreSQL server
pg_restore -h localhost -U manfred -d turbonomic_data -c turbonomic_data_backup.dump
```

### Backup Kubernetes Resources

```bash
# Export all resources
kubectl get all -n turbonomic -o yaml > turbonomic-backup.yaml

# Export specific resources
kubectl get configmap kafka-postgres-consumer-config -n turbonomic -o yaml > configmap-backup.yaml
kubectl get secret kafka-postgres-consumer-secret -n turbonomic -o yaml > secret-backup.yaml
kubectl get deployment kafka-postgres-consumer -n turbonomic -o yaml > deployment-backup.yaml
```

---

## Next Steps

1. Set up monitoring and alerting
2. Configure log aggregation
3. Implement backup automation
4. Set up CI/CD pipeline for updates
5. Document operational procedures
6. Train team on troubleshooting

---

## Support

For issues or questions:
1. Check logs: `kubectl logs $POD_NAME -n turbonomic`
2. Check events: `kubectl get events -n turbonomic`
3. Review this guide's troubleshooting section
4. Check PostgreSQL logs: `journalctl -u postgresql -n 100`

---

## Summary

You have successfully set up:
- ✅ PostgreSQL database on 192.168.178.61
- ✅ Kafka consumer application
- ✅ Kubernetes deployment in turbonomic namespace
- ✅ Monitoring and verification procedures

The system is now consuming messages from Kafka topic `turbonomic.exporter` and storing them in PostgreSQL database `turbonomic_data`.