#!/usr/bin/env bash
# Wrapper: ./run.sh morning|afternoon|preview|auth|status [--now] [--dry-run]
DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$DIR" || exit 1
export PLAYWRIGHT_BROWSERS_PATH="$DIR/.browsers"
if [ "$(id -un)" = "liagent" ]; then
  exec "$DIR/.venv/bin/python" -m agent.main "$@"
else
  exec sudo -u liagent PLAYWRIGHT_BROWSERS_PATH="$DIR/.browsers" "$DIR/.venv/bin/python" -m agent.main "$@"
fi
