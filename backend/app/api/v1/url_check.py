"""POST /api/v1/check/url — the main URL phishing endpoint.

Flow:
    1. Detect whether the input URL is a known shortener.
    2. If so, follow the redirect chain to the real destination.
    3. Run every other checker against the FINAL URL so VirusTotal etc. see
       what the user would actually land on.
    4. Aggregate and return.
"""

import asyncio
import logging
import time
from typing import AsyncIterator
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from app.checkers import (
    heuristics,
    phishtank,
    safe_browsing,
    shortener,
    virustotal,
    whois_check,
)
from app.models.schemas import CheckResponse, CheckSignal, URLCheckRequest, UrlAnatomy
from app.rate_limit import limiter
from app.scoring.aggregator import aggregate
from app.utils.hashing import hash_url

router = APIRouter(tags=["checks"])
logger = logging.getLogger(__name__)


async def get_http_client() -> AsyncIterator[httpx.AsyncClient]:
    """Shared AsyncClient with a safe default timeout."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        yield client


def _parse_anatomy(url: str) -> UrlAnatomy:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    subdomain_count = max(host.count(".") - 1, 0) if tld else 0
    params = parsed.query.split("&") if parsed.query else []
    return UrlAnatomy(
        full=url,
        scheme=parsed.scheme or "",
        host=host,
        port=parsed.port,
        path=parsed.path or "/",
        tld=tld,
        subdomain_count=subdomain_count,
        query_param_count=len([p for p in params if p]),
        has_userinfo=bool(parsed.username),
    )


@router.post("/check/url", response_model=CheckResponse)
@limiter.limit("20/minute")
async def check_url(
    request: Request,
    req: URLCheckRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> CheckResponse:
    """Aggregate signals from every URL checker and return a verdict."""
    original_url = str(req.url)
    started = time.perf_counter()

    # Step 1: shortener expansion (only if the URL is a known shortener).
    shortener_signal = await shortener.check(original_url, client)
    expanded_url = original_url
    if shortener_signal.details.get("is_shortener") and shortener_signal.available:
        expanded_url = shortener_signal.details.get("final_url", original_url)

    # Step 2: run every other checker against the expanded URL.
    try:
        other_signals = await asyncio.gather(
            asyncio.to_thread(heuristics.check, expanded_url),
            whois_check.check(expanded_url),
            safe_browsing.check(expanded_url, client),
            virustotal.check(expanded_url, client),
            phishtank.check(expanded_url, client),
            return_exceptions=True,
        )
    except Exception:
        logger.exception("url_check_failed", extra={"url_hash": hash_url(original_url)})
        raise HTTPException(
            status_code=503,
            detail="We couldn't check that URL right now. Please try again.",
        )

    signals: list[CheckSignal] = [shortener_signal]
    for res in other_signals:
        if isinstance(res, CheckSignal):
            signals.append(res)
        else:
            signals.append(CheckSignal(source="unknown", available=False))

    response = aggregate(signals)
    response.anatomy = _parse_anatomy(expanded_url)
    response.original_url = original_url
    response.expanded_url = expanded_url if expanded_url != original_url else ""
    response.total_duration_ms = int((time.perf_counter() - started) * 1000)

    logger.info(
        "url_check_completed",
        extra={
            "url_hash": hash_url(original_url),
            "verdict": response.verdict,
            "score": response.score,
            "was_shortened": expanded_url != original_url,
            "duration_ms": response.total_duration_ms,
        },
    )
    return response
