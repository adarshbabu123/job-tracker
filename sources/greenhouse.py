"""
sources/greenhouse.py
----------------------
Adapter for Greenhouse public job board APIs.

Greenhouse provides a free, unauthenticated JSON API for each company's
public job board:
  https://boards-api.greenhouse.io/v1/boards/{company}/jobs

We iterate over the list of company boards configured in config.json.
Each company board is independent — failure on one does not stop others.
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

_GREENHOUSE_API = "https://boards-api.greenhouse.io/v1/boards/{board}/jobs"

_INDIA_LOCATION_KEYWORDS = [
    "india", "bangalore", "bengaluru", "mumbai", "hyderabad", "chennai",
    "pune", "delhi", "noida", "gurugram", "remote", "worldwide",
    "kochi", "kerala", "thiruvananthapuram",
]

_EXCLUDE_KEYWORDS = [
    "us only", "usa only", "eu only", "uk only", "authorized to work in the us",
]


def _is_india_eligible(location: str) -> bool:
    loc_lower = location.lower()
    for excl in _EXCLUDE_KEYWORDS:
        if excl in loc_lower:
            return False
    return any(kw in loc_lower for kw in _INDIA_LOCATION_KEYWORDS)


class GreenhouseSource(BaseSource):
    name = "greenhouse"

    def fetch(self) -> List[JobListing]:
        if not self.is_enabled():
            return []

        company_boards: List[str] = self.source_config.get("company_boards", [])
        job_titles = self.config.get("job_titles", [])
        all_jobs: List[JobListing] = []

        for board in company_boards:
            try:
                url = _GREENHOUSE_API.format(board=board)
                logger.info("Greenhouse: fetching board '%s'", board)
                resp = requests.get(url, params={"content": "true"}, timeout=self.timeout)
                resp.raise_for_status()
                data = resp.json()
                raw_jobs = data.get("jobs", [])
                logger.info("Greenhouse[%s]: %d raw jobs", board, len(raw_jobs))

                for raw in raw_jobs:
                    title = raw.get("title", "")
                    if not any(t.lower() in title.lower() for t in job_titles):
                        continue

                    location_data = raw.get("location", {})
                    location = location_data.get("name", "") if isinstance(location_data, dict) else str(location_data)
                    description = strip_html(raw.get("content", ""))

                    # Greenhouse jobs without a location are often in-office;
                    # we only accept them if the description mentions India/remote
                    if not location:
                        if not _is_india_eligible(description[:500]):
                            continue
                        location = "Unknown"
                    elif not _is_india_eligible(location):
                        continue

                    apply_url = raw.get("absolute_url", "")
                    company_name = board.replace("-", " ").title()

                    departments = raw.get("departments", [])
                    dept_names = ", ".join(d.get("name", "") for d in departments if isinstance(d, dict))

                    job = JobListing(
                        job_id=build_job_id("greenhouse", apply_url, title, company_name),
                        title=title,
                        company=company_name,
                        location=normalize_location(location),
                        experience="",
                        skills=dept_names,
                        description=description[:2000],
                        apply_url=apply_url,
                        source_url=url,
                        source="greenhouse",
                        posted_date=parse_date(raw.get("updated_at")),
                        discovered_date=today_iso(),
                    )
                    all_jobs.append(job)

                self._sleep_rate_limit()

            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code == 404:
                    logger.warning("Greenhouse[%s]: board not found (404) — skipping", board)
                else:
                    logger.error("Greenhouse[%s] HTTP error: %s", board, exc)
            except requests.RequestException as exc:
                logger.error("Greenhouse[%s] request failed: %s", board, exc)
            except Exception as exc:
                logger.error("Greenhouse[%s] unexpected error: %s", board, exc)

        logger.info("Greenhouse total: %d India-eligible jobs collected", len(all_jobs))
        return all_jobs
