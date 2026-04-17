"""Combine per-checker signals into a single verdict.

Scoring weights live here and only here — never inside checker modules.
Any weight change must come with tests showing the new score on fixture data.
"""

from __future__ import annotations

from app.models.schemas import CheckResponse, CheckSignal, Verdict

# Per-source weights. Weights are renormalized at use-time across whichever
# sources are actually available on a given request.
WEIGHTS: dict[str, float] = {
    "safe_browsing": 0.35,
    "virustotal": 0.25,
    "phishtank": 0.20,
    "whois": 0.10,
    "heuristics": 0.10,
    # For the email endpoint the AI is the only signal — weight 1.0 keeps its
    # score as-is when it's the only available source.
    "ai": 1.0,
    # Email-address check: the address heuristics carry most of the weight,
    # domain-level lookups reinforce them.
    "email_address": 0.45,
    # Shortener check: informational only; the expanded URL runs through the
    # other checkers which carry the real weight.
    "shortener": 0.05,
}

SAFE_THRESHOLD = 25
SUSPICIOUS_THRESHOLD = 60  # inclusive upper bound for "suspicious"


def _verdict_for(score: int) -> Verdict:
    if score < SAFE_THRESHOLD:
        return "safe"
    if score < SUSPICIOUS_THRESHOLD:
        return "suspicious"
    return "dangerous"


def _recommendation(verdict: Verdict) -> str:
    if verdict == "safe":
        return "No red flags were found, but still double-check the sender and context before acting."
    if verdict == "suspicious":
        return "Be careful. Don't enter passwords or payment info. Verify with the supposed sender."
    return "Do not click, open, or enter any information. Report the message and delete it."


def aggregate(signals: list[CheckSignal]) -> CheckResponse:
    """Combine signals into a single CheckResponse."""
    available = [s for s in signals if s.available]

    if not available:
        return CheckResponse(
            verdict="suspicious",
            score=50,
            reasons=["No check could complete right now — treat this result with caution."],
            recommendation=_recommendation("suspicious"),
            signals=signals,
        )

    # Renormalize weights across the available sources.
    raw_weights = {s.source: WEIGHTS.get(s.source, 0.0) for s in available}
    total = sum(raw_weights.values()) or 1.0
    weighted_score = sum(s.score * (raw_weights[s.source] / total) for s in available)
    score = int(round(weighted_score))

    verdict = _verdict_for(score)
    reasons: list[str] = []
    for s in available:
        reasons.extend(s.reasons)

    return CheckResponse(
        verdict=verdict,
        score=score,
        reasons=reasons,
        recommendation=_recommendation(verdict),
        signals=signals,
    )
