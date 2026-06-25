"""Tests for PubMed PII variants + non-paper husk dropping."""

from papertrail.enrich_cascade import (
    _extract_ids,
    _format_pii_variants,
    _is_nonpaper_host,
    drop_nonpaper_husks,
    has_semantic_content,
)


def test_format_pii_variants_reformats_bare():
    v = _format_pii_variants("S2405471224003120")
    assert "S2405471224003120" in v
    assert "S2405-4712(24)00312-0" in v  # the form PubMed indexes


def test_format_pii_variants_leaves_punctuated():
    v = _format_pii_variants("S0092-8674(24)00827-1")
    assert v == ["S0092-8674(24)00827-1"]


def test_extract_ids_bare_sciencedirect_pii():
    ids = _extract_ids("https://www.sciencedirect.com/science/article/pii/S2405471224003120")
    assert ids.get("pii") == "S2405471224003120"


def test_is_nonpaper_host():
    assert _is_nonpaper_host("https://github.com/owner/repo")
    assert _is_nonpaper_host("https://google.github.io/deepvariant/")
    assert _is_nonpaper_host("https://huggingface.co/spaces/InstaDeepAI/ntv3")
    assert _is_nonpaper_host("https://huggingface.co/docs/hub/models")
    assert _is_nonpaper_host("https://abc.supabase.co/x")
    assert not _is_nonpaper_host("https://huggingface.co/papers/2401.12345")
    assert not _is_nonpaper_host("https://www.biorxiv.org/content/10.1101/x")


def test_drop_nonpaper_husks_keeps_real_paper_husks():
    papers = [
        {"title": "Real Paper", "abstract": "", "url": "https://github.com/x/y"},   # has title -> keep
        {"title": "", "abstract": "", "url": "https://github.com/x/y"},             # husk + repo -> drop
        {"title": "", "abstract": "", "url": "https://huggingface.co/spaces/a/b"},  # husk + space -> drop
        {"title": "", "abstract": "", "url": "https://www.biorxiv.org/content/x"},  # husk but real paper -> keep
    ]
    dropped = drop_nonpaper_husks(papers)
    assert dropped == 2
    assert len(papers) == 2
    assert any("biorxiv" in p["url"] for p in papers)   # real-paper husk preserved
    assert any(has_semantic_content(p) for p in papers)
