"""
core/models.py
--------------
JobListing dataclass — the canonical in-memory representation of a job.
Every source adapter must return a list of JobListing objects.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class JobListing:
    # ── Identity ──────────────────────────────────────────────────────────────
    job_id: str                        # Unique identifier (hash or source-provided)
    title: str
    company: str
    location: str

    # ── Details ───────────────────────────────────────────────────────────────
    experience: str = ""               # Raw experience string from source
    skills: str = ""                   # Comma-separated skill tags from source
    description: str = ""             # Full job description (used for scoring)

    # ── URLs ──────────────────────────────────────────────────────────────────
    apply_url: str = ""               # Direct application URL
    source_url: str = ""              # Source page / API endpoint URL
    source: str = ""                  # Source name (e.g. "remotive", "lever")

    # ── Dates ─────────────────────────────────────────────────────────────────
    # NOTE: posted_date is the ORIGINAL posting date from the source.
    #       discovered_date is the date this script first saw the listing.
    #       These are never conflated.
    posted_date: str = "Unknown"       # ISO-8601 date string or "Unknown"
    discovered_date: str = ""          # ISO-8601 date string (set at collection time)

    # ── Scoring ───────────────────────────────────────────────────────────────
    match_score: int = 0               # 0-100 rule-based score
    match_reason: str = ""             # Human-readable score breakdown
    location_priority: str = "Low"    # "High" | "Medium" | "Low" | "Remote"

    # ── Application tracking (user-managed) ───────────────────────────────────
    application_status: str = "Not Applied"
    notes: str = ""
    last_verified: str = ""

    def to_sheet_row(self) -> list:
        """Return a flat list suitable for a Google Sheets row."""
        return [
            self.job_id,
            self.title,
            self.company,
            self.location,
            self.experience,
            self.skills,
            self.posted_date,
            self.discovered_date,
            self.source,
            self.apply_url,
            self.match_score,
            self.match_reason,
            self.location_priority,
            self.application_status,
            self.notes,
            self.last_verified,
        ]

    @classmethod
    def sheet_headers(cls) -> list[str]:
        return [
            "Job ID", "Title", "Company", "Location", "Experience",
            "Skills", "Posted Date", "Discovered Date", "Source",
            "Apply URL", "Match Score", "Match Reason", "Location Priority",
            "Application Status", "Notes", "Last Verified",
        ]
