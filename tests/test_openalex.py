"""Tests for OpenAlex parsing + title-search query construction."""

from papertrail import enrich_cascade
from papertrail.enrich_cascade import (
    _lookup_openalex_by_abstract,
    _lookup_openalex_title,
    _parse_openalex,
)


def test_parse_openalex_extracts_authors_and_affiliations():
    data = {
        "title": "A Paper",
        "publication_year": 2024,
        "cited_by_count": 42,
        "authorships": [
            {"author": {"display_name": "Ada Lovelace"},
             "institutions": [{"display_name": "MIT"}]},
            {"author": {"display_name": "Alan Turing"},
             "institutions": [{"display_name": "MIT"}, {"display_name": "Stanford"}]},
        ],
    }
    r = _parse_openalex(data)
    assert r["authors"] == ["Ada Lovelace", "Alan Turing"]
    assert r["affiliations"] == ["MIT", "Stanford"]  # de-duped, order-preserving
    assert r["cited_by_count"] == 42


def test_openalex_title_search_is_not_double_encoded(monkeypatch):
    """Regression: the title must reach the API as raw text, not pre-%-encoded.

    Pre-quoting then letting requests encode again turned spaces into %2520
    and matched nothing — silently breaking all title-based enrichment.
    """
    captured = {}

    class _Resp:
        ok = True

        def json(self):
            return {"results": [{"title": "Denoising Diffusion Probabilistic Models"}]}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        return _Resp()

    monkeypatch.setattr(enrich_cascade.requests, "get", fake_get)
    _lookup_openalex_title("Denoising Diffusion Probabilistic Models", "e@x.org")

    assert captured["params"]["filter"] == "title.search:Denoising Diffusion Probabilistic Models"
    assert "%25" not in captured["params"]["filter"]
    assert "%20" not in captured["params"]["filter"]


OURS = ("We present high quality image synthesis results using diffusion probabilistic "
        "models a class of latent variable models inspired by nonequilibrium thermodynamics")


def _mock_openalex(monkeypatch, returned_abstract):
    inv = {}
    for i, w in enumerate(returned_abstract.split()):
        inv.setdefault(w, []).append(i)

    class _Resp:
        ok = True

        def json(self):
            return {"results": [{"title": "Some Paper", "abstract_inverted_index": inv,
                                 "authorships": [], "publication_year": 2020}]}

    monkeypatch.setattr(enrich_cascade.requests, "get",
                        lambda *a, **k: _Resp())


def test_abstract_search_adopts_confident_match(monkeypatch):
    _mock_openalex(monkeypatch, OURS)  # returned abstract == ours
    r = _lookup_openalex_by_abstract(OURS, "e@x.org")
    assert r and r.get("title") == "Some Paper"


def test_abstract_search_rejects_topically_similar_mismatch(monkeypatch):
    # A different diffusion paper — shares some jargon but is not the same abstract.
    other = ("We introduce Palette a unified framework for image-to-image translation "
             "based on conditional diffusion achieving strong results on colorization")
    _mock_openalex(monkeypatch, other)
    assert _lookup_openalex_by_abstract(OURS, "e@x.org") is None
