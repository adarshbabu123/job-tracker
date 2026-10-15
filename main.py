"""
main.py
-------
Daily DevOps Job Tracker — entry-point orchestrator.

Execution flow:
1. Load config.json
2. For each enabled source adapter: fetch jobs (failures are isolated)
3. Combine all collected jobs
4. Filter (title / location / experience / age)
5. Deduplicate (by ID and fuzzy key)
6. Score each job (rule-based 0-100)
7. Update Google Sheets
8. Exit with code 0 on success, 1 if ALL sources failed, 2 on Sheets failure.

This script never updates Google Sheets if zero jobs were collected across
all sources (guard against a total API failure wiping the spreadsheet).
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Dict, Any, List

from core.models import JobListing
from core.filter import filter_jobs
from core.deduplicator import Deduplicator
from core.scorer import score_jobs
from sources import ALL_SOURCES
from sheets.writer import update_sheets


def _setup_logging(level: str = "INFO") -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )


def load_config(path: str = "config.json") -> Dict[str, Any]:
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path.resolve()}")
    with config_path.open() as f:
        return json.load(f)


def collect_from_sources(config: Dict[str, Any]) -> tuple[List[JobListing], int, int]:
    """
    Run all enabled source adapters.

    Returns:
        (all_jobs, sources_attempted, sources_succeeded)
    """
    logger = logging.getLogger(__name__)
    all_jobs: List[JobListing] = []
    attempted = 0
    succeeded = 0

    for source_cls in ALL_SOURCES:
        source = source_cls(config)
        if not source.is_enabled():
            logger.info("Source '%s' is disabled — skipping", source.name)
            continue

        attempted += 1
        logger.info("=== Collecting from source: %s ===", source.name)
        try:
            jobs = source.fetch()
            all_jobs.extend(jobs)
            succeeded += 1
            logger.info("Source '%s' returned %d jobs", source.name, len(jobs))
        except Exception as exc:
            # Defensive catch — each adapter should already handle errors,
            # but this is a last-resort safety net.
            logger.error("Source '%s' raised an unhandled exception: %s", source.name, exc)

    return all_jobs, attempted, succeeded


def main() -> int:
    config = load_config()
    _setup_logging(config.get("run", {}).get("log_level", "INFO"))
    logger = logging.getLogger(__name__)

    logger.info("Daily DevOps Job Tracker starting")
    logger.info("=" * 60)

    # ── Step 1: Collect ───────────────────────────────────────────────────────
    raw_jobs, attempted, succeeded = collect_from_sources(config)
    logger.info("Collection complete: %d jobs from %d/%d sources",
                len(raw_jobs), succeeded, attempted)

    if attempted > 0 and succeeded == 0:
        logger.error("ALL sources failed — aborting to protect existing sheet data.")
        return 1

    if not raw_jobs:
        logger.warning("No jobs collected.  Sheets will NOT be updated.")
        return 0

    # ── Step 2: Filter ────────────────────────────────────────────────────────
    filtered_jobs = filter_jobs(raw_jobs, config)
    logger.info("After filtering: %d jobs", len(filtered_jobs))

    if not filtered_jobs:
        logger.warning("All jobs were filtered out.  Sheets will NOT be updated.")
        return 0

    # ── Step 3: Deduplicate ───────────────────────────────────────────────────
    dedup = Deduplicator()
    unique_jobs = dedup.deduplicate(filtered_jobs)
    logger.info("After deduplication: %d jobs", len(unique_jobs))

    # ── Step 4: Score ─────────────────────────────────────────────────────────
    scored_jobs = score_jobs(unique_jobs, config)
    logger.info("Scoring complete")
    if scored_jobs:
        logger.info("Top job: '%s' @ %s — score %d",
                    scored_jobs[0].title, scored_jobs[0].company, scored_jobs[0].match_score)

    # ── Step 5: Update Google Sheets ──────────────────────────────────────────
    try:
        update_sheets(scored_jobs, config)
    except Exception as exc:
        logger.error("Sheets update failed: %s", exc)
        return 2

    logger.info("=" * 60)
    logger.info("Run complete.  Total jobs written: %d", len(scored_jobs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
