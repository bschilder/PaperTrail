"""
Paper metadata enrichment via Semantic Scholar and OpenAlex APIs.

Both APIs are free and don't require authentication for basic use.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any

import requests

logger = logging.getLogger(__name__)


def _extract_doi(url: str) -> str | None:
    """Extract DOI from a URL."""
    m = re.search(r"10\.\d{4,}/[^\s>]+", url)
    return m.group(0).rstrip(".,;)") if m else None


def _extract_arxiv_id(url: str) -> str | None:
    """Extract arXiv ID from a URL."""
    m = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)", url)
    return m.group(1) if m else None


def enrich_paper(url: str, timeout: int = 15) -> dict[str, Any]:
    """
    Enrich a paper URL with metadata from Semantic Scholar and OpenAlex.

    Parameters
    ----------
    url : str
        The paper URL (DOI, arXiv, bioRxiv, etc.).
    timeout : int
        Request timeout in seconds.

    Returns
    -------
    dict
        Metadata fields: title, authors, year, journal, abstract,
        openalex_link, institutions.
    """
    result: dict[str, Any] = {
        "title": None,
        "authors": [],
        "year": None,
        "journal": None,
        "abstract": None,
        "openalex_link": None,
        "institutions": [],
    }

    # Try Semantic Scholar first
    s2_data = _fetch_semantic_scholar(url, timeout)
    if s2_data:
        result["title"] = s2_data.get("title")
        result["authors"] = [a.get("name", "") for a in s2_data.get("authors", [])]
        result["year"] = s2_data.get("year")
        result["journal"] = (s2_data.get("journal") or {}).get("name")
        result["abstract"] = s2_data.get("abstract")

    # Try OpenAlex for additional data
    oa_data = _fetch_openalex(url, timeout)
    if oa_data:
        if not result["title"]:
            result["title"] = oa_data.get("title")
        if not result["authors"]:
            result["authors"] = [
                a.get("author", {}).get("display_name", "")
                for a in oa_data.get("authorships", [])
            ]
        if not result["year"]:
            result["year"] = oa_data.get("publication_year")
        if not result["journal"]:
            loc = oa_data.get("primary_location") or {}
            src = loc.get("source") or {}
            result["journal"] = src.get("display_name")
        if not result["abstract"] and oa_data.get("abstract_inverted_index"):
            result["abstract"] = _reconstruct_abstract(
                oa_data["abstract_inverted_index"]
            )
        result["openalex_link"] = oa_data.get("id")
        result["institutions"] = list(
            {
                inst.get("display_name", "")
                for a in oa_data.get("authorships", [])
                for inst in a.get("institutions", [])
                if inst.get("display_name")
            }
        )

    if not result["title"]:
        result["title"] = "Unknown Title"

    return result


def _fetch_semantic_scholar(url: str, timeout: int) -> dict | None:
    """Fetch from Semantic Scholar API."""
    doi = _extract_doi(url)
    arxiv_id = _extract_arxiv_id(url)

    paper_id = None
    if doi:
        paper_id = f"DOI:{doi}"
    elif arxiv_id:
        paper_id = f"ARXIV:{arxiv_id}"

    if not paper_id:
        return None

    api_url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id}"
    params = {"fields": "title,authors,year,journal,abstract"}

    try:
        resp = requests.get(api_url, params=params, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 429:
            time.sleep(2)
    except Exception as e:
        logger.debug("S2 fetch failed: %s", e)
    return None


def _fetch_openalex(url: str, timeout: int) -> dict | None:
    """Fetch from OpenAlex API."""
    doi = _extract_doi(url)
    if not doi:
        return None

    api_url = f"https://api.openalex.org/works/doi:{doi}"
    headers = {"Accept": "application/json"}

    try:
        resp = requests.get(api_url, headers=headers, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.debug("OpenAlex fetch failed: %s", e)
    return None


def _reconstruct_abstract(inverted_index: dict[str, list[int]]) -> str:
    """Reconstruct abstract from OpenAlex inverted index format."""
    if not inverted_index:
        return ""
    words: dict[int, str] = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    return " ".join(words[i] for i in sorted(words.keys()))
