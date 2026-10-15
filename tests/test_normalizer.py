"""
tests/test_normalizer.py
"""

import pytest
from core.normalizer import (
    strip_html,
    normalize_url,
    build_job_id,
    normalize_location,
    normalize_skills,
)


class TestStripHtml:
    def test_strips_tags(self):
        assert strip_html("<b>Hello</b> World") == "Hello World"

    def test_decodes_entities(self):
        assert strip_html("&amp; &lt;br&gt;") == "& <br>"

    def test_empty_string(self):
        assert strip_html("") == ""

    def test_plain_text_unchanged(self):
        assert strip_html("plain text") == "plain text"

    def test_collapses_whitespace(self):
        result = strip_html("<p>Hello   World</p>")
        assert "  " not in result


class TestNormalizeUrl:
    def test_strips_utm_params(self):
        url = "https://example.com/job?utm_source=google&utm_medium=cpc"
        result = normalize_url(url)
        assert "utm_source" not in result
        assert "utm_medium" not in result

    def test_strips_ref_param(self):
        url = "https://example.com/job?ref=linkedin&id=123"
        result = normalize_url(url)
        assert "ref=" not in result
        assert "id=123" in result

    def test_lowercases_host(self):
        url = "https://EXAMPLE.COM/Job"
        result = normalize_url(url)
        assert "example.com" in result

    def test_strips_trailing_slash(self):
        result = normalize_url("https://example.com/jobs/123/")
        assert not result.endswith("/")

    def test_empty_url_returns_empty(self):
        assert normalize_url("") == ""

    def test_invalid_url_returned_as_is(self):
        result = normalize_url("not-a-url")
        assert result == "not-a-url"

    def test_same_url_different_tracking_equal(self):
        url1 = normalize_url("https://jobs.example.com/devops?utm_source=a")
        url2 = normalize_url("https://jobs.example.com/devops?utm_source=b")
        assert url1 == url2


class TestBuildJobId:
    def test_produces_16_char_hex(self):
        jid = build_job_id("remotive", "https://example.com/job/1", "DevOps Eng", "Acme")
        assert len(jid) == 16
        assert all(c in "0123456789abcdef" for c in jid)

    def test_reproducible(self):
        a = build_job_id("remotive", "https://example.com/job/1", "DevOps Eng", "Acme")
        b = build_job_id("remotive", "https://example.com/job/1", "DevOps Eng", "Acme")
        assert a == b

    def test_different_url_different_id(self):
        a = build_job_id("remotive", "https://example.com/job/1", "DevOps Eng", "Acme")
        b = build_job_id("remotive", "https://example.com/job/2", "DevOps Eng", "Acme")
        assert a != b

    def test_utm_stripped_before_hashing(self):
        # Two URLs that differ only in tracking params should produce the same ID
        a = build_job_id("remotive", "https://example.com/job/1?utm_source=a", "T", "C")
        b = build_job_id("remotive", "https://example.com/job/1?utm_source=b", "T", "C")
        assert a == b


class TestNormalizeSkills:
    def test_list_input(self):
        result = normalize_skills(["AWS", "Docker", "Kubernetes"])
        assert result == "AWS, Docker, Kubernetes"

    def test_string_input(self):
        result = normalize_skills("AWS, Docker,  Kubernetes")
        assert result == "AWS, Docker, Kubernetes"

    def test_empty_list(self):
        assert normalize_skills([]) == ""

    def test_none_like_input(self):
        assert normalize_skills(None) == ""
