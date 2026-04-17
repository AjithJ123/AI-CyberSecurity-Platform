"""Google Safe Browsing lookup.

Source: https://safebrowsing.googleapis.com/v4/threatMatches:find
Rate limit: 10,000 requests/day on the free tier.
Failure mode: if the API key is missing or the request fails, return unavailable.
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.models.schemas import CheckSignal

ENDPOINT = "https://safebrowsing.googleapis.com/v4/threatMatches:find"
THREAT_TYPES = [
    "MALWARE",
    "SOCIAL_ENGINEERING",
    "UNWANTED_SOFTWARE",
    "POTENTIALLY_HARMFUL_APPLICATION",
]


async def check(url: str, client: httpx.AsyncClient) -> CheckSignal:
    """Return a CheckSignal indicating whether Google flags the URL."""
    api_key = settings.google_safe_browsing_api_key
    if not api_key:
        return CheckSignal(source="safe_browsing", available=False)

    payload = {
        "client": {"clientId": "phishguard-ai", "clientVersion": "1.0.0"},
        "threatInfo": {
            "threatTypes": THREAT_TYPES,
            "platformTypes": ["ANY_PLATFORM"],
            "threatEntryTypes": ["URL"],
            "threatEntries": [{"url": url}],
        },
    }

    try:
        resp = await client.post(
            ENDPOINT,
            params={"key": api_key},
            json=payload,
            timeout=10.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError:
        return CheckSignal(source="safe_browsing", available=False)

    data = resp.json()
    matches = data.get("matches") or []
    if not matches:
        return CheckSignal(
            source="safe_browsing",
            available=True,
            score=0,
            reasons=["Google Safe Browsing has no warning for this URL."],
        )

    types = sorted({m.get("threatType", "UNKNOWN") for m in matches})
    return CheckSignal(
        source="safe_browsing",
        available=True,
        score=90,
        reasons=[f"Google Safe Browsing flagged this URL: {', '.join(types)}."],
    )
