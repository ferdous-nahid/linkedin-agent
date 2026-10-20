#!/usr/bin/env bash
# Stops and PERMANENTLY removes Hermes Agent and everything it was running on this VPS.
# Shows what it found first and asks you to type DELETE before touching anything.
set -uo pipefail
[ "$(id -u)" -eq 0 ] || { echo "Run as root: sudo bash $0"; exit 1; }

echo "== Scanning for Hermes Agent =="
HOMES="/root $(ls -d /home/* 2>/dev/null)"

# systemd units (system + per-user)
SYS_UNITS=$(systemctl list-unit-files --all --no-legend 2>/dev/null | awk '{print $1}' | grep -i hermes || true)
USER_UNITS=""
for h in $HOMES; do
  d="$h/.config/systemd/user"
  [ -d "$d" ] && USER_UNITS+=$(find "$d" -maxdepth 2 -iname '*hermes*' 2>/dev/null)$'\n'
done
UNIT_FILES=$(find /etc/systemd /lib/systemd /usr/lib/systemd -iname '*hermes*' 2>/dev/null || true)

# processes
PROCS=$(pgrep -fai hermes | grep -v -e wipe_old_agent -e pgrep || true)

# pm2 / docker / screen / tmux
PM2=$(command -v pm2 >/dev/null && pm2 jlist 2>/dev/null | grep -oiE '"name":"[^"]*hermes[^"]*"' || true)
DOCKER_C=$(command -v docker >/dev/null && docker ps -a --format '{{.ID}} {{.Names}} {{.Image}}' 2>/dev/null | grep -i hermes || true)
DOCKER_I=$(command -v docker >/dev/null && docker images --format '{{.ID}} {{.Repository}}:{{.Tag}}' 2>/dev/null | grep -i hermes || true)
SCREENS=$(command -v screen >/dev/null && screen -ls 2>/dev/null | grep -i hermes || true)
TMUXS=$(command -v tmux >/dev/null && tmux ls 2>/dev/null | grep -i hermes || true)

# crontab lines
CRON=""
for u in $(cut -d: -f1 /etc/passwd); do
  l=$(crontab -l -u "$u" 2>/dev/null | grep -i hermes || true)
  [ -n "$l" ] && CRON+="[$u] $l"$'\n'
done
CRON_FILES=$(grep -ril hermes /etc/cron* 2>/dev/null || true)

# files and folders
PATHS=""
for h in $HOMES; do
  for p in "$h/.hermes" "$h/.local/bin/hermes" "$h/hermes-agent" "$h/hermes"; do
    [ -e "$p" ] && PATHS+="$p"$'\n'
  done
done
PATHS+=$(find /opt /srv /var/www /root /home -maxdepth 3 -iname '*hermes*' \
         -not -path '*/linkedin-agent/*' 2>/dev/null | sort -u)$'\n'
for p in /usr/local/bin/hermes /usr/bin/hermes; do [ -e "$p" ] && PATHS+="$p"$'\n'; done
PATHS=$(echo "$PATHS" | sed '/^$/d' | sort -u)

show() { [ -n "$(echo "$2" | sed '/^$/d')" ] && { echo "--- $1"; echo "$2" | sed '/^$/d'; }; }
show "systemd units" "$SYS_UNITS"
show "systemd user units" "$USER_UNITS"
show "unit files" "$UNIT_FILES"
show "running processes" "$PROCS"
show "pm2 apps" "$PM2"
show "docker containers" "$DOCKER_C"
show "docker images" "$DOCKER_I"
show "screen sessions" "$SCREENS"
show "tmux sessions" "$TMUXS"
show "crontab lines" "$CRON"
show "cron files" "$CRON_FILES"
show "files/folders to delete" "$PATHS"

echo
echo "Everything listed above will be stopped and PERMANENTLY deleted (no backup)."
read -r -p "Type DELETE to continue: " ans
[ "$ans" = "DELETE" ] || { echo "Aborted. Nothing changed."; exit 0; }

echo "== Stopping =="
for u in $SYS_UNITS; do systemctl stop "$u" 2>/dev/null; systemctl disable "$u" 2>/dev/null; done
for h in $HOMES; do
  owner=$(stat -c %U "$h" 2>/dev/null)
  uid=$(id -u "$owner" 2>/dev/null) || continue
  for f in $(find "$h/.config/systemd/user" -maxdepth 2 -iname '*hermes*' 2>/dev/null); do
    n=$(basename "$f")
    sudo -u "$owner" XDG_RUNTIME_DIR=/run/user/$uid systemctl --user stop "$n" 2>/dev/null
    sudo -u "$owner" XDG_RUNTIME_DIR=/run/user/$uid systemctl --user disable "$n" 2>/dev/null
    rm -rf "$f"
  done
done
for f in $UNIT_FILES; do rm -rf "$f"; done
systemctl daemon-reload; systemctl reset-failed 2>/dev/null

if command -v pm2 >/dev/null; then
  for n in $(pm2 jlist 2>/dev/null | grep -oiE '"name":"[^"]*hermes[^"]*"' | cut -d'"' -f4); do
    pm2 delete "$n"; done; pm2 save --force >/dev/null 2>&1
fi
if command -v docker >/dev/null; then
  echo "$DOCKER_C" | awk 'NF{print $1}' | xargs -r docker rm -f
  echo "$DOCKER_I" | awk 'NF{print $1}' | xargs -r docker rmi -f
fi
command -v screen >/dev/null && screen -ls | grep -i hermes | awk '{print $1}' | xargs -r -I{} screen -S {} -X quit
command -v tmux >/dev/null && tmux ls 2>/dev/null | grep -i hermes | cut -d: -f1 | xargs -r -I{} tmux kill-session -t {}

for u in $(cut -d: -f1 /etc/passwd); do
  if crontab -l -u "$u" 2>/dev/null | grep -qi hermes; then
    crontab -l -u "$u" | grep -vi hermes | crontab -u "$u" -
  fi
done
for f in $CRON_FILES; do rm -f "$f"; done

# never kill this script or the shell that started it
SAFE=" $$ "; p=$$
while [ "$p" -gt 1 ] 2>/dev/null; do p=$(awk '{print $4}' /proc/$p/stat 2>/dev/null || echo 1); SAFE+="$p "; done
killh() { for pid in $(pgrep -fi hermes); do
  case "$SAFE" in *" $pid "*) continue;; esac
  # only kill processes that really are Hermes (not a shell that merely mentions the word)
  cmd=$(tr '\0' ' ' < /proc/$pid/cmdline 2>/dev/null)
  case "$cmd" in *hermes-agent*|*/.hermes/*|*"hermes gateway"*|*/bin/hermes*|hermes\ *|*python*hermes*|*node*hermes*) kill "$1" "$pid" 2>/dev/null;; esac
done; }
killh -TERM; sleep 2; killh -KILL

echo "== Deleting files =="
echo "$PATHS" | while read -r p; do [ -n "$p" ] && rm -rf -- "$p" && echo "removed $p"; done
# Remove Hermes PATH lines from shell rc files
for h in $HOMES; do
  for rc in "$h/.bashrc" "$h/.profile" "$h/.zshrc"; do
    [ -f "$rc" ] && sed -i '/hermes/Id' "$rc"
  done
done

echo
echo "== Verify =="
pgrep -fai hermes | grep -v wipe_old_agent || echo "No Hermes processes running."
systemctl list-units --all | grep -i hermes || echo "No Hermes systemd units."
echo "Hermes cleanup complete."
