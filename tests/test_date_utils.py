"""
tests/test_date_utils.py
"""

import pytest
from core.date_utils import parse_date, days_since, is_within_days, today_iso
from datetime import date, timedelta


class TestParseDate:
    def test_iso_format(self):
        assert parse_date("2024-05-01") == "2024-05-01"

    def test_iso_datetime_with_tz(self):
        result = parse_date("2024-05-01T12:00:00+05:30")
        assert result == "2024-05-01"

    def test_iso_datetime_utc(self):
        result = parse_date("2024-05-01T12:00:00Z")
        assert result == "2024-05-01"

    def test_none_returns_unknown(self):
        assert parse_date(None) == "Unknown"

    def test_empty_string_returns_unknown(self):
        assert parse_date("") == "Unknown"

    def test_null_string_returns_unknown(self):
        assert parse_date("null") == "Unknown"

    def test_none_string_returns_unknown(self):
        assert parse_date("none") == "Unknown"

    def test_garbage_returns_unknown(self):
        assert parse_date("not-a-date-xyz-123!") == "Unknown"

    def test_unknown_literal_returns_unknown(self):
        assert parse_date("Unknown") == "Unknown"

    def test_slash_format_dmy(self):
        result = parse_date("01/05/2024")
        # dateutil parses this as May 1 or Jan 5 depending on locale;
        # we just verify it doesn't return "Unknown"
        assert result != "Unknown"

    def test_unix_timestamp_style_not_supported_gracefully(self):
        # Raw integer timestamps should not crash
        result = parse_date(1714521600)
        # dateutil may parse year out of this; just verify no exception
        assert isinstance(result, str)


class TestDaysSince:
    def test_today_is_zero(self):
        assert days_since(today_iso()) == 0

    def test_yesterday(self):
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        assert days_since(yesterday) == 1

    def test_unknown_returns_none(self):
        assert days_since("Unknown") is None

    def test_invalid_string_returns_none(self):
        assert days_since("bad-date") is None


class TestIsWithinDays:
    def test_today_within_30(self):
        assert is_within_days(today_iso(), 30) is True

    def test_old_date_outside(self):
        old = (date.today() - timedelta(days=60)).isoformat()
        assert is_within_days(old, 30) is False

    def test_unknown_date_passes(self):
        # Critical: unknown dates must NOT be rejected
        assert is_within_days("Unknown", 30) is True

    def test_exactly_at_boundary(self):
        boundary = (date.today() - timedelta(days=30)).isoformat()
        assert is_within_days(boundary, 30) is True
