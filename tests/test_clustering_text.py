"""Tests for clustering-text construction (outlier-artifact fix)."""

from papertrail.enrich_cascade import clustering_text


def test_real_content_used_directly():
    p = {"title": "Denoising Diffusion Probabilistic Models",
         "abstract": "We present high quality image synthesis results.",
         "text": "", "url": "https://arxiv.org/abs/2006.11239",
         "channel": "papers-dl"}
    out = clustering_text(p)
    assert "diffusion" in out.lower() and "synthesis" in out.lower()


def test_husk_falls_back_to_channel_and_url_slug():
    # No title/abstract, URL-only message — would otherwise be empty text.
    p = {"title": "", "abstract": "", "text": "https://openreview.net/pdf?id=HJFVrpCaGE",
         "url": "https://openreview.net/pdf?id=HJFVrpCaGE", "channels": ["papers-genomics"]}
    out = clustering_text(p).lower()
    assert "genomics" in out          # channel topical prior present
    assert out.strip() != ""          # not degenerate


def test_two_husks_in_different_channels_differ():
    a = clustering_text({"title": "", "abstract": "", "text": "",
                         "url": "https://x/a", "channels": ["papers-genomics"]})
    b = clustering_text({"title": "", "abstract": "", "text": "",
                         "url": "https://x/b", "channels": ["papers-ai-agents"]})
    assert a != b  # no longer collapse to one identical string


def test_husk_with_nothing_is_empty():
    assert clustering_text({"title": "", "abstract": "", "text": "", "url": ""}) == ""
