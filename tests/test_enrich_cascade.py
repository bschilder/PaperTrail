"""Tests for the enrichment cascade helpers."""

from papertrail import enrich_cascade
from papertrail.enrich_cascade import is_dead_link


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
