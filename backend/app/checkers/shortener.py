"""URL shortener detection and expansion.

Many phishing campaigns hide a malicious destination behind a reputable-looking
short URL (bit.ly, t.co, tinyurl). We detect known shortener hosts, follow the
redirect chain, and return the final landing URL so the other checkers can
inspect the real destination.

Source: HEAD/GET against the shortener; no external API.
Failure mode: returns unavailable if expansion fails (network error, loop).
"""

from __future__ import annotations

from urllib.parse import urlparse

import httpx

from app.models.schemas import CheckSignal

# Shorteners commonly abused in phishing. Not exhaustive — the top offenders.
SHORTENER_HOSTS: set[str] = {
    "bit.ly",
    "t.co",
    "tinyurl.com",
    "goo.gl",
    "ow.ly",
    "buff.ly",
    "is.gd",
    "cutt.ly",
    "rb.gy",
    "tiny.cc",
    "shorturl.at",
    "rebrand.ly",
    "tr.im",
    "bl.ink",
    "lnkd.in",
    "fb.me",
    "youtu.be",
    "wa.me",
    "amzn.to",
    "t.ly",
    "s.id",
    "short.io",
    "soo.gd",
    "v.gd",
    "x.co",
    "ity.im",
    "qr.net",
    "chilp.it",
    "po.st",
    "adf.ly",
    "bc.vc",
    "sh.st",
    "linktr.ee",
}

MAX_HOPS = 10


def is_shortener(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in SHORTENER_HOSTS


async def expand(url: str, client: httpx.AsyncClient) -> tuple[str, list[str]]:
    """Follow redirects up to MAX_HOPS. Return (final_url, hops)."""
    current = url
    hops: list[str] = []
    for _ in range(MAX_HOPS):
        try:
            resp = await client.request(
                "HEAD",
                current,
                follow_redirects=False,
                timeout=8.0,
            )
        except httpx.HTTPError:
            # Some shorteners reject HEAD — fall back to GET but don't
            # download the body.
            try:
                resp = await client.request(
                    "GET",
                    current,
                    follow_redirects=False,
                    timeout=8.0,
                    headers={"Range": "bytes=0-0"},
                )
            except httpx.HTTPError:
                break

        location = resp.headers.get("location")
        if not location or resp.status_code < 300 or resp.status_code >= 400:
            break

        # Resolve relative redirects against the current URL.
        next_url = str(httpx.URL(current).join(location))
        if next_url == current or next_url in hops:
            break
        hops.append(next_url)
        current = next_url

    return current, hops


async def check(url: str, client: httpx.AsyncClient) -> CheckSignal:
    if not is_shortener(url):
        return CheckSignal(
            source="shortener",
            available=True,
            score=0,
            reasons=[],
            details={"is_shortener": False},
        )

    final_url, hops = await expand(url, client)

    details = {
        "is_shortener": True,
        "original_url": url,
        "final_url": final_url,
        "hops": hops,
        "hop_count": len(hops),
    }

    if final_url == url:
        return CheckSignal(
            source="shortener",
            available=False,
            score=0,
            reasons=[f"Could not expand the shortened link {urlparse(url).hostname}."],
            details=details,
        )

    reasons = [
        f"Link is shortened through {urlparse(url).hostname}.",
        f"Real destination: {final_url}",
    ]
    if len(hops) > 1:
        reasons.append(f"Passed through {len(hops)} redirects before landing.")

    # Shortened URLs are mildly suspicious on their own — the *destination* is
    # what matters, and the other checkers score that.
    return CheckSignal(
        source="shortener",
        available=True,
        score=15,
        reasons=reasons,
        details=details,
    )
