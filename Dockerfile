# ==========================================================
# AI News Aggregator - Production Dockerfile
# ==========================================================
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create output directories
RUN mkdir -p output/digests

EXPOSE 8000

HEALTHCHECK CMD curl --fail http://localhost:8000/api/health || exit 1

# Default runs the API server & web dashboard
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
