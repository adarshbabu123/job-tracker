"""
sources/lever.py
----------------
Adapter for Lever public job board APIs.

Lever provides a free, unauthenticated JSON API for each company:
  https://api.lever.co/v0/postings/{company}

We iterate over configured company boards independently.
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

_LEVER_API = "https://api.lever.co/v0/postings/{company}"

_INDIA_KEYWORDS = [
    "india", "bangalore", "bengaluru", "mumbai", "hyderabad", "chennai",
    "pune", "delhi", "noida", "gurugram", "remote", "worldwide",
    "kochi", "kerala", "thiruvananthapuram",
]

_EXCLUDE_KEYWORDS = [
    "us only", "usa only", "eu only", "uk only",
    "authorized to work in the us",
]


def _is_india_eligible(location: str, description: str = "") -> bool:
    combined = (location + " " + description).lower()
    for excl in _EXCLUDE_KEYWORDS:
        if excl in combined:
            return False
    return any(kw in combined for kw in _INDIA_KEYWORDS)


class LeverSource(BaseSource):
    name = "lever"

    def fetch(self) -> List[JobListing]:
        if not self.is_enabled():
            return []

        company_boards: List[str] = self.source_config.get("company_boards", [])
        job_titles = self.config.get("job_titles", [])
        all_jobs: List[JobListing] = []

        for company in company_boards:
            try:
                url = _LEVER_API.format(company=company)
                logger.info("Lever: fetching board '%s'", company)
                resp = requests.get(url, params={"mode": "json"}, timeout=self.timeout)
                resp.raise_for_status()
                raw_jobs = resp.json()

                if not isinstance(raw_jobs, list):
                    logger.warning("Lever[%s]: unexpected response format", company)
                    continue

                logger.info("Lever[%s]: %d raw jobs", company, len(raw_jobs))

                for raw in raw_jobs:
                    title = raw.get("text", "")
                    if not any(t.lower() in title.lower() for t in job_titles):
                        continue

                    location = raw.get("categories", {}).get("location", "") or ""
                    description_data = raw.get("descriptionPlain", "") or strip_html(raw.get("description", ""))
                    team = raw.get("categories", {}).get("team", "")
                    commitment = raw.get("categories", {}).get("commitment", "")
                    apply_url = raw.get("hostedUrl", raw.get("applyUrl", ""))
                    company_name = company.replace("-", " ").title()

                    if not _is_india_eligible(location, description_data[:500]):
                        continue

                    # Lever uses millisecond Unix timestamps
                    created_at_ms = raw.get("createdAt")
                    if isinstance(created_at_ms, (int, float)):
                        from datetime import datetime, timezone
                        posted = datetime.fromtimestamp(created_at_ms / 1000, tz=timezone.utc).date().isoformat()
                    else:
                        posted = parse_date(created_at_ms)

                    skills_parts = [s for s in [team, commitment] if s]

                    job = JobListing(
                        job_id=build_job_id("lever", apply_url, title, company_name),
                        title=title,
                        company=company_name,
                        location=normalize_location(location) if location else "Unknown",
                        experience="",
                        skills=normalize_skills(skills_parts),
                        description=description_data[:2000],
                        apply_url=apply_url,
                        source_url=url,
                        source="lever",
                        posted_date=posted,
                        discovered_date=today_iso(),
                    )
                    all_jobs.append(job)

                self._sleep_rate_limit()

            except requests.HTTPError as exc:
                if exc.response is not None and exc.response.status_code in (404, 410):
                    logger.warning("Lever[%s]: board not found (%d) — skipping",
                                   company, exc.response.status_code)
                else:
                    logger.error("Lever[%s] HTTP error: %s", company, exc)
            except requests.RequestException as exc:
                logger.error("Lever[%s] request failed: %s", company, exc)
            except Exception as exc:
                logger.error("Lever[%s] unexpected error: %s", company, exc)

        logger.info("Lever total: %d India-eligible jobs collected", len(all_jobs))
        return all_jobs
