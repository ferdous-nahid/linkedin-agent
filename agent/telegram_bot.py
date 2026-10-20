"""Telegram control bot (long polling). Answers ONLY the chat id configured in .env.

Commands:
  /preview          build today's infographic + carousel now and send them here (nothing is posted)
  /post_morning     build and publish the infographic to LinkedIn right now
  /post_afternoon   build and publish the carousel to LinkedIn right now
  /status           LinkedIn token, last posts, next scheduled runs
  /help             this list
"""
import logging
import subprocess
import threading
import time

import requests

from . import config, db, linkedin
from .main import run_slot, setup_logging

log = logging.getLogger("tgbot")
API = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
CHAT = str(config.TELEGRAM_CHAT_ID)
_busy = threading.Lock()

HELP = ("LinkedIn Agent commands:\n"
        "/preview - build today's 2 posts and send them here (not posted)\n"
        "/post_morning - publish the infographic now\n"
        "/post_afternoon - publish the carousel now\n"
        "/status - token, last posts, next runs\n"
        "/help - this list\n\n"
        "Auto schedule: 10:00 infographic, 16:30 carousel (Dhaka).")


def send(text):
    requests.post(f"{API}/sendMessage", timeout=30, data={"chat_id": CHAT, "text": text[:4000]})


def send_file(path, method, field, caption=""):
    with open(path, "rb") as f:
        requests.post(f"{API}/{method}", timeout=120, files={field: f},
                      data={"chat_id": CHAT, "caption": caption[:1000]})


def deliver(res, posted=False):
    label = "Infographic" if res["slot"] == "morning" else "Carousel"
    head = f"{label} {'POSTED to LinkedIn' if posted else 'preview'}: {res['topic']}"
    if res["slot"] == "morning":
        send_file(res["file"], "sendPhoto", "photo", head)
    else:
        send_file(res["image"], "sendPhoto", "photo", head)
        send_file(res["file"], "sendDocument", "document", "Full carousel PDF")
    send("Caption:\n\n" + res["caption"])


def job(slots, publish):
    if not _busy.acquire(blocking=False):
        send("Already working on a post, please wait a minute.")
        return
    try:
        for slot in slots:
            send(f"Working on the {'infographic' if slot == 'morning' else 'carousel'}... (2-3 min)")
            try:
                res = run_slot(slot, dry=not publish, now=True)
                deliver(res, posted=publish)
            except Exception as e:  # noqa: BLE001
                log.exception("job failed")
                send(f"Failed ({slot}): {e}")
    finally:
        _busy.release()


def status():
    lines = [f"LinkedIn token: {linkedin.days_left():.0f} days left"]
    for created, slot, topic, urn in db.last_posts(5):
        lines.append(f"- {created[:16]} {slot}: {topic}")
    try:
        t = subprocess.run(["systemctl", "list-timers", "linkedin-*", "--no-pager"],
                           capture_output=True, text=True, timeout=10).stdout
        lines += ["", "Next runs (UTC):"] + [l[:40] for l in t.splitlines()[1:3]]
    except Exception:  # noqa: BLE001
        pass
    send("\n".join(lines))


def handle(text):
    cmd = text.strip().split()[0].lower().split("@")[0] if text.strip() else ""
    if cmd == "/preview":
        threading.Thread(target=job, args=(["morning", "afternoon"], False), daemon=True).start()
    elif cmd == "/post_morning":
        threading.Thread(target=job, args=(["morning"], True), daemon=True).start()
    elif cmd == "/post_afternoon":
        threading.Thread(target=job, args=(["afternoon"], True), daemon=True).start()
    elif cmd == "/status":
        status()
    else:
        send(HELP)


def main():
    setup_logging()
    if not (config.TELEGRAM_BOT_TOKEN and CHAT):
        raise SystemExit("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID missing in .env")
    requests.post(f"{API}/setMyCommands", timeout=30, json={"commands": [
        {"command": "preview", "description": "Build today's posts and send here"},
        {"command": "post_morning", "description": "Publish the infographic now"},
        {"command": "post_afternoon", "description": "Publish the carousel now"},
        {"command": "status", "description": "Token, last posts, next runs"},
        {"command": "help", "description": "Show commands"}]})
    offset = None
    # skip messages sent while the bot was offline
    try:
        old = requests.get(f"{API}/getUpdates", timeout=30).json().get("result", [])
        if old:
            offset = old[-1]["update_id"] + 1
    except Exception:  # noqa: BLE001
        pass
    log.info("telegram bot running")
    while True:
        try:
            r = requests.get(f"{API}/getUpdates", timeout=60,
                             params={"timeout": 50, "offset": offset}).json()
            for u in r.get("result", []):
                offset = u["update_id"] + 1
                msg = u.get("message") or {}
                if str(msg.get("chat", {}).get("id")) != CHAT:
                    continue  # ignore strangers
                handle(msg.get("text", ""))
        except Exception as e:  # noqa: BLE001
            log.warning("poll error: %s", e)
            time.sleep(5)


if __name__ == "__main__":
    main()
