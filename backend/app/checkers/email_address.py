"""Offline email-address heuristics.

Rate limit: none (local computation).
Failure mode: never fails — returns a signal with score 0 if nothing matches.

Checks:
    - syntactic validity
    - disposable / throwaway providers (mailinator, guerrillamail, ...)
    - typosquatting against common brands (paypa1 vs paypal, g00gle vs google)
    - suspicious TLDs
    - unusually long / obfuscated local parts
"""

from __future__ import annotations

import re

from app.models.schemas import CheckSignal

EMAIL_RE = re.compile(r"^[a-zA-Z0-9._%+\-]+@([a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})$")

# Well-known disposable providers. Not exhaustive but covers the top offenders.
DISPOSABLE_DOMAINS: set[str] = {
    "mailinator.com",
    "10minutemail.com",
    "10minutemail.net",
    "guerrillamail.com",
    "guerrillamail.net",
    "guerrillamail.org",
    "yopmail.com",
    "tempmail.com",
    "temp-mail.org",
    "trashmail.com",
    "dispostable.com",
    "maildrop.cc",
    "throwawaymail.com",
    "getairmail.com",
    "fakeinbox.com",
    "spam4.me",
    "sharklasers.com",
    "mytemp.email",
    "mohmal.com",
    "mailcatch.com",
    "emailondeck.com",
    "inboxbear.com",
    "nada.email",
}

# Common phishing targets. Case insensitive.
IMPERSONATED_BRANDS: tuple[str, ...] = (
    "paypal",
    "google",
    "gmail",
    "microsoft",
    "outlook",
    "apple",
    "icloud",
    "amazon",
    "netflix",
    "facebook",
    "instagram",
    "linkedin",
    "twitter",
    "whatsapp",
    "dhl",
    "fedex",
    "ups",
    "usps",
    "chase",
    "wellsfargo",
    "bankofamerica",
    "citibank",
    "hsbc",
    "barclays",
    "revolut",
    "binance",
    "coinbase",
)

SUSPICIOUS_TLDS: set[str] = {
    "tk",
    "ml",
    "ga",
    "cf",
    "gq",
    "zip",
    "mov",
    "xyz",
    "top",
    "click",
    "country",
    "kim",
    "work",
    "link",
}

# Characters that are commonly used to visually impersonate real letters in
# brand names. Mapping -> the "real" letter.
CONFUSABLES: dict[str, str] = {
    "0": "o",
    "1": "l",
    "3": "e",
    "5": "s",
    "7": "t",
    "@": "a",
    "$": "s",
}


def _normalize_for_typosquat(s: str) -> str:
    return "".join(CONFUSABLES.get(ch, ch) for ch in s.lower())


def _detect_typosquat(domain: str) -> str | None:
    """Return the impersonated brand, or None."""
    base = domain.split(".", 1)[0]
    normalized = _normalize_for_typosquat(base)

    for brand in IMPERSONATED_BRANDS:
        if base == brand:
            return None  # exact match of the base label is legit
        # Same base after confusable substitution → clear typosquat.
        if normalized == brand:
            return brand
        # Brand embedded in a longer label, e.g. "paypal-verify", "securepaypal".
        if brand in normalized and normalized != brand and len(normalized) <= len(brand) + 12:
            return brand
    return None


async def check(email: str) -> CheckSignal:
    reasons: list[str] = []
    score = 0

    cleaned = email.strip()
    match = EMAIL_RE.match(cleaned)
    if not match:
        return CheckSignal(
            source="email_address",
            available=True,
            score=50,
            reasons=["Address is not in a valid email format."],
            details={"email": cleaned, "domain": "", "valid_syntax": False},
        )

    domain = match.group(1).lower()
    local_part = cleaned.split("@", 1)[0]
    tld = domain.rsplit(".", 1)[-1]

    details: dict[str, object] = {
        "email": cleaned,
        "domain": domain,
        "local_part": local_part,
        "tld": tld,
        "valid_syntax": True,
        "disposable": False,
        "typosquat_of": None,
        "suspicious_tld": False,
    }

    if domain in DISPOSABLE_DOMAINS:
        score += 60
        reasons.append(f"{domain} is a disposable / throwaway email provider.")
        details["disposable"] = True

    if tld in SUSPICIOUS_TLDS:
        score += 25
        reasons.append(f"Uses a TLD (.{tld}) frequently abused for phishing.")
        details["suspicious_tld"] = True

    impersonated = _detect_typosquat(domain)
    if impersonated:
        score += 45
        reasons.append(
            f'Domain looks like a fake of "{impersonated}" — a real '
            f'{impersonated} address would end in {impersonated}.com.'
        )
        details["typosquat_of"] = impersonated

    if domain.count("-") >= 3:
        score += 10
        reasons.append("Domain has an unusually high number of hyphens.")

    if len(local_part) > 40:
        score += 10
        reasons.append("The name before @ is unusually long.")

    if len(domain) > 40:
        score += 10
        reasons.append("Domain name is unusually long.")

    if not reasons:
        reasons.append("No obvious red flags in the address itself.")

    return CheckSignal(
        source="email_address",
        available=True,
        score=min(score, 100),
        reasons=reasons,
        details=details,
    )
