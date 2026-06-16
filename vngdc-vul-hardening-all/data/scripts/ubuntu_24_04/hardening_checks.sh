#!/usr/bin/env bash
# Ubuntu 24.04 Security Hardening Check Script
# Outputs structured sections for AI analysis

PASS="[PASS]"
FAIL="[FAIL]"
WARN="[WARN]"
INFO="[INFO]"

sep() { echo ""; echo "=== $1 ==="; }

# ── 1. SSH Configuration ──────────────────────────────────────────────────────
sep "SSH CONFIGURATION"
sshd=/etc/ssh/sshd_config

check_ssh() {
  local key=$1 expected=$2
  val=$(grep -iE "^${key}" $sshd 2>/dev/null | awk '{print $2}')
  if [ "$val" = "$expected" ]; then
    echo "$PASS $key = $val"
  else
    echo "$FAIL $key = ${val:-not set} (expected: $expected)"
  fi
}

check_ssh PermitRootLogin no
check_ssh PasswordAuthentication no
check_ssh PubkeyAuthentication yes
check_ssh MaxAuthTries 3
check_ssh Protocol 2
check_ssh X11Forwarding no
check_ssh PermitEmptyPasswords no
check_ssh ClientAliveInterval 300
check_ssh LoginGraceTime 60

port=$(grep -iE "^Port" $sshd 2>/dev/null | awk '{print $2}')
echo "$INFO SSH Port: ${port:-22}"

# ── 2. Firewall (UFW) ─────────────────────────────────────────────────────────
sep "FIREWALL (UFW)"
if command -v ufw &>/dev/null; then
  ufw_status=$(ufw status 2>/dev/null | head -1)
  if echo "$ufw_status" | grep -q "active"; then
    echo "$PASS UFW is active"
    ufw status numbered 2>/dev/null | head -20
  else
    echo "$FAIL UFW is inactive"
  fi
else
  echo "$WARN UFW not installed"
  # Check iptables as fallback
  iptables -L INPUT --line-numbers 2>/dev/null | head -10 || echo "$INFO iptables: no rules or not available"
fi

# ── 3. Fail2ban ───────────────────────────────────────────────────────────────
sep "FAIL2BAN"
if systemctl is-active --quiet fail2ban 2>/dev/null; then
  echo "$PASS fail2ban is running"
  fail2ban-client status 2>/dev/null | head -5
else
  echo "$FAIL fail2ban is not running"
fi

# ── 4. User Accounts ──────────────────────────────────────────────────────────
sep "USER ACCOUNTS"
echo "$INFO Users with UID 0 (root-level):"
awk -F: '$3 == 0 {print "  " $1}' /etc/passwd

echo "$INFO Users with no password (!! or empty):"
awk -F: '($2 == "" || $2 == "!!") {print "  " $1 " [NO PASSWORD]"}' /etc/shadow 2>/dev/null || \
  echo "  (requires root to read /etc/shadow)"

echo "$INFO Users with login shell:"
awk -F: '$7 ~ /(bash|sh|zsh|fish)$/ {print "  " $1 " -> " $7}' /etc/passwd

echo "$INFO Sudo users:"
getent group sudo 2>/dev/null | cut -d: -f4 | tr ',' '\n' | sed 's/^/  /'
grep -rE "^%?(sudo|wheel|admin)" /etc/sudoers /etc/sudoers.d/ 2>/dev/null | head -10

# ── 5. Password Policy ────────────────────────────────────────────────────────
sep "PASSWORD POLICY"
if [ -f /etc/security/pwquality.conf ]; then
  grep -vE "^#|^$" /etc/security/pwquality.conf | head -15
else
  echo "$WARN /etc/security/pwquality.conf not found"
fi

echo "$INFO /etc/login.defs password aging:"
grep -E "^PASS_(MAX|MIN|WARN)" /etc/login.defs 2>/dev/null

# ── 6. Running Services ───────────────────────────────────────────────────────
sep "RUNNING SERVICES"
systemctl list-units --type=service --state=running --no-legend 2>/dev/null | awk '{print "  " $1}' | head -30

# ── 7. Open Ports ─────────────────────────────────────────────────────────────
sep "OPEN PORTS"
ss -tlnp 2>/dev/null | head -30 || netstat -tlnp 2>/dev/null | head -30

# ── 8. System Updates ─────────────────────────────────────────────────────────
sep "SYSTEM UPDATES"
updates=$(apt list --upgradable 2>/dev/null | grep -c upgradable || echo 0)
security_updates=$(apt list --upgradable 2>/dev/null | grep -c security || echo 0)
echo "$INFO Pending updates    : $updates"
echo "$INFO Security updates   : $security_updates"
if [ "$security_updates" -gt 0 ]; then
  echo "$FAIL Security updates available — apply immediately"
else
  echo "$PASS No pending security updates"
fi

# ── 9. Kernel Parameters (sysctl) ─────────────────────────────────────────────
sep "KERNEL PARAMETERS"

check_sysctl() {
  local key=$1 expected=$2
  val=$(sysctl -n "$key" 2>/dev/null)
  if [ "$val" = "$expected" ]; then
    echo "$PASS $key = $val"
  else
    echo "$FAIL $key = ${val:-not found} (expected: $expected)"
  fi
}

check_sysctl net.ipv4.ip_forward 0
check_sysctl net.ipv4.conf.all.accept_redirects 0
check_sysctl net.ipv4.conf.all.send_redirects 0
check_sysctl net.ipv4.conf.all.rp_filter 1
check_sysctl net.ipv4.tcp_syncookies 1
check_sysctl kernel.dmesg_restrict 1
check_sysctl kernel.randomize_va_space 2
check_sysctl fs.suid_dumpable 0

# ── 10. AppArmor ──────────────────────────────────────────────────────────────
sep "APPARMOR"
if command -v aa-status &>/dev/null; then
  aa_status=$(aa-status 2>/dev/null | head -5)
  echo "$aa_status"
  if aa-status 2>/dev/null | grep -q "enforce mode"; then
    echo "$PASS AppArmor has profiles in enforce mode"
  else
    echo "$WARN AppArmor profiles not in enforce mode"
  fi
else
  echo "$WARN AppArmor not installed"
fi

# ── 11. Auditd ────────────────────────────────────────────────────────────────
sep "AUDITD"
if systemctl is-active --quiet auditd 2>/dev/null; then
  echo "$PASS auditd is running"
  auditctl -l 2>/dev/null | head -10
else
  echo "$FAIL auditd is not running"
fi

# ── 12. SUID/SGID Files ───────────────────────────────────────────────────────
sep "SUID/SGID FILES"
echo "$INFO Non-standard SUID binaries:"
find /usr /bin /sbin -perm /4000 2>/dev/null | grep -vE "/(passwd|sudo|su|ping|mount|umount|newgrp|chsh|chfn|gpasswd|pkexec)$" | head -20

# ── 13. World-Writable Directories ────────────────────────────────────────────
sep "WORLD-WRITABLE DIRECTORIES"
find / -xdev -type d -perm -0002 -not -path "/proc/*" -not -path "/sys/*" -not -path "/dev/*" -not -path "/tmp" -not -path "/var/tmp" 2>/dev/null | head -10

# ── 14. Cron Jobs ─────────────────────────────────────────────────────────────
sep "CRON JOBS"
echo "$INFO System crontabs:"
ls -la /etc/cron* 2>/dev/null
cat /etc/crontab 2>/dev/null | grep -vE "^#|^$"
ls /etc/cron.d/ 2>/dev/null

echo "$INFO User cron jobs:"
for u in $(cut -d: -f1 /etc/passwd); do
  crontab -l -u "$u" 2>/dev/null | grep -vE "^#|^$" | sed "s/^/  [$u] /"
done

# ── 15. Log Configuration ─────────────────────────────────────────────────────
sep "LOGGING"
if systemctl is-active --quiet rsyslog 2>/dev/null || systemctl is-active --quiet syslog 2>/dev/null; then
  echo "$PASS syslog service is running"
else
  echo "$WARN No syslog service running"
fi

if systemctl is-active --quiet systemd-journald 2>/dev/null; then
  echo "$PASS journald is running"
  storage=$(grep -i "^Storage" /etc/systemd/journald.conf 2>/dev/null | cut -d= -f2)
  echo "$INFO Journal storage: ${storage:-auto}"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
sep "CHECK COMPLETE"
echo "Host       : $(hostname)"
echo "OS         : $(lsb_release -d 2>/dev/null | cut -f2 || cat /etc/os-release | grep PRETTY_NAME | cut -d= -f2)"
echo "Kernel     : $(uname -r)"
echo "Uptime     : $(uptime -p 2>/dev/null || uptime)"
echo "Timestamp  : $(date '+%Y-%m-%d %H:%M:%S %Z')"
