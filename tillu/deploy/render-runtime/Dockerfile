FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

LABEL build.version="0.8.1" build.date="2026-10-05"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    PORT=8000

RUN groupadd --system tillu && \
    useradd --system --gid tillu --create-home --shell /bin/false tillu

WORKDIR /app

# ── Copy entire build context so we can detect the layout ────────────────────
COPY . /build/

# ── Install deps ─────────────────────────────────────────────────────────────
# Detect whether context root is deploy/render-runtime or the repo root
RUN if [ -f /build/requirements.txt ]; then \
        pip install --no-cache-dir -r /build/requirements.txt; \
    else \
        pip install --no-cache-dir -r /build/deploy/render-runtime/requirements.txt; \
    fi

# ── Playwright ────────────────────────────────────────────────────────────────
RUN playwright install chromium --with-deps && \
    chmod -R a+rX /ms-playwright

# ── Copy app source ───────────────────────────────────────────────────────────
RUN if [ -d /build/app ]; then \
        cp -r /build/app /app/app; \
    else \
        cp -r /build/deploy/render-runtime/app /app/app; \
    fi && \
    if [ -d /build/skills ]; then \
        cp -r /build/skills /app/skills; \
    elif [ -d /build/deploy/render-runtime/skills ]; then \
        cp -r /build/deploy/render-runtime/skills /app/skills; \
    fi && \
    rm -rf /build

RUN mkdir -p /app/library /app/browser-artifacts && \
    chown -R tillu:tillu /app

USER tillu
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=8s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/live',timeout=5)"

CMD ["sh", "-c", \
     "uvicorn app.main:app \
      --host 0.0.0.0 \
      --port ${PORT:-8000} \
      --workers 1 \
      --proxy-headers \
      --forwarded-allow-ips='*' \
      --log-level $(echo ${LOG_LEVEL:-info} | tr '[:upper:]' '[:lower:]')"]
