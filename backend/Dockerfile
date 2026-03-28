# ── MediaTruth Backend Dockerfile ──────────────────────────────────────────────
FROM python:3.11-bookworm
# Note: Using full bookworm instead of slim to ensure better package availability and pre-installed dependencies

# System deps for OpenCV, magic, ffmpeg
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libsm6 \
    libxrender1 \
    libxext6 \
    libmagic1 \
    ffmpeg \
    libgl1-mesa-glx \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (layer cache)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create weights directory
RUN mkdir -p models/weights

# BUG-019: Run as non-root user for container security
RUN useradd -m -u 1001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
