FROM python:3.13-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

COPY requirements-server.txt .
RUN pip install --no-cache-dir -r requirements-server.txt

COPY licensing_server ./licensing_server
COPY scripts/start_licensing_server.sh ./scripts/start_licensing_server.sh
RUN chmod +x ./scripts/start_licensing_server.sh

ENV COMPAREDOCS_DATA_DIR=/data
ENV PYTHONUNBUFFERED=1

# Volume persistente: configure no Railway (Settings → Volumes → mount /data).
# Não use VOLUME aqui — o builder da Railway rejeita.

EXPOSE 8390

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:' + __import__('os').environ.get('PORT','8390') + '/v1/health', timeout=3)"

CMD ["./scripts/start_licensing_server.sh"]
