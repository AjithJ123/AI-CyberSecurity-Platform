"""Groq-powered writing rewriter.

Source: Groq OpenAI-compatible Chat Completions API (free tier, Llama 3.1 8B).
Failure mode: raises AIAnalysisError if the key is missing or the call fails.

Privacy: we don't log the user's text — only the resulting word counts and
duration. The text is sent to Groq for processing.
"""

import json
import re

import httpx

from app.config import settings
from app.exceptions import AIAnalysisError

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

TONE_GUIDES: dict[str, str] = {
    "natural": (
        "Sound like a thoughtful human writer. Strip AI-tells "
        "(\"it's important to note\", \"in conclusion\", \"delve into\", \"furthermore\", "
        "\"navigating the complexities of\"). Use contractions where natural. "
        "Vary sentence length."
    ),
    "professional": (
        "Sound polished and business-appropriate. Clear, confident, and direct. "
        "Avoid jargon and filler. No casual contractions; no slang."
    ),
    "concise": (
        "Cut every word that isn't pulling its weight. Short sentences. "
        "Aim for ~30% fewer words while preserving every concrete fact."
    ),
    "friendly": (
        "Warm, conversational, helpful. Use second person where it fits. "
        "Contractions are fine. Avoid being overly cute or salesy."
    ),
}

SYSTEM_PROMPT = (
    "You are a careful writing editor. Rewrite the user's text to match the requested tone. "
    "Preserve every concrete fact, name, number, and link. Don't add new information. "
    "Don't add disclaimers or commentary outside the JSON. "
    "Return ONLY a JSON object with this exact shape (no markdown, no code fences):\n"
    "{\n"
    '  "rewritten": "<the rewritten text>",\n'
    '  "changes": ["<short bullet describing one specific change>", ...]\n'
    "}\n"
    "Limit changes to at most 5 short bullets describing the main edits "
    "(e.g. \"removed AI cliché 'delve into'\", \"split long sentence in paragraph 2\")."
)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]
        if stripped.endswith("```"):
            stripped = stripped[: -len("```")]
        if stripped.startswith("json"):
            stripped = stripped[len("json") :]
    return stripped.strip()


async def rewrite(text: str, tone: str) -> dict[str, object]:
    """Ask Groq to rewrite text. Returns {rewritten, changes}."""
    api_key = settings.groq_api_key
    if not api_key:
        raise AIAnalysisError("GROQ_API_KEY is not configured")

    guide = TONE_GUIDES.get(tone, TONE_GUIDES["natural"])
    user_msg = (
        f"Tone: {tone}\n"
        f"Tone guidance: {guide}\n\n"
        "--- Original text starts ---\n"
        f"{text}\n"
        "--- Original text ends ---"
    )

    payload = {
        "model": GROQ_MODEL,
        "temperature": 0.3,
        "max_tokens": 2000,
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
        raise AIAnalysisError("Writing rewrite request failed") from exc

    try:
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(_strip_code_fence(content))
        rewritten = str(parsed.get("rewritten", "")).strip()
        changes = [str(c) for c in parsed.get("changes", [])][:5]
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AIAnalysisError("Writing rewrite returned an unexpected response") from exc

    if not rewritten:
        raise AIAnalysisError("Writing rewrite returned empty text")

    return {"rewritten": rewritten, "changes": changes}


def word_count(text: str) -> int:
    """Public helper exposed for the endpoint."""
    return _word_count(text)
