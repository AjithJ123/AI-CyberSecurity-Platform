"""Verdict aggregation: safe, suspicious, dangerous, and unavailable cases."""

from app.models.schemas import CheckSignal
from app.scoring.aggregator import aggregate


def test_safe_when_all_signals_are_clean() -> None:
    signals = [
        CheckSignal(source="safe_browsing", available=True, score=0, reasons=["clean"]),
        CheckSignal(source="virustotal", available=True, score=0, reasons=["clean"]),
        CheckSignal(source="heuristics", available=True, score=5, reasons=["tiny noise"]),
    ]
    response = aggregate(signals)
    assert response.verdict == "safe"
    assert response.score < 25


def test_dangerous_when_threat_feed_hits() -> None:
    signals = [
        CheckSignal(source="safe_browsing", available=True, score=90, reasons=["malware"]),
        CheckSignal(source="heuristics", available=True, score=30, reasons=["bad tld"]),
    ]
    response = aggregate(signals)
    assert response.verdict == "dangerous"
    assert response.score >= 60


def test_all_unavailable_returns_cautious_suspicious() -> None:
    signals = [CheckSignal(source="safe_browsing", available=False)]
    response = aggregate(signals)
    assert response.verdict == "suspicious"
    assert "couldn't" in response.recommendation.lower() or "cautio" in response.reasons[0].lower()
