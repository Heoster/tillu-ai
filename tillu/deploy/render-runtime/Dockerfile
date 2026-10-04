# ── TILLU Runtime — Render build ─────────────────────────────────────────────
# Base: official Playwright Python image ships Chromium + all system deps.
# We pin to a specific digest via the tag so Render layer-caches reliably.
FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

# Build date label — bump this to force a full cache bust on Render
LABEL build.date="2026-10-05" build.version="0.8.1"

# ── Build-time env ────────────────────────────────────────────────────────────
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Tell Playwright where browsers live so both root and the service user agree
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    # Render injects PORT at runtime; default to 8000 for local docker run
    PORT=8000

# ── System hardening ──────────────────────────────────────────────────────────
RUN groupadd --system tillu && \
    useradd --system --gid tillu --create-home --shell /bin/false tillu

WORKDIR /app

# ── Python dependencies (cached layer) ───────────────────────────────────────
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Playwright browsers ───────────────────────────────────────────────────────
# Install into /ms-playwright (world-readable) so the non-root user can launch.
# --with-deps installs OS packages needed by Chromium (fonts, libs).
RUN playwright install chromium --with-deps && \
    chmod -R a+rX /ms-playwright

# ── Application source ────────────────────────────────────────────────────────
COPY app ./app
# Skills directory (builtin_skills.py resolves Path(__file__).parents[2]/'skills')
COPY skills ./skills

# ── Runtime directories ───────────────────────────────────────────────────────
RUN mkdir -p /app/library /app/browser-artifacts && \
    chown -R tillu:tillu /app

# ── Drop privileges ───────────────────────────────────────────────────────────
USER tillu

EXPOSE 8000

# ── Health check ──────────────────────────────────────────────────────────────
# Render also hits healthCheckPath from render.yaml; this is for docker health.
HEALTHCHECK --interval=30s --timeout=8s --start-period=40s --retries=3 \
  CMD python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:${PORT:-8000}/api/health/live', timeout=5)"

# ── Entrypoint ────────────────────────────────────────────────────────────────
# --workers 1  : Render free plan has 512 MB RAM — one worker is safe
# --proxy-headers: needed behind Render's TLS terminator
# --forwarded-allow-ips='*': Render load-balancer IPs are dynamic
CMD ["sh", "-c", \
     "uvicorn app.main:app \
      --host 0.0.0.0 \
      --port ${PORT:-8000} \
      --workers 1 \
      --proxy-headers \
      --forwarded-allow-ips='*' \
      --log-level $(echo ${LOG_LEVEL:-info} | tr '[:upper:]' '[:lower:]')"]
