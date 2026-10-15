"""
tests/test_filter.py
"""

import json
import pytest
from pathlib import Path
from core.models import JobListing
from core.filter import filter_jobs, _location_priority, _is_location_eligible


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
        posted_date="Unknown",
        description="",
        experience="",
    )
    defaults.update(kwargs)
    return JobListing(**defaults)


class TestLocationPriority:
    def test_bengaluru_is_high(self):
        config = load_config()
        job = make_job(location="Bengaluru, India")
        priority = _location_priority(job.location, config)
        assert priority == "High"

    def test_kochi_is_high(self):
        config = load_config()
        assert _location_priority("Kochi, Kerala", config) == "High"

    def test_mumbai_is_medium(self):
        config = load_config()
        assert _location_priority("Mumbai, India", config) == "Medium"

    def test_remote_worldwide_is_remote(self):
        config = load_config()
        assert _location_priority("Remote (Worldwide)", config) == "Remote"

    def test_us_only_is_low(self):
        config = load_config()
        # US only is explicitly excluded
        result = _location_priority("US only", config)
        assert result == "Low"

    def test_london_is_low(self):
        config = load_config()
        assert _location_priority("London, UK", config) == "Low"


class TestLocationFilter:
    def test_bengaluru_job_accepted(self):
        config = load_config()
        job = make_job(location="Bengaluru")
        assert _is_location_eligible(job, config) is True

    def test_remote_worldwide_accepted(self):
        config = load_config()
        job = make_job(location="Remote (Worldwide)")
        assert _is_location_eligible(job, config) is True

    def test_us_only_rejected(self):
        config = load_config()
        job = make_job(location="US only", description="You must be authorized to work in the US")
        assert _is_location_eligible(job, config) is False

    def test_india_keyword_in_location_accepted(self):
        config = load_config()
        job = make_job(location="India")
        assert _is_location_eligible(job, config) is True


class TestFilterJobs:
    def test_relevant_job_passes(self):
        config = load_config()
        jobs = [make_job(title="DevOps Engineer", location="Bengaluru", posted_date="Unknown")]
        result = filter_jobs(jobs, config)
        assert len(result) == 1

    def test_irrelevant_title_filtered(self):
        config = load_config()
        jobs = [make_job(title="Marketing Manager", location="Bengaluru")]
        result = filter_jobs(jobs, config)
        assert len(result) == 0

    def test_us_only_location_filtered(self):
        config = load_config()
        jobs = [make_job(title="DevOps Engineer", location="New York, US only")]
        result = filter_jobs(jobs, config)
        assert len(result) == 0

    def test_unknown_date_not_filtered(self):
        """Jobs with unknown posting dates must NOT be rejected."""
        config = load_config()
        jobs = [make_job(title="DevOps Engineer", location="Bengaluru", posted_date="Unknown")]
        result = filter_jobs(jobs, config)
        assert len(result) == 1

    def test_old_job_filtered(self):
        config = load_config()
        jobs = [make_job(title="DevOps Engineer", location="Bengaluru", posted_date="2020-01-01")]
        result = filter_jobs(jobs, config)
        assert len(result) == 0

    def test_senior_role_filtered_by_experience(self):
        config = load_config()
        jobs = [make_job(title="Senior DevOps Engineer", location="Bengaluru",
                         experience="8+ years required")]
        result = filter_jobs(jobs, config)
        assert len(result) == 0

    def test_junior_role_passes(self):
        config = load_config()
        jobs = [make_job(title="Junior DevOps Engineer", location="Bengaluru",
                         experience="0-2 years")]
        result = filter_jobs(jobs, config)
        assert len(result) == 1

    def test_location_priority_set_on_passed_job(self):
        config = load_config()
        jobs = [make_job(title="DevOps Engineer", location="Bengaluru")]
        result = filter_jobs(jobs, config)
        assert result[0].location_priority == "High"
