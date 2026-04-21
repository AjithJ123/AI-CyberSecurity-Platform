"""POST /api/v1/image/analyze — vision-model image analysis."""

import logging
import time

from fastapi import APIRouter, HTTPException, Request

from app.ai import image_analyzer
from app.exceptions import AIAnalysisError
from app.models.schemas import ImageAnalyzeRequest, ImageAnalyzeResponse
from app.rate_limit import limiter

router = APIRouter(tags=["image"])
logger = logging.getLogger(__name__)


@router.post("/image/analyze", response_model=ImageAnalyzeResponse)
@limiter.limit("6/minute")
async def analyze_image(
    request: Request,
    req: ImageAnalyzeRequest,
) -> ImageAnalyzeResponse:
    started = time.perf_counter()
    try:
        result = await image_analyzer.analyze(req.image_data_url)
    except AIAnalysisError as exc:
        logger.warning("image_analyze_failed", extra={"reason": str(exc)})
        raise HTTPException(
            status_code=503,
            detail="The image analyzer is unavailable right now. Please try again.",
        )

    duration_ms = int((time.perf_counter() - started) * 1000)
    response = ImageAnalyzeResponse(
        description=result["description"],            # type: ignore[arg-type]
        has_text=result["has_text"],                  # type: ignore[arg-type]
        ocr_text=result["ocr_text"],                  # type: ignore[arg-type]
        ai_generated_score=result["ai_generated_score"],  # type: ignore[arg-type]
        ai_generated_reasons=result["ai_generated_reasons"],  # type: ignore[arg-type]
        subjects=result["subjects"],                  # type: ignore[arg-type]
        content_warnings=result["content_warnings"],  # type: ignore[arg-type]
        model=result["model"],                        # type: ignore[arg-type]
        duration_ms=duration_ms,
    )
    logger.info(
        "image_analyze_completed",
        extra={
            "ai_score": response.ai_generated_score,
            "has_text": response.has_text,
            "duration_ms": duration_ms,
        },
    )
    return response
