#!/usr/bin/env bash
set -euo pipefail

# Ubuntu 24.04 baseline commands configured for this hardening profile.
# Review before running on production. The agent does not execute this file
# automatically during checks.

export DEBIAN_FRONTEND=noninteractive

sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get update
sudo apt-get install -y \
  curl wget vim nano tmux less tree file htop cron \
  iptables iptables-persistent libpam-radius-auth libpam-pwquality fail2ban openssh-server rsyslog \
  zip unzip tar gzip bzip2 \
  net-tools iproute2 iputils-ping traceroute dnsutils whois nmap socat tcpdump mtr ethtool \
  lsof sysstat iotop iftop ncdu parted smartmontools psmisc

sudo timedatectl set-timezone Asia/Ho_Chi_Minh

sudo chmod 644 /etc/passwd
sudo chown root:root /etc/passwd

sudo chmod 644 /etc/passwd-
sudo chown root:root /etc/passwd-

sudo chmod 644 /etc/group
sudo chown root:root /etc/group

sudo chmod 644 /etc/group-
sudo chown root:root /etc/group-

sudo chmod 640 /etc/shadow
sudo chown root:shadow /etc/shadow

sudo chmod 640 /etc/shadow-
sudo chown root:shadow /etc/shadow-

sudo chmod 640 /etc/gshadow
sudo chown root:shadow /etc/gshadow

sudo chmod 640 /etc/gshadow-
sudo chown root:shadow /etc/gshadow-

sudo chmod 644 /etc/shells
sudo chown root:root /etc/shells

sudo touch /etc/security/opasswd
sudo chmod 600 /etc/security/opasswd
sudo chown root:root /etc/security/opasswd
