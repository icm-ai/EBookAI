# EBookAI Dockerfile with Calibre Support
# Multi-stage build for optimal size and performance

# Stage 1: Frontend Build
FROM node:18-alpine AS frontend-builder
WORKDIR /app
COPY frontend/web/package*.json ./
RUN npm ci --only=production
COPY frontend/web/ ./
RUN npm run build

# Stage 2: Production Runtime with Calibre
FROM debian:12-slim

# Install system dependencies including Calibre
RUN apt-get update && apt-get install -y \
    # Core tools
    curl \
    wget \
    gnupg2 \
    # Python and development tools
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    # Calibre and ebook conversion tools
    calibre \
    # Chinese fonts for PDF generation
    fonts-noto-cjk \
    fonts-wqy-zenhei \
    fonts-wqy-microhei \
    # Additional dependencies for better compatibility
    xvfb \
    imagemagick \
    # Clean up
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /tmp/* /var/tmp/*

# Create application user for security
RUN useradd -m -u 1000 ebook && mkdir -p /workspace
WORKDIR /workspace

# Copy Python requirements and install
COPY backend/requirements.txt ./
RUN python3 -m pip install --no-cache-dir --upgrade pip \
    && python3 -m pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ backend/

# Copy frontend build artifacts
COPY --from=frontend-builder /app/build frontend/web/build/

# Create necessary directories
RUN mkdir -p uploads outputs config \
    && chown -R ebook:ebook /workspace

# Switch to non-root user
USER ebook

# Environment variables
ENV PYTHONPATH=/workspace/backend/src
ENV PYTHONUNBUFFERED=1
ENV CALIBRE_WORKER_TEMP_DIR=/tmp

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Expose ports
EXPOSE 8000

# Start command
CMD ["python3", "backend/src/main.py"]