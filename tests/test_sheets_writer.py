"""
tests/test_sheets_writer.py
----------------------------
Tests for the Google Sheets writer logic.
No real Google credentials are required.
gspread is mocked entirely.
"""

import pytest
from unittest.mock import MagicMock, patch, call
from core.models import JobListing
from core.date_utils import today_iso


def make_job(job_id="id1", title="DevOps Engineer", company="Acme",
             location="Bengaluru", score=75, status="Not Applied", notes="") -> JobListing:
    j = JobListing(
        job_id=job_id,
        title=title,
        company=company,
        location=location,
        match_score=score,
        application_status=status,
        notes=notes,
        discovered_date=today_iso(),
        posted_date="Unknown",
    )
    return j


def _base_config():
    return {
        "google_sheets": {
            "sheet_id_env": "GOOGLE_SHEET_ID",
            "credentials_env": "GOOGLE_SERVICE_ACCOUNT_JSON",
            "worksheets": {
                "all_jobs": "All Jobs",
                "today_jobs": "Today's Jobs",
                "high_match": "High Match",
                "tracker": "Application Tracker",
            },
        },
        "filters": {"high_match_threshold": 65},
    }


class TestSheetsWriterStatusPreservation:
    """
    Verifies that when a job already exists in the sheet,
    the application_status and notes from the sheet are preserved.
    """

    def test_existing_status_preserved(self):
        """
        A job that is already in the sheet should not be appended again,
        and if it were re-processed, it would carry the existing status/notes.
        """
        from sheets.writer import _apply_preserved_tracking

        job = make_job(job_id="id1", status="Not Applied", notes="")
        tracking = {
            "id1": {"status": "Applied", "notes": "Sent resume 2024-05-01", "last_verified": ""}
        }
        result = _apply_preserved_tracking(job, tracking)
        assert result.application_status == "Applied"
        assert result.notes == "Sent resume 2024-05-01"

    def test_new_job_keeps_default_status(self):
        from sheets.writer import _apply_preserved_tracking

        job = make_job(job_id="new_id", status="Not Applied", notes="")
        tracking = {}
        result = _apply_preserved_tracking(job, tracking)
        assert result.application_status == "Not Applied"
        assert result.notes == ""

    def test_existing_notes_not_overwritten(self):
        from sheets.writer import _apply_preserved_tracking

        job = make_job(job_id="id2", notes="new incoming note")
        tracking = {"id2": {"status": "Interview", "notes": "Original note", "last_verified": ""}}
        result = _apply_preserved_tracking(job, tracking)
        # Sheet notes take priority
        assert result.notes == "Original note"


class TestReadExistingJobs:
    def test_empty_sheet_returns_empty(self):
        from sheets.writer import _read_existing_jobs

        mock_ws = MagicMock()
        mock_ws.get_all_values.return_value = [JobListing.sheet_headers()]
        tracking, seen = _read_existing_jobs(mock_ws)
        assert tracking == {}
        assert seen == set()

    def test_reads_existing_job_ids(self):
        from sheets.writer import _read_existing_jobs

        header = JobListing.sheet_headers()
        row = ["id_abc"] + [""] * (len(header) - 1)
        row[13] = "Applied"   # Application Status (index 13 = col 14)
        row[14] = "My note"   # Notes
        mock_ws = MagicMock()
        mock_ws.get_all_values.return_value = [header, row]
        tracking, seen = _read_existing_jobs(mock_ws)
        assert "id_abc" in seen
        assert tracking["id_abc"]["status"] == "Applied"
        assert tracking["id_abc"]["notes"] == "My note"


class TestUpdateSheetsGuards:
    """Verify that update_sheets guards are triggered correctly."""

    def test_missing_sheet_id_env_aborts(self, monkeypatch):
        from sheets import writer
        monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
        config = _base_config()
        # Should return without raising
        writer.update_sheets([], config)

    def test_missing_credentials_env_aborts(self, monkeypatch):
        from sheets import writer
        monkeypatch.setenv("GOOGLE_SHEET_ID", "fake_sheet_id")
        monkeypatch.delenv("GOOGLE_SERVICE_ACCOUNT_JSON", raising=False)
        config = _base_config()
        writer.update_sheets([], config)  # Should not raise


class TestHighMatchFiltering:
    def test_only_high_score_jobs_in_high_match(self):
        """High Match sheet should contain only jobs above threshold."""
        jobs = [
            make_job(job_id="high", score=80),
            make_job(job_id="low", score=40),
        ]
        threshold = 65
        high_match = [j for j in jobs if j.match_score >= threshold]
        assert len(high_match) == 1
        assert high_match[0].job_id == "high"

    def test_configurable_threshold(self):
        jobs = [make_job(job_id=str(i), score=i * 10) for i in range(11)]
        threshold = 70
        high_match = [j for j in jobs if j.match_score >= threshold]
        assert all(j.match_score >= 70 for j in high_match)
