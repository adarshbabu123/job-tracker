"""
core/normalizer.py
------------------
Text and URL normalization utilities.

- Strips HTML/whitespace from text fields.
- Normalises apply URLs so that two listings pointing to the same
  canonical URL are not stored twice.
- Builds a stable job_id from source + URL so IDs are reproducible
  across runs.
"""

from __future__ import annotations

import hashlib
import html
import logging
import re
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)

# Regex to strip basic HTML tags (no full HTML parser dependency)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def strip_html(text: str) -> str:
    """Remove HTML tags and decode HTML entities."""
    if not text:
        return ""
    text = _HTML_TAG_RE.sub(" ", text)
    text = html.unescape(text)
    text = _WHITESPACE_RE.sub(" ", text)
    return text.strip()


def normalize_url(url: str) -> str:
    """
    Return a canonical form of *url*.

    - Lowercases scheme and host.
    - Removes trailing slashes from the path.
    - Strips tracking query params (utm_*, ref=, etc.).
    - Returns an empty string if the URL is invalid.
    """
    if not url:
        return ""
    try:
        parsed = urlparse(url.strip())
        if not parsed.scheme or not parsed.netloc:
            return url.strip()

        # Strip known tracking params
        tracking_params = {"utm_source", "utm_medium", "utm_campaign",
                           "utm_term", "utm_content", "ref", "source"}
        if parsed.query:
            kept = "&".join(
                part for part in parsed.query.split("&")
                if part.split("=")[0].lower() not in tracking_params
            )
        else:
            kept = ""

        path = parsed.path.rstrip("/") or "/"
        canonical = urlunparse((
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            path,
            parsed.params,
            kept,
            "",  # drop fragment
        ))
        return canonical
    except Exception as exc:
        logger.debug("URL normalization failed for %r: %s", url, exc)
        return url.strip()


def build_job_id(source: str, apply_url: str, title: str, company: str) -> str:
    """
    Build a reproducible, stable job identifier.

    The ID is a short SHA-256 hex digest over (source, canonical URL,
    lower-cased title, lower-cased company).  Running the same job
    through the pipeline on different days always produces the same ID.
    """
    canonical_url = normalize_url(apply_url)
    fingerprint = "|".join([
        source.lower(),
        canonical_url.lower(),
        title.lower().strip(),
        company.lower().strip(),
    ])
    return hashlib.sha256(fingerprint.encode()).hexdigest()[:16]


def normalize_location(location: str) -> str:
    """Title-case and strip a location string."""
    if not location:
        return "Unknown"
    return location.strip().title()


def normalize_skills(skills_raw: object) -> str:
    """
    Accept a list or comma-separated string and return a clean
    comma-separated skills string.
    """
    if isinstance(skills_raw, list):
        return ", ".join(s.strip() for s in skills_raw if s)
    if isinstance(skills_raw, str):
        return ", ".join(s.strip() for s in skills_raw.split(",") if s.strip())
    return ""
