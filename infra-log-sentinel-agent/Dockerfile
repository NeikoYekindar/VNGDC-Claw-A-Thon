FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production
ENV APP_TIMEZONE=Asia/Ho_Chi_Minh
ENV LOG_SOURCE_MODE=runtime_folder
ENV LOG_ROOT_PATH=/app/data/logs
ENV REPORT_OUTPUT_DIR=/app/reports
ENV STATE_DB_PATH=/app/state/infra_log_sentinel.sqlite
ENV RUNTIME_LOG_BOOTSTRAP_ENABLED=true
ENV DEMO_LOG_BOOTSTRAP_COUNT=16
ENV DEMO_LOG_GENERATOR_ENABLED=true
ENV DEMO_LOG_INTERVAL_SECONDS=30
ENV DEMO_LOG_DOMAIN=all
ENV DEMO_LOG_SEVERITY=abnormal
ENV RUNTIME_SCHEDULER_ENABLED=false
ENV RUNTIME_SCHEDULER_DRY_RUN=true
ENV TELEGRAM_CHAT_ENABLED=false
ENV TELEGRAM_CHAT_POLL_INTERVAL_SECONDS=3
ENV TELEGRAM_CHAT_DRY_RUN=false

WORKDIR /app

RUN mkdir -p /app/data/logs /app/reports /app/state

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY infra_log_sentinel ./infra_log_sentinel
COPY pyproject.toml README.md ./

EXPOSE 8080

CMD ["python", "-m", "infra_log_sentinel.server"]
