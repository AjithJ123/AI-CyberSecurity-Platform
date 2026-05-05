"""POST /api/v1/writing/rewrite — rewrite text in the requested tone."""

import logging
import time

from fastapi import APIRouter, HTTPException, Request

from app.ai import writer
from app.exceptions import AIAnalysisError
from app.models.schemas import WritingRewriteRequest, WritingRewriteResponse
from app.rate_limit import limiter

router = APIRouter(tags=["writing"])
logger = logging.getLogger(__name__)


@router.post("/writing/rewrite", response_model=WritingRewriteResponse)
@limiter.limit("10/minute")
async def rewrite_text(request: Request, req: WritingRewriteRequest) -> WritingRewriteResponse:
    """Send text to the AI rewriter and return the cleaned-up version."""
    started = time.perf_counter()
    try:
        result = await writer.rewrite(req.text, req.tone)
    except AIAnalysisError as exc:
        logger.warning("writing_rewrite_failed", extra={"reason": str(exc)})
        raise HTTPException(
            status_code=503,
            detail="The writing assistant is unavailable right now. Please try again.",
        )

    rewritten: str = result["rewritten"]  # type: ignore[assignment]
    changes: list[str] = result["changes"]  # type: ignore[assignment]
    duration_ms = int((time.perf_counter() - started) * 1000)

    response = WritingRewriteResponse(
        original=req.text,
        rewritten=rewritten,
        tone=req.tone,
        changes=changes,
        original_word_count=writer.word_count(req.text),
        rewritten_word_count=writer.word_count(rewritten),
        duration_ms=duration_ms,
    )
    logger.info(
        "writing_rewrite_completed",
        extra={
            "tone": req.tone,
            "in_words": response.original_word_count,
            "out_words": response.rewritten_word_count,
            "duration_ms": duration_ms,
        },
    )
    return response
