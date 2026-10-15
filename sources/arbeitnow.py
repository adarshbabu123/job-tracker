"""
sources/arbeitnow.py
---------------------
Adapter for Arbeitnow public job board API.

Endpoint: https://www.arbeitnow.com/api/job-board-api
No authentication required.
Terms: https://www.arbeitnow.com/faq — free public access for personal use.

Arbeitnow is primarily a European board but includes global remote roles.
We filter for jobs that contain India-related keywords or are genuinely
"remote worldwide" with no regional exclusion.
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

_INDIA_KEYWORDS = [
    "india", "bangalore", "bengaluru", "mumbai", "delhi", "hyderabad",
    "chennai", "pune", "remote worldwide", "worldwide", "global remote",
    "work from anywhere", "anywhere in the world",
]

_EXCLUDE_KEYWORDS = [
    "us only", "usa only", "eu only", "europe only", "uk only",
    "germany only", "authorized to work in the us",
]


def _is_india_eligible(location: str, description: str) -> bool:
    combined = (location + " " + description).lower()
    for excl in _EXCLUDE_KEYWORDS:
        if excl in combined:
            return False
    for kw in _INDIA_KEYWORDS:
        if kw in combined:
            return True
    return False


class ArbeitnowSource(BaseSource):
    name = "arbeitnow"

    def fetch(self) -> List[JobListing]:
        if not self.is_enabled():
            return []

        base_url = self.source_config.get("base_url", "https://www.arbeitnow.com/api/job-board-api")
        job_titles = self.config.get("job_titles", [])
        all_jobs: List[JobListing] = []
        page = 1
        collected = 0

        try:
            while collected < self.max_jobs:
                logger.info("Arbeitnow: fetching page %d", page)
                resp = requests.get(base_url, params={"page": page}, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                raw_jobs = data.get("data", [])

                if not raw_jobs:
                    logger.info("Arbeitnow: no more jobs on page %d", page)
                    break

                for raw in raw_jobs:
                    title = raw.get("title", "")
                    if not any(t.lower() in title.lower() for t in job_titles):
                        continue

                    location = raw.get("location", "")
                    description = strip_html(raw.get("description", ""))
                    tags = raw.get("tags", [])

                    if not _is_india_eligible(location, description):
                        continue

                    apply_url = raw.get("url", "")
                    company = raw.get("company_name", "Unknown")
                    slug = raw.get("slug", "")

                    # Arbeitnow provides a Unix timestamp for created_at
                    created_at = raw.get("created_at")
                    if isinstance(created_at, (int, float)):
                        from datetime import datetime, timezone
                        posted = datetime.fromtimestamp(created_at, tz=timezone.utc).date().isoformat()
                    else:
                        posted = parse_date(created_at)

                    job = JobListing(
                        job_id=build_job_id("arbeitnow", apply_url, title, company),
                        title=title,
                        company=company,
                        location=normalize_location(location),
                        experience="",
                        skills=normalize_skills(tags),
                        description=description[:2000],
                        apply_url=apply_url,
                        source_url=base_url,
                        source="arbeitnow",
                        posted_date=posted,
                        discovered_date=today_iso(),
                    )
                    all_jobs.append(job)
                    collected += 1
                    if collected >= self.max_jobs:
                        break

                page += 1
                self._sleep_rate_limit()

        except requests.RequestException as exc:
            logger.error("Arbeitnow request failed: %s", exc)
        except Exception as exc:
            logger.error("Arbeitnow unexpected error: %s", exc)

        logger.info("Arbeitnow total: %d India-eligible jobs collected", len(all_jobs))
        return all_jobs
