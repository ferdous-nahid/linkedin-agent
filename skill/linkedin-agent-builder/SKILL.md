---
name: linkedin-agent-builder
description: Build, deploy and operate a free-model LinkedIn auto-posting agent on a Linux VPS — scrapes daily marketing/tracking, business-growth and real-estate news, posts a morning infographic and an afternoon PDF carousel to a personal profile, with Telegram control. Use when asked to set up, rebuild, migrate, fix or extend this agent.
---

# LinkedIn Agent Builder

Builds a self-hosted agent that, every day:

| Local time | Post | What it does |
|---|---|---|
| 09:45 start → **10:00 publish** | Infographic (PNG, 1080×1350) + short bullet caption | Picks the single most important update across all niches |
| 16:15 start → **16:30 publish** | PDF carousel (8–9 slides) + short caption | Picks the hottest niche story of the last 24 h (never the morning story), written from the most engaging angle |

Everything runs on free tiers: Gemini (primary) → Groq → OpenRouter `:free` (fallbacks), RSS + Google News for sources, headless Chromium for rendering, LinkedIn "Share on LinkedIn" product for posting, Telegram Bot API for alerts and remote control.

The complete, tested source lives in the repository root (`agent/`, `scripts/`, `systemd/`), two levels above this file. Copy it as-is; customise only `.env` and `agent/sources.py`.

## Architecture

```
systemd timer ─▶ agent.main <slot>
   news.collect()      RSS + Google News → dedupe → drop blocked sources & already-posted stories
   writer.rank()       LLM scores candidates → top 5
   _pick_with_text()   first story whose full article can be extracted (keeps facts grounded)
   writer.infographic() / writer.carousel()   LLM → strict JSON
   render.*            HTML template → Playwright → PNG / multi-page PDF (auto shrink-to-fit)
   wait_until(post time)
   linkedin.post_image() / post_document()   Images/Documents API → Posts API
   db.record()         SQLite history (no repeats)
   notify()            Telegram photo + link
agent.telegram_bot (always-on service) ─▶ /preview /post_morning /post_afternoon /status /help
```

| File | Role |
|---|---|
| `agent/config.py` | Reads `.env`; paths; brand; schedule |
| `agent/sources.py` | Niches, direct RSS feeds, Google News queries |
| `agent/news.py` | Fetch, dedupe, filters (`BLOCKED_SOURCES`, same-story check vs last 36 h), article extraction (trafilatura) |
| `agent/llm.py` | OpenAI-compatible client, provider fallback, `auto` model discovery, robust JSON parsing |
| `agent/writer.py` | Ranking + content prompts, caption builder |
| `agent/render.py` | Infographic + carousel HTML/CSS, Playwright rendering |
| `agent/linkedin.py` | OAuth (manual paste flow), version auto-detect, uploads, "little" text escaping |
| `agent/telegram_bot.py` | Long-polling command bot, answers only the configured chat id |
| `scripts/install.sh` | apt deps, `liagent` user, venv, Chromium, systemd timers |
| `scripts/setkeys.sh` | Hidden-input key prompts → `.env`, LLM test, then LinkedIn auth |
| `scripts/wipe_old_agent.sh` | Finds and (after typing DELETE) removes an old agent (default pattern: Hermes) |
| `scripts/harden.sh` | ufw, fail2ban, unattended upgrades, key-only SSH if a key exists |

## Procedure

### 0. Ask first (one round)
- Post times and timezone (default 10:00 / 16:30 Asia/Dhaka).
- Personal profile (free, `w_member_social`) or company page (needs Community Management API approval — slow).
- Post language (default English) and brand name/title shown on images.
- What to do with any old agent on the server: back up or delete outright.

### 1. Inspect the server before touching it
Run read-only discovery and show the user the result:
```bash
docker ps -a --format '{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}'
ss -tlnp; ls /opt /root; crontab -l; ls /etc/cron.d
ps aux --sort=-%cpu | head
```
- Look for publicly exposed admin dashboards (`0.0.0.0:<port>`), unknown cron jobs, high-CPU processes, `authorized_keys` changes.
- If the host flagged malware: snapshot first, stop the suspect service, back up sites (`mysqldump` from the DB container, `wp-content`, compose dirs, `docker inspect` of every container for env/config, `docker save` of locally built images), let the user download the backup with `scp`, then decide reinstall vs clean-up together.
- Never delete or stop workloads without explicit confirmation of the exact list.

### 2. Remove the old agent (if requested)
```bash
sudo bash scripts/wipe_old_agent.sh     # lists everything, requires typing DELETE
```
Edit the `hermes` pattern inside the script for a different agent name.

### 3. Install
Upload the template (from the user's PC: `scp agent.zip root@HOST:/root/`), then:
```bash
unzip agent.zip && cd linkedin-agent && sudo bash scripts/install.sh
```
Verify on the server (no keys needed):
```bash
cd /opt/linkedin-agent && sudo -u liagent PLAYWRIGHT_BROWSERS_PATH=$PWD/.browsers .venv/bin/python -c \
"import logging; logging.disable(logging.WARNING); from agent import news, render; i=news.collect(30); print('ITEMS', len(i)); render.render_png('<p>ok</p>', '/tmp/t.png'); print('RENDER_OK')"
```
Expect 80+ items. Remove any irrelevant source that shows up (add to `BLOCKED_SOURCES`).

### 4. Accounts and keys (the user does the secret parts)
- **Gemini:** aistudio.google.com/apikey → Create API key. Use the user's own Google account, not a client's.
- **Groq:** console.groq.com/keys → Create API Key (Cloudflare CAPTCHA, so the user clicks).
- **LinkedIn app:** linkedin.com/developers/apps → Create app.
  - App name must not contain "LinkedIn".
  - Link a company page the user manages, then upload a logo.
  - Products: request **Share on LinkedIn** and **Sign In with LinkedIn using OpenID Connect**.
  - Auth tab: add the redirect URL `http://localhost:8765/callback`.
  - Confirm the scopes include `openid profile w_member_social`.
- Accepting API terms needs the user's explicit OK. Creating keys may hit bot checks, and a CAPTCHA is always the user's to solve.

The assistant never types API keys, secrets or passwords into the server. The user runs:
```bash
bash /opt/linkedin-agent/setkeys.sh
```
Run it alone, never inside a pasted multi-line block. Paste each value and press Enter; an empty Enter keeps the current value. The script tests the LLM, then starts the LinkedIn OAuth flow:
1. Open the printed URL in a normal desktop browser (not an embedded/automation browser, which cannot load `localhost`).
2. Click Allow.
3. On the "can't reach this page" screen, copy the full address bar and paste it into the terminal within about 5 minutes.
4. Success prints `Connected as <name> (urn:li:person:...)`.

### 5. Preview
```bash
/opt/linkedin-agent/run.sh preview      # builds both posts, publishes nothing
```
Check the outputs (`/opt/linkedin-agent/output/`):
- Facts and numbers must match the source.
- No text overflowing into the footer.
- Captions short and bulleted.

### 6. Telegram (optional, recommended)
1. In @BotFather, send `/newbot` and copy the token.
2. Open the bot, press Start and send "hi".
3. On the server, read the token in its own command, then fetch the chat id with `getUpdates` and write `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` into `.env` (see `references/troubleshooting.md` for the exact snippet).
4. Enable the bot: `systemctl enable --now linkedin-telegram`.

Commands:

| Command | Action |
|---|---|
| `/preview` | Build both posts and send them to Telegram (nothing published) |
| `/post_morning` | Build and publish the infographic now |
| `/post_afternoon` | Build and publish the carousel now |
| `/status` | Token days left, last posts, next runs |

The bot ignores every chat except the configured one.

### 7. Hand-over checklist
- `systemctl list-timers 'linkedin-*'` shows both timers. Check that the UTC times equal the local post time minus 15 minutes.
- `run.sh status` shows: LLM OK, items > 0, token ~60 days.
- Remind the user:
  - The LinkedIn token expires every 60 days; run `run.sh auth` again.
  - Rotate any key that was pasted into a chat.
  - Reboot if the server reports "System restart required".

## Customising
- **Niches/sources:** edit `NICHES`, `DIRECT_FEEDS` and `GOOGLE_NEWS_QUERIES` in `agent/sources.py`. Broken feeds are skipped automatically.
- **Voice/rules:** `STYLE` and the prompts in `agent/writer.py`. Keep the "never invent statistics" rule.
- **Look:** `BRAND_*` in `.env`. The layout lives in `agent/render.py`, and its fit-to-canvas JS shrinks text when content is long.
- **Times:** `MORNING_POST_AT`/`AFTERNOON_POST_AT` in `.env` **and** `OnCalendar` in `/etc/systemd/system/linkedin-*.timer` (keep the timer about 15 min earlier), then `systemctl daemon-reload`.

## Rules learned the hard way
See `references/troubleshooting.md` for symptoms and fixes. The essentials:
1. Escape LinkedIn "little" text (`\ | { } @ [ ] ( ) < > # * _ ~`) and send hashtags as `{hashtag|\#|Tag}`. Unescaped parentheses silently truncate posts.
2. Send `LinkedIn-Version` as `YYYYMM`. Versions expire, so the code tries the last 12 months automatically.
3. Free model names change often. `MODEL=auto` lists the provider's models and picks the newest non-preview Flash (Gemini) or a large Groq model.
4. Ground every post in the extracted article text. If no article text is readable, fall back to the next ranked story.
5. Dedupe across slots: the afternoon run must exclude stories similar to anything posted in the last 36 h. Use URL, fuzzy title and keyword overlap.
6. Windows users: PowerShell is not bash. Remote commands go through `ssh HOST "cmd && cmd"`. Quote paths that contain spaces, and never end a quoted Windows path with `\`.
