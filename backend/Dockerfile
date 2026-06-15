# ═══════════════════════════════════════════════════════════════════════════════
# MediaTruth Backend — Dockerfile
# ═══════════════════════════════════════════════════════════════════════════════
#
# Multi-stage build:
#   Stage 1 (builder): Install Python deps with pip
#   Stage 2 (runtime): Copy only what's needed — keeps image lean
#
# ARCH-01 fix: Pre-download timm EfficientNet-B5 weights during build
#   so startup doesn't require internet access or cold-start download delay.
# ═══════════════════════════════════════════════════════════════════════════════

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS builder

WORKDIR /build

# Install build tools for packages that need compilation (e.g. Pillow, OpenCV)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgl1-mesa-glx \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for Docker layer caching
COPY requirements.txt .

# Install all Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ARCH-01 fix: Pre-download timm model weights during build
# This prevents 30s+ cold start download and network dependency at runtime
RUN python -c "import timm; timm.create_model('efficientnet_b5', pretrained=True)" \
    2>&1 || echo "WARNING: timm pre-download failed (no internet in build env). Will download at runtime."

# Pre-download torchvision ResNet50 weights for CNNDetect
RUN python -c "import torchvision.models as m; m.resnet50(weights=m.ResNet50_Weights.IMAGENET1K_V2)" \
    2>&1 || echo "WARNING: ResNet50 pre-download failed. Will download at runtime."


# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM python:3.11-slim AS runtime

WORKDIR /app

# Runtime system libraries (OpenCV and Pillow need these)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libgl1-mesa-glx \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy pre-downloaded HuggingFace / torch cache
COPY --from=builder /root/.cache /root/.cache

# Copy application source
COPY . .

# Create model weights directory (mounted as volume in docker-compose)
RUN mkdir -p models/weights

# Create temp upload directory
RUN mkdir -p /tmp/mediatruth_uploads

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:8000/health/ || exit 1

# Run with uvicorn
CMD ["uvicorn", "main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--log-level", "info"]
