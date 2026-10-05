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

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN playwright install chromium --with-deps && \
    chmod -R a+rX /ms-playwright

COPY app ./app
COPY skills ./skills

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
