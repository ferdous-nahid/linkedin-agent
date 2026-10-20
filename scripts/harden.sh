#!/usr/bin/env bash
# Basic security hardening for a fresh Ubuntu/Debian VPS. Run as root AFTER a clean OS reinstall.
# - firewall: only SSH, HTTP, HTTPS open
# - fail2ban against SSH brute force
# - automatic security updates
# - password login disabled ONLY if an SSH key is already installed (so you can't lock yourself out)
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Run as root"; exit 1; }
export DEBIAN_FRONTEND=noninteractive

apt-get update -y && apt-get upgrade -y
apt-get install -y ufw fail2ban unattended-upgrades

ufw default deny incoming
ufw default allow outgoing
ufw allow OpenSSH
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable

cat > /etc/fail2ban/jail.local <<'EOF'
[sshd]
enabled = true
maxretry = 4
findtime = 10m
bantime = 24h
EOF
systemctl enable --now fail2ban
systemctl restart fail2ban
dpkg-reconfigure -f noninteractive unattended-upgrades

if [ -s /root/.ssh/authorized_keys ]; then
  mkdir -p /etc/ssh/sshd_config.d
  cat > /etc/ssh/sshd_config.d/99-hardening.conf <<'EOF'
PasswordAuthentication no
KbdInteractiveAuthentication no
PermitRootLogin prohibit-password
EOF
  systemctl restart ssh 2>/dev/null || systemctl restart sshd
  echo "Password login DISABLED. Use your SSH key from now on."
else
  echo "WARNING: no SSH key in /root/.ssh/authorized_keys, password login left ON."
  echo "Add your key first (Hostinger panel > Settings > SSH keys), then run this script again."
fi
echo "Hardening done."; ufw status
