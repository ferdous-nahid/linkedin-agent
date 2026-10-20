"""Entry point.

  python -m agent.main morning      # infographic post (scheduled 10:00)
  python -m agent.main afternoon    # carousel post   (scheduled 16:30)
  python -m agent.main preview      # build both, post nothing
  python -m agent.main auth         # connect LinkedIn (every ~60 days)
  python -m agent.main status       # health check
Flags: --now (don't wait for post time), --dry-run (build only)
"""
import argparse
import logging
import sys
import time
import traceback
from datetime import datetime
from logging.handlers import RotatingFileHandler
from zoneinfo import ZoneInfo

import requests

from . import config, db, linkedin, news, render, writer

log = logging.getLogger("agent")


def setup_logging():
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    fh = RotatingFileHandler(config.LOG_DIR / "agent.log", maxBytes=2_000_000, backupCount=5)
    fh.setFormatter(fmt)
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    root.handlers = [fh, sh]


def notify(text, photo=None):
    if not (config.TELEGRAM_BOT_TOKEN and config.TELEGRAM_CHAT_ID):
        return
    base = f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}"
    try:
        if photo:
            with open(photo, "rb") as f:
                requests.post(f"{base}/sendPhoto", timeout=60, files={"photo": f},
                              data={"chat_id": config.TELEGRAM_CHAT_ID, "caption": text[:1000]})
        else:
            requests.post(f"{base}/sendMessage", timeout=30,
                          data={"chat_id": config.TELEGRAM_CHAT_ID, "text": text[:4000]})
    except Exception as e:  # noqa: BLE001
        log.warning("telegram failed: %s", e)


def wait_until(hhmm):
    tz = ZoneInfo(config.TIMEZONE)
    now = datetime.now(tz)
    h, m = map(int, hhmm.split(":"))
    target = now.replace(hour=h, minute=m, second=0, microsecond=0)
    secs = (target - now).total_seconds()
    if 0 < secs < 3 * 3600:
        log.info("content ready, waiting %.0fs until %s", secs, hhmm)
        time.sleep(secs)


def _pick_with_text(ranked):
    """First ranked story whose article text we can actually read (keeps posts factual)."""
    best = None
    for s in ranked:
        text = news.article_text(s["url"], fallback="")
        if len(text) > 600:
            return s, text
        best = best or (s, f"{s['title']}. {s['summary']}")
    return best


def run_slot(slot, dry=False, now=False):
    stamp = datetime.now(ZoneInfo(config.TIMEZONE)).strftime("%Y%m%d")
    items = news.collect(max_age_hours=24 if slot == "afternoon" else 30)
    if not items:
        raise RuntimeError("No news items collected (all feeds failed?)")
    ranked = writer.rank(items, slot)
    story, text = _pick_with_text(ranked)
    log.info("selected: [%s] %s (%s)", story["niche"], story["title"], story["source"])

    if slot == "morning":
        d = writer.infographic(story, text)
        caption = writer.build_caption(d["caption"], story["source"])
        png = config.OUT_DIR / f"{stamp}-morning.png"
        render.render_png(render.infographic_html(d, story["source"]), png)
        artifact = png
    else:
        d = writer.carousel(story, text)
        caption = writer.build_caption(d["caption"], story["source"])
        pdf = config.OUT_DIR / f"{stamp}-carousel.pdf"
        preview = config.OUT_DIR / f"{stamp}-carousel-cover.png"
        render.render_pdf(render.carousel_html(d), pdf, preview)
        artifact = preview
    (config.OUT_DIR / f"{stamp}-{slot}-caption.txt").write_text(caption)
    log.info("caption:\n%s", caption)

    result = {"slot": slot, "caption": caption, "image": artifact,
              "file": png if slot == "morning" else pdf, "topic": d.get("topic", story["title"])}
    if dry or config.DRY_RUN:
        log.info("dry run: built %s, not posting", artifact)
        return result
    if not now:
        wait_until(config.MORNING_POST_AT if slot == "morning" else config.AFTERNOON_POST_AT)

    for attempt in range(3):
        try:
            if slot == "morning":
                urn = linkedin.post_image(caption, png, alt_text=f"{d['headline']}. {d['subhead']}")
            else:
                urn = linkedin.post_document(caption, pdf, title=d.get("doc_title") or d["topic"])
            break
        except Exception as e:  # noqa: BLE001
            log.warning("post attempt %d failed: %s", attempt + 1, e)
            if attempt == 2:
                raise
            time.sleep(30)
    db.record(slot, story["url"], story["title"], d.get("topic", story["title"]), urn, d)
    log.info("posted %s: %s", slot, urn)
    notify(f"Posted {slot}: {d.get('topic')}\n{urn}", photo=artifact)
    left = linkedin.days_left()
    if 0 <= left < 7:
        notify(f"LinkedIn token expires in {left:.0f} days. Run ./run.sh auth on the VPS.")
    result["urn"] = urn
    return result


def status():
    from . import llm
    print("LinkedIn token days left:", round(linkedin.days_left(), 1))
    try:
        print("LLM test:", llm.chat("Reply with one word.", "Say OK").strip()[:40])
    except Exception as e:  # noqa: BLE001
        print("LLM error:", e)
    items = news.collect()
    print("News items available:", len(items))
    for row in db.last_posts(5):
        print("posted:", row)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["morning", "afternoon", "preview", "auth", "status"])
    ap.add_argument("--now", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    setup_logging()
    if a.cmd == "auth":
        return linkedin.auth_interactive()
    if a.cmd == "status":
        return status()
    slots = ["morning", "afternoon"] if a.cmd == "preview" else [a.cmd]
    for slot in slots:
        try:
            run_slot(slot, dry=a.dry_run or a.cmd == "preview", now=a.now)
        except Exception as e:  # noqa: BLE001
            log.error("%s failed: %s\n%s", slot, e, traceback.format_exc())
            notify(f"LinkedIn agent {slot} FAILED: {e}")
            if a.cmd != "preview":
                sys.exit(1)


if __name__ == "__main__":
    main()
