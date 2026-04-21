"""Groq-powered context-aware translator.

Source: Groq Chat Completions API (Llama 3.1 8B).
Failure mode: raises AIAnalysisError if the key is missing or the call fails.

Privacy: we don't log the text — only the detected language + word count.
"""

from __future__ import annotations

import json
import re

import httpx

from app.config import settings
from app.exceptions import AIAnalysisError

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"


SYSTEM_PROMPT = (
    "You are a careful translator. Translate the user's text into the target "
    "language while preserving tone, idioms, and intent — never do literal "
    "word-by-word swaps. Keep proper nouns, product names, URLs, and numbers as-is.\n"
    "\n"
    "Return ONLY a JSON object with this exact shape (no markdown, no code fences):\n"
    "{\n"
    '  "source_detected": "<name of detected source language>",\n'
    '  "translated": "<the idiomatic translation>",\n'
    '  "alternative": "<one alternative phrasing if useful, or empty string>",\n'
    '  "notes": [\n'
    '    "<short bullet explaining a translation choice, idiom, or ambiguity>", ...\n'
    "  ]\n"
    "}\n"
    "Cap notes at 4. Only add notes when they meaningfully help the reader."
)


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]
        if stripped.endswith("```"):
            stripped = stripped[: -len("```")]
        if stripped.startswith("json"):
            stripped = stripped[len("json") :]
    return stripped.strip()


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


async def translate(
    text: str,
    source: str,
    target: str,
    formality: str,
    preserve_tone: bool,
) -> dict[str, object]:
    api_key = settings.groq_api_key
    if not api_key:
        raise AIAnalysisError("GROQ_API_KEY is not configured")

    formality_guide = {
        "default": "Match the register of the original. Don't force formal or casual.",
        "formal": "Use a formal, professional register suitable for business correspondence.",
        "casual": "Use a warm, conversational register with natural contractions.",
    }.get(formality, "")

    source_line = "Auto-detect the source language." if source.lower() == "auto" else f"Source language: {source}"
    tone_line = (
        "Preserve the tone and voice of the original writer."
        if preserve_tone
        else "Tone can be normalized; prioritize clarity."
    )

    user_msg = (
        f"{source_line}\n"
        f"Target language: {target}\n"
        f"Formality guidance: {formality_guide}\n"
        f"Tone policy: {tone_line}\n"
        "\n"
        "--- Text starts ---\n"
        f"{text}\n"
        "--- Text ends ---"
    )

    payload = {
        "model": GROQ_MODEL,
        "temperature": 0.25,
        "max_tokens": 2200,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(GROQ_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise AIAnalysisError("Translate request failed") from exc

    try:
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(_strip_code_fence(content))
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AIAnalysisError("Translate returned an unexpected response") from exc

    translated = str(parsed.get("translated", "")).strip()
    if not translated:
        raise AIAnalysisError("Translate returned empty text")

    source_detected = str(parsed.get("source_detected", source or "unknown")).strip() or "unknown"
    alternative = str(parsed.get("alternative", "")).strip()
    notes_raw = parsed.get("notes") or []
    notes: list[str] = []
    if isinstance(notes_raw, list):
        for n in notes_raw[:4]:
            s = str(n).strip()
            if s:
                notes.append(s)

    return {
        "source_detected": source_detected,
        "translated": translated,
        "alternative": alternative,
        "notes": notes,
    }


def word_count(text: str) -> int:
    return _word_count(text)
