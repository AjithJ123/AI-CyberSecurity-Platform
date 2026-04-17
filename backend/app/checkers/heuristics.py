"""Offline URL heuristics — fast, no network.

Rate limit: none (local computation).
Failure mode: never fails; signal is always available.
"""

from __future__ import annotations

import unicodedata
from urllib.parse import urlparse

from app.models.schemas import CheckSignal

SUSPICIOUS_TLDS = {"zip", "mov", "xyz", "top", "click", "country", "kim", "work", "link"}
SENSITIVE_KEYWORDS = (
    "login",
    "verify",
    "account",
    "update",
    "secure",
    "banking",
    "password",
    "wallet",
    "signin",
    "confirm",
)


def _host_is_punycode(host: str) -> bool:
    return any(label.startswith("xn--") for label in host.split("."))


def _unicode_host(host: str) -> str | None:
    """Decode a punycode host to its Unicode form. Returns None if decode fails."""
    try:
        return host.encode("ascii").decode("idna")
    except (UnicodeError, UnicodeDecodeError):
        return None


def _detect_mixed_script(label: str) -> set[str]:
    """Return the set of Unicode scripts present in a label (letters only)."""
    scripts: set[str] = set()
    for ch in label:
        if not ch.isalpha():
            continue
        try:
            name = unicodedata.name(ch, "")
        except ValueError:
            continue
        # The Unicode name starts with the script, e.g. "CYRILLIC SMALL LETTER A".
        first = name.split(" ", 1)[0]
        if first in {
            "LATIN",
            "CYRILLIC",
            "GREEK",
            "ARMENIAN",
            "HEBREW",
            "ARABIC",
            "THAI",
            "DEVANAGARI",
            "CJK",
            "HIRAGANA",
            "KATAKANA",
            "HANGUL",
        }:
            scripts.add(first)
    return scripts


def check(url: str) -> CheckSignal:
    """Score an URL based on static heuristics.

    Args:
        url: The full URL to inspect.

    Returns:
        A CheckSignal with an accumulated suspicion score (0-100) and reasons.
    """
    reasons: list[str] = []
    score = 0

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path or ""
    full = url.lower()

    if parsed.scheme == "http":
        score += 15
        reasons.append("Uses plain HTTP instead of HTTPS.")

    if "@" in parsed.netloc:
        score += 25
        reasons.append("Contains '@' in the host — a known redirect trick.")

    if host and host.replace(".", "").isdigit():
        score += 20
        reasons.append("Uses a raw IP address instead of a domain name.")

    if host.count("-") >= 3:
        score += 10
        reasons.append("Domain has many hyphens, a common disguise technique.")

    if len(host) > 40:
        score += 10
        reasons.append("Domain name is unusually long.")

    tld = host.rsplit(".", 1)[-1] if "." in host else ""
    if tld in SUSPICIOUS_TLDS:
        score += 15
        reasons.append(f"Uses a TLD (.{tld}) frequently abused in phishing.")

    hits = [kw for kw in SENSITIVE_KEYWORDS if kw in full]
    if hits:
        score += min(20, 5 * len(hits))
        reasons.append(f"Contains sensitive keywords: {', '.join(hits)}.")

    if path.count("/") > 6:
        score += 5
        reasons.append("URL path is unusually deep.")

    # --- Punycode / homograph detection ---
    if _host_is_punycode(host):
        unicode_host = _unicode_host(host)
        score += 35
        if unicode_host and unicode_host != host:
            reasons.append(
                f"Domain uses punycode (displays as '{unicode_host}') — a common "
                "technique to impersonate real brands with look-alike letters."
            )
        else:
            reasons.append("Domain uses punycode encoding — treat with caution.")
    else:
        # Even without punycode, mixed scripts inside a single label are a
        # strong homograph signal (e.g. manual Unicode in the hostname).
        for label in host.split("."):
            scripts = _detect_mixed_script(label)
            if len(scripts) > 1:
                score += 30
                reasons.append(
                    "Domain mixes multiple writing systems "
                    f"({', '.join(sorted(scripts)).title()}) — possible homograph attack."
                )
                break

    return CheckSignal(
        source="heuristics",
        available=True,
        score=min(score, 100),
        reasons=reasons,
    )
