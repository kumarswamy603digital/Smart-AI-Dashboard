# AI Insights Dashboard — production image
# Pure Python stack: Dash (Flask) + pandas + optional OpenAI integration.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DASH_HOST=0.0.0.0 \
    DASH_PORT=8050

WORKDIR /app

# curl is needed for the container healthcheck
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install dependencies first for better layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Application code (secrets are NOT copied — see .dockerignore / .env.example)
COPY config/ config/
COPY src/ src/
COPY assets/ assets/
COPY tests/ tests/
COPY data/ data/
COPY app.py pyproject.toml ./

# Non-root runtime user; writable dirs for sample data & reports
RUN useradd --create-home --shell /usr/sbin/nologin appuser \
    && mkdir -p reports \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8050

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD curl -fsS http://127.0.0.1:8050/ || exit 1

# Gunicorn (Linux) serving the Flask object exposed by app.py
CMD ["gunicorn", "--workers", "1", "--bind", "0.0.0.0:8050", "--timeout", "120", "app:server"]
