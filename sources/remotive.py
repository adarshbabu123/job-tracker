"""
sources/remotive.py
-------------------
Adapter for Remotive.com public API.

Endpoint: https://remotive.com/api/remote-jobs
No authentication required.
Terms: https://remotive.com/remote-jobs-api (free for personal/non-commercial use)

Remotive jobs are remote-first.  We apply an India-eligibility filter:
  - Accept if location says "Worldwide", "Anywhere", empty, or contains "India".
  - Reject if location explicitly excludes India (US-only, EU-only, etc.).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import requests

from core.models import JobListing
from core.date_utils import parse_date, today_iso
from core.normalizer import build_job_id, normalize_location, normalize_skills, strip_html
from sources.base import BaseSource

logger = logging.getLogger(__name__)

# Regions that are clearly not India-eligible
_EXCLUDE_REGIONS = [
    "us only", "usa only", "united states only",
    "uk only", "united kingdom only",
    "eu only", "europe only", "european union only",
    "canada only", "australia only",
    "must be in us", "must be based in us",
    "authorized to work in the us",
]

# India-eligible indicators (empty location or "worldwide" is accepted)
_INDIA_ELIGIBLE = [
    "worldwide", "anywhere", "global", "india", "remote",
    "", "all countries",
]


def _is_india_eligible(candidate_required_region: str) -> bool:
    region = (candidate_required_region or "").lower().strip()
    for excl in _EXCLUDE_REGIONS:
        if excl in region:
            return False
    for kw in _INDIA_ELIGIBLE:
        if kw in region:
            return True
    # If there's a region specified but none of the above matched, exclude it
    # (conservative: if we don't recognise it, don't assume India is allowed)
    if region and region not in ("", "remote"):
        return False
    return True


class RemotiveSource(BaseSource):
    name = "remotive"

    def fetch(self) -> List[JobListing]:
        if not self.is_enabled():
            return []

        base_url = self.source_config.get("base_url", "https://remotive.com/api/remote-jobs")
        categories = self.source_config.get("categories", ["devops"])
        job_titles = self.config.get("job_titles", [])

        all_jobs: List[JobListing] = []

        for category in categories:
            try:
                logger.info("Remotive: fetching category '%s'", category)
                params = {"category": category, "limit": self.max_jobs}
                resp = requests.get(base_url, params=params, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                raw_jobs = data.get("jobs", [])
                logger.info("Remotive[%s]: %d raw jobs received", category, len(raw_jobs))

                for raw in raw_jobs:
                    title = raw.get("title", "")

                    # Basic title relevance pre-filter before expensive processing
                    if not any(t.lower() in title.lower() for t in job_titles):
                        continue

                    candidate_region = raw.get("candidate_required_location", "")
                    if not _is_india_eligible(candidate_region):
                        logger.debug("Remotive: skipping non-India-eligible: %s [%s]",
                                     title, candidate_region)
                        continue

                    apply_url = raw.get("url", "")
                    company = raw.get("company_name", "Unknown")
                    description = strip_html(raw.get("description", ""))
                    location = candidate_region or "Remote (Worldwide)"
                    skills_raw = raw.get("tags", [])

                    job = JobListing(
                        job_id=build_job_id("remotive", apply_url, title, company),
                        title=title,
                        company=company,
                        location=normalize_location(location),
                        experience="",
                        skills=normalize_skills(skills_raw),
                        description=description[:2000],  # cap description size
                        apply_url=apply_url,
                        source_url=f"{base_url}?category={category}",
                        source="remotive",
                        posted_date=parse_date(raw.get("publication_date")),
                        discovered_date=today_iso(),
                    )
                    all_jobs.append(job)

                self._sleep_rate_limit()

            except requests.RequestException as exc:
                logger.error("Remotive[%s] request failed: %s", category, exc)
            except Exception as exc:
                logger.error("Remotive[%s] unexpected error: %s", category, exc)

        logger.info("Remotive total: %d India-eligible jobs collected", len(all_jobs))
        return all_jobs
