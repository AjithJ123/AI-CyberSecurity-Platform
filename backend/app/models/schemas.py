"""Pydantic request and response models for the PhishGuard API."""

from typing import Any, Literal

from pydantic import BaseModel, Field, HttpUrl

Verdict = Literal["safe", "suspicious", "dangerous"]


class URLCheckRequest(BaseModel):
    """Input for POST /api/v1/check/url."""

    url: HttpUrl


class EmailCheckRequest(BaseModel):
    """Input for POST /api/v1/check/email."""

    subject: str = Field(default="", max_length=500)
    sender: str = Field(default="", max_length=500)
    body: str = Field(..., min_length=1, max_length=10_000)


class EmailAddressCheckRequest(BaseModel):
    """Input for POST /api/v1/check/email-address."""

    email: str = Field(..., min_length=3, max_length=320)


class CheckSignal(BaseModel):
    """A single signal contributed by one checker module."""

    source: str
    available: bool = True
    score: int = 0  # 0..100, higher = more suspicious
    reasons: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)
    duration_ms: int = 0


class UrlAnatomy(BaseModel):
    """Parsed view of the URL being checked."""

    full: str
    scheme: str
    host: str
    port: int | None = None
    path: str
    tld: str
    subdomain_count: int
    query_param_count: int
    has_userinfo: bool


class CheckResponse(BaseModel):
    """Common response shape for URL and email checks."""

    verdict: Verdict
    score: int  # 0..100
    reasons: list[str]
    recommendation: str
    signals: list[CheckSignal] = Field(default_factory=list)
    anatomy: UrlAnatomy | None = None
    total_duration_ms: int = 0
    original_url: str = ""
    expanded_url: str = ""
