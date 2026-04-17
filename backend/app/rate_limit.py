"""Shared rate-limiter.

CLAUDE.md requires every public endpoint to be rate-limited and forbids logging
user IPs in plaintext. We key the limiter on a hashed IP so the in-memory
counters can't be trivially reversed if the process is inspected.
"""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter

from app.utils.hashing import hash_ip


def _hashed_ip_key(request: Request) -> str:
    """Limiter key: SHA-256 prefix of the client IP (never the raw IP)."""
    client = request.client
    ip = client.host if client else "unknown"
    return hash_ip(ip)


limiter = Limiter(key_func=_hashed_ip_key)
