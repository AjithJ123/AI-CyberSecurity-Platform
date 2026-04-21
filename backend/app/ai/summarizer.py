"""Groq-powered data summarizer.

We do a lightweight local sniff of the tabular text (delimiter detection,
column typing, basic stats) before calling the model. The model then writes
the narrative part (summary + highlights + outliers) on top of those stats.

Source: Groq Chat Completions API (Llama 3.1 8B).
Failure mode: raises AIAnalysisError if the key is missing or the call fails.

Privacy: we don't log the raw data — only the derived row/column counts and
the final duration.
"""

from __future__ import annotations

import csv
import io
import json
import math
import re
from collections import Counter
from datetime import datetime
from typing import Any

import httpx

from app.config import settings
from app.exceptions import AIAnalysisError

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
GROQ_MODEL = "llama-3.1-8b-instant"

MAX_ROWS_FOR_MODEL = 60       # truncate huge tables before sending
MAX_SAMPLE_VALUES = 4
NUMERIC_RE = re.compile(r"^-?\d+(?:\.\d+)?$")
DATE_PATTERNS = ("%Y-%m-%d", "%Y/%m/%d", "%m/%d/%Y", "%d-%m-%Y", "%d/%m/%Y")


def _sniff_delimiter(sample: str) -> str:
    """Return the most likely delimiter from a short sample."""
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        return dialect.delimiter
    except csv.Error:
        # Fallback heuristic — tab if there are any tabs, else comma.
        if "\t" in sample:
            return "\t"
        return ","


def _parse_table(text: str) -> tuple[list[str], list[list[str]], str, bool]:
    """Return (header, rows, delimiter, truncated)."""
    sample = "\n".join(text.splitlines()[:10])
    delim = _sniff_delimiter(sample)
    reader = csv.reader(io.StringIO(text), delimiter=delim)

    rows: list[list[str]] = []
    for row in reader:
        rows.append([cell.strip() for cell in row])
        if len(rows) > 5000:
            break

    if not rows:
        raise AIAnalysisError("No rows detected in the input")

    header = rows[0]
    body = rows[1:]

    # Detect "no header" case: if the first row is all-numeric, treat everything
    # as data and generate synthetic headers.
    if header and all(NUMERIC_RE.match(c) for c in header if c):
        body = rows
        header = [f"col_{i + 1}" for i in range(len(rows[0]))]

    truncated = False
    if len(body) > MAX_ROWS_FOR_MODEL:
        body = body[:MAX_ROWS_FOR_MODEL]
        truncated = True

    return header, body, delim, truncated


def _infer_type(values: list[str]) -> str:
    non_empty = [v for v in values if v]
    if not non_empty:
        return "empty"
    types = set()
    for v in non_empty:
        lv = v.lower()
        if lv in {"true", "false", "yes", "no"}:
            types.add("boolean")
        elif NUMERIC_RE.match(v):
            types.add("numeric")
        elif any(_try_date(v, p) for p in DATE_PATTERNS):
            types.add("date")
        else:
            types.add("text")
    if len(types) == 1:
        return next(iter(types))
    return "mixed"


def _try_date(value: str, fmt: str) -> bool:
    try:
        datetime.strptime(value, fmt)
        return True
    except ValueError:
        return False


def _column_stats(name: str, values: list[str]) -> dict[str, Any]:
    non_empty = [v for v in values if v]
    col_type = _infer_type(values)
    out: dict[str, Any] = {
        "name": name,
        "type": col_type,
        "non_empty": len(non_empty),
        "unique": len(set(non_empty)),
        "min": "",
        "max": "",
        "mean": None,
        "sample_values": [],
    }

    if col_type == "numeric":
        nums = [float(v) for v in non_empty if NUMERIC_RE.match(v)]
        if nums:
            out["min"] = _fmt_num(min(nums))
            out["max"] = _fmt_num(max(nums))
            out["mean"] = round(sum(nums) / len(nums), 4)
    elif col_type in {"text", "boolean", "mixed"}:
        counts = Counter(non_empty)
        most_common = [v for v, _ in counts.most_common(MAX_SAMPLE_VALUES)]
        out["sample_values"] = most_common
        if non_empty:
            out["min"] = min(non_empty, key=len)
            out["max"] = max(non_empty, key=len)
    elif col_type == "date":
        out["min"] = min(non_empty)
        out["max"] = max(non_empty)
        out["sample_values"] = non_empty[:MAX_SAMPLE_VALUES]

    return out


def _fmt_num(n: float) -> str:
    if math.isnan(n) or math.isinf(n):
        return str(n)
    if n == int(n):
        return str(int(n))
    return f"{n:.4f}".rstrip("0").rstrip(".")


SYSTEM_PROMPT = (
    "You are a careful data analyst. You receive (1) pre-computed column "
    "statistics and (2) a sample of rows from a table. Write a short, specific "
    "story about what the data shows. Cite real numbers from the stats where "
    "possible.\n"
    "\n"
    "Return ONLY a JSON object with this exact shape (no markdown, no code fences):\n"
    "{\n"
    '  "summary": "<one crisp sentence capturing the headline of the data>",\n'
    '  "highlights": ["<3-5 short bullets on notable patterns, trends, distributions>"],\n'
    '  "outliers": [\n'
    "    {\n"
    '      "description": "<what is unusual, 1 sentence>",\n'
    '      "detail": "<which row/value, if specific; empty string if general>"\n'
    "    }\n"
    "  ]\n"
    "}\n"
    "Keep bullets short and specific. Never invent numbers — only cite what the "
    "stats or rows actually contain. Cap highlights at 5 and outliers at 5. "
    "If nothing stands out, return empty arrays."
)


def _strip_code_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[-1]
        if stripped.endswith("```"):
            stripped = stripped[: -len("```")]
        if stripped.startswith("json"):
            stripped = stripped[len("json") :]
    return stripped.strip()


async def summarize(
    text: str,
    context: str,
    total_rows_hint: int | None = None,
    file_size_bytes: int | None = None,
) -> dict[str, Any]:
    api_key = settings.groq_api_key
    if not api_key:
        raise AIAnalysisError("GROQ_API_KEY is not configured")

    header, body, delim, truncated = _parse_table(text)
    # Normalise row widths to the header length.
    width = len(header)
    body = [(row + [""] * width)[:width] for row in body]

    # Per-column values and stats.
    cols_by_index: list[list[str]] = [[] for _ in range(width)]
    for row in body:
        for i in range(width):
            cols_by_index[i].append(row[i])
    columns = [_column_stats(header[i] or f"col_{i+1}", cols_by_index[i]) for i in range(width)]

    # Build model prompt — stats block + a small preview of rows (max 20).
    preview_rows = body[:20]
    preview_table = (
        delim.join(header)
        + "\n"
        + "\n".join(delim.join(r) for r in preview_rows)
    )
    stats_block = json.dumps({"columns": columns, "row_count": len(body)}, indent=2)

    user_msg_parts = [
        f"Delimiter: {'TAB' if delim == chr(9) else delim}",
        f"Column count: {width}",
    ]
    # If the client streamed a much larger file and sampled, tell the model so
    # it narrates at the right scale ("across 1.2M rows …") rather than just
    # the sample size.
    effective_row_count = total_rows_hint if total_rows_hint else len(body)
    user_msg_parts.append(f"Total row count in original file: {effective_row_count:,}")
    if total_rows_hint and total_rows_hint > len(body):
        user_msg_parts.append(
            f"You are seeing a representative sample of {len(body)} rows "
            f"from the full {total_rows_hint:,}-row dataset. "
            "Write the narrative about the full dataset, but only cite values "
            "you can see in the sample or in the column stats."
        )
    elif truncated:
        user_msg_parts.append("(Body truncated for analysis — originals were longer.)")
    if file_size_bytes:
        user_msg_parts.append(f"Source file size: {_fmt_bytes(file_size_bytes)}")
    if context:
        user_msg_parts.append(f"Context: {context}")
    user_msg_parts.append("")
    user_msg_parts.append("Column stats (pre-computed):")
    user_msg_parts.append(stats_block)
    user_msg_parts.append("")
    user_msg_parts.append("Preview of rows (up to 20):")
    user_msg_parts.append(preview_table)
    user_msg = "\n".join(user_msg_parts)

    payload = {
        "model": GROQ_MODEL,
        "temperature": 0.25,
        "max_tokens": 900,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(GROQ_URL, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
    except httpx.HTTPError as exc:
        raise AIAnalysisError("Data summarize request failed") from exc

    try:
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(_strip_code_fence(content))
    except (KeyError, IndexError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise AIAnalysisError("Data summarize returned an unexpected response") from exc

    summary = str(parsed.get("summary", "")).strip() or "No summary produced."
    highlights_raw = parsed.get("highlights") or []
    outliers_raw = parsed.get("outliers") or []

    highlights = [
        str(h).strip()
        for h in (highlights_raw if isinstance(highlights_raw, list) else [])
        if str(h).strip()
    ][:5]

    outliers: list[dict[str, str]] = []
    if isinstance(outliers_raw, list):
        for o in outliers_raw[:5]:
            if isinstance(o, dict):
                desc = str(o.get("description", "")).strip()
                detail = str(o.get("detail", "")).strip()
                if desc:
                    outliers.append({"description": desc, "detail": detail})

    return {
        "summary": summary,
        # If the client told us the real size, use that so the UI shows the
        # full dataset stats (not just what made it through the sample).
        "row_count": total_rows_hint if total_rows_hint else len(body),
        "sampled_row_count": len(body),
        "column_count": width,
        "delimiter": "tab" if delim == "\t" else delim,
        "highlights": highlights,
        "outliers": outliers,
        "columns": columns,
        "truncated": truncated or (total_rows_hint and total_rows_hint > len(body)),
    }


def _fmt_bytes(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    return f"{n / (1024 * 1024):.2f} MB"
