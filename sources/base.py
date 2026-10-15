"""
sources/base.py
---------------
Abstract base class for all job-source adapters.

Every adapter must:
  - Implement `fetch(config)` and return List[JobListing].
  - Never invent job vacancies or fake URLs.
  - Handle API failures gracefully and return an empty list on error.
  - Log the source of each failure clearly.
  - Respect rate limits from config.
"""

from __future__ import annotations

import abc
import logging
import time
from typing import Any, Dict, List

from core.models import JobListing

logger = logging.getLogger(__name__)


class BaseSource(abc.ABC):
    """Base class for job-source adapters."""

    name: str = "base"  # Subclasses must set this

    def __init__(self, config: Dict[str, Any]) -> None:
        self.config = config
        self.source_config = config.get("sources", {}).get(self.name, {})
        self.timeout = config.get("run", {}).get("request_timeout_seconds", 15)
        self.rate_limit = self.source_config.get("rate_limit_seconds", 1)
        self.max_jobs = config.get("run", {}).get("max_jobs_per_source", 200)

    @abc.abstractmethod
    def fetch(self) -> List[JobListing]:
        """
        Fetch and return a list of JobListing objects.

        Must return an empty list on error — never raise to the caller.
        """
        ...

    def _sleep_rate_limit(self) -> None:
        """Sleep for the configured rate limit between requests."""
        time.sleep(self.rate_limit)

    def is_enabled(self) -> bool:
        return self.source_config.get("enabled", True)
