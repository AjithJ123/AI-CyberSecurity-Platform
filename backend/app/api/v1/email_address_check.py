"""POST /api/v1/check/email-address — analyze a sender address for fraud signals.

We run the offline email_address heuristics, then reinforce with domain-level
reputation lookups (VirusTotal, Safe Browsing, WHOIS) applied to the domain
portion of the address.
"""

import asyncio
import logging
import re
import time
from typing import AsyncIterator

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request

from app.checkers import email_address, safe_browsing, virustotal, whois_check
from app.models.schemas import CheckResponse, CheckSignal, EmailAddressCheckRequest
from app.rate_limit import limiter
from app.scoring.aggregator import aggregate

router = APIRouter(tags=["checks"])
logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@([a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})$")


async def get_http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        yield client


@router.post("/check/email-address", response_model=CheckResponse)
@limiter.limit("20/minute")
async def check_email_address(
    request: Request,
    req: EmailAddressCheckRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> CheckResponse:
    started = time.perf_counter()
    email = req.email.strip()
    match = EMAIL_RE.match(email)
    domain = match.group(1).lower() if match else ""
    probe_url = f"https://{domain}/" if domain else ""

    # Always run the offline heuristic; the domain lookups only run if the
    # address parsed cleanly (otherwise we'd be querying nonsense).
    tasks: list = [email_address.check(email)]
    if probe_url:
        tasks.extend(
            [
                whois_check.check(probe_url),
                safe_browsing.check(probe_url, client),
                virustotal.check(probe_url, client),
            ]
        )

    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
    except Exception:
        logger.exception("email_address_check_failed")
        raise HTTPException(
            status_code=503,
            detail="We couldn't check that address right now. Please try again.",
        )

    signals: list[CheckSignal] = []
    for res in results:
        if isinstance(res, CheckSignal):
            signals.append(res)
        else:
            signals.append(CheckSignal(source="unknown", available=False))

    response = aggregate(signals)
    response.total_duration_ms = int((time.perf_counter() - started) * 1000)

    logger.info(
        "email_address_check_completed",
        extra={"verdict": response.verdict, "score": response.score},
    )
    return response
