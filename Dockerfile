FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
      libglib2.0-0 libgl1 curl \
    && rm -rf /var/lib/apt/lists/* \
    && groupadd --system facecode \
    && useradd --system --gid facecode --home /app facecode

WORKDIR /app
COPY requirements.txt .
RUN python -m pip install --upgrade pip && python -m pip install -r requirements.txt

COPY api_server.py runner_service.py ./
COPY backend ./backend
COPY model ./model
RUN mkdir -p /data && chown -R facecode:facecode /data /app

USER facecode
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=90s --retries=3 \
  CMD curl --fail http://127.0.0.1:8000/api/health || exit 1

CMD ["uvicorn", "api_server:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*", "--ws-max-size", "4000000"]
