# --- STAGE 1: BUILDER STAGE (uv package installation) ---
FROM python:3.14-slim AS builder

ENV UV_SYSTEM_PYTHON=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc \
    && rm -rf /var/lib/apt/lists/*

# Pinned uv from its official image instead of piping an unpinned install script into sh
COPY --from=ghcr.io/astral-sh/uv:0.9.21 /uv /uvx /usr/local/bin/

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
    && chmod +x /app/entrypoint.sh \
    && groupadd --system --gid 10001 orion \
    && useradd --system --uid 10001 --gid orion --no-create-home orion \
    && mkdir -p /app/uploads \
    && chown -R orion:orion /app/uploads

# The entrypoint starts as root only to fix ownership of an existing uploads volume, then drops to
# the unprivileged "orion" user (setpriv) before running migrations and the app.

EXPOSE 8000

# Healthcheck for Python runtime
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/orion/api/v1/health')" || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
