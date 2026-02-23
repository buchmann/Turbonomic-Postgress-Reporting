# Deployment Checklist - Kafka to PostgreSQL Consumer

Use this checklist to ensure a successful deployment.

## Pre-Deployment

### Infrastructure Preparation

- [ ] Linux server at 192.168.178.61 is accessible via SSH
- [ ] Root/sudo access available on 192.168.178.61
- [ ] Kubernetes cluster is accessible
- [ ] kubectl is configured and working
- [ ] `turbonomic` namespace exists in Kubernetes
- [ ] Docker is installed for building images
- [ ] Network connectivity verified between Kubernetes and 192.168.178.61

### File Preparation

- [ ] All project files downloaded/cloned
- [ ] PostgreSQL setup scripts are executable
- [ ] Consumer application code reviewed
- [ ] Kubernetes manifests reviewed
- [ ] Configuration values verified (IP, credentials, etc.)

## PostgreSQL Setup

### Installation

- [ ] SSH to 192.168.178.61 successful
- [ ] `install-postgres.sh` copied to server
- [ ] Script made executable: `chmod +x install-postgres.sh`
- [ ] Script executed: `sudo ./install-postgres.sh`
- [ ] PostgreSQL service is running
- [ ] No errors in installation output

### Database Initialization

- [ ] `init-database.sql` copied to server
- [ ] Script executed: `sudo -u postgres psql -f init-database.sql`
- [ ] Database `turbonomic_data` created
- [ ] User `manfred` created
- [ ] Schema `kafka` created
- [ ] Table `kafka_messages` created
- [ ] Indexes created
- [ ] Test record inserted successfully

### Remote Access Configuration

- [ ] `configure-postgres.sh` copied to server
- [ ] Script made executable: `chmod +x configure-postgres.sh`
- [ ] Script executed: `sudo ./configure-postgres.sh`
- [ ] `postgresql.conf` updated (listen_addresses = '*')
- [ ] `pg_hba.conf` updated with remote access rules
- [ ] Firewall configured (port 5432 open)
- [ ] PostgreSQL service restarted
- [ ] No errors in configuration output

### PostgreSQL Verification

- [ ] Local connection test successful
- [ ] Remote connection test successful (from local machine)
- [ ] Test script passes: `python tests/test-postgres-connection.py`
- [ ] All 8 tests pass
- [ ] Can query `kafka.kafka_messages` table
- [ ] Can execute `kafka.get_message_count_by_topic()` function

## Docker Image

### Build

- [ ] Navigated to `consumer-app` directory
- [ ] Dockerfile reviewed
- [ ] Image built: `docker build -t kafka-postgres-consumer:latest .`
- [ ] Build completed without errors
- [ ] Image size is reasonable (< 500MB)

### Registry (if applicable)

- [ ] Image tagged for registry
- [ ] Image pushed to registry
- [ ] Image pull verified
- [ ] Registry credentials configured in Kubernetes (if private)

### Local Cluster (if applicable)

- [ ] Image loaded to minikube: `minikube image load kafka-postgres-consumer:latest`
- [ ] OR image loaded to kind: `kind load docker-image kafka-postgres-consumer:latest`
- [ ] Image available in cluster

## Kubernetes Deployment

### Namespace

- [ ] Namespace exists: `kubectl get namespace turbonomic`
- [ ] OR namespace created: `kubectl create namespace turbonomic`
- [ ] Can access namespace: `kubectl get all -n turbonomic`

### ConfigMap

- [ ] ConfigMap file reviewed: `kubernetes/configmap.yaml`
- [ ] Configuration values verified:
  - [ ] KAFKA_BOOTSTRAP_SERVERS correct
  - [ ] KAFKA_TOPIC correct
  - [ ] POSTGRES_HOST = 192.168.178.61
  - [ ] POSTGRES_DATABASE = turbonomic_data
  - [ ] BATCH_SIZE appropriate
- [ ] ConfigMap applied: `kubectl apply -f kubernetes/configmap.yaml`
- [ ] ConfigMap created successfully
- [ ] ConfigMap verified: `kubectl describe configmap kafka-postgres-consumer-config -n turbonomic`

### Secret

- [ ] Secret file reviewed: `kubernetes/secret.yaml`
- [ ] Credentials are base64 encoded
- [ ] Credentials are correct:
  - [ ] POSTGRES_USER = manfred (bWFuZnJlZA==)
  - [ ] POSTGRES_PASSWORD = Test7283 (VGVzdDcyODM=)
- [ ] Secret applied: `kubectl apply -f kubernetes/secret.yaml`
- [ ] Secret created successfully
- [ ] Secret verified: `kubectl get secret kafka-postgres-consumer-secret -n turbonomic`

### Deployment

- [ ] Deployment file reviewed: `kubernetes/deployment.yaml`
- [ ] Image name correct in deployment
- [ ] Resource limits appropriate
- [ ] Environment variables configured
- [ ] Deployment applied: `kubectl apply -f kubernetes/deployment.yaml`
- [ ] Deployment created successfully
- [ ] Deployment verified: `kubectl get deployment kafka-postgres-consumer -n turbonomic`

### Pod Status

- [ ] Pod created: `kubectl get pods -n turbonomic -l app=kafka-postgres-consumer`
- [ ] Pod status is Running
- [ ] Pod ready: 1/1
- [ ] No restart count (or low restart count)
- [ ] Pod age > 1 minute
- [ ] No errors in pod events: `kubectl describe pod $POD_NAME -n turbonomic`

## Verification

### Consumer Logs

- [ ] Logs accessible: `kubectl logs $POD_NAME -n turbonomic`
- [ ] Logs show successful startup
- [ ] PostgreSQL connection successful
- [ ] Kafka consumer initialized
- [ ] Message consumption started
- [ ] No error messages
- [ ] Batch inserts occurring (if messages available)

### Kafka Connectivity

- [ ] Consumer connected to Kafka
- [ ] Topic `turbonomic.exporter` accessible
- [ ] Consumer group created
- [ ] Partitions assigned
- [ ] Messages being polled (if available)

### PostgreSQL Connectivity

- [ ] Consumer connected to PostgreSQL
- [ ] Connection pool initialized
- [ ] Database version logged
- [ ] No connection errors

### Data Flow

- [ ] Messages being consumed from Kafka
- [ ] Messages being inserted into PostgreSQL
- [ ] Can query messages: `SELECT COUNT(*) FROM kafka.kafka_messages;`
- [ ] Message count increasing
- [ ] Recent messages visible: `SELECT * FROM kafka.recent_messages LIMIT 10;`
- [ ] No duplicate key violations (or handled correctly)

### Performance

- [ ] CPU usage reasonable: `kubectl top pod $POD_NAME -n turbonomic`
- [ ] Memory usage reasonable
- [ ] Batch processing time < 1 second
- [ ] No consumer lag (or acceptable lag)
- [ ] Database insert performance acceptable

## Post-Deployment

### Monitoring Setup

- [ ] Log aggregation configured (if applicable)
- [ ] Metrics collection configured (if applicable)
- [ ] Alerts configured (if applicable)
- [ ] Dashboard created (if applicable)

### Documentation

- [ ] Deployment documented
- [ ] Configuration documented
- [ ] Credentials stored securely
- [ ] Runbook created
- [ ] Team trained

### Backup

- [ ] PostgreSQL backup configured
- [ ] Kubernetes resources backed up
- [ ] Backup tested
- [ ] Recovery procedure documented

### Testing

- [ ] End-to-end test performed
- [ ] Test message produced to Kafka
- [ ] Test message appears in PostgreSQL
- [ ] Error handling tested
- [ ] Restart behavior tested

## Rollback Plan

If deployment fails:

- [ ] Rollback procedure documented
- [ ] Previous state documented
- [ ] Rollback tested in non-production
- [ ] Team aware of rollback procedure

### Rollback Steps

1. [ ] Scale deployment to 0: `kubectl scale deployment kafka-postgres-consumer -n turbonomic --replicas=0`
2. [ ] Investigate logs and errors
3. [ ] Fix issues
4. [ ] Redeploy with fixes
5. [ ] Verify functionality

## Sign-Off

### Technical Validation

- [ ] All tests pass
- [ ] No errors in logs
- [ ] Performance acceptable
- [ ] Data integrity verified

### Stakeholder Approval

- [ ] Technical lead approval: _________________ Date: _______
- [ ] Operations approval: _________________ Date: _______
- [ ] Security approval: _________________ Date: _______

### Go-Live

- [ ] Deployment date: _________________
- [ ] Deployed by: _________________
- [ ] Verified by: _________________
- [ ] Production ready: YES / NO

## Post-Go-Live Monitoring (First 24 Hours)

### Hour 1
- [ ] Check logs for errors
- [ ] Verify message consumption
- [ ] Check database growth
- [ ] Monitor resource usage

### Hour 4
- [ ] Review metrics
- [ ] Check for any alerts
- [ ] Verify no restarts
- [ ] Confirm data integrity

### Hour 12
- [ ] Performance review
- [ ] Error rate check
- [ ] Consumer lag check
- [ ] Database size check

### Hour 24
- [ ] Full system review
- [ ] Performance analysis
- [ ] Capacity planning
- [ ] Documentation updates

## Troubleshooting Reference

If issues occur, refer to:

1. **[QUICKSTART.md](QUICKSTART.md)** - Quick fixes
2. **[docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md)** - Detailed troubleshooting
3. **[docs/SETUP_GUIDE.md](docs/SETUP_GUIDE.md)** - Setup verification
4. **Pod logs**: `kubectl logs $POD_NAME -n turbonomic`
5. **PostgreSQL logs**: `ssh user@192.168.178.61 'sudo journalctl -u postgresql -n 100'`

## Success Criteria

✅ All checklist items completed  
✅ Consumer running without errors  
✅ Messages flowing from Kafka to PostgreSQL  
✅ Performance within acceptable limits  
✅ Monitoring and alerts configured  
✅ Documentation complete  
✅ Team trained and ready  

---

**Deployment Status**: ⬜ Not Started | ⬜ In Progress | ⬜ Complete | ⬜ Failed

**Notes**:
_______________________________________________________________________
_______________________________________________________________________
_______________________________________________________________________