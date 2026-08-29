# --- STAGE 1: BUILDER STAGE (uv package installation) ---
FROM python:3.14-slim AS builder

ENV UV_SYSTEM_PYTHON=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc curl \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && ln -s /root/.local/bin/uv /usr/local/bin/uv

COPY pyproject.toml uv.lock* ./
RUN uv sync --frozen --no-dev --no-install-project

# --- STAGE 2: RUNNER STAGE (Minimal Runtime) ---
FROM python:3.14-slim AS runner

ENV APP_HOME=/app \
    PORT=8000 \
    HOST=0.0.0.0 \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR ${APP_HOME}

COPY --from=builder /build/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

COPY . .

RUN sed -i 's/\r$//' /app/entrypoint.sh \
    && chmod +x /app/entrypoint.sh

EXPOSE 8000

# Healthcheck for Python runtime
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/orion/api/v1/health')" || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
