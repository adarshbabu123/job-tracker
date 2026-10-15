"""
core/filter.py
--------------
Job filtering pipeline.

Applies three independent filter stages in sequence:
1. Title relevance   — must match at least one configured job title keyword
2. Location filter   — must be India/remote-India eligible
3. Experience filter — must not require experience clearly above the user's level
4. Age filter        — must be within max_listing_age_days (Unknown date passes)
5. Hard-exclude      — drops listings that contain a config'd exclude keyword
"""

from __future__ import annotations

import logging
import re
from typing import List, Dict, Any

from core.models import JobListing
from core.date_utils import is_within_days

logger = logging.getLogger(__name__)


def _contains_any(text: str, keywords: List[str]) -> bool:
    """Case-insensitive check if *text* contains any keyword from *keywords*."""
    text_lower = text.lower()
    return any(kw.lower() in text_lower for kw in keywords if kw)


def _location_priority(location: str, config: Dict[str, Any]) -> str:
    """
    Return "High", "Medium", "Low", or "Remote" for a location string.

    "High"   — explicitly in priority South-India list
    "Medium" — other Indian city
    "Remote" — remote listing eligible for India
    "Low"    — anything else (international, unclear)
    """
    loc_lower = location.lower()
    loc_cfg = config.get("locations", {})

    # Remote check
    remote_kws = loc_cfg.get("remote_eligible_keywords", [])
    if _contains_any(loc_lower, remote_kws):
        # Ensure it is not explicitly US/UK/EU-only
        exclude_kws = loc_cfg.get("exclude_keywords", [])
        if _contains_any(loc_lower, exclude_kws):
            return "Low"
        return "Remote"

    # Priority South India cities
    priority = loc_cfg.get("priority", [])
    if _contains_any(loc_lower, priority):
        return "High"

    # Other India cities or India keyword
    india_cities = loc_cfg.get("india_cities", [])
    india_kws = loc_cfg.get("india_keywords", [])
    if _contains_any(loc_lower, india_cities) or _contains_any(loc_lower, india_kws):
        return "Medium"

    return "Low"


def _is_location_eligible(job: JobListing, config: Dict[str, Any]) -> bool:
    """
    Return True if the job location is India or remote-eligible.
    Remote jobs are only accepted if they are NOT flagged as region-exclusive.
    """
    text = f"{job.location} {job.description}".lower()
    loc_cfg = config.get("locations", {})

    exclude_kws = loc_cfg.get("exclude_keywords", [])
    if _contains_any(text, exclude_kws):
        logger.debug("Location excluded (%s): %s", job.location, job.title)
        return False

    priority = _location_priority(job.location, config)
    return priority in ("High", "Medium", "Remote")


def _is_title_relevant(job: JobListing, config: Dict[str, Any]) -> bool:
    """Return True if the job title matches at least one configured title keyword."""
    title_keywords = config.get("job_titles", [])
    combined = f"{job.title} {job.description}"
    return _contains_any(combined, title_keywords)


def _is_experience_compatible(job: JobListing, config: Dict[str, Any]) -> bool:
    """
    Return True if the required experience does not clearly exceed
    the user's profile.  Errs on the side of inclusion when ambiguous.
    """
    user_years = config.get("user_profile", {}).get("years_experience", 2)
    text = f"{job.title} {job.experience} {job.description}".lower()

    # Hard excludes from filter config (senior, lead, etc.)
    hard_exclude = config.get("filters", {}).get("exclude_keywords", [])
    if _contains_any(text, hard_exclude):
        logger.debug("Experience excluded (hard keyword): %s", job.title)
        return False

    # Look for explicit year requirements (e.g., "5+ years", "5 years experience")
    year_pattern = re.compile(r"(\d+)\s*\+?\s*years?")
    matches = year_pattern.findall(text)
    if matches:
        required = max(int(m) for m in matches)
        # Allow up to 1 year above user's experience for junior-ish roles
        if required > user_years + 1:
            logger.debug("Experience mismatch (%d req vs %d user): %s",
                         required, user_years, job.title)
            return False

    return True


def filter_jobs(jobs: List[JobListing], config: Dict[str, Any]) -> List[JobListing]:
    """
    Apply all filter stages to *jobs*.

    Returns filtered list with location_priority populated.
    """
    max_age = config.get("filters", {}).get("max_listing_age_days", 30)
    results: List[JobListing] = []

    for job in jobs:
        # Stage 1: Title relevance
        if not _is_title_relevant(job, config):
            logger.debug("Filtered (title): %s", job.title)
            continue

        # Stage 2: Location eligibility
        if not _is_location_eligible(job, config):
            logger.debug("Filtered (location): %s @ %s", job.title, job.location)
            continue

        # Stage 3: Experience compatibility
        if not _is_experience_compatible(job, config):
            continue

        # Stage 4: Age filter (Unknown dates pass through)
        if not is_within_days(job.posted_date, max_age):
            logger.debug("Filtered (age): %s posted %s", job.title, job.posted_date)
            continue

        # Populate derived field
        job.location_priority = _location_priority(job.location, config)
        results.append(job)

    logger.info("Filter: %d → %d jobs", len(jobs), len(results))
    return results
