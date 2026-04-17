"""Custom exceptions for the PhishGuard backend."""


class CheckerError(Exception):
    """Base class for all checker-related failures."""


class WhoisLookupError(CheckerError):
    """Raised when the WHOIS service is unreachable or returns unusable data."""


class SafeBrowsingError(CheckerError):
    """Raised when the Google Safe Browsing API fails."""


class VirusTotalError(CheckerError):
    """Raised when the VirusTotal API fails."""


class PhishTankError(CheckerError):
    """Raised when the PhishTank API fails."""


class AIAnalysisError(CheckerError):
    """Raised when the AI email analyzer fails."""
