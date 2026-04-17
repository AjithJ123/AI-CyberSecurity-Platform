"""PhishTank lookup.

Source: https://checkurl.phishtank.com/checkurl/
Rate limit: unauthenticated usage is unmetered but discouraged; prefer an app key.
Failure mode: returns unavailable on network errors or unexpected payloads.
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.models.schemas import CheckSignal

ENDPOINT = "https://checkurl.phishtank.com/checkurl/"


async def check(url: str, client: httpx.AsyncClient) -> CheckSignal:
    """Return a signal based on whether PhishTank already knows the URL."""
    data = {"url": url, "format": "json"}
    if settings.phishtank_api_key:
        data["app_key"] = settings.phishtank_api_key

    try:
        resp = await client.post(ENDPOINT, data=data, timeout=10.0)
        resp.raise_for_status()
        payload = resp.json()
    except (httpx.HTTPError, ValueError):
        return CheckSignal(source="phishtank", available=False)

    results = payload.get("results") or {}
    in_db = bool(results.get("in_database"))
    valid = bool(results.get("valid"))
    verified = bool(results.get("verified"))

    if in_db and valid:
        score = 90 if verified else 70
        label = "verified" if verified else "reported"
        return CheckSignal(
            source="phishtank",
            available=True,
            score=score,
            reasons=[f"PhishTank has a {label} phishing report for this URL."],
        )

    return CheckSignal(
        source="phishtank",
        available=True,
        score=0,
        reasons=["PhishTank has no current report for this URL."],
    )
