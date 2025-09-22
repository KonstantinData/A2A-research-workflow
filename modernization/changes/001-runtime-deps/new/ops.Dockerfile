FROM python:3.13-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_NO_CACHE_DIR=off \
    POETRY_VIRTUALENVS_CREATE=false

# System deps for WeasyPrint (HTML → PDF)
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    build-essential libcairo2 libpango-1.0-0 libpangoft2-1.0-0 libgdk-pixbuf-2.0-0 \
    libffi-dev libjpeg62-turbo-dev libxml2 libxslt1.1 shared-mime-info fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.lock.txt /app/
RUN python -m pip install --upgrade pip && pip install -r requirements.lock.txt

# Copy application code first
COPY . /app

# Non-root user & writable dirs
RUN useradd -m -u 1000 appuser
RUN mkdir -p /app/output /app/logs /app/data
RUN chown -R appuser:appuser /app
USER appuser

VOLUME ["/app/output", "/app/logs", "/app/data"]
# No hardcoded entrypoint; commands defined per service in docker-compose
CMD ["python", "-m", "app.app.worker"]
