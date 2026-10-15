"""
core/date_utils.py
------------------
Robust date parsing helpers.

Rules:
- A missing or unparseable date is returned as the string "Unknown".
- "Unknown" is never confused with a real date.
- The caller decides what to do with "Unknown" (we do NOT reject jobs for it).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

_DATEUTIL_AVAILABLE = False
try:
    from dateutil import parser as dateutil_parser
    _DATEUTIL_AVAILABLE = True
except ImportError:
    logger.warning("python-dateutil not installed; falling back to basic parsing.")


def today_iso() -> str:
    """Return today's date in ISO-8601 format (UTC)."""
    return datetime.now(timezone.utc).date().isoformat()


def parse_date(raw: object) -> str:
    """
    Attempt to parse *raw* into an ISO-8601 date string.

    Returns:
        ISO-8601 date string (e.g. "2024-05-01") on success.
        "Unknown" when the value is missing or cannot be parsed.
    """
    if raw is None:
        return "Unknown"

    raw_str = str(raw).strip()
    if not raw_str or raw_str.lower() in ("", "none", "null", "n/a", "unknown"):
        return "Unknown"

    # Prefer dateutil for flexible format support
    if _DATEUTIL_AVAILABLE:
        try:
            dt = dateutil_parser.parse(raw_str, fuzzy=True)
            return dt.date().isoformat()
        except Exception:
            pass

    # Fallback: try a handful of common formats
    for fmt in (
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%B %d, %Y",
        "%b %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ):
        try:
            return datetime.strptime(raw_str, fmt).date().isoformat()
        except ValueError:
            continue

    logger.debug("Could not parse date value: %r — marking as Unknown", raw_str)
    return "Unknown"


def days_since(iso_date_str: str) -> Optional[int]:
    """
    Return how many days have elapsed since *iso_date_str*.

    Returns None when the input is "Unknown" or unparseable.
    """
    if iso_date_str == "Unknown":
        return None
    try:
        posted = date.fromisoformat(iso_date_str)
        return (date.today() - posted).days
    except (ValueError, TypeError):
        return None


def is_within_days(iso_date_str: str, max_days: int) -> bool:
    """
    Return True if the posting is within *max_days* old.

    If the date is "Unknown", returns True to avoid rejecting valid jobs.
    """
    age = days_since(iso_date_str)
    if age is None:
        return True   # Unknown date → do NOT reject
    return age <= max_days
