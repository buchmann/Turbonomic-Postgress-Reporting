#!/bin/bash

################################################################################
# PostgreSQL 15 Installation Script
# Target: Linux box at 192.168.178.61
# Purpose: Install and configure PostgreSQL for Kafka message storage
################################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
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

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    log_error "Please run as root (use sudo)"
    exit 1
fi

log_info "Starting PostgreSQL 15 installation..."

# Detect Linux distribution
if [ -f /etc/os-release ]; then
    . /etc/os-release
    OS=$ID
    VERSION=$VERSION_ID
else
    log_error "Cannot detect Linux distribution"
    exit 1
fi

log_info "Detected OS: $OS $VERSION"

# Install PostgreSQL based on distribution
case $OS in
    ubuntu|debian)
        log_info "Installing PostgreSQL on Ubuntu/Debian..."
        
        # Install prerequisites
        apt-get update
        apt-get install -y wget gnupg2 lsb-release
        
        # Add PostgreSQL repository
        wget --quiet -O - https://www.postgresql.org/media/keys/ACCC4CF8.asc | apt-key add -
        echo "deb http://apt.postgresql.org/pub/repos/apt $(lsb_release -cs)-pgdg main" > /etc/apt/sources.list.d/pgdg.list
        
        # Install PostgreSQL 15
        apt-get update
        apt-get install -y postgresql-15 postgresql-contrib-15
        
        # Start and enable service
        systemctl start postgresql
        systemctl enable postgresql
        ;;
        
    rhel|centos|rocky|almalinux)
        log_info "Installing PostgreSQL on RHEL/CentOS..."
        
        # Install PostgreSQL repository
        dnf install -y https://download.postgresql.org/pub/repos/yum/reporpms/EL-${VERSION%%.*}-x86_64/pgdg-redhat-repo-latest.noarch.rpm
        
        # Disable built-in PostgreSQL module
        dnf -qy module disable postgresql
        
        # Install PostgreSQL 15
        dnf install -y postgresql15-server postgresql15-contrib
        
        # Initialize database
        /usr/pgsql-15/bin/postgresql-15-setup initdb
        
        # Start and enable service
        systemctl start postgresql-15
        systemctl enable postgresql-15
        ;;
        
    fedora)
        log_info "Installing PostgreSQL on Fedora..."
        
        # Install PostgreSQL repository
        dnf install -y https://download.postgresql.org/pub/repos/yum/reporpms/F-${VERSION}-x86_64/pgdg-fedora-repo-latest.noarch.rpm
        
        # Disable built-in PostgreSQL module
        dnf -qy module disable postgresql
        
        # Install PostgreSQL 15
        dnf install -y postgresql15-server postgresql15-contrib
        
        # Initialize database
        /usr/pgsql-15/bin/postgresql-15-setup initdb
        
        # Start and enable service
        systemctl start postgresql-15
        systemctl enable postgresql-15
        ;;
        
    *)
        log_error "Unsupported distribution: $OS"
        log_info "Please install PostgreSQL 15 manually"
        exit 1
        ;;
esac

# Wait for PostgreSQL to be ready
log_info "Waiting for PostgreSQL to be ready..."
sleep 5

# Verify installation
if systemctl is-active --quiet postgresql || systemctl is-active --quiet postgresql-15; then
    log_info "PostgreSQL service is running"
else
    log_error "PostgreSQL service is not running"
    exit 1
fi

# Get PostgreSQL version
PG_VERSION=$(sudo -u postgres psql -t -c "SELECT version();" | head -n 1)
log_info "PostgreSQL version: $PG_VERSION"

# Display PostgreSQL status
log_info "PostgreSQL installation completed successfully!"
log_info ""
log_info "Next steps:"
log_info "1. Run init-database.sql to create database and user"
log_info "2. Run configure-postgres.sh to enable remote connections"
log_info ""
log_info "PostgreSQL service status:"
systemctl status postgresql 2>/dev/null || systemctl status postgresql-15

exit 0

# Made with Bob
