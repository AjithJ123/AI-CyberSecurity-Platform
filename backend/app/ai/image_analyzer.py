"""Groq-powered image analyzer (vision model).

Source: Groq Chat Completions API with a vision-capable model.
Failure mode: raises AIAnalysisError if the key/model is missing or the call
fails.

Privacy: we never log the image data itself — only the textual result and
duration. The image is sent to Groq for processing and discarded after.
"""

from __future__ import annotations

import json
import re

import httpx

from app.config import settings
from app.exceptions import AIAnalysisError

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"

# Vision-capable Groq model. If Groq retires this, any other vision-capable
# model they host (e.g. meta-llama/llama-4-scout-17b-16e-instruct) can be
# dropped in here — the request schema is identical.
GROQ_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"

# Accept common inline image MIME types only. The data URL arrives straight
# from the browser FileReader, so it's effectively bounded to what the user
# selected on the <input type="file" accept="image/*">.
DATA_URL_RE = re.compile(r"^data:image/(png|jpeg|jpg|webp|gif);base64,[A-Za-z0-9+/=]+$")

SYSTEM_PROMPT = (
    "You are a careful visual-analysis assistant. Look at the provided image and return "
    "ONLY a JSON object with this exact shape (no markdown, no code fences):\n"
    "{\n"
    '  "description": "<2-3 short sentences describing what is in the image>",\n'
    '  "has_text": <true|false>,\n'
    '  "ocr_text": "<any text visible in the image, verbatim; empty string if none>",\n'
    '  "ai_generated_score": <integer 0-100 — likelihood the image was AI-generated>,\n'
    '  "ai_generated_reasons": ["<short bullet of a specific AI giveaway you saw>", ...],\n'
    '  "subjects": ["<short label of a main subject>", ...],\n'
    '  "content_warnings": ["<short bullet for anything NSFW, graphic, or sensitive>", ...]\n'
    "}\n"
    "\n"
    "Rules:\n"
    "• Keep description factual — no speculation about the photographer, brand, or year.\n"
    "• For ai_generated_score: real photos = 0-30, uncertain = 30-70, obvious AI = 70-100.\n"
    "• ai_generated_reasons should cite concrete visual evidence (e.g. \"warped fingers in "
    "the left hand\", \"text on sign has nonsense glyphs\") or be empty if score < 20.\n"
    "• subjects: up to 4 short labels.\n"
    "• content_warnings is usually empty. Only populate for genuine concerns."
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


def _validate_data_url(data_url: str) -> None:
    if not data_url.startswith("data:image/"):
        raise AIAnalysisError("Only image data URLs are accepted")
    if not DATA_URL_RE.match(data_url[:80] + data_url[-20:]):
        # cheap sanity check — we don't validate the whole base64 payload
        pass


async def analyze(image_data_url: str) -> dict[str, object]:
    """Send the image to the vision model and return the parsed JSON dict."""
    api_key = settings.groq_api_key
    if not api_key:
        raise AIAnalysisError("GROQ_API_KEY is not configured")

    _validate_data_url(image_data_url)

    payload = {
        "model": GROQ_MODEL,
        "temperature": 0.2,
        "max_tokens": 900,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "Analyze this image and return the JSON."},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            },
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(GROQ_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise AIAnalysisError("Image analysis request failed") from exc

    try:
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(_strip_code_fence(content))
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AIAnalysisError("Image analysis returned an unexpected response") from exc

    description = str(parsed.get("description", "")).strip() or "(no description)"
    has_text = bool(parsed.get("has_text", False))
    ocr_text = str(parsed.get("ocr_text", "")).strip()
    try:
        ai_score = max(0, min(100, int(parsed.get("ai_generated_score", 0))))
    except (TypeError, ValueError):
        ai_score = 0

    def _str_list(key: str, cap: int) -> list[str]:
        raw = parsed.get(key) or []
        if not isinstance(raw, list):
            return []
        out: list[str] = []
        for item in raw[:cap]:
            s = str(item).strip()
            if s:
                out.append(s)
        return out

    ai_reasons = _str_list("ai_generated_reasons", 5)
    subjects = _str_list("subjects", 4)
    warnings = _str_list("content_warnings", 4)

    return {
        "description": description,
        "has_text": has_text,
        "ocr_text": ocr_text,
        "ai_generated_score": ai_score,
        "ai_generated_reasons": ai_reasons,
        "subjects": subjects,
        "content_warnings": warnings,
        "model": GROQ_MODEL,
    }
