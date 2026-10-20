"""LinkedIn personal-profile posting via the free 'Share on LinkedIn' product (w_member_social)."""
import json
import logging
import re
import secrets
import time
from datetime import datetime
from urllib.parse import parse_qs, urlencode, urlparse

import requests

from . import config

log = logging.getLogger("linkedin")
API = "https://api.linkedin.com"
SCOPES = "openid profile w_member_social"


# ---------------- OAuth (one-time, repeat every ~60 days) ----------------
def auth_interactive():
    if not (config.LINKEDIN_CLIENT_ID and config.LINKEDIN_CLIENT_SECRET):
        raise SystemExit("Set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in .env first.")
    state = secrets.token_urlsafe(16)
    url = "https://www.linkedin.com/oauth/v2/authorization?" + urlencode({
        "response_type": "code", "client_id": config.LINKEDIN_CLIENT_ID,
        "redirect_uri": config.LINKEDIN_REDIRECT_URI, "state": state, "scope": SCOPES})
    print("\n1) Open this URL in your browser and click Allow:\n\n" + url)
    print("\n2) The browser will go to a localhost page that may show an error. That's fine.")
    print("   Copy the FULL address from the address bar and paste it here.\n")
    redirected = input("Paste URL: ").strip()
    q = parse_qs(urlparse(redirected).query)
    if q.get("state", [""])[0] != state:
        raise SystemExit("State mismatch. Run auth again.")
    code = q.get("code", [""])[0]
    r = requests.post("https://www.linkedin.com/oauth/v2/accessToken", timeout=30, data={
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": config.LINKEDIN_REDIRECT_URI,
        "client_id": config.LINKEDIN_CLIENT_ID, "client_secret": config.LINKEDIN_CLIENT_SECRET})
    r.raise_for_status()
    tok = r.json()
    me = requests.get(f"{API}/v2/userinfo", timeout=30,
                      headers={"Authorization": f"Bearer {tok['access_token']}"}).json()
    tok["person_urn"] = f"urn:li:person:{me['sub']}"
    tok["name"] = me.get("name", "")
    tok["expires_at"] = int(time.time()) + int(tok.get("expires_in", 5184000))
    config.TOKEN_FILE.write_text(json.dumps(tok, indent=2))
    config.TOKEN_FILE.chmod(0o600)
    days = (tok["expires_at"] - time.time()) / 86400
    print(f"\nConnected as {tok['name']} ({tok['person_urn']}). Token valid ~{days:.0f} days.")


def _token():
    if not config.TOKEN_FILE.exists():
        raise RuntimeError("LinkedIn not connected. Run: ./run.sh auth")
    tok = json.loads(config.TOKEN_FILE.read_text())
    if tok.get("expires_at", 0) < time.time():
        raise RuntimeError("LinkedIn token expired. Run: ./run.sh auth")
    return tok


def days_left():
    try:
        return (_token()["expires_at"] - time.time()) / 86400
    except Exception:  # noqa: BLE001
        return -1


# ---------------- API helpers ----------------
_version = {}


def _candidate_versions():
    if config.LINKEDIN_VERSION != "auto":
        return [config.LINKEDIN_VERSION]
    now = datetime.utcnow()
    y, m = now.year, now.month
    out = []
    for _ in range(12):
        m -= 1
        if m == 0:
            y, m = y - 1, 12
        out.append(f"{y}{m:02d}")
    return out


def _req(method, path, **kw):
    tok = _token()
    versions = [_version["v"]] if "v" in _version else _candidate_versions()
    last = None
    for v in versions:
        h = {"Authorization": f"Bearer {tok['access_token']}", "LinkedIn-Version": v,
             "X-Restli-Protocol-Version": "2.0.0", "Content-Type": "application/json"}
        r = requests.request(method, API + path, headers=h, timeout=60, **kw)
        if r.status_code == 426 or (r.status_code == 400 and "version" in r.text.lower()
                                    and "NONEXISTENT" in r.text.upper()):
            last = r
            continue
        _version["v"] = v
        return r
    return last


def escape_little(text):
    """LinkedIn 'little' text format: reserved chars must be escaped, hashtags templated."""
    out = []
    for token in re.split(r"(#[A-Za-z][A-Za-z0-9_]*)", text):
        if re.fullmatch(r"#[A-Za-z][A-Za-z0-9_]*", token):
            out.append("{hashtag|\\#|" + token[1:] + "}")
        else:
            out.append(re.sub(r"([\\|{}@\[\]()<>#*_~])", r"\\\1", token))
    return "".join(out)


def _upload(kind, file_path):
    owner = _token()["person_urn"]
    r = _req("POST", f"/rest/{kind}s?action=initializeUpload",
             json={"initializeUploadRequest": {"owner": owner}})
    if r.status_code >= 300:
        raise RuntimeError(f"{kind} init failed {r.status_code}: {r.text[:400]}")
    v = r.json()["value"]
    urn = v.get(kind) or v.get("image") or v.get("document")
    up = requests.put(v["uploadUrl"], data=open(file_path, "rb").read(), timeout=180,
                      headers={"Authorization": f"Bearer {_token()['access_token']}",
                               "Content-Type": "application/octet-stream"})
    if up.status_code >= 300:
        raise RuntimeError(f"{kind} upload failed {up.status_code}: {up.text[:300]}")
    # wait until processed
    for _ in range(30):
        s = _req("GET", f"/rest/{kind}s/{requests.utils.quote(urn, safe='')}")
        status = s.json().get("status", "") if s.status_code == 200 else ""
        if status == "AVAILABLE":
            break
        if status == "PROCESSING_FAILED":
            raise RuntimeError(f"LinkedIn could not process the {kind}")
        time.sleep(4)
    return urn


def _create_post(commentary, media):
    body = {"author": _token()["person_urn"], "commentary": escape_little(commentary),
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [],
                             "thirdPartyDistributionChannels": []},
            "content": {"media": media}, "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False}
    r = _req("POST", "/rest/posts", json=body)
    if r.status_code >= 300:
        raise RuntimeError(f"post failed {r.status_code}: {r.text[:400]}")
    return r.headers.get("x-restli-id") or r.headers.get("x-linkedin-id") or "ok"


def post_image(commentary, png_path, alt_text):
    urn = _upload("image", png_path)
    return _create_post(commentary, {"id": urn, "altText": alt_text[:4000]})


def post_document(commentary, pdf_path, title):
    urn = _upload("document", pdf_path)
    return _create_post(commentary, {"id": urn, "title": title[:200]})
