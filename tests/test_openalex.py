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


def test_fill_missing_metadata_raw_title_and_affiliations(monkeypatch):
    """The batch backfill must also pass raw titles and now fills affiliations."""
    from papertrail import enricher

    captured = {}

    class _Resp:
        ok = True

        def json(self):
            return {"results": [{
                "title": "Some Real Paper Title",
                "publication_year": 2020,
                "cited_by_count": 5,
                "authorships": [{"author": {"display_name": "Ada Lovelace"},
                                 "institutions": [{"display_name": "MIT"}]}],
                "abstract_inverted_index": {"Hello": [0], "world": [1]},
            }]}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["params"] = params
        return _Resp()

    monkeypatch.setattr(enricher.requests, "get", fake_get)
    papers = [{"title": "Some Real Paper Title", "url": "https://h/x", "authors": []}]
    enricher.fill_missing_metadata(papers, email="e@x.org")

    assert captured["params"]["filter"] == "title.search:Some Real Paper Title"
    assert papers[0]["authors"] == ["Ada Lovelace"]
    assert papers[0]["affiliations"] == ["MIT"]


def test_fill_missing_metadata_rejects_mismatched_title(monkeypatch):
    """A blog/repo title that best-matches an unrelated paper must NOT adopt it."""
    from papertrail import enricher

    class _Resp:
        ok = True

        def json(self):
            return {"results": [{
                "title": "SCALPEL: Selective Capability Ablation",
                "authorships": [{"author": {"display_name": "Someone Else"}}],
                "publication_year": 2025,
            }]}

    monkeypatch.setattr(enricher.requests, "get", lambda *a, **k: _Resp())
    papers = [{"title": "Interpreting Language Model Parameters", "url": "https://goodfire.ai/x", "authors": []}]
    enricher.fill_missing_metadata(papers, email="e@x.org")
    assert not papers[0].get("authors")  # mismatch rejected, no wrong metadata


def test_clean_doi_truncates_embedded_url():
    from papertrail.enrich_cascade import _clean_doi
    assert _clean_doi("10.1126/science.abl4290https://www.science.org/doi/x") == "10.1126/science.abl4290"
    assert _clean_doi("10.1101/2023.07.26.550653.full") == "10.1101/2023.07.26.550653"


def test_doi_candidates_trims_trailing_segments():
    from papertrail.enrich_cascade import _doi_candidates
    cands = list(_doi_candidates("10.1093/gigascience/giaf132/829"))
    assert cands[0] == "10.1093/gigascience/giaf132/829"
    assert "10.1093/gigascience/giaf132" in cands   # the real DOI is reached
    assert all(c.startswith("10.1093/") for c in cands)
    assert "10.1093" not in cands                    # never trims below prefix+1


def test_extract_ids_cleans_doubled_science_url():
    from papertrail.enrich_cascade import _extract_ids
    ids = _extract_ids("https://www.science.org/doi/10.1126/science.abl4290https://www.science.org/doi/1")
    assert ids.get("doi") == "10.1126/science.abl4290"


def test_doi_candidates_strips_version():
    from papertrail.enrich_cascade import _doi_candidates
    cands = list(_doi_candidates("10.1101/2024.10.29.620913v2"))
    assert "10.1101/2024.10.29.620913" in cands  # versionless form tried


def test_extract_ids_biorxiv_early_format():
    from papertrail.enrich_cascade import _extract_ids
    ids = _extract_ids("http://biorxiv.org/content/early/2023/10/26/2023.07.26.550653")
    assert ids.get("doi") == "10.1101/2023.07.26.550653"
    assert ids.get("biorxiv_doi") == "10.1101/2023.07.26.550653"
