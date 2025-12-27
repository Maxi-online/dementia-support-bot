FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create a non-root user
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

WORKDIR /app

# Copy and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy code
COPY src/ ./src/

# Copy microservice
COPY docker/services/api/service/ ./service/

# Create logs directory
RUN mkdir -p /app/logs && chown -R appuser:appgroup /app

# Configure environment variables
ENV PYTHONPATH=/app
ENV SERVICE_PORT=8004

USER appuser

EXPOSE 8004

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8004/health || exit 1

CMD ["python", "service/main.py"]
