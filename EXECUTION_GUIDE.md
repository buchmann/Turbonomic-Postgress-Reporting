# Execution Guide - Step-by-Step Commands

This guide provides the exact commands to run for each step of the setup.

## Prerequisites

You need:
- SSH access to 192.168.178.61
- Root/sudo privileges on that server
- The project files copied to the server

---

## Step 1: Copy Files to PostgreSQL Server

From your local machine:

```bash
# Create a directory on the server
ssh user@192.168.178.61 "mkdir -p ~/kafka-postgres-setup"

# Copy PostgreSQL setup files
scp postgres-setup/install-postgres.sh user@192.168.178.61:~/kafka-postgres-setup/
scp postgres-setup/init-database.sql user@192.168.178.61:~/kafka-postgres-setup/
scp postgres-setup/configure-postgres.sh user@192.168.178.61:~/kafka-postgres-setup/
```

---

## Step 2: Install PostgreSQL

SSH to the server and run the installation script:

```bash
# SSH to the server
ssh user@192.168.178.61

# Navigate to the setup directory
cd ~/kafka-postgres-setup

# Make scripts executable
chmod +x install-postgres.sh configure-postgres.sh

# Run installation script as root
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

**Verify Installation:**
```bash
# Check PostgreSQL is running
sudo systemctl status postgresql

# Should show: Active: active (running)
```

---

## Step 3: Initialize Database

Run the SQL script to create the database, user, and schema:

```bash
# Still on the PostgreSQL server (192.168.178.61)
cd ~/kafka-postgres-setup

# Option 1: Copy file to /tmp (recommended - postgres user can access /tmp)
sudo cp init-database.sql /tmp/
sudo -u postgres psql -f /tmp/init-database.sql

# Option 2: Use absolute path with sudo
sudo -u postgres psql -f $(pwd)/init-database.sql

# Option 3: Pipe the file content
sudo cat init-database.sql | sudo -u postgres psql
```

**What these commands do:**
- **Option 1** (Recommended): Copy file to /tmp where postgres user has access
- **Option 2**: Use absolute path with current directory
- **Option 3**: Pipe file content directly to psql

**Why the error occurred:**
The postgres user doesn't have permission to access your home directory (`/home/manfred/Bob/...`). We need to either copy the file to an accessible location or pipe its content.

**Expected Output:**
```
Database turbonomic_data created successfully
User manfred created successfully
Privileges granted to user manfred
Schema kafka created and privileges granted
Table kafka.kafka_messages created successfully
Indexes created successfully
...
Database initialization completed successfully!
```

**Verify Database Creation:**
```bash
# Connect to the database
sudo -u postgres psql -d turbonomic_data

# Inside psql, run:
\dt kafka.*

# Should show the kafka_messages table
# Type \q to exit psql
```

---

## Step 4: Configure Remote Access

Configure PostgreSQL to accept remote connections:

```bash
# Still on the PostgreSQL server
cd ~/kafka-postgres-setup

# Run configuration script as root
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

**Verify Configuration:**
```bash
# Check PostgreSQL is listening on all interfaces
sudo netstat -tlnp | grep 5432

# Should show: 0.0.0.0:5432

# Check firewall
sudo firewall-cmd --list-ports  # For firewalld
# OR
sudo ufw status                  # For ufw

# Should show: 5432/tcp
```

---

## Step 5: Test Connection from Local Machine

From your local machine (not the server):

```bash
# Install psycopg2 if not already installed
pip install psycopg2-binary

# Run the connection test
python tests/test-postgres-connection.py
```

**Expected Output:**
```
======================================================================
PostgreSQL Connection Test
======================================================================
✓ Connected to PostgreSQL at 192.168.178.61:5432
✓ PostgreSQL version: PostgreSQL 15.x ...
✓ Connected to database: turbonomic_data
✓ Schema 'kafka' exists
✓ Table 'kafka.kafka_messages' exists
...
All tests passed! PostgreSQL is ready for use.
```

**Manual Test (Alternative):**
```bash
# Test with psql client
psql -h 192.168.178.61 -U manfred -d turbonomic_data

# When prompted, enter password: Test7283

# Inside psql, run:
SELECT COUNT(*) FROM kafka.kafka_messages;

# Should return: 1 (the test record)
```

---

## Step 6: Build Docker Image

From your local machine, in the project directory:

```bash
# Navigate to consumer app directory
cd consumer-app

# Build the Docker image
docker build -t kafka-postgres-consumer:latest .

# Verify image was created
docker images | grep kafka-postgres-consumer
```

**For Minikube users:**
```bash
# Load image into minikube
minikube image load kafka-postgres-consumer:latest

# Verify
minikube image ls | grep kafka-postgres-consumer
```

**For Kind users:**
```bash
# Load image into kind
kind load docker-image kafka-postgres-consumer:latest

# Verify
docker exec -it kind-control-plane crictl images | grep kafka-postgres-consumer
```

---

## Step 7: Deploy to Kubernetes

From your local machine:

```bash
# Ensure you're in the project root directory
cd /path/to/kafka-postgres-consumer

# Create namespace (if it doesn't exist)
kubectl create namespace turbonomic

# Apply ConfigMap
kubectl apply -f kubernetes/configmap.yaml

# Verify ConfigMap
kubectl get configmap kafka-postgres-consumer-config -n turbonomic

# Apply Secret
kubectl apply -f kubernetes/secret.yaml

# Verify Secret
kubectl get secret kafka-postgres-consumer-secret -n turbonomic

# Apply Deployment
kubectl apply -f kubernetes/deployment.yaml

# Verify Deployment
kubectl get deployment kafka-postgres-consumer -n turbonomic
```

**Expected Output:**
```
namespace/turbonomic created (or already exists)
configmap/kafka-postgres-consumer-config created
secret/kafka-postgres-consumer-secret created
deployment.apps/kafka-postgres-consumer created
```

---

## Step 8: Verify Pod is Running

```bash
# Get pod status
kubectl get pods -n turbonomic -l app=kafka-postgres-consumer

# Expected output:
# NAME                                      READY   STATUS    RESTARTS   AGE
# kafka-postgres-consumer-xxxxxxxxxx-xxxxx   1/1     Running   0          30s

# Get pod name
POD_NAME=$(kubectl get pods -n turbonomic -l app=kafka-postgres-consumer -o jsonpath='{.items[0].metadata.name}')

# View logs
kubectl logs -f $POD_NAME -n turbonomic
```

**Expected Log Output:**
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

## Step 9: Verify Data Flow

Check that messages are being stored in the database:

```bash
# From your local machine
psql -h 192.168.178.61 -U manfred -d turbonomic_data

# Inside psql, run these queries:

-- Check message count
SELECT COUNT(*) FROM kafka.kafka_messages;

-- View recent messages
SELECT * FROM kafka.recent_messages LIMIT 10;

-- Get statistics by topic
SELECT * FROM kafka.get_message_count_by_topic();

-- View messages from last hour
SELECT 
    id, 
    message_key, 
    topic, 
    partition, 
    offset, 
    consumed_at
FROM kafka.kafka_messages
WHERE consumed_at > NOW() - INTERVAL '1 hour'
ORDER BY consumed_at DESC
LIMIT 20;
```

---

## Common Commands Reference

### PostgreSQL Server Commands

```bash
# SSH to server
ssh user@192.168.178.61

# Check PostgreSQL status
sudo systemctl status postgresql

# Restart PostgreSQL
sudo systemctl restart postgresql

# View PostgreSQL logs
sudo journalctl -u postgresql -n 100 -f

# Connect to database
sudo -u postgres psql -d turbonomic_data
```

### Kubernetes Commands

```bash
# Get pod name
POD_NAME=$(kubectl get pods -n turbonomic -l app=kafka-postgres-consumer -o jsonpath='{.items[0].metadata.name}')

# View logs (real-time)
kubectl logs -f $POD_NAME -n turbonomic

# View last 100 log lines
kubectl logs --tail=100 $POD_NAME -n turbonomic

# Describe pod (for troubleshooting)
kubectl describe pod $POD_NAME -n turbonomic

# Check resource usage
kubectl top pod $POD_NAME -n turbonomic

# Restart deployment
kubectl rollout restart deployment kafka-postgres-consumer -n turbonomic

# Scale deployment
kubectl scale deployment kafka-postgres-consumer -n turbonomic --replicas=3

# Delete and recreate
kubectl delete -f kubernetes/deployment.yaml
kubectl apply -f kubernetes/deployment.yaml
```

### Database Queries

```sql
-- Connect to database
psql -h 192.168.178.61 -U manfred -d turbonomic_data

-- Inside psql:

-- Count all messages
SELECT COUNT(*) FROM kafka.kafka_messages;

-- Recent messages
SELECT * FROM kafka.recent_messages LIMIT 10;

-- Messages by topic
SELECT * FROM kafka.get_message_count_by_topic();

-- Messages per hour (last 24 hours)
SELECT 
    DATE_TRUNC('hour', consumed_at) as hour,
    COUNT(*) as message_count
FROM kafka.kafka_messages
WHERE consumed_at > NOW() - INTERVAL '24 hours'
GROUP BY hour
ORDER BY hour DESC;

-- Database size
SELECT pg_size_pretty(pg_database_size('turbonomic_data'));

-- Table size
SELECT pg_size_pretty(pg_total_relation_size('kafka.kafka_messages'));

-- Clean old messages (older than 30 days)
SELECT kafka.cleanup_old_messages(30);
```

---

## Troubleshooting Commands

### If PostgreSQL won't start:

```bash
# Check logs
sudo journalctl -u postgresql -n 100

# Check configuration
sudo -u postgres psql -c "SHOW config_file;"
sudo cat /var/lib/pgsql/15/data/postgresql.conf | grep listen_addresses
```

### If can't connect remotely:

```bash
# Test from pod
kubectl exec -it $POD_NAME -n turbonomic -- bash
apt-get update && apt-get install -y telnet postgresql-client
telnet 192.168.178.61 5432
psql -h 192.168.178.61 -U manfred -d turbonomic_data
```

### If pod won't start:

```bash
# Check events
kubectl describe pod $POD_NAME -n turbonomic

# Check previous logs (if crashed)
kubectl logs --previous $POD_NAME -n turbonomic

# Check ConfigMap and Secret
kubectl get configmap kafka-postgres-consumer-config -n turbonomic -o yaml
kubectl get secret kafka-postgres-consumer-secret -n turbonomic -o yaml
```

---

## Quick Reference Card

```bash
# PostgreSQL Server (192.168.178.61)
sudo systemctl status postgresql          # Check status
sudo systemctl restart postgresql         # Restart
sudo -u postgres psql -d turbonomic_data  # Connect

# Kubernetes
kubectl get pods -n turbonomic -l app=kafka-postgres-consumer  # Status
kubectl logs -f $POD_NAME -n turbonomic                        # Logs
kubectl describe pod $POD_NAME -n turbonomic                   # Details

# Database
psql -h 192.168.178.61 -U manfred -d turbonomic_data  # Connect
SELECT COUNT(*) FROM kafka.kafka_messages;             # Count messages
```

---

## Summary of All Commands in Order

```bash
# 1. Copy files to server
scp postgres-setup/* user@192.168.178.61:~/kafka-postgres-setup/

# 2. Install PostgreSQL
ssh user@192.168.178.61
cd ~/kafka-postgres-setup
chmod +x *.sh
sudo ./install-postgres.sh

# 3. Initialize database (copy to /tmp first)
sudo cp init-database.sql /tmp/
sudo -u postgres psql -f /tmp/init-database.sql

# 4. Configure remote access
sudo ./configure-postgres.sh

# 5. Test connection (from local machine)
python tests/test-postgres-connection.py

# 6. Build Docker image
cd consumer-app
docker build -t kafka-postgres-consumer:latest .

# 7. Deploy to Kubernetes
kubectl apply -f kubernetes/configmap.yaml
kubectl apply -f kubernetes/secret.yaml
kubectl apply -f kubernetes/deployment.yaml

# 8. Verify
kubectl get pods -n turbonomic -l app=kafka-postgres-consumer
kubectl logs -f <pod-name> -n turbonomic
```

---

**Need Help?** See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) for detailed problem resolution.