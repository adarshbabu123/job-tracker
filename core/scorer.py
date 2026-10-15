"""
core/scorer.py
--------------
Transparent rule-based job match scorer.

Score range: 0 – 100
Score components (configurable weights in config.json):
  - skill_overlap       (default 40 pts) — matched skills / total user skills
  - role_relevance      (default 25 pts) — how closely the title matches target roles
  - experience_match    (default 15 pts) — how well the job experience fits user level
  - location_priority   (default 15 pts) — High > Remote > Medium > Low
  - posting_freshness   (default  5 pts) — recency of the listing

This is a RULE-BASED scorer.  It is NOT an AI prediction.
"""

from __future__ import annotations

import logging
import re
from typing import Dict, Any, List, Tuple

from core.models import JobListing
from core.date_utils import days_since
from core.filter import _contains_any  # shared helper

logger = logging.getLogger(__name__)

# ── Default weights (overridden by config) ────────────────────────────────────
DEFAULT_WEIGHTS = {
    "skill_overlap": 40,
    "role_relevance": 25,
    "experience_match": 15,
    "location_priority": 15,
    "posting_freshness": 5,
}

# High-value title keywords for role_relevance
_PRIMARY_TITLES = [
    "devops", "site reliability", "sre", "cloud engineer",
    "platform engineer", "infrastructure engineer",
]
_SECONDARY_TITLES = [
    "linux admin", "linux engineer", "systems engineer",
    "ci/cd", "build and release", "cloud support",
    "kubernetes engineer", "terraform engineer",
    "cloud operations", "aws engineer",
]


def _score_skill_overlap(job: JobListing, user_skills: List[str], max_pts: int) -> Tuple[int, str]:
    combined = f"{job.title} {job.description} {job.skills}".lower()
    matched = [s for s in user_skills if s.lower() in combined]
    ratio = len(matched) / len(user_skills) if user_skills else 0
    pts = round(ratio * max_pts)
    reason = f"Skills: {len(matched)}/{len(user_skills)} matched ({', '.join(matched[:5])}{'…' if len(matched)>5 else ''})"
    return pts, reason


def _score_role_relevance(job: JobListing, max_pts: int) -> Tuple[int, str]:
    title_lower = job.title.lower()
    if _contains_any(title_lower, _PRIMARY_TITLES):
        pts = max_pts
        reason = "Role: primary DevOps/SRE/Cloud role"
    elif _contains_any(title_lower, _SECONDARY_TITLES):
        pts = round(max_pts * 0.7)
        reason = "Role: secondary relevant role"
    else:
        pts = round(max_pts * 0.3)
        reason = "Role: tangentially relevant"
    return pts, reason


def _score_experience_match(job: JobListing, user_years: int, max_pts: int) -> Tuple[int, str]:
    text = f"{job.experience} {job.description}".lower()
    year_pattern = re.compile(r"(\d+)\s*\+?\s*years?")
    matches = year_pattern.findall(text)

    if not matches:
        # No explicit requirement — neutral bonus
        pts = round(max_pts * 0.7)
        reason = "Experience: no explicit requirement stated"
    else:
        required = max(int(m) for m in matches)
        diff = required - user_years
        if diff <= 0:
            pts = max_pts
            reason = f"Experience: user meets {required}y requirement"
        elif diff == 1:
            pts = round(max_pts * 0.6)
            reason = f"Experience: slightly below ({required}y required, user ~{user_years}y)"
        elif diff == 2:
            pts = round(max_pts * 0.3)
            reason = f"Experience: below ({required}y required, user ~{user_years}y)"
        else:
            pts = 0
            reason = f"Experience: significantly below ({required}y required, user ~{user_years}y)"
    return pts, reason


def _score_location(job: JobListing, max_pts: int) -> Tuple[int, str]:
    priority_map = {
        "High": (max_pts, "Location: priority South India city"),
        "Remote": (round(max_pts * 0.85), "Location: remote (India-eligible)"),
        "Medium": (round(max_pts * 0.6), "Location: other Indian city"),
        "Low": (round(max_pts * 0.1), "Location: outside India / unclear"),
    }
    pts, reason = priority_map.get(job.location_priority, (0, "Location: unknown"))
    return pts, reason


def _score_freshness(job: JobListing, cfg: Dict[str, Any], max_pts: int) -> Tuple[int, str]:
    thresholds = cfg.get("freshness_thresholds_days", {
        "very_fresh": 3, "fresh": 7, "recent": 14, "older": 30,
    })
    age = days_since(job.posted_date)
    if age is None:
        pts = round(max_pts * 0.5)
        reason = "Freshness: posting date unknown"
    elif age <= thresholds["very_fresh"]:
        pts = max_pts
        reason = f"Freshness: very fresh ({age}d old)"
    elif age <= thresholds["fresh"]:
        pts = round(max_pts * 0.8)
        reason = f"Freshness: fresh ({age}d old)"
    elif age <= thresholds["recent"]:
        pts = round(max_pts * 0.5)
        reason = f"Freshness: recent ({age}d old)"
    else:
        pts = round(max_pts * 0.2)
        reason = f"Freshness: older ({age}d old)"
    return pts, reason


def score_job(job: JobListing, config: Dict[str, Any]) -> JobListing:
    """
    Compute a 0–100 match score for *job* and attach the score and
    human-readable reason to the JobListing object in-place.

    Returns the same object (mutated).
    """
    weights = {**DEFAULT_WEIGHTS, **config.get("scoring", {}).get("weights", {})}
    freshness_cfg = config.get("scoring", {}).get("freshness_thresholds_days", {})
    user_profile = config.get("user_profile", {})
    user_skills = user_profile.get("skills", [])
    user_years = user_profile.get("years_experience", 2)

    pts_skill, r_skill = _score_skill_overlap(job, user_skills, weights["skill_overlap"])
    pts_role, r_role = _score_role_relevance(job, weights["role_relevance"])
    pts_exp, r_exp = _score_experience_match(job, user_years, weights["experience_match"])
    pts_loc, r_loc = _score_location(job, weights["location_priority"])
    pts_fresh, r_fresh = _score_freshness(job, freshness_cfg, weights["posting_freshness"])

    total = pts_skill + pts_role + pts_exp + pts_loc + pts_fresh
    total = max(0, min(100, total))  # clamp to [0, 100]

    job.match_score = total
    job.match_reason = " | ".join([r_skill, r_role, r_exp, r_loc, r_fresh])
    return job


def score_jobs(jobs: List[JobListing], config: Dict[str, Any]) -> List[JobListing]:
    """Score all jobs and return them sorted by score descending."""
    scored = [score_job(job, config) for job in jobs]
    scored.sort(key=lambda j: j.match_score, reverse=True)
    logger.info("Scored %d jobs; top score: %d", len(scored),
                scored[0].match_score if scored else 0)
    return scored
