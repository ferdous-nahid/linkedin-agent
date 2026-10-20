"""Tiny SQLite store: remembers what was already posted so topics never repeat."""
import json
import sqlite3
from datetime import datetime, timedelta, timezone

from .config import DB_FILE


def _conn():
    c = sqlite3.connect(DB_FILE)
    c.execute(
        """CREATE TABLE IF NOT EXISTS posts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TEXT, slot TEXT, url TEXT, title TEXT,
            topic TEXT, post_urn TEXT, payload TEXT)"""
    )
    return c


def used_urls(days=14):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _conn() as c:
        return {r[0] for r in c.execute("SELECT url FROM posts WHERE created_at > ?", (since,))}


def recent_topics(days=10):
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    with _conn() as c:
        return [r[0] for r in c.execute(
            "SELECT topic FROM posts WHERE created_at > ? ORDER BY id DESC", (since,))]


def record(slot, url, title, topic, post_urn, payload):
    with _conn() as c:
        c.execute(
            "INSERT INTO posts (created_at, slot, url, title, topic, post_urn, payload) VALUES (?,?,?,?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), slot, url, title, topic, post_urn,
             json.dumps(payload, ensure_ascii=False)),
        )


def last_posts(n=10):
    with _conn() as c:
        return list(c.execute(
            "SELECT created_at, slot, topic, post_urn FROM posts ORDER BY id DESC LIMIT ?", (n,)))


def recent_titles(hours=36):
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    with _conn() as c:
        return [r[0] for r in c.execute("SELECT title FROM posts WHERE created_at > ?", (since,))]
