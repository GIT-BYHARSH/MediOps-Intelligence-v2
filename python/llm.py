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


def ask_llm(system, user, temperature=0.2, max_tokens=900):
    """Return the model's text answer, or None when no key is set or the call fails."""
    if not llm_available():
        return None
    base = (os.environ.get("LLM_BASE_URL", "").strip() or "https://api.openai.com/v1").rstrip("/")
    try:
        response = requests.post(
            f"{base}/chat/completions",
            headers={"Authorization": f"Bearer {_value('LLM_API_KEY')}"},
            json={
                "model": _value("LLM_MODEL"),
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
            timeout=60,
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except Exception as error:  # never show the request (it contains the key)
        status = getattr(getattr(error, "response", None), "status_code", None)
        detail = f"HTTP {status}" if status else type(error).__name__
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
