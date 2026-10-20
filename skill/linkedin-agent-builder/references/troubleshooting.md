# Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `401 Unauthorized` on `/oauth/v2/accessToken` | Client Secret wrong or empty. A common mix-up is pasting the Client ID (14 chars) into the secret | `awk -F= '/^LINKEDIN_CLIENT_SECRET/{print length($2)}' .env`. A real secret is 30+ chars and usually starts with `WPL_AP1.`. Re-run `setkeys.sh`, press Enter for the other fields and paste only the secret |
| OAuth code rejected (`invalid_grant`) | Code older than ~5 min, or already used | Run `run.sh auth` again and paste quickly |
| Allow button greys out and nothing happens | An embedded/automation browser cannot load `http://localhost` | Do the OAuth step in a normal desktop browser |
| `426` / "version" error from LinkedIn | `LinkedIn-Version` header expired | Leave `LINKEDIN_VERSION=auto`, or set a recent `YYYYMM` |
| Post text cut off after a `(` | Unescaped little-text characters | Always go through `linkedin.escape_little()` |
| Token expired | Member tokens last 60 days, and self-serve apps get no refresh token | `run.sh auth`. Telegram warns 7 days ahead |
| `All LLM providers failed` | Free-tier rate limit or a retired model | Check `run.sh status`. Keep both Gemini and Groq keys set. Force a model with `GEMINI_MODEL=<id>` if auto-pick fails |
| Gemini key page shows "Available regions" | Wrong Google account (e.g. a client's), or age not verified | Switch to the user's own account (`?authuser=N`) |
| "Failed to generate API key: request is suspicious" | Google bot detection on automated clicks | The user clicks Create key themselves |
| Groq "No cfToken" | Cloudflare CAPTCHA | The user ticks the CAPTCHA and submits |
| Irrelevant stories (sports replays etc.) | A Google News query matched loosely | Add the source to `BLOCKED_SOURCES` or adjust the query in `sources.py` |
| Morning and afternoon on the same story | Only possible in `preview` (nothing is recorded) | Production runs record to SQLite, and `news.collect()` excludes similar titles from the last 36 h |
| Text overflows into the footer | Content longer than the layout allows | The fit-to-canvas JS shrinks it to 55% at most. Shorten the word limits in the `writer.py` prompts if it still overflows |
| `read -s` in a pasted block swallowed the next line | `read` consumes the following pasted line as its input | Run `read -rsp "Token: " T; echo` alone, then paste the rest. Check with `echo ${#T}` |
| Telegram "Chat ID not found" | Bot never received a message | Open the bot, press Start, send "hi", then retry |
| Bot answers `/help` to the first command after a restart | Messages sent while the bot was offline are skipped on purpose | Send the command again |
| `scp: local mkdir ... Invalid argument` (Windows) | Quoted destination path ends with `\` | Drop the trailing backslash |
| `The token '&&' is not a valid statement separator` | Bash command typed into PowerShell | Wrap it: `ssh root@HOST "cmd1 && cmd2"` |

## Telegram connect snippet (run on the server, in two parts)

Part 1 — its own command:
```bash
read -rsp "Telegram bot token: " T; echo
```

Part 2:
```bash
C=$(curl -s "https://api.telegram.org/bot$T/getUpdates" | python3 -c "import sys,json;d=json.load(sys.stdin);r=d.get('result',[]);print(r[-1]['message']['chat']['id'] if r else 'ERR:'+str(d.get('description','no messages')))")
case "$C" in ERR:*) echo "Problem: $C";; *)
T="$T" C="$C" python3 -c "
import os,re;p='/opt/linkedin-agent/.env';s=open(p).read()
s=re.sub(r'^TELEGRAM_BOT_TOKEN=.*$','TELEGRAM_BOT_TOKEN='+os.environ['T'],s,flags=re.M)
s=re.sub(r'^TELEGRAM_CHAT_ID=.*$','TELEGRAM_CHAT_ID='+os.environ['C'],s,flags=re.M)
open(p,'w').write(s)"
chown liagent: /opt/linkedin-agent/.env
systemctl enable --now linkedin-telegram && echo "Telegram connected (chat id $C)";; esac
```

## Security notes
- The old agent's public dashboard on `0.0.0.0` was the likely malware entry point in the reference deployment. Never expose agent dashboards without auth, and prefer binding to `127.0.0.1`.
- `.env` is `chmod 600` and owned by `liagent`. The agent runs as an unprivileged system user.
- Keys, passwords and OAuth secrets are entered by the user through hidden prompts, never typed by the assistant and never pasted into chat.
- Back-up archives contain DB passwords and sGTM container config. Delete them from the server once downloaded.
