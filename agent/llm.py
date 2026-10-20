"""Free LLM access with automatic fallback: Gemini (free tier) -> Groq -> OpenRouter free models.

All three expose an OpenAI-compatible /chat/completions endpoint, so one client covers them.
With MODEL=auto the newest suitable free model is discovered at runtime, so the agent keeps
working when providers rename or retire models.
"""
import json
import logging
import re
import time

import requests

from . import config

log = logging.getLogger("llm")
_model_cache = {}

BAD = re.compile(r"(preview|exp|live|tts|audio|image|vision|embed|transcribe|translate|"
                 r"guard|whisper|thinking|omni|veo|imagen|lyria|aqa|learnlm|robotics|computer)", re.I)


def _version_key(name):
    nums = [int(x) for x in re.findall(r"\d+", name)[:3]]
    return nums + [0] * (3 - len(nums))


def _gemini_model():
    if config.GEMINI_MODEL != "auto":
        return config.GEMINI_MODEL
    if "gemini" in _model_cache:
        return _model_cache["gemini"]
    r = requests.get("https://generativelanguage.googleapis.com/v1beta/models",
                     params={"key": config.GEMINI_API_KEY, "pageSize": 200}, timeout=30)
    r.raise_for_status()
    names = []
    for m in r.json().get("models", []):
        name = m["name"].split("/")[-1]
        if ("generateContent" in m.get("supportedGenerationMethods", [])
                and name.startswith("gemini") and "flash" in name and not BAD.search(name)
                and "lite" not in name):
            names.append(name)
    if not names:
        raise RuntimeError("no Gemini flash model available")
    names.sort(key=_version_key, reverse=True)
    _model_cache["gemini"] = names[0]
    return names[0]


def _groq_model():
    if config.GROQ_MODEL != "auto":
        return config.GROQ_MODEL
    if "groq" in _model_cache:
        return _model_cache["groq"]
    r = requests.get("https://api.groq.com/openai/v1/models",
                     headers={"Authorization": f"Bearer {config.GROQ_API_KEY}"}, timeout=30)
    r.raise_for_status()
    ids = [m["id"] for m in r.json().get("data", []) if not BAD.search(m["id"])]
    preferred = ["llama-3.3-70b-versatile", "openai/gpt-oss-120b", "moonshotai/kimi-k2-instruct"]
    pick = next((p for p in preferred if p in ids), None)
    if not pick:
        big = [i for i in ids if re.search(r"(70b|120b|405b|k2)", i)]
        pick = (big or ids)[0]
    _model_cache["groq"] = pick
    return pick


def _openrouter_model():
    if config.OPENROUTER_MODEL != "auto":
        return config.OPENROUTER_MODEL
    if "openrouter" in _model_cache:
        return _model_cache["openrouter"]
    r = requests.get("https://openrouter.ai/api/v1/models", timeout=30)
    r.raise_for_status()
    free = [m for m in r.json().get("data", []) if m["id"].endswith(":free")
            and m.get("context_length", 0) >= 32000]
    free.sort(key=lambda m: m.get("context_length", 0), reverse=True)
    if not free:
        raise RuntimeError("no free OpenRouter model")
    _model_cache["openrouter"] = free[0]["id"]
    return free[0]["id"]


def _providers():
    p = []
    if config.GEMINI_API_KEY:
        p.append(("gemini", "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions",
                  config.GEMINI_API_KEY, _gemini_model))
    if config.GROQ_API_KEY:
        p.append(("groq", "https://api.groq.com/openai/v1/chat/completions",
                  config.GROQ_API_KEY, _groq_model))
    if config.OPENROUTER_API_KEY:
        p.append(("openrouter", "https://openrouter.ai/api/v1/chat/completions",
                  config.OPENROUTER_API_KEY, _openrouter_model))
    if not p:
        raise RuntimeError("No LLM key set. Add GEMINI_API_KEY and/or GROQ_API_KEY to .env")
    return p


def chat(system, user, temperature=0.7, max_tokens=8000):
    errors = []
    for name, url, key, model_fn in _providers():
        for attempt in range(3):
            try:
                model = model_fn()
                body = {"model": model, "temperature": temperature, "max_tokens": max_tokens,
                        "messages": [{"role": "system", "content": system},
                                     {"role": "user", "content": user}]}
                if name == "gemini":
                    body["reasoning_effort"] = "low"   # keep thinking tokens small on free tier
                r = requests.post(url, timeout=180, headers={"Authorization": f"Bearer {key}"},
                                  json=body)
                if r.status_code == 400 and "reasoning" in r.text.lower():
                    body.pop("reasoning_effort", None)
                    r = requests.post(url, timeout=180,
                                      headers={"Authorization": f"Bearer {key}"}, json=body)
                if r.status_code == 429 or r.status_code >= 500:
                    raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
                r.raise_for_status()
                text = r.json()["choices"][0]["message"]["content"] or ""
                if text.strip():
                    log.info("LLM ok via %s/%s", name, model)
                    return text
                raise RuntimeError("empty response")
            except Exception as e:  # noqa: BLE001
                errors.append(f"{name}#{attempt + 1}: {e}")
                log.warning("LLM %s attempt %d failed: %s", name, attempt + 1, e)
                time.sleep(4 * (attempt + 1))
    raise RuntimeError("All LLM providers failed: " + " | ".join(errors[-4:]))


def chat_json(system, user, **kw):
    """Ask for JSON and parse it robustly (strips code fences / extra prose)."""
    last = None
    for _ in range(2):
        text = chat(system + "\n\nReturn ONLY valid JSON. No markdown, no commentary.", user, **kw)
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError as e:
                last = e
    raise RuntimeError(f"LLM did not return valid JSON: {last}")
