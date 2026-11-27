# AI Story Factory - image for hosting it for a group of people (see README: "Host it for your group").
FROM python:3.12-slim-bookworm

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 PIP_NO_CACHE_DIR=1 PIP_DISABLE_PIP_VERSION_CHECK=1

# Debian's FFmpeg includes libx264 and libass, which the renderer needs.
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt "gunicorn>=23.0"

COPY . .
RUN useradd --system --uid 10001 --home-dir /app app \
 && mkdir -p /data \
 && chown -R app:app /app /data \
 && chmod +x /app/docker-entrypoint.sh

# SF_HOSTED=1: refuse to start unless SF_ACCESS_CODES is set. SF_TRUST_PROXY=1: the host's HTTPS proxy sits in front.
ENV SF_HOSTED=1 SF_TRUST_PROXY=1 SF_DATA_DIR=/data PORT=8000
VOLUME ["/data"]
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('PORT','8000'), timeout=4)"

# One worker on purpose: render jobs run in this process. Many threads serve many friends at once.
ENTRYPOINT ["/app/docker-entrypoint.sh"]
CMD ["sh", "-c", "exec gunicorn --worker-class gthread --workers 1 --threads 24 --timeout 600 --graceful-timeout 30 --bind 0.0.0.0:${PORT} --access-logfile - backend.app:app"]
