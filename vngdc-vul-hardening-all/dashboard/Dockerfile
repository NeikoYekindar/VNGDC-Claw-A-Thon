# Build context: vngdc-vul-hardening-all/
# Command: docker build -f dashboard/Dockerfile -t <image> .

FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /build

COPY dashboard/frontend/package*.json ./
RUN npm ci

COPY dashboard/frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1 \
    API_BASE_URL=http://127.0.0.1:8000
RUN npm run build


FROM node:20-bookworm-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    nginx \
    openssh-client \
    python3 \
    python3-pip \
    python3-venv \
    tini \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./agent-requirements.txt
COPY dashboard/backend/requirements.txt ./dashboard-requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r agent-requirements.txt -r dashboard-requirements.txt

COPY dashboard/backend/ ./backend/
COPY src/ ./src/
COPY data/ ./data/

COPY --from=frontend-builder /build/.next/standalone ./frontend/
COPY --from=frontend-builder /build/.next/static ./frontend/.next/static/
COPY --from=frontend-builder /build/public ./frontend/public/

COPY dashboard/nginx.conf /etc/nginx/nginx.conf
COPY dashboard/start.sh /app/start.sh
RUN chmod +x /app/start.sh

VOLUME ["/data"]

ENV DB_PATH=/data/dashboard.db \
    AGENT_URL="" \
    LOCAL_AGENT_ENABLED=true \
    API_BASE_URL=http://127.0.0.1:8000 \
    NEXT_TELEMETRY_DISABLED=1 \
    PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app:/app/backend \
    PYTHONUNBUFFERED=1

EXPOSE 8080

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/start.sh"]
