"""Small LLM client for any OpenAI-compatible provider (OpenAI, Gemini, Groq, OpenRouter, Ollama...).

Settings come from the private .env file (never committed). See .env.example:
    LLM_API_KEY   your key
    LLM_MODEL     the model name your provider uses
    LLM_BASE_URL  optional, defaults to OpenAI. Examples are in .env.example.

If no key is set, ask_llm() returns None and every feature falls back to its template mode,
so the project always runs. The key is never printed or logged.
"""
import os
import re
import time

import requests

import db  # noqa: F401  (importing db loads the .env file)


_PLACEHOLDERS = {"", "key", "model", "model_name", "base_url"}


def _value(name):
    """A setting from .env, or '' if it is empty or still placeholder text from .env.example."""
    value = os.environ.get(name, "").strip()
    lowered = value.lower()
    if lowered in _PLACEHOLDERS or lowered.startswith(("paste_", "your_", "the_")):
        return ""
    return value


def config_problem():
    """Plain-English reason the LLM cannot be used, or None if the settings look usable."""
    if not _value("LLM_API_KEY") or not _value("LLM_MODEL"):
        return "LLM_API_KEY and LLM_MODEL are empty or still placeholder text in .env."
    raw_base = os.environ.get("LLM_BASE_URL", "").strip()
    if raw_base and not raw_base.startswith(("http://", "https://")):
        return "LLM_BASE_URL in .env must start with https://"
    return None


def llm_available():
    return config_problem() is None


def model_label():
    return _value("LLM_MODEL") if llm_available() else "template mode (no LLM key)"


last_failure = {"reason": None}  # why the latest call failed (e.g. "HTTP 429"), for friendly messages


def busy_message():
    """Plain-English note for the user when the AI service could not be reached."""
    reason = last_failure["reason"] or "unknown error"
    if reason == "HTTP 429":
        why = "the free plan's request limit was reached (it resets within a minute)"
    elif reason in ("HTTP 500", "HTTP 502", "HTTP 503", "HTTP 504"):
        why = "Google's AI servers are busy right now"
    else:
        why = f"the call failed ({reason})"
    return f"The AI service could not answer because {why}. Please try again in a minute."


def ask_llm(system, user, temperature=0.2, max_tokens=900):
    """Return the model's text answer, or None when no key is set or the call fails."""
    last_failure["reason"] = None
    if not llm_available():
        return None
    base = (os.environ.get("LLM_BASE_URL", "").strip() or "https://api.openai.com/v1").rstrip("/")
    try:
        body = {
            "model": _value("LLM_MODEL"),
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
            # "thinking" models spend part of this budget on hidden reasoning,
            # so keep it generous or the visible answer comes back empty.
            "max_tokens": max(max_tokens, 4000),
        }
        effort = os.environ.get("LLM_REASONING_EFFORT", "").strip()
        if effort:  # optional, e.g. "low" for Gemini 3 models (faster, cheaper)
            body["reasoning_effort"] = effort
        for attempt in range(3):  # busy servers (503) usually clear in seconds
            response = requests.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {_value('LLM_API_KEY')}"},
                json=body,
                timeout=90,
            )
            # retry only busy-server errors; retrying a 429 would burn more of the limited quota
            if response.status_code not in (500, 502, 503, 504) or attempt == 2:
                break
            time.sleep(4 * (attempt + 1))
        response.raise_for_status()
        text = (response.json()["choices"][0]["message"].get("content") or "").strip()
        if not text:
            print("[LLM returned an empty answer. Using template mode instead.]")
            return None
        return text
    except Exception as error:  # never show the request (it contains the key)
        status = getattr(getattr(error, "response", None), "status_code", None)
        detail = f"HTTP {status}" if status else type(error).__name__
        last_failure["reason"] = detail
        print(f"[LLM call failed: {detail}. Using template mode instead.]")
        return None


# ---------- Grounding check: are the numbers in the AI text really in the data? ----------
_NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _numbers(text):
    values = set()
    for token in _NUMBER.findall(text or ""):
        try:
            values.add(round(float(token.replace(",", "")), 2))
        except ValueError:
            pass
    return values


def unverified_numbers(ai_text, source_text, ignore_up_to=10):
    """Numbers that appear in the AI text but nowhere in the source facts.
    Small whole numbers (list numbering, 'top 3') are ignored. A non-empty result means:
    do not trust the text until a person checks it."""
    allowed = _numbers(source_text)
    return sorted(n for n in _numbers(ai_text) - allowed if not (n == int(n) and n <= ignore_up_to))
