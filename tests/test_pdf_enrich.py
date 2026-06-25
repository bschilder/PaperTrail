"""Tests for PDF text → title/abstract parsing."""

from papertrail.enrich_cascade import (
    _is_pdf_url,
    _parse_pdf_abstract,
    _parse_pdf_title,
    _titles_match,
)


def test_titles_match_confirms_same_title():
    assert _titles_match("Attention is all you need", "Attention Is All You Need")
    assert _titles_match(
        "Distilling the Knowledge in a Neural Network",
        "Distilling the knowledge in a neural network (NIPS workshop)",
    )


def test_titles_match_rejects_unrelated():
    assert not _titles_match("The conflicting constraints", "A Foundation Model for the Cancer Genome")
    assert not _titles_match("", "anything")


def test_titles_match_rejects_partial_fragment_false_positive():
    # Real bug: a PDF body fragment matched an unrelated paper because its few
    # tokens were a subset of the candidate. Jaccard (overlap/union) rejects it.
    assert not _titles_match(
        "The conflicting constraints",
        "Conflicting constraints on the form of intertidal algae",
    )


def test_titles_match_tolerates_minor_truncation():
    assert _titles_match(
        "Denoising Diffusion Probabilistic",
        "Denoising Diffusion Probabilistic Models",
    )


def test_is_pdf_url():
    assert _is_pdf_url("https://tahoebio-assets.com/rhaister-manuscript.pdf")
    assert _is_pdf_url("https://www.ttic.edu/dl/dark14.pdf")
    assert _is_pdf_url("https://cdn.openai.com/pdf/abc.pdf?token=xyz")  # query string
    assert not _is_pdf_url("https://arxiv.org/abs/2401.12345")
    assert not _is_pdf_url("https://www.nature.com/articles/s41586-024-1.html")


def test_is_pdf_url_openreview():
    # OpenReview serves PDFs at /pdf?id=... — no .pdf extension, id in query.
    assert _is_pdf_url("https://openreview.net/pdf?id=HJFVrpCaGE")
    assert _is_pdf_url("https://openreview.net/pdf/abc123")
    assert not _is_pdf_url("https://openreview.net/forum?id=HJFVrpCaGE")  # forum page, not PDF


SAMPLE = """A Foundation Model for the Cancer Genome
Jane Doe, John Smith, Alice Lee
Some Institute of Technology

Abstract
We introduce a foundation model trained on whole-exome data that learns
useful representations of genomic variation. It outperforms prior methods.

1 Introduction
Deep learning has transformed genomics in recent years ...
"""


def test_parse_pdf_abstract_extracts_section():
    abstract = _parse_pdf_abstract(SAMPLE)
    assert abstract.startswith("We introduce a foundation model")
    assert "outperforms prior methods" in abstract
    assert "Introduction" not in abstract
    assert "foundation model trained" in abstract


def test_parse_pdf_abstract_handles_keywords_terminator():
    text = "Title\nAbstract\nThis is the abstract body here.\nKeywords: genomics, ML\nMore."
    assert _parse_pdf_abstract(text) == "This is the abstract body here."


def test_parse_pdf_abstract_empty_when_no_marker():
    assert _parse_pdf_abstract("Just some text\nwith no abstract heading\n") == ""


def test_parse_pdf_title_uses_first_substantive_line():
    assert _parse_pdf_title(SAMPLE) == "A Foundation Model for the Cancer Genome"


def test_parse_pdf_title_prefers_good_metadata_title():
    title = _parse_pdf_title(SAMPLE, meta_title="A Foundation Model for the Cancer Genome")
    assert title == "A Foundation Model for the Cancer Genome"


def test_parse_pdf_title_ignores_junk_metadata_title():
    # PDF producers often set the title to the source filename — ignore it.
    title = _parse_pdf_title(SAMPLE, meta_title="Microsoft Word - manuscript_final_v3.docx")
    assert title == "A Foundation Model for the Cancer Genome"


def test_parse_pdf_title_rejects_author_and_legal_lines():
    # Real-world PDF top matter: legal notice, then an author line, then the title.
    text = (
        "Provided proper attribution is provided, Google hereby grants permission\n"
        "Geoffrey Hinton, Oriol Vinyals & Jeff Dean\n"
        "Distilling the Knowledge in a Neural Network\n"
    )
    assert _parse_pdf_title(text) == "Distilling the Knowledge in a Neural Network"
