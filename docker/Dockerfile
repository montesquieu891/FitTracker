FROM python:3.12-slim

WORKDIR /app

# Install system dependencies (gcc for C extensions)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc curl \
    && rm -rf /var/lib/apt/lists/*

# Copy project metadata first (for layer caching)
COPY pyproject.toml .
COPY src/ src/

# Install the package + faker for seed data
RUN pip install --no-cache-dir . faker

# Copy application files
COPY scripts/ scripts/
COPY static/ static/
COPY tests/factories/ tests/factories/
COPY tests/__init__.py tests/__init__.py

# Ensure src is on PYTHONPATH
ENV PYTHONPATH=/app/src:/app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "fittrack.main:app", "--host", "0.0.0.0", "--port", "8000"]
