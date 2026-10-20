#!/usr/bin/env bash
# Interactive key setup: paste each key when asked (input is hidden), then connects LinkedIn.
set -euo pipefail
ENV=/opt/linkedin-agent/.env
ask() { local v; read -r -s -p "$1: " v; echo; printf '%s' "$v"; }
echo "Paste each value and press Enter. Leave empty to keep the current value."
G=$(ask "GEMINI_API_KEY")
Q=$(ask "GROQ_API_KEY")
I=$(ask "LINKEDIN_CLIENT_ID")
S=$(ask "LINKEDIN_CLIENT_SECRET")
G="$G" Q="$Q" I="$I" S="$S" python3 - "$ENV" <<'PY'
import os, re, sys
p = sys.argv[1]; s = open(p).read()
for k, e in [("GEMINI_API_KEY", "G"), ("GROQ_API_KEY", "Q"),
             ("LINKEDIN_CLIENT_ID", "I"), ("LINKEDIN_CLIENT_SECRET", "S")]:
    v = os.environ[e].strip()
    if v:
        s = re.sub(rf"^{k}=.*$", lambda m: f"{k}={v}", s, flags=re.M)
open(p, "w").write(s)
print("Saved keys to .env")
PY
chown liagent:liagent "$ENV"; chmod 600 "$ENV"
echo; echo "Testing the AI model..."
/opt/linkedin-agent/run.sh status 2>&1 | grep -E "LLM|News|token" || true
echo; echo "Now connecting LinkedIn:"
/opt/linkedin-agent/run.sh auth
