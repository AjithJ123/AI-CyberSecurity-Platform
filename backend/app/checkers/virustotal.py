"""VirusTotal URL reputation lookup.

Source: https://www.virustotal.com/api/v3/urls/{id}
Rate limit: 4 requests/min on the free public API.
Failure mode: returns unavailable if the key is missing or the request fails.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.models.schemas import CheckSignal

BASE = "https://www.virustotal.com/api/v3"

# Map raw VirusTotal engine labels (often single lowercase words) to friendlier
# human-readable titles. Anything not in the map is just Title-Cased.
LABEL_MAP: dict[str, str] = {
    "phishing": "Phishing site",
    "phish": "Phishing site",
    "malicious": "Malicious site",
    "malicious site": "Malicious site",
    "malware": "Malware",
    "malware site": "Malware",
    "suspicious": "Suspicious",
    "spam": "Spam",
    "scam": "Scam",
    "fraud": "Fraud",
    "flagged": "Flagged",
    "unspecified": "Flagged",
    "unrated site": "Unrated site",
    "clean site": "Clean",
}


def _friendly_label(raw: str) -> str:
    key = raw.strip().lower()
    if key in LABEL_MAP:
        return LABEL_MAP[key]
    # Title-case anything else so it reads nicely.
    return " ".join(word.capitalize() for word in key.split())


def _url_id(url: str) -> str:
    """VirusTotal uses URL-safe base64 of the URL, stripped of padding."""
    return base64.urlsafe_b64encode(url.encode("utf-8")).decode("utf-8").strip("=")


async def check(url: str, client: httpx.AsyncClient) -> CheckSignal:
    """Query VirusTotal for this URL's community verdicts."""
    api_key = settings.virustotal_api_key
    if not api_key:
        return CheckSignal(source="virustotal", available=False)

    headers = {"x-apikey": api_key}
    try:
        resp = await client.get(f"{BASE}/urls/{_url_id(url)}", headers=headers, timeout=10.0)
    except httpx.HTTPError:
        return CheckSignal(source="virustotal", available=False)

    if resp.status_code == 404:
        return CheckSignal(
            source="virustotal",
            available=True,
            score=0,
            reasons=["VirusTotal has no record of this URL."],
        )
    if resp.status_code != 200:
        return CheckSignal(source="virustotal", available=False)

    data = resp.json()
    attributes = data.get("data", {}).get("attributes", {})
    stats = attributes.get("last_analysis_stats", {}) or {}
    results = attributes.get("last_analysis_results", {}) or {}
    categories = attributes.get("categories", {}) or {}
    votes = attributes.get("total_votes", {}) or {}
    reputation = attributes.get("reputation", 0)
    times_submitted = attributes.get("times_submitted", 0)
    last_analysis_ts = attributes.get("last_analysis_date")

    malicious = int(stats.get("malicious", 0))
    suspicious = int(stats.get("suspicious", 0))
    harmless = int(stats.get("harmless", 0))
    undetected = int(stats.get("undetected", 0))
    timeout = int(stats.get("timeout", 0))
    total = malicious + suspicious + harmless + undetected + timeout or 1
    hits = malicious + suspicious

    # Per-engine detections with their threat label. Labels are normalized to
    # friendly, human-readable titles (e.g. "phishing" -> "Phishing site").
    detections: list[dict[str, str]] = []
    by_label: dict[str, int] = {}
    for engine, info in results.items():
        if not isinstance(info, dict):
            continue
        category = info.get("category", "")
        if category not in {"malicious", "suspicious"}:
            continue
        raw_label = (info.get("result") or "flagged").strip() or "flagged"
        label = _friendly_label(raw_label)
        detections.append(
            {"engine": engine, "label": label, "category": category}
        )
        by_label[label] = by_label.get(label, 0) + 1

    detections.sort(key=lambda e: e["engine"].lower())

    # Format the last analysis date for humans.
    last_analysis_human = ""
    if isinstance(last_analysis_ts, (int, float)) and last_analysis_ts > 0:
        dt = datetime.fromtimestamp(last_analysis_ts, tz=timezone.utc)
        last_analysis_human = dt.strftime("%Y-%m-%d %H:%M UTC")

    # Pick the most common vendor categories (e.g. "malicious site", "phishing").
    category_labels = sorted({v for v in categories.values() if isinstance(v, str)})

    details = {
        "stats": {
            "malicious": malicious,
            "suspicious": suspicious,
            "harmless": harmless,
            "undetected": undetected,
            "timeout": timeout,
            "total": total,
        },
        "detections": detections,
        "threat_groups": [
            {"label": k, "count": v}
            for k, v in sorted(by_label.items(), key=lambda kv: -kv[1])
        ],
        "categories": category_labels,
        "vendor_categories": categories,
        "reputation": int(reputation) if isinstance(reputation, int) else 0,
        "community_votes": {
            "harmless": int(votes.get("harmless", 0)),
            "malicious": int(votes.get("malicious", 0)),
        },
        "times_submitted": int(times_submitted) if isinstance(times_submitted, int) else 0,
        "last_analysis": last_analysis_human,
    }

    if hits == 0:
        return CheckSignal(
            source="virustotal",
            available=True,
            score=0,
            reasons=["No VirusTotal engines flagged this URL."],
            details=details,
        )

    reasons = [f"{hits} of {total} VirusTotal engines flagged this URL."]
    if by_label:
        top = ", ".join(f"{k} ({v})" for k, v in sorted(by_label.items(), key=lambda kv: -kv[1])[:5])
        reasons.append(f"Top threat labels: {top}.")
    if category_labels:
        reasons.append(f"Vendor categories: {', '.join(category_labels[:4])}.")
    if detections:
        reasons.append("Engines that flagged it:")
        reasons.extend(f"{d['engine']}: {d['label']}" for d in detections)

    ratio = hits / total
    score = min(int(ratio * 100) + 20, 95)
    return CheckSignal(
        source="virustotal",
        available=True,
        score=score,
        reasons=reasons,
        details=details,
    )
