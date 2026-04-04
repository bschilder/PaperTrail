"""Tests for the enricher module."""

from papertrail.enricher import _extract_arxiv_id, _extract_doi


def test_extract_doi():
    assert _extract_doi("https://doi.org/10.1101/2024.01.01.123456") == "10.1101/2024.01.01.123456"
    assert _extract_doi("https://nature.com/articles/s41586-024-01234-5") is None
    assert _extract_doi("no doi here") is None


def test_extract_arxiv_id():
    assert _extract_arxiv_id("https://arxiv.org/abs/2401.12345") == "2401.12345"
    assert _extract_arxiv_id("https://arxiv.org/pdf/2401.12345v2") == "2401.12345v2"
    assert _extract_arxiv_id("https://example.com") is None
