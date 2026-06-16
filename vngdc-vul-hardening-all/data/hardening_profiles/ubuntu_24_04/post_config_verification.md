# Ubuntu Post-Configuration Verification Procedure

Purpose: verify the Ubuntu server after applying the configured hardening commands in `apply_hardening.sh`.

Scope:

- System package metadata and pending upgrades
- Required operational/security packages
- Timezone
- Sensitive system file ownership and permissions

Run the automated helper:

```bash
sudo bash data/hardening_profiles/ubuntu_24_04/verify_config_template.sh
```

When running on a target server outside the repo, copy the script first:

```bash
scp data/hardening_profiles/ubuntu_24_04/verify_config_template.sh user@server:/tmp/
ssh user@server 'sudo bash /tmp/verify_config_template.sh'
```

The script only reads system state. It does not change configuration.

## Expected Result

Treat these as failure conditions:

- Any required package is missing.
- Any package upgrade is still pending immediately after applying the baseline.
- Timezone is not `Asia/Ho_Chi_Minh`.
- Any sensitive file has different mode, owner, or group than expected.
- `/etc/security/opasswd` is missing after the baseline is applied.

Treat these as review conditions:

- APT metadata is older than 7 days. This can happen on long-running servers; refresh with `sudo apt update`.
- New package upgrades appear after the original hardening run because upstream repositories changed.

## Manual Verification Commands

### 1. System Updates

```bash
sudo apt update
apt list --upgradable
```

Expected:

- APT metadata can be refreshed successfully.
- `apt list --upgradable` returns no package rows immediately after `sudo apt upgrade -y`.

### 2. Required Packages

```bash
dpkg -s \
  curl wget vim nano tmux less tree file htop cron \
  iptables iptables-persistent libpam-radius-auth libpam-pwquality fail2ban openssh-server rsyslog \
  zip unzip tar gzip bzip2 \
  net-tools iproute2 iputils-ping traceroute dnsutils whois nmap socat tcpdump mtr ethtool \
  lsof sysstat iotop iftop ncdu parted smartmontools psmisc
```

Expected:

- Every listed package is installed.

### 3. Timezone

```bash
timedatectl
timedatectl show -p Timezone --value
```

Expected:

- Timezone is `Asia/Ho_Chi_Minh`.

### 4. Sensitive File Permissions

```bash
stat -c '%a %U:%G %n' \
  /etc/passwd /etc/passwd- /etc/group /etc/group- \
  /etc/shadow /etc/shadow- /etc/gshadow /etc/gshadow- \
  /etc/shells /etc/security/opasswd
```

Expected:

- `/etc/passwd`: `644 root:root`
- `/etc/passwd-`: `644 root:root`
- `/etc/group`: `644 root:root`
- `/etc/group-`: `644 root:root`
- `/etc/shadow`: `640 root:shadow`
- `/etc/shadow-`: `640 root:shadow`
- `/etc/gshadow`: `640 root:shadow`
- `/etc/gshadow-`: `640 root:shadow`
- `/etc/shells`: `644 root:root`
- `/etc/security/opasswd`: `600 root:root`
