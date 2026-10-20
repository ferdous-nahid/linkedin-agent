#!/usr/bin/env bash
# Installs the LinkedIn agent to /opt/linkedin-agent and schedules it with systemd timers.
# Usage (from the unzipped folder):  sudo bash scripts/install.sh
set -euo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Run as root: sudo bash $0"; exit 1; }

SRC="$(cd "$(dirname "$0")/.." && pwd)"
DST=/opt/linkedin-agent
USR=liagent

echo "== System packages =="
export DEBIAN_FRONTEND=noninteractive
apt-get update -y
apt-get install -y python3 python3-venv python3-pip rsync fonts-dejavu-core fonts-noto-core
apt-get install -y fonts-inter 2>/dev/null || echo "(fonts-inter not in this distro, using fallback fonts)"

echo "== User and files =="
id "$USR" >/dev/null 2>&1 || useradd --system --create-home --home-dir "$DST" --shell /usr/sbin/nologin "$USR"
mkdir -p "$DST"
rsync -a --exclude '.venv' --exclude 'data' --exclude 'output' --exclude 'logs' --exclude '.env' --exclude '.git' --exclude 'docs' --exclude 'skill' "$SRC/" "$DST/"
[ -f "$DST/.env" ] || cp "$DST/.env.example" "$DST/.env"
chmod 600 "$DST/.env"
chown -R "$USR:$USR" "$DST"
chmod +x "$DST/run.sh"

echo "== Python env + Chromium =="
sudo -u "$USR" python3 -m venv "$DST/.venv"
sudo -u "$USR" "$DST/.venv/bin/pip" install -q --upgrade pip
sudo -u "$USR" "$DST/.venv/bin/pip" install -q -r "$DST/requirements.txt"
"$DST/.venv/bin/python" -m playwright install-deps chromium
sudo -u "$USR" PLAYWRIGHT_BROWSERS_PATH="$DST/.browsers" "$DST/.venv/bin/python" -m playwright install chromium

echo "== systemd timers (Asia/Dhaka) =="
cp "$DST"/systemd/*.service "$DST"/systemd/*.timer /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now linkedin-morning.timer linkedin-afternoon.timer

echo
echo "Installed. Next steps:"
echo "  1) nano $DST/.env            (add GEMINI_API_KEY, GROQ_API_KEY, LinkedIn app keys)"
echo "  2) $DST/run.sh auth          (connect your LinkedIn profile)"
echo "  3) $DST/run.sh preview       (build today's posts without publishing)"
echo "  4) $DST/run.sh status        (health check)"
systemctl list-timers 'linkedin-*' --no-pager
