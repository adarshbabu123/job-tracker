"""
core/deduplicator.py
--------------------
Duplicate detection for JobListing objects.

Strategy:
1. Primary key  — job_id (reproducible SHA-256 hash of source+URL+title+company)
2. Fuzzy key    — normalised (title, company, location) tuple

A job is a duplicate if EITHER key matches a previously seen listing.
"""

from __future__ import annotations

import logging
from typing import List, Set, Tuple

from core.models import JobListing
from core.normalizer import normalize_url

logger = logging.getLogger(__name__)


def _fuzzy_key(job: JobListing) -> Tuple[str, str, str]:
    """Return a case-insensitive (title, company, location) tuple."""
    return (
        job.title.lower().strip(),
        job.company.lower().strip(),
        job.location.lower().strip(),
    )


class Deduplicator:
    """
    Stateful deduplicator.  Pass existing job IDs from Google Sheets on
    initialisation so that already-recorded jobs are also detected.
    """

    def __init__(self, existing_ids: Set[str] | None = None,
                 existing_fuzzy: Set[Tuple[str, str, str]] | None = None) -> None:
        self._seen_ids: Set[str] = set(existing_ids or [])
        self._seen_fuzzy: Set[Tuple[str, str, str]] = set(existing_fuzzy or [])

    def is_duplicate(self, job: JobListing) -> bool:
        fk = _fuzzy_key(job)
        if job.job_id in self._seen_ids:
            logger.debug("Duplicate by ID: %s  (%s @ %s)", job.job_id, job.title, job.company)
            return True
        if fk in self._seen_fuzzy:
            logger.debug("Duplicate by fuzzy key: %s @ %s", job.title, job.company)
            return True
        return False

    def register(self, job: JobListing) -> None:
        """Mark a job as seen so subsequent calls to is_duplicate catch it."""
        self._seen_ids.add(job.job_id)
        self._seen_fuzzy.add(_fuzzy_key(job))

    def deduplicate(self, jobs: List[JobListing]) -> List[JobListing]:
        """
        Filter *jobs*, returning only the first occurrence of each unique job.
        The internal seen-sets are updated for every kept job.
        """
        result: List[JobListing] = []
        for job in jobs:
            if not self.is_duplicate(job):
                result.append(job)
                self.register(job)
            else:
                logger.debug("Dropping duplicate: %s – %s", job.title, job.company)
        logger.info("Deduplication: %d → %d jobs", len(jobs), len(result))
        return result
