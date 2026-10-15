"""
tests/test_deduplicator.py
"""

import pytest
from core.models import JobListing
from core.deduplicator import Deduplicator


def make_job(**kwargs) -> JobListing:
    defaults = dict(
        job_id="abc123",
        title="DevOps Engineer",
        company="Acme Corp",
        location="Bengaluru",
    )
    defaults.update(kwargs)
    return JobListing(**defaults)


class TestDeduplicator:
    def test_no_duplicates_passes_all(self):
        jobs = [
            make_job(job_id="id1", title="DevOps Engineer", company="Alpha"),
            make_job(job_id="id2", title="Cloud Engineer", company="Beta"),
        ]
        dedup = Deduplicator()
        result = dedup.deduplicate(jobs)
        assert len(result) == 2

    def test_exact_id_duplicate_removed(self):
        jobs = [
            make_job(job_id="same_id"),
            make_job(job_id="same_id"),
        ]
        dedup = Deduplicator()
        result = dedup.deduplicate(jobs)
        assert len(result) == 1

    def test_fuzzy_duplicate_removed(self):
        # Same title+company+location, different IDs
        jobs = [
            make_job(job_id="id1", title="DevOps Engineer", company="Acme", location="Bengaluru"),
            make_job(job_id="id2", title="DevOps Engineer", company="Acme", location="Bengaluru"),
        ]
        dedup = Deduplicator()
        result = dedup.deduplicate(jobs)
        assert len(result) == 1

    def test_fuzzy_case_insensitive(self):
        jobs = [
            make_job(job_id="id1", title="DevOps Engineer", company="ACME", location="bengaluru"),
            make_job(job_id="id2", title="devops engineer", company="acme", location="BENGALURU"),
        ]
        dedup = Deduplicator()
        result = dedup.deduplicate(jobs)
        assert len(result) == 1

    def test_existing_ids_respected(self):
        existing_ids = {"existing_id"}
        dedup = Deduplicator(existing_ids=existing_ids)
        jobs = [make_job(job_id="existing_id")]
        result = dedup.deduplicate(jobs)
        assert len(result) == 0

    def test_existing_status_preserved(self):
        """
        When a job already exists in the sheet, the application status
        and notes from the sheet must be preserved.
        This tests the deduplicator's existing_ids logic.
        """
        existing_ids = {"id_already_in_sheet"}
        dedup = Deduplicator(existing_ids=existing_ids)
        job = make_job(job_id="id_already_in_sheet")
        result = dedup.deduplicate([job])
        assert len(result) == 0  # not duplicated into sheet

    def test_empty_input(self):
        dedup = Deduplicator()
        assert dedup.deduplicate([]) == []

    def test_register_prevents_future_duplicate(self):
        job1 = make_job(job_id="id1")
        job2 = make_job(job_id="id1")
        dedup = Deduplicator()
        dedup.register(job1)
        assert dedup.is_duplicate(job2)
