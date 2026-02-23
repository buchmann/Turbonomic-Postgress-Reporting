# Multi-stage build for smaller final image
FROM python:3.11-slim as builder

# Set working directory
WORKDIR /app

# Install build dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    python3-dev \
    libpq-dev \
    libsnappy-dev \
    liblz4-dev \
    libzstd-dev && \
    rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Final stage
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install runtime dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    libpq5 \
    libsnappy1v5 \
    liblz4-1 \
    libzstd1 && \
    rm -rf /var/lib/apt/lists/*

# Copy Python dependencies from builder to a location accessible by all users
COPY --from=builder /root/.local /usr/local

# Copy application code
COPY consumer.py .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && \
    chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# Make sure scripts in .local are usable
ENV PATH=/usr/local/bin:$PATH

# Set Python to run in unbuffered mode for better logging
ENV PYTHONUNBUFFERED=1

# Health check (optional - requires adding health endpoint to consumer.py)
# HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
#   CMD python -c "import sys; sys.exit(0)"

# Run the consumer
CMD ["python", "-u", "consumer.py"]