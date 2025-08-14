# Phase 21: Dockerfile (GPU-optional)
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# System deps for OpenCV, Tesseract optional tools, and build
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy project
COPY . /app

EXPOSE 8000

CMD ["python3", "-m", "uvicorn", "KYC VERIFICATION.src.api.app:app", "--host", "0.0.0.0", "--port", "8000"]

# syntax=docker/dockerfile:1

# Base: Python 3.10 slim for smaller image
FROM python:3.10-slim as base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# System deps for OpenCV runtime and optional OCR/barcode binaries
# Note: tesseract-ocr and libzbar0 are optional; pipeline degrades gracefully if missing
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    cmake \
    pkg-config \
    git \
    curl \
    wget \
    ffmpeg \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libopenblas-dev \
    liblapack-dev \
    libjpeg62-turbo-dev \
    libpng-dev \
    libtiff5 \
    libx11-dev \
    tesseract-ocr \
    libzbar0 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy repository (respects .dockerignore)
COPY . /app

# Install Python dependencies (KYC VERIFICATION specific)
# We intentionally install from the KYC requirements to align with API modules
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r "KYC VERIFICATION/requirements.txt"

# Ensure Python can import modules from the KYC project path that contains a space
ENV PYTHONPATH="/app/KYC VERIFICATION:${PYTHONPATH}"

EXPOSE 8000

# Healthcheck probes FastAPI readiness endpoint
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python -c "import urllib.request as u; u.urlopen('http://127.0.0.1:8000/ready').read(); print('ok')" || exit 1

# Uvicorn entrypoint (no reload inside container)
CMD ["python", "-m", "uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
