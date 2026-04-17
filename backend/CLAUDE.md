# CLAUDE.md — Backend (Python + FastAPI)

Rules for writing Python code in the `backend/` folder. Read the root `CLAUDE.md` first.

---

## 1. Stack and Versions

- **Python:** 3.11 or newer (no 3.10 syntax workarounds needed).
- **Framework:** FastAPI.
- **HTTP client:** `httpx` with `AsyncClient` — never `requests` (blocks the event loop).
- **Validation:** Pydantic v2.
- **Testing:** pytest + pytest-asyncio.
- **Formatter:** Black (line length 100).
- **Linter:** Ruff.
- **Type checker:** mypy (strict mode on new files).

---

## 2. Folder Structure

```
backend/
├── app/
│   ├── main.py              # FastAPI app instance, router registration
│   ├── config.py            # Settings loaded from env
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── url_check.py
│   │       └── email_check.py
│   ├── checkers/            # One file per external source
│   │   ├── whois_check.py
│   │   ├── safe_browsing.py
│   │   ├── virustotal.py
│   │   └── phishtank.py
│   ├── scoring/             # Verdict logic
│   │   └── aggregator.py
│   ├── ai/                  # Claude API calls, prompts
│   │   └── email_analyzer.py
│   ├── models/              # Pydantic request/response models
│   └── utils/
├── tests/
├── requirements.txt
├── .env.example
└── CLAUDE.md                # This file
```

**Rule:** one external source = one file in `checkers/`. Don't mix them.

---

## 3. Coding Style

### 3.1 General
- Follow PEP 8. Black + Ruff enforce this automatically.
- Max line length: 100 characters.
- Use f-strings for formatting. Never `%` or `.format()`.
- Prefer `pathlib.Path` over `os.path`.

### 3.2 Type hints are mandatory
Every function signature must have type hints. No exceptions on new code.

```python
# Good
async def check_url(url: str) -> URLCheckResult:
    ...

# Bad
async def check_url(url):
    ...
```

### 3.3 Docstrings
Public functions and classes get a docstring. Use Google style.

```python
async def check_domain_age(domain: str) -> int:
    """Return the age of a domain in days.

    Args:
        domain: The domain to check, without scheme (e.g. "example.com").

    Returns:
        Number of days since registration. Returns -1 if unknown.

    Raises:
        WhoisLookupError: If the WHOIS service is unreachable.
    """
```

### 3.4 Naming
- Functions and variables: `snake_case`.
- Classes: `PascalCase`.
- Constants: `UPPER_SNAKE_CASE`.
- Private helpers: prefix with `_`.

---

## 4. FastAPI Patterns

### 4.1 Use Pydantic models for every request and response
Never accept `dict` or return raw dicts from endpoints.

```python
# Good
from pydantic import BaseModel, HttpUrl

class URLCheckRequest(BaseModel):
    url: HttpUrl

class URLCheckResponse(BaseModel):
    verdict: Literal["safe", "suspicious", "dangerous"]
    score: int
    reasons: list[str]
    recommendation: str

@router.post("/check/url", response_model=URLCheckResponse)
async def check_url(req: URLCheckRequest) -> URLCheckResponse:
    ...
```

### 4.2 Use dependency injection for shared resources
HTTP clients, DB connections, settings — inject them, don't create them inside handlers.

```python
async def get_http_client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient(timeout=10.0) as client:
        yield client

@router.post("/check/url")
async def check_url(
    req: URLCheckRequest,
    client: httpx.AsyncClient = Depends(get_http_client),
) -> URLCheckResponse:
    ...
```

### 4.3 Versioned routes
All routes live under `/api/v1/`. Never skip the version.

### 4.4 Use `async def` for endpoints
Every endpoint is async. External API calls use `await`. No sync I/O in request handlers.

---

## 5. External API Calls

### 5.1 Always set a timeout
Default timeout: 10 seconds. Never make a request without one.

```python
async with httpx.AsyncClient(timeout=10.0) as client:
    resp = await client.get(url)
```

### 5.2 Handle failures gracefully
If an external API fails, return a partial result with that source marked as unavailable — don't fail the whole request.

```python
try:
    result = await safe_browsing.check(url)
except httpx.HTTPError as e:
    logger.warning("Safe Browsing unavailable", extra={"error": str(e)})
    result = CheckSignal(source="safe_browsing", available=False)
```

### 5.3 Cache aggressively
Use an in-memory LRU cache for identical URLs within a 5-minute window. Most phishing checks hit the same URL multiple times fast.

### 5.4 Never log the full URL of a user-submitted check
Log a hash or a truncated version only.

---

## 6. Error Handling

### 6.1 Use custom exceptions
Define exceptions in `app/exceptions.py`. Don't raise generic `Exception`.

```python
class CheckerError(Exception):
    """Base for all checker failures."""

class WhoisLookupError(CheckerError):
    pass
```

### 6.2 Convert to HTTP responses in one place
Use FastAPI exception handlers in `main.py`. Don't catch and re-raise `HTTPException` in every handler.

### 6.3 Never leak internal errors to the user
```python
# Good
raise HTTPException(status_code=503, detail="Unable to analyze URL right now. Please try again.")

# Bad
raise HTTPException(status_code=500, detail=str(e))  # leaks stack info
```

---

## 7. Configuration and Secrets

Use `pydantic-settings` for config.

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    google_safe_browsing_api_key: str
    virustotal_api_key: str
    anthropic_api_key: str
    redis_url: str = "redis://localhost:6379"
    environment: Literal["dev", "staging", "prod"] = "dev"

    class Config:
        env_file = ".env"
```

**Never** hardcode a key, even a test one. Use `.env.example` with placeholder values.

---

## 8. Testing

### 8.1 Structure
```
tests/
├── unit/            # Fast, no network
├── integration/     # Hit real APIs (run manually, not in CI)
└── fixtures/
    ├── phishing_urls.txt
    └── safe_urls.txt
```

### 8.2 Rules
- Every endpoint has a test in `tests/unit/api/`.
- External APIs are **mocked in unit tests** using `respx` or `httpx.MockTransport`.
- Use `pytest.fixture` for shared setup.
- Aim for 80%+ coverage, but don't chase it at the cost of meaningful tests.

### 8.3 Example
```python
@pytest.mark.asyncio
async def test_check_url_dangerous(mock_safe_browsing):
    mock_safe_browsing.add_malicious("http://bad.example")
    response = await client.post("/api/v1/check/url", json={"url": "http://bad.example"})
    assert response.status_code == 200
    assert response.json()["verdict"] == "dangerous"
```

---

## 9. Logging

Use structured logging with `structlog` or the stdlib `logging` with JSON formatter.

```python
logger.info("url_check_completed", extra={
    "url_hash": hash_url(url),
    "verdict": verdict,
    "duration_ms": duration,
})
```

**Never log:** full submitted URLs, email bodies, user IPs in plaintext, API keys.

---

## 10. Performance Targets

- p50 response time: under 2 seconds.
- p95 response time: under 6 seconds.
- If a checker consistently takes over 3s, either parallelize it with `asyncio.gather` or move it to a background job.

---

## 11. Scoring Engine

- Scoring logic lives only in `app/scoring/`.
- Signal weights are defined as constants at the top of the file.
- Never hardcode scoring numbers inside checker modules.
- Any weight change requires a PR that includes updated tests showing the new score on fixture data.

---

## 12. Common Mistakes to Avoid

- **Using `requests` instead of `httpx`.** Breaks async.
- **Forgetting `await` on async calls.** The call returns a coroutine object, not a result.
- **Catching `Exception` broadly.** Catch specific exceptions.
- **Passing raw dicts through the API.** Use Pydantic models.
- **Making DB or network calls in `__init__`.** Use FastAPI's lifespan events instead.
- **Mutating Pydantic models in place.** Create new ones with `.model_copy(update=...)`.

---

## 13. When Adding a New Checker

1. Create `app/checkers/<name>.py`.
2. Implement a function returning `CheckSignal`.
3. Register it in the scoring aggregator.
4. Add unit tests with mocked responses.
5. Add the API key (if any) to `.env.example` and `config.py`.
6. Document the source, rate limit, and failure mode in a docstring at the top of the file.
