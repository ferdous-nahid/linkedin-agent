"""Picks the top story and writes the infographic / carousel content with the free LLM."""
import time
from datetime import datetime

from . import db, llm
from .sources import NICHES

STYLE = """Voice: a sharp, practical digital growth & marketing manager writing on LinkedIn for
business owners, marketers and real estate professionals (UK + global audience).
Rules:
- English only. Plain, confident, specific. Short sentences. No hype words ("game-changer",
  "revolutionary", "unlock", "delve", "in today's fast-paced world").
- Every fact, number, date and name must come from the provided source text. Never invent
  statistics. If the source has no number, leave stat fields empty.
- Explain WHY it matters and WHAT the reader should do. Be useful in 20 seconds of reading.
- Do not use em dashes. Do not use emojis inside the infographic/slide text."""


def _candidates_block(items):
    now = time.time()
    lines = []
    for i, it in enumerate(items):
        age = int((now - it["ts"]) / 3600)
        lines.append(f"[{i}] ({it['niche']}, {it['source']}, {age}h ago) {it['title']} :: "
                     f"{it['summary'][:260]}")
    return "\n".join(lines)


def rank(items, slot):
    niches = "\n".join(f"- {k}: {v}" for k, v in NICHES.items())
    recent = "; ".join(db.recent_topics()[:12]) or "none"
    if slot == "morning":
        goal = ("Pick the single most important update of the day for the morning INFOGRAPHIC. "
                "Priority: real impact on marketers/business owners/real estate marketers > "
                "official platform changes (Google, Meta, LinkedIn, GA4, GTM, privacy rules) > "
                "fresh data/research > actionability > broad interest.")
    else:
        goal = ("Pick the single hottest NICHE news story of the last 24 hours for an afternoon "
                "CAROUSEL that will drive the most engagement (comments, saves, shares). Prefer "
                "stories with a debate, a surprising implication, or a clear 'what this means "
                "for you' angle.")
    user = f"""Niches:
{niches}

Topics already posted recently (avoid repeating them): {recent}

Candidates:
{_candidates_block(items[:70])}

Task: {goal}
Ignore press-release fluff, local crime/politics, celebrity news, deals/coupons and listicles
without news value. Return JSON:
{{"ranked": [{{"id": <int>, "score": <1-100>, "why": "<short>"}}]}} with the best 5, best first."""
    data = llm.chat_json("You are a senior marketing news editor.", user, temperature=0.2)
    ids = [r["id"] for r in data.get("ranked", []) if isinstance(r.get("id"), int)
           and 0 <= r["id"] < len(items)]
    return [items[i] for i in ids] or items[:5]


def _today():
    return datetime.now().strftime("%d %b %Y")


def infographic(story, article):
    user = f"""Create a LinkedIn INFOGRAPHIC post about this story.

Niche: {story['niche']} | Source: {story['source']} | Date: {_today()}
Title: {story['title']}
Source text:
\"\"\"{article[:6500]}\"\"\"

Return JSON exactly in this shape:
{{
 "topic": "<3-6 word topic label for de-duplication>",
 "category_label": "<2-3 words in caps, e.g. TRACKING UPDATE, GROWTH UPDATE, REAL ESTATE MARKETING>",
 "headline": "<max 9 words, punchy, no clickbait>",
 "subhead": "<max 22 words: what happened, in plain English>",
 "stat": {{"value": "<a real number from the source like 38% or $2.1B, or empty>", "label": "<max 8 words or empty>"}},
 "points": [{{"title": "<2-5 words>", "text": "<max 16 words>"}}],
 "takeaway": "<max 18 words: the one thing to do now>",
 "caption": {{
   "hook": "<1 line, max 14 words, makes people stop scrolling>",
   "bullets": ["<4 to 6 bullets, each max 16 words, facts + why it matters>"],
   "action": "<1 line: what to do this week>",
   "question": "<1 short question to invite comments>",
   "hashtags": ["<3 to 5 relevant hashtags without #>"]
 }}
}}
"points" must have 4 to 6 items."""
    return llm.chat_json(STYLE, user, temperature=0.6)


ANGLES = [
    "What this means for you (practical impact)",
    "Myth vs reality",
    "Winners and losers",
    "Step-by-step: what to do now",
    "The hidden detail most people will miss",
    "Before vs after",
]


def carousel(story, article):
    user = f"""Create a LinkedIn PDF CAROUSEL about this single news story.

Niche: {story['niche']} | Source: {story['source']} | Date: {_today()}
Title: {story['title']}
Source text:
\"\"\"{article[:6500]}\"\"\"

First choose the angle that will engage this audience most, from: {"; ".join(ANGLES)}.
Then write 8 to 9 slides. Slide 1 is a scroll-stopping cover. Each content slide = ONE idea.
Last two slides: a recap and a call to action (follow + comment).

Return JSON exactly in this shape:
{{
 "topic": "<3-6 word topic label>",
 "angle": "<chosen angle>",
 "doc_title": "<max 8 words, shown on LinkedIn above the carousel>",
 "slides": [
   {{"type": "cover", "kicker": "<2-4 words caps>", "title": "<max 10 words>", "subtitle": "<max 14 words>"}},
   {{"type": "point", "heading": "<max 8 words>", "body": "<max 28 words>", "bullets": ["<0-3 bullets, max 10 words each>"]}},
   {{"type": "stat", "value": "<real number from source>", "label": "<max 12 words>", "body": "<max 20 words>"}},
   {{"type": "recap", "heading": "<max 6 words>", "items": ["<3-5 items, max 10 words each>"]}},
   {{"type": "cta", "heading": "<max 8 words>", "body": "<max 20 words>"}}
 ],
 "caption": {{
   "hook": "<1 line, max 14 words>",
   "bullets": ["<3 or 4 bullets, max 15 words each>"],
   "question": "<1 short question>",
   "hashtags": ["<3 to 5 hashtags without #>"]
 }}
}}
Use "stat" slides only when the source has a real number. Use mostly "point" slides."""
    return llm.chat_json(STYLE, user, temperature=0.7)


def build_caption(c, source_name, arrow="→"):
    parts = [c.get("hook", "").strip(), ""]
    parts += [f"{arrow} {b.strip()}" for b in c.get("bullets", [])[:6] if b.strip()]
    if c.get("action"):
        parts += ["", f"What to do: {c['action'].strip()}"]
    if c.get("question"):
        parts += ["", c["question"].strip()]
    parts += ["", f"Source: {source_name}"]
    tags = [t.strip().lstrip("#").replace(" ", "") for t in c.get("hashtags", [])[:5] if t.strip()]
    if tags:
        parts += ["", " ".join("#" + t for t in tags)]
    return "\n".join(parts).strip()[:2900]
