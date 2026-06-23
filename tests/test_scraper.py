"""Tests for the scraper module."""

import pytest

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


@pytest.fixture
def scraper():
    return SlackScraper(token="xoxb-test")


@pytest.mark.parametrize(
    "url",
    [
        "https://www.sciencedirect.com/science/article/pii/S0092867424001234",
        "https://huggingface.co/papers/2401.12345",
        "https://www.nejm.org/doi/full/10.1056/NEJMoa2034577",
        "https://www.thelancet.com/journals/lancet/article/abc/fulltext",
        "https://aclanthology.org/2023.acl-long.1/",
        "https://proceedings.neurips.cc/paper_files/paper/2023/hash/abc.html",
        "https://proceedings.mlr.press/v202/smith23a.html",
        "https://openaccess.thecvf.com/content/CVPR2023/html/paper.html",
        "https://dl.acm.org/doi/10.1145/3580305",
        "https://ieeexplore.ieee.org/document/9999999",
        "https://www.mdpi.com/2073-4409/12/1/100",
        "https://www.frontiersin.org/articles/10.3389/fgene.2023.123/full",
        "https://chemrxiv.org/engage/chemrxiv/article-details/abc",
        "https://osf.io/preprints/abc123",
        "https://www.researchsquare.com/article/rs-123/v1",
        "https://jamanetwork.com/journals/jama/fullarticle/2788888",
    ],
)
def test_expanded_publisher_domains_recognized(scraper, url):
    """Major publisher/preprint domains the team uses should be recognized."""
    assert scraper.is_paper_url(url)


def test_wiley_domain_recognized(scraper):
    """Regression: the www-strip bug mangled domains starting with 'w' (wiley.com)."""
    assert scraper.is_paper_url("https://onlinelibrary.wiley.com/page/journal/abc")


def test_arbitrary_host_pdf_recognized(scraper):
    """Direct PDF links on arbitrary hosts are papers/manuscripts."""
    assert scraper.is_paper_url("https://tahoebio-assets.com/rhaister-manuscript.pdf")
    assert scraper.is_paper_url("https://www.ttic.edu/dl/dark14.pdf")


def test_research_blog_and_announcements_recognized(scraper):
    """Research blogs and model/benchmark announcement pages should count."""
    assert scraper.is_paper_url("https://nrehiew.github.io/blog/sft_rl_opd/")
    assert scraper.is_paper_url("https://openai.com/index/introducing-life-sci-bench/")
    assert scraper.is_paper_url("https://blog.google/technology/developers-tools/introducing-gemma-4-12b/")
    assert scraper.is_paper_url("https://tilderesearch.com/research")


def test_social_and_noise_still_excluded(scraper):
    """Social media and chat noise must stay excluded even with broadened rules."""
    assert not scraper.is_paper_url("https://twitter.com/someone/status/123")
    assert not scraper.is_paper_url("https://x.com/i/status/2063067286408478867")
    assert not scraper.is_paper_url("https://www.youtube.com/watch?v=abc")
    assert not scraper.is_paper_url("https://app.slack.com/client/T1/C1")
    assert not scraper.is_paper_url("https://www.linkedin.com/posts/someone-activity-123")


def test_redirect_links_resolved_then_matched(scraper, monkeypatch):
    """share.google-style redirects should resolve to their real paper URL."""
    real = "https://www.nature.com/articles/s41586-026-10675-5"
    monkeypatch.setattr(scraper, "_resolve_redirect", lambda u: real)
    out = scraper.extract_paper_urls(["check this <https://share.google/WXIRml0ZwMyhxNE0q>"])
    assert any("nature.com" in u for u in out)


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
