FROM python:3.12-slim

# Graphviz lays out the diagrams; DejaVu fonts give it readable labels.
RUN apt-get update \
 && apt-get install -y --no-install-recommends graphviz fonts-dejavu-core \
 && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 WORK_DIR=/tmp/sa-jobs
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

RUN useradd --create-home appuser && mkdir -p /tmp/sa-jobs && chown appuser /tmp/sa-jobs
USER appuser

# Render sets PORT (default 10000). Proxy headers keep https redirects correct behind Render's load balancer.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-10000} --proxy-headers --forwarded-allow-ips='*'"]
