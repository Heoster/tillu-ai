FROM mcr.microsoft.com/playwright/python:v1.55.0-noble
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1

RUN groupadd --system tillu && useradd --system --gid tillu --create-home tillu

WORKDIR /app

# Install Python dependencies first (layer-cached until requirements.txt changes)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers as root so they land in /root/.cache and are accessible
RUN playwright install chromium --with-deps

# Application source
COPY app ./app

# Skills directory (builtin_skills.py resolves Path(__file__).parents[2]/'skills')
COPY skills ./skills

# Runtime directories (owned by the service user)
RUN mkdir -p /app/library /app/browser-artifacts && chown -R tillu:tillu /app

# Copy browsers into tillu's home so the user can access them
RUN cp -r /root/.cache /home/tillu/.cache && chown -R tillu:tillu /home/tillu/.cache

USER tillu
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health/live',timeout=3)"

CMD ["sh","-c","uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --proxy-headers --forwarded-allow-ips='*'"]
