"""Tests for the enrichment cascade helpers."""

from papertrail import enrich_cascade
from papertrail.enrich_cascade import (
    apply_url_fallback_titles,
    derive_title_from_url,
    is_dead_link,
)


class _FakeResp:
    def __init__(self, status_code=200, text=""):
        self.status_code = status_code
        self.text = text


def _patch_get(monkeypatch, **kwargs):
    def fake_get(*a, **k):
        if "exc" in kwargs:
            raise kwargs["exc"]
        return _FakeResp(kwargs.get("status_code", 200), kwargs.get("text", ""))

    monkeypatch.setattr(enrich_cascade.requests, "get", fake_get)


def test_true_404_is_dead(monkeypatch):
    _patch_get(monkeypatch, status_code=404)
    assert is_dead_link("https://example.com/missing") is True


def test_not_found_body_is_dead(monkeypatch):
    _patch_get(monkeypatch, status_code=200, text="<h1>Page not found</h1>")
    assert is_dead_link("https://example.com/gone") is True


def test_forbidden_is_not_dead(monkeypatch):
    """403 = bot-blocked publisher, not a dead link — keep the paper."""
    _patch_get(monkeypatch, status_code=403)
    assert is_dead_link("https://www.sciencedirect.com/science/article/pii/X") is False


def test_rate_limited_is_not_dead(monkeypatch):
    """429 = rate limited, not dead — keep the paper."""
    _patch_get(monkeypatch, status_code=429)
    assert is_dead_link("https://example.com/paper") is False


def test_paywall_401_is_not_dead(monkeypatch):
    _patch_get(monkeypatch, status_code=401)
    assert is_dead_link("https://www.nature.com/articles/abc") is False


def test_server_error_is_not_dead(monkeypatch):
    _patch_get(monkeypatch, status_code=503)
    assert is_dead_link("https://example.com/paper") is False


def test_timeout_is_not_dead(monkeypatch):
    """Network failure must not delete a paper — be conservative, keep it."""
    _patch_get(monkeypatch, exc=enrich_cascade.requests.Timeout("slow"))
    assert is_dead_link("https://example.com/paper") is False


def test_ok_page_is_not_dead(monkeypatch):
    _patch_get(monkeypatch, status_code=200, text="<html>A real paper abstract</html>")
    assert is_dead_link("https://example.com/paper") is False


# --- URL-based fallback titles -------------------------------------------------

def test_derive_title_arxiv():
    assert derive_title_from_url("https://arxiv.org/abs/2401.12345") == "arXiv:2401.12345"
    assert derive_title_from_url("https://arxiv.org/pdf/2401.12345v2") == "arXiv:2401.12345v2"


def test_derive_title_humanizes_last_path_segment():
    assert derive_title_from_url("https://tahoebio-assets.com/rhaister-manuscript.pdf") == "Rhaister Manuscript"
    assert derive_title_from_url("https://nrehiew.github.io/blog/sft_rl_opd") == "Sft Rl Opd"


def test_derive_title_opaque_id_falls_back_to_host():
    # ScienceDirect PII is opaque — better to show the host than a meaningless id
    title = derive_title_from_url("https://www.sciencedirect.com/science/article/pii/S0092867418302290")
    assert "sciencedirect.com" in title


def test_derive_title_never_empty():
    assert derive_title_from_url("https://example.com/") != ""


def test_apply_url_fallback_titles_only_fills_untitled():
    papers = [
        {"url": "https://arxiv.org/abs/2401.12345", "title": ""},
        {"url": "https://example.com/x", "title": "A Real Title"},
        {"url": "https://tahoebio-assets.com/rhaister-manuscript.pdf"},  # no title key
        {"url": "https://x.com/y", "title": "Preparing to download ..."},  # junk → treated as untitled
    ]
    filled = apply_url_fallback_titles(papers)
    assert filled == 3
    assert papers[0]["title"] == "arXiv:2401.12345"
    assert papers[1]["title"] == "A Real Title"  # untouched
    assert papers[2]["title"] == "Rhaister Manuscript"
    assert papers[3]["title"] == "Y"
