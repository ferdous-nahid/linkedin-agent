"""Collects fresh stories from RSS feeds + Google News and extracts article text."""
import calendar
import html
import logging
import re
import time
from concurrent.futures import ThreadPoolExecutor
from difflib import SequenceMatcher

import feedparser
import requests

from . import db
from .sources import all_feeds

log = logging.getLogger("news")
UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")


def _clean(text, limit=600):
    text = html.unescape(re.sub(r"<[^>]+>", " ", text or ""))
    return re.sub(r"\s+", " ", text).strip()[:limit]


def _fetch_feed(item):
    niche, url = item
    try:
        r = requests.get(url, headers={"User-Agent": UA}, timeout=20)
        r.raise_for_status()
        feed = feedparser.parse(r.content)
    except Exception as e:  # noqa: BLE001
        log.warning("feed failed %s: %s", url, e)
        return []
    out = []
    for e in feed.entries[:40]:
        ts = e.get("published_parsed") or e.get("updated_parsed")
        if not ts:
            continue
        title = _clean(e.get("title", ""), 220)
        source = ""
        if "news.google.com" in url:
            # Google News titles look like "Headline - Publisher"
            src = e.get("source", {})
            source = src.get("title", "") if isinstance(src, dict) else ""
            if source and title.endswith(" - " + source):
                title = title[: -len(source) - 3]
        else:
            source = _clean(feed.feed.get("title", ""), 60)
        out.append({
            "niche": niche,
            "title": title,
            "summary": _clean(e.get("summary", "")),
            "url": e.get("link", ""),
            "source": source or "Industry news",
            "ts": calendar.timegm(ts),
        })
    return out


BLOCKED_SOURCES = {"at the races", "racing post", "espn", "sky sports", "bbc sport"}


def _overlap(a, b):
    """True when two headlines share most of their meaningful words (same story)."""
    wa = {w for w in a.split() if len(w) > 3}
    wb = {w for w in b.split() if len(w) > 3}
    return bool(wa and wb) and len(wa & wb) / min(len(wa), len(wb)) >= 0.5


def _norm(t):
    return re.sub(r"[^a-z0-9 ]", "", t.lower())


def collect(max_age_hours=24, min_items=12):
    """Return deduplicated recent stories, newest first."""
    with ThreadPoolExecutor(max_workers=12) as ex:
        items = [i for batch in ex.map(_fetch_feed, all_feeds()) for i in batch]
    log.info("fetched %d raw items", len(items))

    used = db.used_urls()
    posted = [_norm(t) for t in db.recent_titles()]
    now = time.time()
    result = []
    for hours in (max_age_hours, max_age_hours * 2, max_age_hours * 4):
        fresh = [i for i in items if now - i["ts"] <= hours * 3600
                 and i["url"] not in used and len(i["title"]) > 15
                 and i["source"].lower() not in BLOCKED_SOURCES
                 and not re.match(r"(replay|watch|live|horoscope)\b", i["title"], re.I)]
        fresh.sort(key=lambda i: i["ts"], reverse=True)
        result = []
        for it in fresh:
            n = _norm(it["title"])
            if any(SequenceMatcher(None, n, p).ratio() > 0.5 or _overlap(n, p) for p in posted):
                continue
            if any(SequenceMatcher(None, n, _norm(r["title"])).ratio() > 0.72 for r in result):
                continue
            result.append(it)
        if len(result) >= min_items:
            break
        log.info("only %d items within %dh, widening window", len(result), hours)
    return result


def article_text(url, fallback=""):
    """Best-effort full article text (keeps the writer grounded in real facts)."""
    try:
        import trafilatura
        r = requests.get(url, headers={"User-Agent": UA}, timeout=25, allow_redirects=True)
        if "news.google.com" in r.url:
            return fallback
        text = trafilatura.extract(r.text, include_comments=False, include_tables=False) or ""
        if len(text) > 400:
            return text[:7000]
    except Exception as e:  # noqa: BLE001
        log.warning("article fetch failed: %s", e)
    return fallback
