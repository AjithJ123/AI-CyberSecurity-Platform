"""Positive + negative cases for the offline URL heuristic checker."""

from app.checkers import heuristics


def test_safe_looking_url_scores_low() -> None:
    signal = heuristics.check("https://www.example.com/")
    assert signal.available is True
    assert signal.score < 25


def test_http_login_page_is_flagged() -> None:
    signal = heuristics.check("http://login-secure-update-account.tk/verify")
    assert signal.score >= 30
    assert any("HTTP" in reason for reason in signal.reasons)


def test_raw_ip_host_is_flagged() -> None:
    signal = heuristics.check("http://192.168.0.1/signin")
    assert signal.score >= 20
    assert any("IP address" in reason for reason in signal.reasons)
