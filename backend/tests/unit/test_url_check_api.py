"""Happy-path + error-path tests for POST /api/v1/check/url."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.schemas import CheckSignal


@pytest.fixture(autouse=True)
def _mock_checkers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace network-bound checkers with deterministic fakes."""
    from app.checkers import phishtank, safe_browsing, virustotal, whois_check

    async def _clean_signal(*_args: Any, **_kwargs: Any) -> CheckSignal:
        return CheckSignal(source="stub", available=True, score=0, reasons=["clean"])

    monkeypatch.setattr(whois_check, "check", _clean_signal)
    monkeypatch.setattr(safe_browsing, "check", _clean_signal)
    monkeypatch.setattr(virustotal, "check", _clean_signal)
    monkeypatch.setattr(phishtank, "check", _clean_signal)


def test_check_url_happy_path() -> None:
    client = TestClient(app)
    resp = client.post("/api/v1/check/url", json={"url": "https://www.example.com/"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["verdict"] in {"safe", "suspicious", "dangerous"}
    assert isinstance(body["reasons"], list)


def test_check_url_rejects_invalid_url() -> None:
    client = TestClient(app)
    resp = client.post("/api/v1/check/url", json={"url": "not-a-url"})
    assert resp.status_code == 422
