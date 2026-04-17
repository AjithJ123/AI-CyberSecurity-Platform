"""WHOIS / domain-age lookup.

Source: python-whois against public WHOIS servers.
Rate limit: varies by TLD registrar; typical soft cap ~10 req/min/IP.
Failure mode: if the lookup fails or returns unusable data, mark as unavailable.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from app.models.schemas import CheckSignal

NEW_DOMAIN_THRESHOLD_DAYS = 90


def _first_datetime(value: Any) -> datetime | None:
    if isinstance(value, list):
        value = value[0] if value else None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return None


def _lookup(domain: str) -> dict[str, Any]:
    try:
        import whois  # type: ignore[import-untyped]
    except Exception:  # pragma: no cover — import-time guard
        return {}

    try:
        record = whois.whois(domain)
    except Exception:
        return {}

    created = _first_datetime(record.creation_date)
    expires = _first_datetime(record.expiration_date)
    updated = _first_datetime(record.updated_date)

    now = datetime.now(tz=timezone.utc)
    age_days = int((now - created).days) if created else -1
    expires_in_days = int((expires - now).days) if expires else -1

    registrar = record.registrar
    if isinstance(registrar, list):
        registrar = registrar[0] if registrar else ""
    country = record.country
    if isinstance(country, list):
        country = country[0] if country else ""

    return {
        "age_days": age_days,
        "expires_in_days": expires_in_days,
        "created": created.isoformat() if created else "",
        "expires": expires.isoformat() if expires else "",
        "updated": updated.isoformat() if updated else "",
        "registrar": registrar or "",
        "country": country or "",
    }


async def check(url: str) -> CheckSignal:
    """Return a CheckSignal reflecting the age of the URL's domain."""
    host = urlparse(url).hostname or ""
    if not host:
        return CheckSignal(source="whois", available=False)

    try:
        info = await asyncio.to_thread(_lookup, host)
    except Exception:
        return CheckSignal(source="whois", available=False)

    age = int(info.get("age_days", -1))
    if age < 0:
        return CheckSignal(source="whois", available=False)

    reasons: list[str] = []
    score = 0
    if age < NEW_DOMAIN_THRESHOLD_DAYS:
        score = 25
        reasons.append(f"Domain is only {age} days old — new domains are often used for phishing.")
    elif age < 365:
        score = 10
        reasons.append(f"Domain is {age} days old (under one year).")
    else:
        reasons.append(f"Domain has existed for {age} days.")

    if info.get("registrar"):
        reasons.append(f"Registrar: {info['registrar']}.")
    if info.get("country"):
        reasons.append(f"Registered country: {info['country']}.")
    if isinstance(info.get("expires_in_days"), int) and info["expires_in_days"] >= 0:
        reasons.append(f"Expires in {info['expires_in_days']} days.")

    details = {"domain": host, **info}

    return CheckSignal(
        source="whois",
        available=True,
        score=score,
        reasons=reasons,
        details=details,
    )
