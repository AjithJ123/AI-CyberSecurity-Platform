"""Groq-powered code reviewer.

Source: Groq OpenAI-compatible Chat Completions API (free tier, Llama 3.1 8B).
Failure mode: raises AIAnalysisError if the key is missing or the call fails.

Privacy: we don't log the user's code — only the resulting issue counts and
duration. The code is sent to Groq for processing.
"""

import json

import httpx

from app.config import settings
from app.exceptions import AIAnalysisError

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

VALID_SEVERITIES = {"bug", "security", "readability", "style"}

SYSTEM_PROMPT = (
    "You are a concise, direct code reviewer. Given a snippet, identify real issues "
    "in four categories: bug (wrong behaviour / crash), security (vulnerabilities or unsafe "
    "practice), readability (hard to follow, unclear names, long functions), style "
    "(convention violations). Skip trivial nits.\n"
    "\n"
    "Return ONLY a JSON object with this exact shape (no markdown, no code fences):\n"
    "{\n"
    '  "summary": "<one-line description of what the code does, ~20 words>",\n'
    '  "language_detected": "<python|javascript|...>",\n'
    '  "overall_quality": <integer 1-10>,\n'
    '  "issues": [\n'
    "    {\n"
    '      "severity": "bug|security|readability|style",\n'
    '      "line": <1-indexed line number or null>,\n'
    '      "message": "<what is wrong, 1 sentence>",\n'
    '      "suggestion": "<how to fix, 1 sentence>"\n'
    "    }\n"
    "  ],\n"
    '  "positives": ["<short bullet of something the code does well>", ...]\n'
    "}\n"
    "Cap issues at 8 items. Cap positives at 3. If the code is fine, return an empty issues array."
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


def line_count(code: str) -> int:
    return len(code.splitlines())


async def review(code: str, language: str, context: str) -> dict[str, object]:
    """Ask Groq to review the given code. Returns the parsed JSON dict."""
    api_key = settings.groq_api_key
    if not api_key:
        raise AIAnalysisError("GROQ_API_KEY is not configured")

    lines = code.splitlines()
    numbered = "\n".join(f"{i + 1}: {line}" for i, line in enumerate(lines))
    user_msg_parts = [
        f"Declared language: {language}",
    ]
    if context:
        user_msg_parts.append(f"Context (what it should do): {context}")
    user_msg_parts.append("--- Code starts ---")
    user_msg_parts.append(numbered)
    user_msg_parts.append("--- Code ends ---")
    user_msg = "\n".join(user_msg_parts)

    payload = {
        "model": GROQ_MODEL,
        "temperature": 0.2,
        "max_tokens": 1800,
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
        raise AIAnalysisError("Code review request failed") from exc

    try:
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(_strip_code_fence(content))
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AIAnalysisError("Code review returned an unexpected response") from exc

    summary = str(parsed.get("summary", "")).strip() or "No summary provided."
    language_detected = str(parsed.get("language_detected", language)).strip() or language
    try:
        overall_quality = max(1, min(10, int(parsed.get("overall_quality", 5))))
    except (TypeError, ValueError):
        overall_quality = 5

    raw_issues = parsed.get("issues") or []
    issues: list[dict[str, object]] = []
    if isinstance(raw_issues, list):
        for item in raw_issues[:8]:
            if not isinstance(item, dict):
                continue
            severity = str(item.get("severity", "readability")).lower()
            if severity not in VALID_SEVERITIES:
                severity = "readability"
            line = item.get("line")
            try:
                line_num = int(line) if line is not None else None
            except (TypeError, ValueError):
                line_num = None
            issues.append(
                {
                    "severity": severity,
                    "line": line_num,
                    "message": str(item.get("message", "")).strip(),
                    "suggestion": str(item.get("suggestion", "")).strip(),
                }
            )

    raw_positives = parsed.get("positives") or []
    positives: list[str] = []
    if isinstance(raw_positives, list):
        for p in raw_positives[:3]:
            s = str(p).strip()
            if s:
                positives.append(s)

    return {
        "summary": summary,
        "language_detected": language_detected,
        "overall_quality": overall_quality,
        "issues": issues,
        "positives": positives,
    }
