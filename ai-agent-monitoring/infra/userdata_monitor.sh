#!/bin/bash
# EC2 #1 — Monitor server User Data
# Paste this into EC2 "User Data" when launching
# After boot: edit TARGET_EC2_IP in /etc/prometheus/prometheus.yml, then restart prometheus

set -e
exec > /var/log/userdata.log 2>&1

AGENT_ENDPOINT="https://endpoint-dbd6717d-569f-413e-b9da-b63ceda13b22.agentbase-runtime.aiplatform.vngcloud.vn"
PROM_VERSION="2.51.0"
AM_VERSION="0.27.0"
ARCH="linux-amd64"

apt-get update -qq && apt-get install -y -qq curl wget tar

id -u prometheus &>/dev/null || useradd --no-create-home --shell /bin/false prometheus

# ── Prometheus ───────────────────────────────────────────────────────────────
cd /tmp
wget -q "https://github.com/prometheus/prometheus/releases/download/v${PROM_VERSION}/prometheus-${PROM_VERSION}.${ARCH}.tar.gz"
tar xf "prometheus-${PROM_VERSION}.${ARCH}.tar.gz"
cp "prometheus-${PROM_VERSION}.${ARCH}/prometheus" /usr/local/bin/
cp "prometheus-${PROM_VERSION}.${ARCH}/promtool"   /usr/local/bin/
mkdir -p /etc/prometheus /var/lib/prometheus
cp -r "prometheus-${PROM_VERSION}.${ARCH}/consoles"           /etc/prometheus/
cp -r "prometheus-${PROM_VERSION}.${ARCH}/console_libraries"  /etc/prometheus/
chown -R prometheus:prometheus /etc/prometheus /var/lib/prometheus

# ── Alertmanager ─────────────────────────────────────────────────────────────
wget -q "https://github.com/prometheus/alertmanager/releases/download/v${AM_VERSION}/alertmanager-${AM_VERSION}.${ARCH}.tar.gz"
tar xf "alertmanager-${AM_VERSION}.${ARCH}.tar.gz"
cp "alertmanager-${AM_VERSION}.${ARCH}/alertmanager" /usr/local/bin/
cp "alertmanager-${AM_VERSION}.${ARCH}/amtool"       /usr/local/bin/
mkdir -p /etc/alertmanager /var/lib/alertmanager
chown -R prometheus:prometheus /etc/alertmanager /var/lib/alertmanager

# ── prometheus.yml ───────────────────────────────────────────────────────────
cat > /etc/prometheus/prometheus.yml << 'EOF'
global:
  scrape_interval: 15s
  evaluation_interval: 15s

alerting:
  alertmanagers:
    - static_configs:
        - targets: ['localhost:9093']

rule_files:
  - /etc/prometheus/alert_rules.yml

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']

  - job_name: 'node_exporter'
    static_configs:
      - targets:
          - 'TARGET_EC2_IP:9100'
        labels:
          instance: 'TARGET_EC2_IP'
          env: 'production'
          service: 'node'
EOF

# ── alert_rules.yml ──────────────────────────────────────────────────────────
cat > /etc/prometheus/alert_rules.yml << 'EOF'
groups:
  - name: resource_alerts
    interval: 15s
    rules:

      - alert: HighCPU
        expr: 100 - (avg by(instance) (rate(node_cpu_seconds_total{mode="idle"}[2m])) * 100) > 70
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "High CPU on {{ $labels.instance }}"
          description: "CPU usage is {{ $value | printf \"%.1f\" }}% on {{ $labels.instance }}"

      - alert: HighMemory
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 80
        for: 1m
        labels:
          severity: warning
        annotations:
          summary: "High Memory on {{ $labels.instance }}"
          description: "Memory usage is {{ $value | printf \"%.1f\" }}% on {{ $labels.instance }}"

      - alert: HighDisk
        expr: (1 - (node_filesystem_avail_bytes{mountpoint="/"} / node_filesystem_size_bytes{mountpoint="/"})) * 100 > 85
        for: 2m
        labels:
          severity: warning
        annotations:
          summary: "High Disk on {{ $labels.instance }}"
          description: "Disk usage is {{ $value | printf \"%.1f\" }}% on {{ $labels.instance }}"
EOF

# ── alertmanager.yml ─────────────────────────────────────────────────────────
cat > /etc/alertmanager/alertmanager.yml << EOF
global:
  resolve_timeout: 5m

route:
  group_by: ['alertname', 'instance']
  group_wait: 30s
  group_interval: 2m
  repeat_interval: 1h
  receiver: 'ai-agent'

receivers:
  - name: 'ai-agent'
    webhook_configs:
      - url: '${AGENT_ENDPOINT}/invocations'
        send_resolved: false
        http_config:
          tls_config:
            insecure_skip_verify: true
EOF

chown -R prometheus:prometheus /etc/prometheus /etc/alertmanager

# ── Systemd ──────────────────────────────────────────────────────────────────
cat > /etc/systemd/system/prometheus.service << 'EOF'
[Unit]
Description=Prometheus
After=network.target

[Service]
User=prometheus
ExecStart=/usr/local/bin/prometheus \
  --config.file=/etc/prometheus/prometheus.yml \
  --storage.tsdb.path=/var/lib/prometheus \
  --web.listen-address=0.0.0.0:9090
Restart=always

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/alertmanager.service << 'EOF'
[Unit]
Description=Alertmanager
After=network.target

[Service]
User=prometheus
ExecStart=/usr/local/bin/alertmanager \
  --config.file=/etc/alertmanager/alertmanager.yml \
  --storage.path=/var/lib/alertmanager \
  --web.listen-address=0.0.0.0:9093
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable prometheus alertmanager
systemctl start prometheus alertmanager

echo "=== Monitor server setup complete ==="
echo "Prometheus:   http://$(curl -s ifconfig.me):9090"
echo "Alertmanager: http://$(curl -s ifconfig.me):9093"
echo ""
echo "TODO: Replace TARGET_EC2_IP in /etc/prometheus/prometheus.yml"
echo "      then: systemctl restart prometheus"
