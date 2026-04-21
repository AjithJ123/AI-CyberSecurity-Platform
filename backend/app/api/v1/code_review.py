"""POST /api/v1/code/review — AI-assisted code review."""

import logging
import time

from fastapi import APIRouter, HTTPException, Request

from app.ai import reviewer
from app.exceptions import AIAnalysisError
from app.models.schemas import (
    CodeIssue,
    CodeReviewRequest,
    CodeReviewResponse,
)
from app.rate_limit import limiter

router = APIRouter(tags=["code"])
logger = logging.getLogger(__name__)


@router.post("/code/review", response_model=CodeReviewResponse)
@limiter.limit("8/minute")
async def review_code(request: Request, req: CodeReviewRequest) -> CodeReviewResponse:
    started = time.perf_counter()
    try:
        result = await reviewer.review(req.code, req.language, req.context)
    except AIAnalysisError as exc:
        logger.warning("code_review_failed", extra={"reason": str(exc)})
        raise HTTPException(
            status_code=503,
            detail="The code reviewer is unavailable right now. Please try again.",
        )

    issues = [CodeIssue(**i) for i in result["issues"]]  # type: ignore[arg-type]
    duration_ms = int((time.perf_counter() - started) * 1000)

    response = CodeReviewResponse(
        summary=result["summary"],         # type: ignore[arg-type]
        language_detected=result["language_detected"],  # type: ignore[arg-type]
        overall_quality=result["overall_quality"],      # type: ignore[arg-type]
        issues=issues,
        positives=result["positives"],                  # type: ignore[arg-type]
        line_count=reviewer.line_count(req.code),
        duration_ms=duration_ms,
    )
    logger.info(
        "code_review_completed",
        extra={
            "language": req.language,
            "lines": response.line_count,
            "issues": len(issues),
            "duration_ms": duration_ms,
        },
    )
    return response
