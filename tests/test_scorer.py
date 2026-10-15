"""
tests/test_scorer.py
"""

import json
import pytest
from pathlib import Path
from core.models import JobListing
from core.scorer import score_job, score_jobs


def load_config():
    config_path = Path(__file__).parent.parent / "config.json"
    with config_path.open() as f:
        return json.load(f)


def make_job(**kwargs) -> JobListing:
    defaults = dict(
        job_id="test_id",
        title="DevOps Engineer",
        company="TestCo",
        location="Bengaluru",
        location_priority="High",
        posted_date="Unknown",
        description="",
        experience="",
        skills="",
    )
    defaults.update(kwargs)
    return JobListing(**defaults)


class TestScoreJob:
    def test_score_in_valid_range(self):
        config = load_config()
        job = make_job()
        result = score_job(job, config)
        assert 0 <= result.match_score <= 100

    def test_high_skill_match_raises_score(self):
        config = load_config()
        job_high = make_job(description="AWS Terraform Docker Kubernetes CI/CD Prometheus Grafana")
        job_low = make_job(description="No relevant skills here")
        score_job(job_high, config)
        score_job(job_low, config)
        assert job_high.match_score > job_low.match_score

    def test_high_priority_location_raises_score(self):
        config = load_config()
        job_high = make_job(location_priority="High")
        job_low = make_job(location_priority="Low")
        score_job(job_high, config)
        score_job(job_low, config)
        assert job_high.match_score > job_low.match_score

    def test_match_reason_contains_components(self):
        config = load_config()
        job = make_job()
        score_job(job, config)
        assert "Skills:" in job.match_reason
        assert "Role:" in job.match_reason
        assert "Experience:" in job.match_reason
        assert "Location:" in job.match_reason
        assert "Freshness:" in job.match_reason

    def test_primary_devops_title_scores_higher_than_tangential(self):
        config = load_config()
        job_primary = make_job(title="DevOps Engineer")
        job_tangential = make_job(title="Office Manager")
        score_job(job_primary, config)
        score_job(job_tangential, config)
        assert job_primary.match_score > job_tangential.match_score

    def test_fresh_posting_scores_higher(self):
        config = load_config()
        from datetime import date, timedelta
        fresh = (date.today() - timedelta(days=1)).isoformat()
        old = (date.today() - timedelta(days=29)).isoformat()
        job_fresh = make_job(posted_date=fresh)
        job_old = make_job(posted_date=old)
        score_job(job_fresh, config)
        score_job(job_old, config)
        assert job_fresh.match_score >= job_old.match_score

    def test_experience_over_user_years_penalised(self):
        config = load_config()
        job_over = make_job(experience="8+ years required")
        job_match = make_job(experience="1-2 years experience")
        score_job(job_over, config)
        score_job(job_match, config)
        assert job_match.match_score > job_over.match_score

    def test_unknown_date_does_not_crash(self):
        config = load_config()
        job = make_job(posted_date="Unknown")
        result = score_job(job, config)
        assert isinstance(result.match_score, int)
        assert 0 <= result.match_score <= 100


class TestScoreJobs:
    def test_sorted_descending(self):
        config = load_config()
        jobs = [
            make_job(job_id="1", title="Marketing Manager", location_priority="Low"),
            make_job(job_id="2", title="DevOps Engineer", location_priority="High",
                     description="AWS Docker Kubernetes Terraform CI/CD"),
        ]
        result = score_jobs(jobs, config)
        scores = [j.match_score for j in result]
        assert scores == sorted(scores, reverse=True)

    def test_empty_list(self):
        config = load_config()
        assert score_jobs([], config) == []
