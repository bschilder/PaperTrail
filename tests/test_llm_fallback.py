"""Tests for the Claude LLM enrichment fallback."""

from papertrail import enrich_cascade
from papertrail.enrich_cascade import (
    _coerce_llm_meta,
    _llm_extract_metadata,
    _parse_llm_json,
    _sanitize_for_api,
)


def test_sanitize_strips_control_chars_and_keeps_text():
    raw = "Hello\x00 world\x07\nLine\ttwo"
    out = _sanitize_for_api(raw)
    assert "\x00" not in out and "\x07" not in out
    assert "Hello" in out and "world" in out
    assert "\n" in out and "\t" in out  # legitimate whitespace preserved


def test_sanitize_drops_lone_surrogates():
    raw = "ok\ud800text"  # lone surrogate from bad decoding
    out = _sanitize_for_api(raw)
    assert "ok" in out and "text" in out
    out.encode("utf-8")  # must be encodable (would raise on a surrogate)


def test_parse_llm_json_plain():
    assert _parse_llm_json('{"is_paper": true, "title": "X"}') == {"is_paper": True, "title": "X"}


def test_parse_llm_json_strips_fences_and_prose():
    raw = 'Here you go:\n```json\n{"is_paper": false, "title": ""}\n```'
    assert _parse_llm_json(raw) == {"is_paper": False, "title": ""}


def test_parse_llm_json_garbage():
    assert _parse_llm_json("not json at all") == {}


def test_coerce_keeps_paper_fields():
    data = {
        "is_paper": True,
        "title": "A Real Paper Title",
        "authors": ["Ada Lovelace", "Alan Turing"],
        "affiliations": ["MIT"],
        "abstract": "We show something interesting.",
    }
    out = _coerce_llm_meta(data)
    assert out["title"] == "A Real Paper Title"
    assert out["authors"] == ["Ada Lovelace", "Alan Turing"]
    assert out["affiliations"] == ["MIT"]
    assert out["abstract"] == "We show something interesting."


def test_coerce_drops_non_paper():
    data = {"is_paper": False, "title": "Pricing — Acme Corp", "authors": [], "affiliations": [], "abstract": ""}
    assert _coerce_llm_meta(data) == {}


def test_coerce_drops_when_no_title():
    data = {"is_paper": True, "title": "", "authors": ["X"], "affiliations": [], "abstract": "abc"}
    assert _coerce_llm_meta(data) == {}


def test_coerce_omits_empty_fields():
    data = {"is_paper": True, "title": "T", "authors": [], "affiliations": [], "abstract": ""}
    out = _coerce_llm_meta(data)
    assert out == {"title": "T"}  # empty lists/strings dropped


def test_llm_extract_skips_without_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Must not attempt any network/model call when the key is absent.
    monkeypatch.setattr(enrich_cascade, "_fetch_text_for_llm",
                        lambda url: (_ for _ in ()).throw(AssertionError("should not fetch")))
    assert _llm_extract_metadata("https://host/x.pdf", "e@x.org") == {}
