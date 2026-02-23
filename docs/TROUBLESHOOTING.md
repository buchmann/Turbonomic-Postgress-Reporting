# Troubleshooting Guide - Kafka to PostgreSQL Consumer

This guide helps diagnose and resolve common issues with the Kafka to PostgreSQL consumer system.

## Table of Contents

1. [Quick Diagnostics](#quick-diagnostics)
2. [PostgreSQL Issues](#postgresql-issues)
3. [Kafka Issues](#kafka-issues)
4. [Consumer Application Issues](#consumer-application-issues)
5. [Kubernetes Issues](#kubernetes-issues)
6. [Performance Issues](#performance-issues)
7. [Data Issues](#data-issues)
8. [Network Issues](#network-issues)

---

## Quick Diagnostics

### Health Check Commands

```bash
# Check pod status
kubectl get pods -n turbonomic -l app=kafka-postgres-consumer

# Check pod logs
POD_NAME=$(kubectl get pods -n turbonomic -l app=kafka-postgres-consumer -o jsonpath='{.items[0].metadata.name}')
kubectl logs --tail=50 $POD_NAME -n turbonomic

# Check pod events
kubectl describe pod $POD_NAME -n turbonomic | grep -A 20 Events

# Check resource usage
kubectl top pod $POD_NAME -n turbonomic

# Test PostgreSQL connection
python tests/test-postgres-connection.py

# Test Kafka connection (from within cluster)
kubectl exec -it $POD_NAME -n turbonomic -- python -c "from kafka import KafkaConsumer; print('OK')"
```

---

## PostgreSQL Issues

### Issue: Cannot Connect to PostgreSQL

**Symptoms:**
- Consumer logs show connection errors
- `psycopg2.OperationalError: could not connect to server`

**Diagnosis:**
```bash
# Test connection from pod
kubectl exec -it $POD_NAME -n turbonomic -- bash
apt-get update && apt-get install -y postgresql-client telnet
telnet 192.168.178.61 5432
psql -h 192.168.178.61 -U manfred -d turbonomic_data
```

**Solutions:**

1. **Check PostgreSQL is running:**
   ```bash
   ssh user@192.168.178.61
   sudo systemctl status postgresql
   # or
   sudo systemctl status postgresql-15
   ```

2. **Check firewall:**
   ```bash
   # On PostgreSQL server
   sudo firewall-cmd --list-ports  # For firewalld
   sudo ufw status                  # For ufw
   sudo iptables -L -n | grep 5432  # For iptables
   ```

3. **Check PostgreSQL configuration:**
   ```bash
   # On PostgreSQL server
   sudo grep listen_addresses /var/lib/pgsql/15/data/postgresql.conf
   # Should show: listen_addresses = '*'
   
   sudo grep "host.*turbonomic_data" /var/lib/pgsql/15/data/pg_hba.conf
   # Should have entries allowing remote connections
   ```

4. **Check credentials:**
   ```bash
   # Verify Secret
   kubectl get secret kafka-postgres-consumer-secret -n turbonomic -o yaml
   # Decode values
   echo "bWFuZnJlZA==" | base64 -d  # Should show: manfred
   echo "VGVzdDcyODM=" | base64 -d  # Should show: Test7283
   ```

5. **Restart PostgreSQL:**
   ```bash
   ssh user@192.168.178.61
   sudo systemctl restart postgresql
   # or
   sudo systemctl restart postgresql-15
   ```

### Issue: Database Connection Pool Exhausted

**Symptoms:**
- `PoolError: connection pool exhausted`
- Consumer stops processing messages

**Solutions:**

1. **Increase connection pool size:**
   ```bash
   kubectl edit configmap kafka-postgres-consumer-config -n turbonomic
   # Change POSTGRES_MAX_CONN to higher value (e.g., 20)
   kubectl rollout restart deployment kafka-postgres-consumer -n turbonomic
   ```

2. **Check for connection leaks:**
   ```sql
   -- On PostgreSQL
   SELECT count(*) FROM pg_stat_activity WHERE usename = 'manfred';
   SELECT * FROM pg_stat_activity WHERE usename = 'manfred';
   ```

3. **Kill idle connections:**
   ```sql
   SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE usename = 'manfred' 
   AND state = 'idle' 
   AND state_change < NOW() - INTERVAL '5 minutes';
   ```

### Issue: Slow Database Inserts

**Symptoms:**
- High batch processing time in logs
- Consumer lag increasing

**Solutions:**

1. **Check database performance:**
   ```sql
   -- Check slow queries
   SELECT query, mean_exec_time, calls 
   FROM pg_stat_statements 
   ORDER BY mean_exec_time DESC 
   LIMIT 10;
   
   -- Check table bloat
   SELECT 
       schemaname, tablename,
       pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
   FROM pg_tables 
   WHERE schemaname = 'kafka';
   ```

2. **Optimize indexes:**
   ```sql
   -- Rebuild indexes
   REINDEX TABLE kafka.kafka_messages;
   
   -- Analyze table
   ANALYZE kafka.kafka_messages;
   ```

3. **Vacuum table:**
   ```sql
   VACUUM FULL ANALYZE kafka.kafka_messages;
   ```

4. **Increase batch size:**
   ```bash
   kubectl edit configmap kafka-postgres-consumer-config -n turbonomic
   # Increase BATCH_SIZE (e.g., to 200)
   ```

### Issue: Database Disk Full

**Symptoms:**
- `ERROR: could not extend file: No space left on device`
- Insert operations failing

**Solutions:**

1. **Check disk space:**
   ```bash
   ssh user@192.168.178.61
   df -h
   ```

2. **Clean old messages:**
   ```sql
   -- Delete messages older than 30 days
   SELECT kafka.cleanup_old_messages(30);
   
   -- Or manually
   DELETE FROM kafka.kafka_messages 
   WHERE consumed_at < NOW() - INTERVAL '30 days';
   
   VACUUM FULL kafka.kafka_messages;
   ```

3. **Archive old data:**
   ```sql
   -- Create archive table
   CREATE TABLE kafka.kafka_messages_archive AS 
   SELECT * FROM kafka.kafka_messages 
   WHERE consumed_at < NOW() - INTERVAL '90 days';
   
   -- Delete archived data
   DELETE FROM kafka.kafka_messages 
   WHERE consumed_at < NOW() - INTERVAL '90 days';
   ```

---

## Kafka Issues

### Issue: Cannot Connect to Kafka

**Symptoms:**
- `NoBrokersAvailable` error
- Consumer cannot start

**Diagnosis:**
```bash
# Test from pod
kubectl exec -it $POD_NAME -n turbonomic -- bash
apt-get update && apt-get install -y telnet
telnet kafka 9092

# Check Kafka pods
kubectl get pods -n turbonomic | grep kafka
```

**Solutions:**

1. **Check Kafka service:**
   ```bash
   kubectl get svc kafka -n turbonomic
   kubectl describe svc kafka -n turbonomic
   ```

2. **Check Kafka broker logs:**
   ```bash
   kubectl logs kafka-0 -n turbonomic
   ```

3. **Verify bootstrap servers:**
   ```bash
   kubectl get configmap kafka-postgres-consumer-config -n turbonomic -o yaml | grep KAFKA_BOOTSTRAP_SERVERS
   ```

### Issue: Topic Does Not Exist

**Symptoms:**
- `UnknownTopicOrPartitionError`
- Consumer logs show topic not found

**Solutions:**

1. **List topics:**
   ```bash
   kubectl exec -it kafka-0 -n turbonomic -- kafka-topics \
     --bootstrap-server kafka:9092 --list
   ```

2. **Create topic:**
   ```bash
   kubectl exec -it kafka-0 -n turbonomic -- kafka-topics \
     --bootstrap-server kafka:9092 \
     --create \
     --topic turbonomic.exporter \
     --partitions 3 \
     --replication-factor 1
   ```

3. **Verify topic name in ConfigMap:**
   ```bash
   kubectl get configmap kafka-postgres-consumer-config -n turbonomic -o yaml | grep KAFKA_TOPIC
   ```

### Issue: Consumer Lag Increasing

**Symptoms:**
- Messages not being consumed fast enough
- Lag increasing over time

**Diagnosis:**
```bash
# Check consumer group lag
kubectl exec -it kafka-0 -n turbonomic -- kafka-consumer-groups \
  --bootstrap-server kafka:9092 \
  --group turbonomic-postgres-consumer \
  --describe
```

**Solutions:**

1. **Scale horizontally:**
   ```bash
   kubectl scale deployment kafka-postgres-consumer -n turbonomic --replicas=3
   ```

2. **Increase batch size:**
   ```bash
   kubectl edit configmap kafka-postgres-consumer-config -n turbonomic
   # Increase BATCH_SIZE and KAFKA_MAX_POLL_RECORDS
   ```

3. **Optimize database inserts:**
   - See [Slow Database Inserts](#issue-slow-database-inserts)

---

## Consumer Application Issues

### Issue: Pod Crashing or Restarting

**Symptoms:**
- Pod status shows `CrashLoopBackOff`
- High restart count

**Diagnosis:**
```bash
# Check pod status
kubectl describe pod $POD_NAME -n turbonomic

# Check current logs
kubectl logs $POD_NAME -n turbonomic

# Check previous logs
kubectl logs --previous $POD_NAME -n turbonomic
```

**Solutions:**

1. **Check for Python errors:**
   ```bash
   kubectl logs --previous $POD_NAME -n turbonomic | grep -i "error\|exception\|traceback"
   ```

2. **Check resource limits:**
   ```bash
   kubectl describe pod $POD_NAME -n turbonomic | grep -A 10 "Limits\|Requests"
   kubectl top pod $POD_NAME -n turbonomic
   ```

3. **Increase memory limits:**
   ```yaml
   # Edit deployment.yaml
   resources:
     limits:
       memory: "1Gi"  # Increase from 512Mi
   ```

4. **Check environment variables:**
   ```bash
   kubectl exec -it $POD_NAME -n turbonomic -- env | grep -E "KAFKA|POSTGRES"
   ```

### Issue: Messages Not Being Processed

**Symptoms:**
- Consumer running but no messages in database
- No errors in logs

**Diagnosis:**
```bash
# Check consumer logs
kubectl logs $POD_NAME -n turbonomic | grep -i "consumed\|processed\|inserted"

# Check if messages exist in Kafka
kubectl exec -it kafka-0 -n turbonomic -- kafka-console-consumer \
  --bootstrap-server kafka:9092 \
  --topic turbonomic.exporter \
  --from-beginning \
  --max-messages 10
```

**Solutions:**

1. **Check consumer offset:**
   ```bash
   kubectl exec -it kafka-0 -n turbonomic -- kafka-consumer-groups \
     --bootstrap-server kafka:9092 \
     --group turbonomic-postgres-consumer \
     --describe
   ```

2. **Reset consumer offset:**
   ```bash
   # Stop consumer
   kubectl scale deployment kafka-postgres-consumer -n turbonomic --replicas=0
   
   # Reset offset to earliest
   kubectl exec -it kafka-0 -n turbonomic -- kafka-consumer-groups \
     --bootstrap-server kafka:9092 \
     --group turbonomic-postgres-consumer \
     --reset-offsets \
     --to-earliest \
     --topic turbonomic.exporter \
     --execute
   
   # Start consumer
   kubectl scale deployment kafka-postgres-consumer -n turbonomic --replicas=1
   ```

3. **Check for deserialization errors:**
   ```bash
   kubectl logs $POD_NAME -n turbonomic | grep -i "deserializ\|json\|parse"
   ```

### Issue: High Memory Usage

**Symptoms:**
- Pod using more memory than expected
- OOMKilled events

**Solutions:**

1. **Reduce batch size:**
   ```bash
   kubectl edit configmap kafka-postgres-consumer-config -n turbonomic
   # Reduce BATCH_SIZE (e.g., to 50)
   # Reduce KAFKA_MAX_POLL_RECORDS (e.g., to 250)
   ```

2. **Increase memory limits:**
   ```yaml
   resources:
     limits:
       memory: "1Gi"
   ```

3. **Check for memory leaks:**
   ```bash
   # Monitor memory over time
   watch kubectl top pod $POD_NAME -n turbonomic
   ```

---

## Kubernetes Issues

### Issue: Image Pull Errors

**Symptoms:**
- `ImagePullBackOff` or `ErrImagePull`
- Pod not starting

**Solutions:**

1. **Check image name:**
   ```bash
   kubectl describe pod $POD_NAME -n turbonomic | grep Image
   ```

2. **Build and load image locally:**
   ```bash
   cd consumer-app
   docker build -t kafka-postgres-consumer:latest .
   
   # For minikube
   minikube image load kafka-postgres-consumer:latest
   
   # For kind
   kind load docker-image kafka-postgres-consumer:latest
   ```

3. **Use imagePullPolicy: IfNotPresent:**
   ```yaml
   spec:
     containers:
     - name: consumer
       imagePullPolicy: IfNotPresent
   ```

### Issue: ConfigMap or Secret Not Found

**Symptoms:**
- Pod fails to start
- Error about missing ConfigMap or Secret

**Solutions:**

1. **Verify resources exist:**
   ```bash
   kubectl get configmap kafka-postgres-consumer-config -n turbonomic
   kubectl get secret kafka-postgres-consumer-secret -n turbonomic
   ```

2. **Recreate resources:**
   ```bash
   kubectl apply -f kubernetes/configmap.yaml
   kubectl apply -f kubernetes/secret.yaml
   ```

3. **Check namespace:**
   ```bash
   kubectl get all -n turbonomic
   ```

### Issue: Insufficient Resources

**Symptoms:**
- Pod stuck in `Pending` state
- Events show insufficient CPU or memory

**Solutions:**

1. **Check cluster resources:**
   ```bash
   kubectl describe nodes | grep -A 5 "Allocated resources"
   ```

2. **Reduce resource requests:**
   ```yaml
   resources:
     requests:
       memory: "128Mi"
       cpu: "100m"
   ```

3. **Scale down other workloads:**
   ```bash
   kubectl scale deployment <other-deployment> -n turbonomic --replicas=0
   ```

---

## Performance Issues

### Issue: Slow Message Processing

**Diagnosis:**
```bash
# Check processing rate in logs
kubectl logs $POD_NAME -n turbonomic | grep "Processed.*messages"

# Check batch processing time
kubectl logs $POD_NAME -n turbonomic | grep "Batch inserted"
```

**Solutions:**

1. **Increase batch size:**
   ```bash
   kubectl edit configmap kafka-postgres-consumer-config -n turbonomic
   # Increase BATCH_SIZE to 200-500
   ```

2. **Optimize database:**
   - See [Slow Database Inserts](#issue-slow-database-inserts)

3. **Scale horizontally:**
   ```bash
   kubectl scale deployment kafka-postgres-consumer -n turbonomic --replicas=3
   ```

4. **Increase resources:**
   ```yaml
   resources:
     requests:
       cpu: "500m"
       memory: "512Mi"
     limits:
       cpu: "1000m"
       memory: "1Gi"
   ```

---

## Data Issues

### Issue: Duplicate Messages

**Symptoms:**
- Unique constraint violations in logs
- Same message appears multiple times

**Diagnosis:**
```sql
-- Check for duplicates
SELECT topic, partition, offset, COUNT(*) 
FROM kafka.kafka_messages 
GROUP BY topic, partition, offset 
HAVING COUNT(*) > 1;
```

**Solutions:**

1. **This is expected behavior** - The unique constraint prevents duplicates
2. **Check logs for constraint violations:**
   ```bash
   kubectl logs $POD_NAME -n turbonomic | grep "unique_message"
   ```

### Issue: Missing Messages

**Diagnosis:**
```bash
# Check consumer offset vs topic offset
kubectl exec -it kafka-0 -n turbonomic -- kafka-consumer-groups \
  --bootstrap-server kafka:9092 \
  --group turbonomic-postgres-consumer \
  --describe

# Check database count
psql -h 192.168.178.61 -U manfred -d turbonomic_data \
  -c "SELECT COUNT(*) FROM kafka.kafka_messages;"
```

**Solutions:**

1. **Check for processing errors:**
   ```bash
   kubectl logs $POD_NAME -n turbonomic | grep -i "error\|failed"
   ```

2. **Reset offset and reprocess:**
   - See [Messages Not Being Processed](#issue-messages-not-being-processed)

---

## Network Issues

### Issue: Network Timeout

**Symptoms:**
- Connection timeout errors
- Intermittent connectivity

**Solutions:**

1. **Check network policies:**
   ```bash
   kubectl get networkpolicies -n turbonomic
   ```

2. **Test connectivity:**
   ```bash
   kubectl exec -it $POD_NAME -n turbonomic -- bash
   ping 192.168.178.61
   telnet 192.168.178.61 5432
   telnet kafka 9092
   ```

3. **Check DNS resolution:**
   ```bash
   kubectl exec -it $POD_NAME -n turbonomic -- nslookup kafka
   kubectl exec -it $POD_NAME -n turbonomic -- nslookup 192.168.178.61
   ```

---

## Getting Help

If you cannot resolve the issue:

1. **Collect diagnostic information:**
   ```bash
   # Pod information
   kubectl describe pod $POD_NAME -n turbonomic > pod-describe.txt
   kubectl logs $POD_NAME -n turbonomic > pod-logs.txt
   kubectl logs --previous $POD_NAME -n turbonomic > pod-logs-previous.txt
   
   # Configuration
   kubectl get configmap kafka-postgres-consumer-config -n turbonomic -o yaml > configmap.yaml
   kubectl get deployment kafka-postgres-consumer -n turbonomic -o yaml > deployment.yaml
   
   # Events
   kubectl get events -n turbonomic --sort-by='.lastTimestamp' > events.txt
   ```

2. **Check PostgreSQL logs:**
   ```bash
   ssh user@192.168.178.61
   sudo journalctl -u postgresql -n 100 > postgres-logs.txt
   ```

3. **Review all logs for errors**

4. **Contact support with collected information**