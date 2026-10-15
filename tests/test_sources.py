"""
tests/test_sources.py
---------------------
Tests for source adapters using mocked HTTP responses.
No real network requests are made.
"""

import json
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path


def load_config():
    config_path = Path(__file__).parent.parent / "config.json"
    with config_path.open() as f:
        return json.load(f)


# ── Remotive ──────────────────────────────────────────────────────────────────

class TestRemotiveSource:
    def _make_mock_response(self, jobs_data, status=200):
        mock_resp = MagicMock()
        mock_resp.status_code = status
        mock_resp.json.return_value = {"jobs": jobs_data}
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    def test_returns_india_eligible_job(self):
        from sources.remotive import RemotiveSource
        config = load_config()
        source = RemotiveSource(config)
        fake_job = {
            "id": 1,
            "title": "DevOps Engineer",
            "company_name": "TestCo",
            "url": "https://remotive.com/job/1",
            "candidate_required_location": "Worldwide",
            "description": "<p>AWS Docker Kubernetes</p>",
            "tags": ["aws", "docker"],
            "publication_date": "2024-05-01",
        }
        # The mock is called once per configured category (3 total by default),
        # so the same fake job appears multiple times.  We assert >= 1.
        with patch("requests.get", return_value=self._make_mock_response([fake_job])):
            jobs = source.fetch()
        assert len(jobs) >= 1
        assert jobs[0].company == "TestCo"
        assert jobs[0].source == "remotive"

    def test_rejects_us_only_job(self):
        from sources.remotive import RemotiveSource
        config = load_config()
        source = RemotiveSource(config)
        fake_job = {
            "id": 2,
            "title": "DevOps Engineer",
            "company_name": "USCo",
            "url": "https://remotive.com/job/2",
            "candidate_required_location": "US only",
            "description": "US only role",
            "tags": [],
            "publication_date": "2024-05-01",
        }
        with patch("requests.get", return_value=self._make_mock_response([fake_job])):
            jobs = source.fetch()
        assert len(jobs) == 0

    def test_handles_api_failure_gracefully(self):
        from sources.remotive import RemotiveSource
        import requests as req_module
        config = load_config()
        source = RemotiveSource(config)
        with patch("requests.get", side_effect=req_module.RequestException("timeout")):
            jobs = source.fetch()
        assert jobs == []

    def test_missing_date_becomes_unknown(self):
        from sources.remotive import RemotiveSource
        config = load_config()
        source = RemotiveSource(config)
        fake_job = {
            "id": 3,
            "title": "Cloud Engineer",
            "company_name": "AnonCo",
            "url": "https://remotive.com/job/3",
            "candidate_required_location": "Worldwide",
            "description": "Cloud engineer role",
            "tags": [],
            "publication_date": None,
        }
        with patch("requests.get", return_value=self._make_mock_response([fake_job])):
            jobs = source.fetch()
        if jobs:
            assert jobs[0].posted_date == "Unknown"


# ── Arbeitnow ─────────────────────────────────────────────────────────────────

class TestArbeitnowSource:
    def _make_mock_response(self, data, status=200):
        mock_resp = MagicMock()
        mock_resp.status_code = status
        mock_resp.json.return_value = data
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    def test_returns_india_eligible_job(self):
        from sources.arbeitnow import ArbeitnowSource
        config = load_config()
        source = ArbeitnowSource(config)
        fake_job = {
            "title": "DevOps Engineer",
            "company_name": "IndiaCo",
            "url": "https://arbeitnow.com/jobs/indiago/devops",
            "location": "Remote Worldwide",
            "description": "<p>Work from anywhere in India</p>",
            "tags": ["devops", "aws"],
            "created_at": 1714521600,
        }
        # First call returns data; second (pagination) returns empty to stop
        side_effects = [
            self._make_mock_response({"data": [fake_job]}),
            self._make_mock_response({"data": []}),
        ]
        with patch("requests.get", side_effect=side_effects):
            jobs = source.fetch()
        assert len(jobs) == 1
        assert jobs[0].source == "arbeitnow"

    def test_handles_api_failure(self):
        from sources.arbeitnow import ArbeitnowSource
        import requests as req_module
        config = load_config()
        source = ArbeitnowSource(config)
        with patch("requests.get", side_effect=req_module.RequestException("connection refused")):
            jobs = source.fetch()
        assert jobs == []

    def test_unix_timestamp_parsed_correctly(self):
        from sources.arbeitnow import ArbeitnowSource
        from datetime import datetime, timezone
        config = load_config()
        source = ArbeitnowSource(config)
        ts = 1714521600  # 2024-04-30 or similar
        expected = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        fake_job = {
            "title": "Cloud Engineer",
            "company_name": "Acme",
            "url": "https://arbeitnow.com/jobs/acme/cloud",
            "location": "Remote Worldwide",
            "description": "remote worldwide india eligible",
            "tags": [],
            "created_at": ts,
        }
        side_effects = [
            self._make_mock_response({"data": [fake_job]}),
            self._make_mock_response({"data": []}),
        ]
        with patch("requests.get", side_effect=side_effects):
            jobs = source.fetch()
        if jobs:
            assert jobs[0].posted_date == expected


# ── Greenhouse ────────────────────────────────────────────────────────────────

class TestGreenhouseSource:
    def _make_mock_response(self, jobs_data, status=200):
        mock_resp = MagicMock()
        mock_resp.status_code = status
        mock_resp.json.return_value = {"jobs": jobs_data}
        mock_resp.raise_for_status = MagicMock()
        if status == 404:
            import requests
            http_err = requests.HTTPError(response=mock_resp)
            mock_resp.raise_for_status.side_effect = http_err
        return mock_resp

    def test_returns_india_job(self):
        from sources.greenhouse import GreenhouseSource
        config = load_config()
        source = GreenhouseSource(config)
        fake_job = {
            "title": "DevOps Engineer",
            "absolute_url": "https://boards.greenhouse.io/thoughtworks/jobs/123",
            "location": {"name": "Bengaluru, India"},
            "content": "<p>Great devops role</p>",
            "departments": [{"name": "Engineering"}],
            "updated_at": "2024-05-01T00:00:00Z",
        }
        with patch("requests.get", return_value=self._make_mock_response([fake_job])):
            jobs = source.fetch()
        assert len(jobs) >= 1
        assert "Bengaluru" in jobs[0].location

    def test_404_board_skipped_gracefully(self):
        from sources.greenhouse import GreenhouseSource
        import requests as req_mod
        config = load_config()
        source = GreenhouseSource(config)
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        http_err = req_mod.HTTPError(response=mock_resp)
        mock_resp.raise_for_status.side_effect = http_err
        with patch("requests.get", return_value=mock_resp):
            jobs = source.fetch()
        assert jobs == []

    def test_partial_source_failure_continues(self):
        """If one board fails, others should still be attempted."""
        from sources.greenhouse import GreenhouseSource
        import requests as req_mod
        config = load_config()
        source = GreenhouseSource(config)
        # Override company_boards to just 2 boards
        source.source_config["company_boards"] = ["fail-co", "success-co"]
        fake_job = {
            "title": "Platform Engineer",
            "absolute_url": "https://boards.greenhouse.io/success-co/jobs/1",
            "location": {"name": "Hyderabad, India"},
            "content": "Platform engineer role in India",
            "departments": [],
            "updated_at": "2024-05-01T00:00:00Z",
        }
        fail_resp = MagicMock()
        fail_resp.status_code = 404
        fail_resp.raise_for_status.side_effect = req_mod.HTTPError(response=fail_resp)

        ok_resp = MagicMock()
        ok_resp.status_code = 200
        ok_resp.json.return_value = {"jobs": [fake_job]}
        ok_resp.raise_for_status = MagicMock()

        with patch("requests.get", side_effect=[fail_resp, ok_resp]):
            jobs = source.fetch()
        assert len(jobs) == 1


# ── Lever ─────────────────────────────────────────────────────────────────────

class TestLeverSource:
    def _make_mock_response(self, jobs_data, status=200):
        mock_resp = MagicMock()
        mock_resp.status_code = status
        mock_resp.json.return_value = jobs_data
        mock_resp.raise_for_status = MagicMock()
        return mock_resp

    def test_returns_india_job(self):
        from sources.lever import LeverSource
        config = load_config()
        source = LeverSource(config)
        fake_job = {
            "text": "DevOps Engineer",
            "hostedUrl": "https://jobs.lever.co/razorpay/123",
            "categories": {"location": "Bengaluru", "team": "Engineering", "commitment": "Full-time"},
            "descriptionPlain": "AWS DevOps role in Bengaluru India",
            "createdAt": 1714521600000,
        }
        with patch("requests.get", return_value=self._make_mock_response([fake_job])):
            jobs = source.fetch()
        assert len(jobs) >= 1

    def test_ms_timestamp_parsed(self):
        from sources.lever import LeverSource
        from datetime import datetime, timezone
        config = load_config()
        source = LeverSource(config)
        ts_ms = 1714521600000
        expected = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date().isoformat()
        fake_job = {
            "text": "Cloud Engineer",
            "hostedUrl": "https://jobs.lever.co/company/456",
            "categories": {"location": "Remote India"},
            "descriptionPlain": "Remote india cloud role",
            "createdAt": ts_ms,
        }
        with patch("requests.get", return_value=self._make_mock_response([fake_job])):
            jobs = source.fetch()
        if jobs:
            assert jobs[0].posted_date == expected

    def test_handles_failure_gracefully(self):
        from sources.lever import LeverSource
        import requests as req_mod
        config = load_config()
        source = LeverSource(config)
        with patch("requests.get", side_effect=req_mod.RequestException("timeout")):
            jobs = source.fetch()
        assert jobs == []
