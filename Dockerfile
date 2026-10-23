# ============================================================
# 🌍 Kenya Live Data Engine - Streamlit dashboard container
# ============================================================

# ---------- Stage 1: build dependencies ----------
FROM python:3.11-slim AS builder

WORKDIR /build

# Compilers are only needed to build wheels (numpy/pandas/scipy etc.),
# so they stay in this stage and never reach the final image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first so Docker caches this layer until they change
COPY requirements.txt .
RUN pip wheel --no-cache-dir --wheel-dir /wheels -r requirements.txt


# ---------- Stage 2: lightweight runtime ----------
FROM python:3.11-slim

LABEL org.opencontainers.image.title="Kenya Live Data Engine" \
      org.opencontainers.image.description="Real-time climate anomaly pipeline and Streamlit dashboard for Kenya" \
      org.opencontainers.image.source="https://github.com/Haldline777/KENYA-_-LIVE_DATA_ENGINE"

# Python behaves better in containers with these settings:
#   - no .pyc clutter, logs appear instantly in `docker logs`
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    TZ=Africa/Nairobi \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false \
    STREAMLIT_SERVER_ENABLE_CORS=false

WORKDIR /app

# Only curl is needed at runtime (for the health check); tzdata sets Nairobi time
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tzdata \
    && ln -snf /usr/share/zoneinfo/$TZ /etc/localtime && echo $TZ > /etc/timezone \
    && rm -rf /var/lib/apt/lists/*

# Install pre-built wheels from stage 1 (fast, no compiler needed)
COPY --from=builder /wheels /wheels
COPY requirements.txt .
RUN pip install --no-index --find-links=/wheels -r requirements.txt \
    && rm -rf /wheels

# Run as a non-root user for security
RUN useradd --create-home --uid 1000 appuser

# Copy project files (pipeline.py, Satellite_engine.py, app.py, CSV, etc.)
COPY --chown=appuser:appuser . .

# Make sure the anomaly data can be updated by the app/pipeline
RUN mkdir -p /app/data && chown -R appuser:appuser /app
VOLUME ["/app/data"]

USER appuser

# Port Streamlit runs on
EXPOSE 8501

# Container is marked unhealthy if Streamlit stops responding
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Start the dashboard
CMD ["streamlit", "run", "app.py", \
     "--server.address=0.0.0.0", \
     "--server.port=8501"]