"""Tests for the scraper module."""

from papertrail.scraper import PAPER_URL_REGEX, SlackScraper


def test_paper_url_detection():
    """Test that paper URL patterns are detected correctly."""
    assert PAPER_URL_REGEX.search("https://doi.org/10.1101/test")
    assert PAPER_URL_REGEX.search("https://arxiv.org/abs/2401.12345")
    assert PAPER_URL_REGEX.search("https://www.biorxiv.org/content/10.1101/test")
    assert PAPER_URL_REGEX.search("https://pubmed.ncbi.nlm.nih.gov/12345678")
    assert PAPER_URL_REGEX.search("https://www.nature.com/articles/s41586-test")
    assert not PAPER_URL_REGEX.search("https://google.com")
    assert not PAPER_URL_REGEX.search("https://slack.com/messages")


def test_clean_text():
    """Test Slack text cleanup."""
    text = "<https://example.com|Click here> :fire: <@U12345|Alice> said hello"
    cleaned = SlackScraper._clean_text(text)
    assert "Click here" in cleaned
    assert "<" not in cleaned
    assert ":fire:" not in cleaned


def test_ts_to_date():
    """Test timestamp to date conversion."""
    assert SlackScraper._ts_to_date("1770330392.065239") == "2026-02-05"
    assert SlackScraper._ts_to_date("invalid") == ""
