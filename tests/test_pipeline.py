"""Tests for pipeline helpers."""

from pathlib import Path

from papertrail.pipeline import _existing_data_path


def test_existing_data_path_koolab():
    cfg = {"slack_workspace_url": "https://koolab.slack.com"}
    assert _existing_data_path(cfg) == Path("data/koolab/papers_final.json")


def test_existing_data_path_standardmodelbio():
    cfg = {"slack_workspace_url": "https://standardmodelbio.slack.com"}
    assert _existing_data_path(cfg) == Path("data/standardmodelbio/papers_final.json")


def test_existing_data_path_default_when_no_url():
    assert _existing_data_path({}) == Path("data/dashboard/papers_final.json")
