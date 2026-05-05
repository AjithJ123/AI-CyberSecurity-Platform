"""Writing rewrite endpoint."""

from __future__ import annotations

import certifi
import httpx
from groq import AsyncGroq
from fastapi import APIRouter, Request
from pydantic import BaseModel

from app.config import settings
from app.exceptions import CheckerError
from app.rate_limit import limiter

router = APIRouter(tags=["writing"])


class RewriteRequest(BaseModel):
    text: str
    tone: str = "natural"


class RewriteResponse(BaseModel):
    rewritten: str


def _get_groq_client() -> AsyncGroq:
    """Return Groq client with proper SSL verification."""
    http_client = httpx.AsyncClient(verify=certifi.where())
    return AsyncGroq(api_key=settings.groq_api_key, http_client=http_client)


@router.post("/writing/rewrite", response_model=RewriteResponse)
@limiter.limit("20/minute")
async def rewrite_text(request: Request, body: RewriteRequest) -> RewriteResponse:
    """Rewrite text in the requested tone using Groq AI."""
    try:
        client = _get_groq_client()

        prompt = (
            f"Rewrite the following text in a {body.tone} tone. "
            f"Return only the rewritten text, no explanations.\n\n"
            f"Text: {body.text}"
        )

        response = await client.chat.completions.create(
            model="llama3-8b-8192",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1024,
            temperature=0.7,
        )

        rewritten = response.choices[0].message.content.strip()
        return RewriteResponse(rewritten=rewritten)

    except Exception as exc:
        raise CheckerError("Writing assistant unavailable") from exc