"""FastAPI app entry point."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api.v1 import (
    code_review,
    data_summary,
    email_address_check,
    email_check,
    image_analyze,
    translate,
    url_check,
    writing_check,
)
from app.config import settings
from app.exceptions import CheckerError
from app.rate_limit import limiter

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

app = FastAPI(
    title="Helix",
    version="1.0.0",
    description="A growing suite of AI tools. First module: phishing-threat scanner for URLs and emails.",
)

# Rate limiting — per-endpoint decorators live on the individual routers.
# We do NOT use SlowAPIMiddleware because it interferes with CORS preflight.
app.state.limiter = limiter

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.exception_handler(RateLimitExceeded)
async def rate_limit_handler(_: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Plain-English 429 — no stack, no leaked internals."""
    return JSONResponse(
        status_code=429,
        content={"detail": "Too many checks. Please slow down and try again in a minute."},
    )


@app.exception_handler(CheckerError)
async def checker_error_handler(_: Request, exc: CheckerError) -> JSONResponse:
    """Convert internal checker errors into safe 503 responses."""
    return JSONResponse(
        status_code=503,
        content={"detail": "A check service is temporarily unavailable. Please try again."},
    )


@app.get("/", tags=["meta"])
async def root() -> dict[str, str]:
    return {"name": "Helix", "version": "1.0.0"}


@app.get("/health", tags=["meta"])
async def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(url_check.router, prefix="/api/v1")
app.include_router(email_check.router, prefix="/api/v1")
app.include_router(email_address_check.router, prefix="/api/v1")
app.include_router(writing_check.router, prefix="/api/v1")
app.include_router(code_review.router, prefix="/api/v1")
app.include_router(image_analyze.router, prefix="/api/v1")
app.include_router(data_summary.router, prefix="/api/v1")
app.include_router(translate.router, prefix="/api/v1")
