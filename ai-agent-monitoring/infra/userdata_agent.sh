#!/bin/bash
# EC2 #2 — Agent/target server User Data
# Installs node_exporter + creates monitor user for SSH

set -e
exec > /var/log/userdata.log 2>&1

SSH_PASSWORD="quantc3101"
NE_VERSION="1.7.0"
ARCH="linux-amd64"

apt-get update -qq && apt-get install -y -qq curl wget tar stress-ng

# ── monitor user ─────────────────────────────────────────────────────────────
id "monitor" &>/dev/null || useradd -m -s /bin/bash monitor
echo "monitor:${SSH_PASSWORD}" | chpasswd

# Enable SSH password authentication
sed -i 's/^PasswordAuthentication no/PasswordAuthentication yes/' /etc/ssh/sshd_config
sed -i 's/^#PasswordAuthentication yes/PasswordAuthentication yes/' /etc/ssh/sshd_config
grep -q "^PasswordAuthentication" /etc/ssh/sshd_config || echo "PasswordAuthentication yes" >> /etc/ssh/sshd_config
# Ubuntu 24.04 uses "ssh" not "sshd"
systemctl restart ssh || systemctl restart sshd

# ── node_exporter ─────────────────────────────────────────────────────────────
cd /tmp
wget -q "https://github.com/prometheus/node_exporter/releases/download/v${NE_VERSION}/node_exporter-${NE_VERSION}.${ARCH}.tar.gz"
tar xf "node_exporter-${NE_VERSION}.${ARCH}.tar.gz"
cp "node_exporter-${NE_VERSION}.${ARCH}/node_exporter" /usr/local/bin/

id -u node_exporter &>/dev/null || useradd --no-create-home --shell /bin/false node_exporter

cat > /etc/systemd/system/node_exporter.service << 'EOF'
[Unit]
Description=Node Exporter
After=network.target

[Service]
User=node_exporter
ExecStart=/usr/local/bin/node_exporter --web.listen-address=0.0.0.0:9100
Restart=always

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable node_exporter
systemctl start node_exporter

echo "=== Agent server setup complete ==="
echo "node_exporter: http://$(curl -s ifconfig.me):9100/metrics"
echo "SSH: monitor@$(curl -s ifconfig.me)"
