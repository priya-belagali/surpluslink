"""Optional language-model assistant: turn a sentence into a pre-filled donation form.

Off unless ANTHROPIC_API_KEY is set. The text typed is sent to the Anthropic API, so do not type anything private.
The model only suggests values. Every suggestion is validated here, and the donor reviews the form before posting.
"""
import json
import os
import re
import urllib.request
from datetime import time

from core import config, safety

API_URL = "https://api.anthropic.com/v1/messages"
CATEGORIES = list(safety.SAFE_HOURS)


class AssistantError(Exception):
    """Anything that stops the assistant from returning usable values. The message is safe to show."""


def available() -> bool:
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def system_prompt() -> str:
    cats = "; ".join(f'"{c}"' for c in CATEGORIES)
    return (
        "You turn a short description of leftover food into fields for a donation form. "
        "Reply with ONE JSON object and nothing else, using exactly these keys: "
        '"title" (short text), "category" (one of: ' + cats + '), "veg" (true or false), '
        '"quantity_meals" (whole number), "cooked_time" (24-hour "HH:MM"), "temperature_c" (number), "notes" (text). '
        "Use null for anything the description does not say. Never guess a number. "
        "If the description says plates, portions or servings, treat each as one meal."
    )


def validate(raw: dict) -> dict:
    """Keep only values of the right type and range. Anything else is dropped (the form keeps its default)."""
    out: dict = {}
    title = raw.get("title")
    if isinstance(title, str) and title.strip():
        out["title"] = title.strip()[:160]
    if raw.get("category") in CATEGORIES:
        out["category"] = raw["category"]
    if isinstance(raw.get("veg"), bool):
        out["veg"] = raw["veg"]
    q = raw.get("quantity_meals")
    if isinstance(q, (int, float)) and not isinstance(q, bool) and 1 <= q <= 100000:
        out["quantity_meals"] = int(q)
    ct = raw.get("cooked_time")
    if isinstance(ct, str):
        m = re.fullmatch(r"\s*([01]?\d|2[0-3]):([0-5]\d)\s*", ct)
        if m:
            out["cooked_time"] = time(int(m.group(1)), int(m.group(2)))
    t = raw.get("temperature_c")
    if isinstance(t, (int, float)) and not isinstance(t, bool) and -30 <= t <= 120:
        out["temperature_c"] = float(t)
    notes = raw.get("notes")
    if isinstance(notes, str) and notes.strip():
        out["notes"] = notes.strip()[:500]
    return out


def parse_response(text: str) -> dict:
    """Pull the JSON object out of the model's reply (it may wrap it in a code fence) and validate it."""
    match = re.search(r"\{.*\}", text or "", re.S)
    if not match:
        raise AssistantError("The assistant did not return usable values. Please fill the form by hand.")
    try:
        raw = json.loads(match.group(0))
    except ValueError:
        raise AssistantError("The assistant's reply could not be read. Please fill the form by hand.") from None
    if not isinstance(raw, dict):
        raise AssistantError("The assistant's reply was not in the expected form.")
    values = validate(raw)
    if not values:
        raise AssistantError("Nothing in that description could be turned into form fields.")
    return values


def parse_listing_text(description: str) -> dict:
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        raise AssistantError("The assistant is not switched on. Set ANTHROPIC_API_KEY to enable it.")
    body = {"model": config.LLM_MODEL, "max_tokens": 400, "system": system_prompt(),
            "messages": [{"role": "user", "content": (description or "")[:1000]}]}
    req = urllib.request.Request(
        API_URL, data=json.dumps(body).encode(),
        headers={"content-type": "application/json", "x-api-key": key, "anthropic-version": "2023-06-01"})
    try:
        with urllib.request.urlopen(req, timeout=25) as resp:
            data = json.load(resp)
    except Exception as exc:
        print(f"[assistant] request failed: {exc}")
        raise AssistantError("The assistant could not be reached. Please fill the form by hand.") from None
    text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
    return parse_response(text)
