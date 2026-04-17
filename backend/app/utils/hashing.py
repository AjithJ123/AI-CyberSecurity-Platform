"""Hashing helpers — used for privacy-preserving logging."""

import hashlib


def hash_url(url: str) -> str:
    """Return a short hex digest for a URL, safe for logs.

    We only need collision resistance for debugging, not cryptographic strength.
    """
    return hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]


def hash_ip(ip: str) -> str:
    """Return a hashed IP suitable for rate-limit keys."""
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:24]
