"""POST /api/v1/data/summarize — narrate a tabular dataset."""

import logging
import time

from fastapi import APIRouter, HTTPException, Request

from app.ai import summarizer
from app.exceptions import AIAnalysisError
from app.models.schemas import (
    DataColumnStat,
    DataOutlier,
    DataSummaryRequest,
    DataSummaryResponse,
)
from app.rate_limit import limiter

router = APIRouter(tags=["data"])
logger = logging.getLogger(__name__)


@router.post("/data/summarize", response_model=DataSummaryResponse)
@limiter.limit("8/minute")
async def summarize_data(
    request: Request,
    req: DataSummaryRequest,
) -> DataSummaryResponse:
    started = time.perf_counter()
    try:
        result = await summarizer.summarize(
            req.data,
            req.context,
            total_rows_hint=req.total_rows_hint,
            file_size_bytes=req.file_size_bytes,
        )
    except AIAnalysisError as exc:
        logger.warning("data_summary_failed", extra={"reason": str(exc)})
        raise HTTPException(
            status_code=503,
            detail="The data summarizer is unavailable right now. Please try again.",
        )

    duration_ms = int((time.perf_counter() - started) * 1000)
    response = DataSummaryResponse(
        summary=result["summary"],                     # type: ignore[arg-type]
        row_count=result["row_count"],                 # type: ignore[arg-type]
        sampled_row_count=result.get("sampled_row_count", 0),  # type: ignore[arg-type]
        column_count=result["column_count"],           # type: ignore[arg-type]
        delimiter=result["delimiter"],                 # type: ignore[arg-type]
        highlights=result["highlights"],               # type: ignore[arg-type]
        outliers=[DataOutlier(**o) for o in result["outliers"]],  # type: ignore[arg-type]
        columns=[DataColumnStat(**c) for c in result["columns"]],  # type: ignore[arg-type]
        truncated=bool(result["truncated"]),           # type: ignore[arg-type]
        duration_ms=duration_ms,
    )
    logger.info(
        "data_summary_completed",
        extra={
            "rows": response.row_count,
            "cols": response.column_count,
            "duration_ms": duration_ms,
        },
    )
    return response
