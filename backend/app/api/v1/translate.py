"""POST /api/v1/translate — context-aware translation."""

import logging
import time

from fastapi import APIRouter, HTTPException, Request

from app.ai import translator
from app.exceptions import AIAnalysisError
from app.models.schemas import TranslateRequest, TranslateResponse
from app.rate_limit import limiter

router = APIRouter(tags=["translate"])
logger = logging.getLogger(__name__)


@router.post("/translate", response_model=TranslateResponse)
@limiter.limit("12/minute")
async def translate_text(request: Request, req: TranslateRequest) -> TranslateResponse:
    started = time.perf_counter()
    try:
        result = await translator.translate(
            req.text,
            req.source,
            req.target,
            req.formality,
            req.preserve_tone,
        )
    except AIAnalysisError as exc:
        logger.warning("translate_failed", extra={"reason": str(exc)})
        raise HTTPException(
            status_code=503,
            detail="The translator is unavailable right now. Please try again.",
        )

    duration_ms = int((time.perf_counter() - started) * 1000)
    response = TranslateResponse(
        source_detected=result["source_detected"],    # type: ignore[arg-type]
        target=req.target,
        formality=req.formality,
        translated=result["translated"],              # type: ignore[arg-type]
        alternative=result["alternative"],            # type: ignore[arg-type]
        notes=result["notes"],                        # type: ignore[arg-type]
        word_count=translator.word_count(result["translated"]),  # type: ignore[arg-type]
        duration_ms=duration_ms,
    )
    logger.info(
        "translate_completed",
        extra={
            "source": response.source_detected,
            "target": req.target,
            "formality": req.formality,
            "words": response.word_count,
            "duration_ms": duration_ms,
        },
    )
    return response
