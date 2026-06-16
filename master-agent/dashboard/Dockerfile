# Build context: master-agent/
# Command: docker build -f dashboard/Dockerfile -t <image> .

FROM node:20-bookworm-slim AS frontend-builder

WORKDIR /build

COPY dashboard/frontend/package*.json ./
RUN npm install

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
    python3 \
    python3-pip \
    python3-venv \
    tini \
    && rm -rf /var/lib/apt/lists/*

COPY dashboard/backend/requirements.txt ./backend-requirements.txt
RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r backend-requirements.txt

COPY main.py agent_runtime.py ./
COPY prompts/ ./prompts/

COPY --from=frontend-builder /build/.next/standalone ./frontend/
COPY --from=frontend-builder /build/.next/static ./frontend/.next/static/
COPY --from=frontend-builder /build/public ./frontend/public/

COPY dashboard/nginx.conf /etc/nginx/nginx.conf
COPY dashboard/start.sh /app/start.sh
RUN chmod +x /app/start.sh

ENV MONITORING_AGENT_URL="https://endpoint-dbd6717d-569f-413e-b9da-b63ceda13b22.agentbase-runtime.aiplatform.vngcloud.vn" \
    LOGGING_AGENT_URL="https://endpoint-c42c8f0b-6d74-42d5-9d6d-9fc7ce6b49e9.agentbase-runtime.aiplatform.vngcloud.vn" \
    SECURITY_AGENT_URL="https://endpoint-c73f7b5b-2611-4304-90bc-c503feb4af38.agentbase-runtime.aiplatform.vngcloud.vn" \
    API_BASE_URL=http://127.0.0.1:8000 \
    MASTER_LLM_SYNTHESIS_ENABLED=true \
    MASTER_LLM_TIMEOUT_SECONDS=60 \
    LLM_MODEL=minimax/minimax-m2.5 \
    LLM_BASE_URL=https://maas-llm-aiplatform-hcm.api.vngcloud.vn/v1 \
    NEXT_TELEMETRY_DISABLED=1 \
    PATH=/opt/venv/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1

EXPOSE 8080

ENTRYPOINT ["/usr/bin/tini", "--"]
CMD ["/app/start.sh"]
