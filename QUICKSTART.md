# Quick Start Guide - Kafka to PostgreSQL Consumer

This guide gets you up and running in 15 minutes.

## Prerequisites Checklist

- [ ] SSH access to 192.168.178.61
- [ ] Root/sudo access on 192.168.178.61
- [ ] kubectl access to Kubernetes cluster
- [ ] turbonomic namespace exists in Kubernetes
- [ ] Docker installed (for building image)

## Step 1: PostgreSQL Setup (5 minutes)

```bash
# 1. SSH to PostgreSQL server
ssh user@192.168.178.61

# 2. Copy setup files to server (use scp or copy-paste)
# Files needed: install-postgres.sh, init-database.sql, configure-postgres.sh

# 3. Run installation
chmod +x install-postgres.sh configure-postgres.sh
sudo ./install-postgres.sh
sudo -u postgres psql -f init-database.sql
sudo ./configure-postgres.sh

# 4. Verify installation
sudo systemctl status postgresql
```

**Expected Result**: PostgreSQL running and accessible on port 5432

## Step 2: Test PostgreSQL (2 minutes)

```bash
# From your local machine
pip install psycopg2-binary
python tests/test-postgres-connection.py
```

**Expected Result**: All tests pass ✓

## Step 3: Build Docker Image (3 minutes)

```bash
# Navigate to consumer app directory
cd consumer-app

# Build image
docker build -t kafka-postgres-consumer:latest .

# For minikube users
minikube image load kafka-postgres-consumer:latest

# For kind users
kind load docker-image kafka-postgres-consumer:latest
```

**Expected Result**: Image built successfully

## Step 4: Deploy to Kubernetes (3 minutes)

```bash
# Create namespace (if not exists)
kubectl create namespace turbonomic

# Deploy resources
kubectl apply -f kubernetes/configmap.yaml
kubectl apply -f kubernetes/secret.yaml
kubectl apply -f kubernetes/deployment.yaml

# Wait for pod to be ready
kubectl wait --for=condition=ready pod -l app=kafka-postgres-consumer -n turbonomic --timeout=60s
```

**Expected Result**: Pod running with status 1/1 Ready

## Step 5: Verify Operation (2 minutes)

```bash
# Get pod name
POD_NAME=$(kubectl get pods -n turbonomic -l app=kafka-postgres-consumer -o jsonpath='{.items[0].metadata.name}')

# Check logs
kubectl logs $POD_NAME -n turbonomic

# Should see:
# ✓ "PostgreSQL connection pool initialized successfully"
# ✓ "Kafka consumer initialized successfully"
# ✓ "Starting message consumption..."

# Check database
psql -h 192.168.178.61 -U manfred -d turbonomic_data -c "SELECT COUNT(*) FROM kafka.kafka_messages;"
```

**Expected Result**: Consumer running, messages being stored

## Troubleshooting Quick Fixes

### Pod Not Starting

```bash
# Check pod status
kubectl describe pod $POD_NAME -n turbonomic

# Check logs
kubectl logs $POD_NAME -n turbonomic

# Common fix: Recreate resources
kubectl delete -f kubernetes/deployment.yaml
kubectl apply -f kubernetes/deployment.yaml
```

### Cannot Connect to PostgreSQL

```bash
# Test from pod
kubectl exec -it $POD_NAME -n turbonomic -- bash
apt-get update && apt-get install -y telnet
telnet 192.168.178.61 5432

# If fails, check firewall on PostgreSQL server
ssh user@192.168.178.61
sudo firewall-cmd --list-ports  # Should show 5432/tcp
```

### Cannot Connect to Kafka

```bash
# Check Kafka service
kubectl get svc kafka -n turbonomic

# Test from pod
kubectl exec -it $POD_NAME -n turbonomic -- bash
telnet kafka 9092
```

## Next Steps

Once everything is running:

1. **Monitor logs**: `kubectl logs -f $POD_NAME -n turbonomic`
2. **Check database growth**: Run queries in PostgreSQL
3. **Scale if needed**: `kubectl scale deployment kafka-postgres-consumer -n turbonomic --replicas=3`
4. **Read full documentation**: See [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md)

## Useful Commands

```bash
# View logs
kubectl logs -f $POD_NAME -n turbonomic

# Check resource usage
kubectl top pod $POD_NAME -n turbonomic

# Restart consumer
kubectl rollout restart deployment kafka-postgres-consumer -n turbonomic

# Scale consumer
kubectl scale deployment kafka-postgres-consumer -n turbonomic --replicas=3

# Check database
psql -h 192.168.178.61 -U manfred -d turbonomic_data

# Inside psql:
SELECT COUNT(*) FROM kafka.kafka_messages;
SELECT * FROM kafka.recent_messages LIMIT 10;
SELECT * FROM kafka.get_message_count_by_topic();
```

## Success Criteria

✅ PostgreSQL installed and running on 192.168.178.61  
✅ Database `turbonomic_data` created with schema  
✅ Consumer pod running in Kubernetes  
✅ No errors in pod logs  
✅ Messages appearing in PostgreSQL database  

## Getting Help

- **Setup issues**: See [docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md)
- **Errors**: See [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)
- **Architecture**: See [TECHNICAL_SPECIFICATIONS.md](TECHNICAL_SPECIFICATIONS.md)

---

**Time to Complete**: ~15 minutes  
**Difficulty**: Intermediate  
**Status**: Production Ready ✅