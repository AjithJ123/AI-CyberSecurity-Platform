"""POST /api/v1/check/email — analyze an email body for phishing indicators."""

import logging

from fastapi import APIRouter, HTTPException, Request

from app.ai import email_analyzer
from app.exceptions import AIAnalysisError
from app.models.schemas import CheckResponse, CheckSignal, EmailCheckRequest
from app.rate_limit import limiter
from app.scoring.aggregator import aggregate

router = APIRouter(tags=["checks"])
logger = logging.getLogger(__name__)


@router.post("/check/email", response_model=CheckResponse)
@limiter.limit("10/minute")
async def check_email(request: Request, req: EmailCheckRequest) -> CheckResponse:
    """Analyze an email body using Claude and return a verdict."""
    try:
        ai_signal: CheckSignal = await email_analyzer.analyze(
            subject=req.subject,
            sender=req.sender,
            body=req.body,
        )
    except AIAnalysisError:
        logger.warning("email_check_ai_unavailable")
        raise HTTPException(
            status_code=503,
            detail="Email analysis is temporarily unavailable. Please try again.",
        )

    # For v1, the email pipeline is AI-only. Weight it as 1.0 via a single signal.
    response = aggregate([ai_signal])
    logger.info("email_check_completed", extra={"verdict": response.verdict, "score": response.score})
    return response
