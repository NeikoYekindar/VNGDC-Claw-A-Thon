#!/usr/bin/env bash
set -u

PASS="[PASS]"
FAIL="[FAIL]"
WARN="[WARN]"
INFO="[INFO]"

sep() { echo ""; echo "=== $1 ==="; }
pass() { echo "$PASS $*"; }
fail() { echo "$FAIL $*"; }
warn() { echo "$WARN $*"; }
info() { echo "$INFO $*"; }

has_cmd() { command -v "$1" >/dev/null 2>&1; }

check_pkg() {
  local pkg="$1"
  if dpkg -s "$pkg" >/dev/null 2>&1; then
    pass "package installed: $pkg"
  else
    fail "package missing: $pkg"
  fi
}

check_recent_apt_metadata() {
  if find /var/lib/apt/lists -type f -name '*_InRelease' -mtime -7 2>/dev/null | grep -q .; then
    pass "apt metadata refreshed within 7 days"
  else
    warn "apt metadata was not refreshed within 7 days or cannot be verified"
  fi
}

check_pending_upgrades() {
  if ! has_cmd apt; then
    fail "apt command missing"
    return
  fi

  local count
  count=$(apt list --upgradable 2>/dev/null | awk 'NR > 1 { count++ } END { print count + 0 }')
  if [ "$count" = "0" ]; then
    pass "no upgradable packages pending"
  else
    fail "$count upgradable package(s) pending; run sudo apt update && sudo apt upgrade -y"
  fi
}

check_timezone() {
  local expected="Asia/Ho_Chi_Minh"
  local actual=""

  if has_cmd timedatectl; then
    actual=$(timedatectl show -p Timezone --value 2>/dev/null || true)
  fi

  if [ "$actual" = "$expected" ]; then
    pass "timezone $expected"
  else
    fail "timezone ${actual:-unknown} expected $expected"
  fi
}

check_stat_required() {
  local path="$1" mode="$2" owner="$3" group="$4"
  if [ ! -e "$path" ]; then
    fail "$path missing expected $mode $owner:$group"
    return
  fi

  local actual_mode actual_owner actual_group
  actual_mode=$(stat -c "%a" "$path")
  actual_owner=$(stat -c "%U" "$path")
  actual_group=$(stat -c "%G" "$path")

  if [ "$actual_mode" = "$mode" ] && [ "$actual_owner" = "$owner" ] && [ "$actual_group" = "$group" ]; then
    pass "$path permission $mode $owner:$group"
  else
    fail "$path permission ${actual_mode} ${actual_owner}:${actual_group} expected $mode $owner:$group"
  fi
}

sep "SYSTEM UPDATES"
check_recent_apt_metadata
check_pending_upgrades

sep "REQUIRED PACKAGES"
required_packages=(
  curl wget vim nano tmux less tree file htop cron
  iptables iptables-persistent libpam-radius-auth libpam-pwquality fail2ban openssh-server rsyslog
  zip unzip tar gzip bzip2
  net-tools iproute2 iputils-ping traceroute dnsutils whois nmap socat tcpdump mtr ethtool
  lsof sysstat iotop iftop ncdu parted smartmontools psmisc
)

for pkg in "${required_packages[@]}"; do
  check_pkg "$pkg"
done

sep "TIMEZONE"
check_timezone

sep "SENSITIVE FILE PERMISSIONS"
check_stat_required /etc/passwd 644 root root
check_stat_required /etc/passwd- 644 root root
check_stat_required /etc/group 644 root root
check_stat_required /etc/group- 644 root root
check_stat_required /etc/shadow 640 root shadow
check_stat_required /etc/shadow- 640 root shadow
check_stat_required /etc/gshadow 640 root shadow
check_stat_required /etc/gshadow- 640 root shadow
check_stat_required /etc/shells 644 root root
check_stat_required /etc/security/opasswd 600 root root

sep "CHECK COMPLETE"
info "Host: $(hostname)"
info "Timestamp: $(date '+%Y-%m-%d %H:%M:%S %Z')"
