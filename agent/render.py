"""Renders the infographic (PNG) and carousel (PDF) from HTML with headless Chromium."""
from datetime import datetime
from html import escape as e

from playwright.sync_api import sync_playwright

from . import config

W, H = 1080, 1350


def _initials(name):
    parts = [p for p in name.replace(".", " ").split() if p[0].isalpha()]
    return (parts[0][0] + parts[-1][0]).upper() if len(parts) > 1 else name[:2].upper()


BASE_CSS = f"""
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
:root {{ --a: {config.BRAND_ACCENT}; --b: {config.BRAND_ACCENT_2}; --ink: #F8FAFC;
        --muted: #A5B4CC; --card: rgba(255,255,255,0.055); --line: rgba(255,255,255,0.10); }}
html, body {{ background: #0A1020; }}
body {{ font-family: 'Inter', 'Noto Sans', 'DejaVu Sans', sans-serif; color: var(--ink);
       -webkit-font-smoothing: antialiased; }}
.canvas {{ width: {W}px; height: {H}px; position: relative; overflow: hidden;
          background:
            radial-gradient(900px 600px at 100% 0%, color-mix(in srgb, var(--b) 28%, transparent), transparent 60%),
            radial-gradient(800px 700px at 0% 100%, color-mix(in srgb, var(--a) 22%, transparent), transparent 60%),
            linear-gradient(160deg, #0B1324 0%, #0A1020 55%, #070B16 100%); }}
.grid-bg {{ position: absolute; inset: 0; opacity: .07;
           background-image: linear-gradient(var(--ink) 1px, transparent 1px),
                             linear-gradient(90deg, var(--ink) 1px, transparent 1px);
           background-size: 54px 54px; mask-image: linear-gradient(180deg, #000 0%, transparent 70%); }}
.inner {{ position: absolute; inset: 0; padding: 72px 72px 0; display: flex; flex-direction: column; }}
.fit {{ transform-origin: top left; }}
.pill {{ display: inline-flex; align-items: center; gap: 12px; font-weight: 700; font-size: 22px;
        letter-spacing: .14em; text-transform: uppercase; color: #0A1020;
        background: linear-gradient(90deg, var(--a), var(--b)); padding: 12px 22px; border-radius: 999px; }}
.dot {{ width: 10px; height: 10px; border-radius: 50%; background: #0A1020; }}
.date {{ font-size: 22px; color: var(--muted); font-weight: 600; letter-spacing: .06em; }}
.grad {{ background: linear-gradient(90deg, var(--a), var(--b)); -webkit-background-clip: text;
        background-clip: text; color: transparent; }}
.footer {{ position: absolute; left: 0; right: 0; bottom: 0; height: 120px; padding: 0 72px;
          display: flex; align-items: center; justify-content: space-between;
          border-top: 1px solid var(--line); background: rgba(5,8,18,.55); }}
.who {{ display: flex; align-items: center; gap: 18px; }}
.avatar {{ width: 62px; height: 62px; border-radius: 50%; display: grid; place-items: center;
          font-weight: 800; font-size: 24px; color: #0A1020;
          background: linear-gradient(135deg, var(--a), var(--b)); }}
.who b {{ display: block; font-size: 25px; }}
.who span {{ font-size: 19px; color: var(--muted); }}
.src {{ font-size: 19px; color: var(--muted); text-align: right; max-width: 430px; }}
"""

FIT_JS = """
() => {
  for (const box of document.querySelectorAll('.inner')) {
    const fit = box.querySelector('.fit');
    const padTop = parseFloat(getComputedStyle(box).paddingTop);
    const limit = box.clientHeight - padTop - parseFloat(box.dataset.reserve || 150);
    let s = 1;
    fit.style.width = (box.clientWidth - 144) + 'px';
    while (fit.scrollHeight * s > limit && s > 0.55) {
      s -= 0.02;
      fit.style.transform = `scale(${s})`;
      fit.style.width = ((box.clientWidth - 144) / s) + 'px';
    }
  }
}
"""


def _footer(source, page=None):
    right = f"Source: {e(source)}" if source else ""
    if page:
        right = page
    return f"""<div class="footer"><div class="who"><div class="avatar">{e(_initials(config.BRAND_NAME))}</div>
      <div><b>{e(config.BRAND_NAME)}</b><span>{e(config.BRAND_TITLE)}</span></div></div>
      <div class="src">{right}</div></div>"""


def infographic_html(d, source):
    pts = d.get("points", [])[:6]
    stat = d.get("stat") or {}
    stat_html = ""
    if str(stat.get("value", "")).strip():
        stat_html = f"""<div class="stat"><div class="sv grad">{e(stat['value'])}</div>
            <div class="sl">{e(stat.get('label', ''))}</div></div>"""
    cards = "".join(
        f"""<div class="card"><div class="num grad">{i + 1:02d}</div>
            <h3>{e(p.get('title', ''))}</h3><p>{e(p.get('text', ''))}</p></div>"""
        for i, p in enumerate(pts))
    css = BASE_CSS + """
    .top { display: flex; justify-content: space-between; align-items: center; margin-bottom: 44px; }
    h1 { font-size: 76px; line-height: 1.04; font-weight: 800; letter-spacing: -0.025em; margin-bottom: 24px; }
    .sub { font-size: 31px; line-height: 1.4; color: #CBD5E1; margin-bottom: 36px; }
    .stat { display: flex; align-items: center; gap: 28px; padding: 26px 32px; margin-bottom: 30px;
            border: 1px solid var(--line); border-radius: 26px; background: var(--card); }
    .sv { font-size: 84px; font-weight: 800; letter-spacing: -0.03em; line-height: 1; }
    .sl { font-size: 27px; color: #CBD5E1; line-height: 1.3; }
    .cards { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 28px; }
    .cards .card:last-child:nth-child(odd) { grid-column: 1 / -1; }
    .card { background: var(--card); border: 1px solid var(--line); border-radius: 24px; padding: 28px 28px 30px; }
    .num { font-size: 30px; font-weight: 800; margin-bottom: 12px; }
    .card h3 { font-size: 29px; line-height: 1.2; margin-bottom: 10px; font-weight: 750; }
    .card p { font-size: 23px; line-height: 1.42; color: #CBD5E1; }
    .take { display: flex; gap: 24px; align-items: flex-start; padding: 28px 32px; border-radius: 24px;
            background: linear-gradient(90deg, color-mix(in srgb, var(--a) 18%, transparent), color-mix(in srgb, var(--b) 12%, transparent));
            border: 1px solid color-mix(in srgb, var(--a) 45%, transparent); }
    .take small { font-size: 19px; font-weight: 800; letter-spacing: .16em; color: var(--a); display: block; margin-bottom: 8px; }
    .take p { font-size: 28px; line-height: 1.35; font-weight: 650; }
    """
    date = datetime.now().strftime("%d %b %Y").upper()
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>
<div class="canvas"><div class="grid-bg"></div><div class="inner"><div class="fit">
  <div class="top"><div class="pill"><span class="dot"></span>{e(d.get('category_label', 'MARKETING UPDATE'))}</div>
    <div class="date">{date}</div></div>
  <h1>{e(d.get('headline', ''))}</h1>
  <div class="sub">{e(d.get('subhead', ''))}</div>
  {stat_html}
  <div class="cards">{cards}</div>
  <div class="take"><div><small>THE MOVE</small><p>{e(d.get('takeaway', ''))}</p></div></div>
</div></div>{_footer(source)}</div></body></html>"""


def _slide(s, i, n, kicker):
    t = s.get("type", "point")
    page = f"{i}/{n}"
    if t == "cover":
        body = f"""<div class="pill"><span class="dot"></span>{e(s.get('kicker') or kicker)}</div>
          <h1 class="cover-t">{e(s.get('title', ''))}</h1>
          <p class="cover-s">{e(s.get('subtitle', ''))}</p>
          <div class="swipe">Swipe <span class="grad">&#8594;</span></div>"""
    elif t == "stat":
        body = f"""<div class="big-n">{i:02d}</div>
          <div class="stat-v">{e(s.get('value', ''))}</div>
          <h2>{e(s.get('label', ''))}</h2><p class="body">{e(s.get('body', ''))}</p>"""
    elif t == "recap":
        items = "".join(f"<li><span class='tick'>&#10003;</span>{e(x)}</li>" for x in s.get("items", [])[:5])
        body = f"""<div class="label">RECAP</div><h2>{e(s.get('heading', ''))}</h2><ul class="recap">{items}</ul>"""
    elif t == "cta":
        body = f"""<div class="cta-av">{e(_initials(config.BRAND_NAME))}</div>
          <h2>{e(s.get('heading', ''))}</h2><p class="body">{e(s.get('body', ''))}</p>
          <div class="cta-row"><span class="btn">Follow {e(config.BRAND_NAME)}</span>
          <span class="btn ghost">Comment your take</span></div>
          <p class="handle">{e(config.BRAND_HANDLE)}</p>"""
    else:
        bl = "".join(f"<li>{e(x)}</li>" for x in (s.get("bullets") or [])[:3] if str(x).strip())
        body = f"""<div class="big-n">{i:02d}</div><h2>{e(s.get('heading', ''))}</h2>
          <p class="body">{e(s.get('body', ''))}</p>{f'<ul class="bl">{bl}</ul>' if bl else ''}"""
    cls = "center"
    return f"""<section class="canvas"><div class="grid-bg"></div>
      <div class="bar"><div style="width:{i / n * 100:.1f}%"></div></div>
      <div class="inner {cls}" data-reserve="150"><div class="fit">{body}</div></div>
      {_footer('', page)}</section>"""


def carousel_html(d):
    slides = d.get("slides", [])[:10]
    n = len(slides)
    kicker = "NICHE NEWS"
    css = BASE_CSS + f"""
    @page {{ size: {W}px {H}px; margin: 0; }}
    section.canvas {{ page-break-after: always; break-after: page; }}
    .bar {{ position: absolute; top: 0; left: 0; right: 0; height: 10px; background: rgba(255,255,255,.08); }}
    .bar div {{ height: 100%; background: linear-gradient(90deg, var(--a), var(--b)); }}
    .inner {{ padding-top: 110px; }}
    .inner.center {{ justify-content: center; padding-bottom: 150px; padding-top: 72px; }}
    .cover-t {{ font-size: 96px; line-height: 1.02; font-weight: 850; letter-spacing: -0.03em; margin: 40px 0 30px; }}
    .cover-s {{ font-size: 36px; line-height: 1.38; color: #CBD5E1; }}
    .swipe {{ margin-top: 60px; font-size: 32px; font-weight: 700; color: var(--muted); }}
    .big-n {{ font-size: 150px; font-weight: 850; line-height: .9; color: rgba(255,255,255,.08); margin-bottom: 26px; }}
    h2 {{ font-size: 76px; line-height: 1.08; font-weight: 800; letter-spacing: -0.02em; margin-bottom: 34px; }}
    .body {{ font-size: 40px; line-height: 1.45; color: #D5DEEA; }}
    .bl {{ list-style: none; margin-top: 40px; display: grid; gap: 20px; }}
    .bl li {{ font-size: 33px; line-height: 1.35; padding: 22px 28px; border-radius: 20px;
             background: var(--card); border: 1px solid var(--line); border-left: 6px solid var(--a); }}
    .stat-v {{ color: var(--a); font-size: 170px; font-weight: 850; letter-spacing: -0.04em; line-height: 1; margin-bottom: 28px; }}
    .label {{ font-size: 24px; font-weight: 800; letter-spacing: .2em; color: var(--a); margin-bottom: 20px; }}
    .recap {{ list-style: none; display: grid; gap: 22px; }}
    .recap li {{ display: flex; gap: 22px; align-items: flex-start; font-size: 36px; line-height: 1.32;
                padding: 24px 28px; border-radius: 20px; background: var(--card); border: 1px solid var(--line); }}
    .tick {{ flex: 0 0 48px; height: 48px; border-radius: 50%; display: grid; place-items: center;
            font-size: 26px; font-weight: 900; color: #0A1020; background: linear-gradient(135deg, var(--a), var(--b)); }}
    .cta-av {{ width: 150px; height: 150px; border-radius: 50%; display: grid; place-items: center; font-size: 58px;
              font-weight: 850; color: #0A1020; background: linear-gradient(135deg, var(--a), var(--b)); margin-bottom: 44px; }}
    .cta-row {{ display: flex; gap: 20px; margin-top: 48px; flex-wrap: wrap; }}
    .btn {{ font-size: 30px; font-weight: 750; padding: 22px 34px; border-radius: 999px; color: #0A1020;
           background: linear-gradient(90deg, var(--a), var(--b)); }}
    .btn.ghost {{ background: transparent; color: var(--ink); border: 2px solid var(--line); }}
    .handle {{ margin-top: 36px; font-size: 28px; color: var(--muted); }}
    """
    body = "".join(_slide(s, i + 1, n, kicker) for i, s in enumerate(slides))
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{css}</style></head><body>{body}</body></html>"""


def render_png(html, path):
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": W, "height": H}, device_scale_factor=1.5)
        pg.set_content(html, wait_until="load")
        pg.evaluate(FIT_JS)
        pg.screenshot(path=str(path), clip={"x": 0, "y": 0, "width": W, "height": H})
        b.close()
    return path


def render_pdf(html, path, preview_png=None):
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox"])
        pg = b.new_page(viewport={"width": W, "height": H})
        pg.set_content(html, wait_until="load")
        pg.evaluate(FIT_JS)
        pg.pdf(path=str(path), width=f"{W}px", height=f"{H}px", print_background=True,
               margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        if preview_png:  # first slide preview for logs / Telegram
            pg.screenshot(path=str(preview_png), clip={"x": 0, "y": 0, "width": W, "height": H})
        b.close()
    return path
