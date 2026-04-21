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


WritingTone = Literal["natural", "professional", "concise", "friendly"]


class WritingRewriteRequest(BaseModel):
    """Input for POST /api/v1/writing/rewrite."""

    text: str = Field(..., min_length=1, max_length=8000)
    tone: WritingTone = "natural"


class WritingRewriteResponse(BaseModel):
    """Output for the writing rewriter."""

    original: str
    rewritten: str
    tone: WritingTone
    changes: list[str] = Field(default_factory=list)
    original_word_count: int
    rewritten_word_count: int
    duration_ms: int = 0


CodeLanguage = Literal[
    "auto",
    "python",
    "javascript",
    "typescript",
    "java",
    "go",
    "rust",
    "cpp",
    "csharp",
    "ruby",
    "php",
    "sql",
    "bash",
    "html",
    "css",
    "other",
]

Severity = Literal["bug", "security", "readability", "style"]


class CodeReviewRequest(BaseModel):
    """Input for POST /api/v1/code/review."""

    code: str = Field(..., min_length=1, max_length=12_000)
    language: CodeLanguage = "auto"
    context: str = Field(default="", max_length=500)


class CodeIssue(BaseModel):
    """A single reported issue in the reviewed code."""

    severity: Severity
    line: int | None = None
    message: str
    suggestion: str = ""


class CodeReviewResponse(BaseModel):
    """Output for the code reviewer."""

    summary: str
    language_detected: str
    overall_quality: int  # 1..10
    issues: list[CodeIssue] = Field(default_factory=list)
    positives: list[str] = Field(default_factory=list)
    line_count: int
    duration_ms: int = 0


class ImageAnalyzeRequest(BaseModel):
    """Input for POST /api/v1/image/analyze.

    The image arrives as a full data URL from the browser, e.g.
    ``data:image/png;base64,iVBORw0KGgoA...``.
    """

    image_data_url: str = Field(..., min_length=30, max_length=12_000_000)
    filename: str = Field(default="", max_length=200)


class ImageAnalyzeResponse(BaseModel):
    """Output for the image analyzer."""

    description: str
    has_text: bool
    ocr_text: str
    ai_generated_score: int  # 0..100, higher = more likely AI-generated
    ai_generated_reasons: list[str] = Field(default_factory=list)
    subjects: list[str] = Field(default_factory=list)
    content_warnings: list[str] = Field(default_factory=list)
    model: str
    duration_ms: int = 0


class DataSummaryRequest(BaseModel):
    """Input for POST /api/v1/data/summarize."""

    data: str = Field(..., min_length=3, max_length=60_000)
    context: str = Field(default="", max_length=500)


class DataOutlier(BaseModel):
    """A single row or value the analyst flagged as unusual."""

    description: str
    detail: str = ""


class DataColumnStat(BaseModel):
    """Per-column summary computed locally before we call the model."""

    name: str
    type: Literal["numeric", "text", "date", "boolean", "empty", "mixed"]
    non_empty: int
    unique: int
    min: str = ""
    max: str = ""
    mean: float | None = None
    sample_values: list[str] = Field(default_factory=list)


class DataSummaryResponse(BaseModel):
    """Output for the data summarizer."""

    summary: str
    row_count: int
    column_count: int
    delimiter: str
    highlights: list[str] = Field(default_factory=list)
    outliers: list[DataOutlier] = Field(default_factory=list)
    columns: list[DataColumnStat] = Field(default_factory=list)
    truncated: bool = False
    duration_ms: int = 0


class TranslateRequest(BaseModel):
    """Input for POST /api/v1/translate."""

    text: str = Field(..., min_length=1, max_length=8000)
    source: str = Field(default="auto", max_length=40)   # "auto" or ISO-ish code / name
    target: str = Field(..., min_length=2, max_length=40)
    formality: Literal["default", "formal", "casual"] = "default"
    preserve_tone: bool = True


class TranslateResponse(BaseModel):
    """Output for the translator."""

    source_detected: str
    target: str
    formality: str
    translated: str
    alternative: str = ""
    notes: list[str] = Field(default_factory=list)
    word_count: int
    duration_ms: int = 0


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
