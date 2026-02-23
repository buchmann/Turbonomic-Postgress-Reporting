#!/bin/bash

################################################################################
# PostgreSQL Remote Access Configuration Script
# Purpose: Configure PostgreSQL to accept remote connections from Kubernetes
# Target: Linux box at 192.168.178.61
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_step() {
    echo -e "${BLUE}[STEP]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    log_error "Please run as root (use sudo)"
    exit 1
fi

log_info "Starting PostgreSQL remote access configuration..."

# Detect PostgreSQL data directory
if [ -d "/var/lib/pgsql/15/data" ]; then
    PG_DATA="/var/lib/pgsql/15/data"
    PG_SERVICE="postgresql-15"
elif [ -d "/var/lib/postgresql/15/main" ]; then
    PG_DATA="/var/lib/postgresql/15/main"
    PG_SERVICE="postgresql"
else
    log_error "Cannot find PostgreSQL data directory"
    exit 1
fi

log_info "PostgreSQL data directory: $PG_DATA"
log_info "PostgreSQL service: $PG_SERVICE"

# Backup configuration files
log_step "Creating backup of configuration files..."
BACKUP_DIR="/root/postgres-backup-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
cp "$PG_DATA/postgresql.conf" "$BACKUP_DIR/" 2>/dev/null || true
cp "$PG_DATA/pg_hba.conf" "$BACKUP_DIR/" 2>/dev/null || true
log_info "Backup created at: $BACKUP_DIR"

# Configure postgresql.conf for remote connections
log_step "Configuring postgresql.conf for remote connections..."

# Check if listen_addresses is already configured
if grep -q "^listen_addresses" "$PG_DATA/postgresql.conf"; then
    log_warn "listen_addresses already configured, updating..."
    sed -i "s/^listen_addresses.*/listen_addresses = '*'/" "$PG_DATA/postgresql.conf"
else
    echo "listen_addresses = '*'" >> "$PG_DATA/postgresql.conf"
fi

# Set max_connections if needed
if ! grep -q "^max_connections" "$PG_DATA/postgresql.conf"; then
    echo "max_connections = 100" >> "$PG_DATA/postgresql.conf"
fi

log_info "postgresql.conf configured successfully"

# Configure pg_hba.conf for authentication
log_step "Configuring pg_hba.conf for authentication..."

# Add entry for Kubernetes pod network (adjust if needed)
# This allows connections from any IP - you may want to restrict this
if ! grep -q "# Kubernetes pod network" "$PG_DATA/pg_hba.conf"; then
    cat >> "$PG_DATA/pg_hba.conf" << 'EOF'

# Kubernetes pod network
# Allow connections from Kubernetes cluster
host    turbonomic_data    manfred    0.0.0.0/0    scram-sha-256
host    turbonomic_data    manfred    ::/0         scram-sha-256

# Allow connections from local network (adjust as needed)
host    all                all        192.168.0.0/16    scram-sha-256
host    all                all        10.0.0.0/8        scram-sha-256
EOF
    log_info "pg_hba.conf updated with remote access rules"
else
    log_warn "Remote access rules already exist in pg_hba.conf"
fi

# Configure firewall
log_step "Configuring firewall..."

# Detect firewall type
if command -v firewall-cmd &> /dev/null; then
    log_info "Detected firewalld, configuring..."
    firewall-cmd --permanent --add-port=5432/tcp
    firewall-cmd --reload
    log_info "Firewall configured (firewalld)"
elif command -v ufw &> /dev/null; then
    log_info "Detected ufw, configuring..."
    ufw allow 5432/tcp
    log_info "Firewall configured (ufw)"
elif command -v iptables &> /dev/null; then
    log_info "Detected iptables, configuring..."
    iptables -A INPUT -p tcp --dport 5432 -j ACCEPT
    # Try to save iptables rules
    if command -v iptables-save &> /dev/null; then
        iptables-save > /etc/iptables/rules.v4 2>/dev/null || \
        iptables-save > /etc/sysconfig/iptables 2>/dev/null || \
        log_warn "Could not save iptables rules permanently"
    fi
    log_info "Firewall configured (iptables)"
else
    log_warn "No firewall detected or firewall not supported"
    log_warn "Please manually configure firewall to allow port 5432"
fi

# Restart PostgreSQL service
log_step "Restarting PostgreSQL service..."
systemctl restart "$PG_SERVICE"

# Wait for PostgreSQL to be ready
log_info "Waiting for PostgreSQL to be ready..."
sleep 5

# Verify PostgreSQL is running
if systemctl is-active --quiet "$PG_SERVICE"; then
    log_info "PostgreSQL service is running"
else
    log_error "PostgreSQL service failed to start"
    log_error "Check logs with: journalctl -u $PG_SERVICE -n 50"
    exit 1
fi

# Test local connection
log_step "Testing local connection..."
if sudo -u postgres psql -d turbonomic_data -c "SELECT 1;" > /dev/null 2>&1; then
    log_info "Local connection test successful"
else
    log_error "Local connection test failed"
    exit 1
fi

# Display connection information
log_info ""
log_info "=================================================================="
log_info "PostgreSQL remote access configuration completed successfully!"
log_info "=================================================================="
log_info ""
log_info "Server IP: 192.168.178.61"
log_info "Port: 5432"
log_info "Database: turbonomic_data"
log_info "User: manfred"
log_info "Password: Test7283"
log_info ""
log_info "Connection string:"
log_info "postgresql://manfred:Test7283@192.168.178.61:5432/turbonomic_data"
log_info ""
log_info "To test remote connection from another machine:"
log_info "psql -h 192.168.178.61 -U manfred -d turbonomic_data"
log_info ""
log_info "Configuration backup saved to: $BACKUP_DIR"
log_info ""
log_info "Firewall status:"
if command -v firewall-cmd &> /dev/null; then
    firewall-cmd --list-ports
elif command -v ufw &> /dev/null; then
    ufw status | grep 5432 || echo "Port 5432 allowed"
fi
log_info ""
log_info "PostgreSQL service status:"
systemctl status "$PG_SERVICE" --no-pager -l
log_info ""
log_info "=================================================================="

exit 0

# Made with Bob
