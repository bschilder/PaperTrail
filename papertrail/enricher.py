"""
Paper metadata enrichment module using Semantic Scholar and OpenAlex APIs.

This module provides comprehensive paper metadata enrichment through multiple
strategies (DOI, arXiv ID, PubMed ID, title-based search, direct URL analysis).

Features:
- Multiple identifier extraction (DOI, arXiv, PubMed/PMC, PII)
- Dual API backend: Semantic Scholar + OpenAlex
- Intelligent fallback strategy
- Batch enrichment with retry logic
- Rate limiting and exponential backoff
- Comprehensive metadata standardization
- Caching to reduce API calls

Both APIs are free and don't require authentication for basic use:
- Semantic Scholar API: https://api.semanticscholar.org
- OpenAlex API: https://api.openalex.org

Example:
    >>> from papertrail.enricher import PaperEnricher
    >>> enricher = PaperEnricher()
    >>> metadata = enricher.enrich_by_doi("10.1038/nature12373")
    >>> print(metadata["title"], metadata["authors"])

    >>> papers = [
    ...     {"url": "https://arxiv.org/abs/2301.04821"},
    ...     {"doi": "10.1103/PhysRevLett.123.021102"},
    ... ]
    >>> enriched = enricher.enrich_papers(papers)
    >>> for p in enriched:
    ...     print(p["title"])
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Optional
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

# Try to import pyalex for faster, more reliable OpenAlex access
try:
    import pyalex
    from pyalex import Works
    HAS_PYALEX = True
except ImportError:
    HAS_PYALEX = False

# API endpoints
SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper"
OPENALEX_API = "https://api.openalex.org/works"
PUBMED_API = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

# Timeouts and retry settings
DEFAULT_TIMEOUT = 15
MAX_RETRIES = 3
INITIAL_BACKOFF = 1.0  # seconds


@dataclass
class PaperMetadata:
    """
    Standardized paper metadata extracted from enrichment APIs.

    Attributes
    ----------
    title : str
        Paper title.
    authors : list[str]
        List of author names.
    year : int, optional
        Publication year.
    journal : str, optional
        Journal or venue name.
    abstract : str, optional
        Paper abstract.
    doi : str, optional
        Digital Object Identifier.
    arxiv_id : str, optional
        arXiv identifier (e.g., "2301.04821").
    pubmed_id : str, optional
        PubMed ID.
    pmc_id : str, optional
        PubMed Central ID.
    openalex_id : str, optional
        OpenAlex work ID.
    semantic_scholar_id : str, optional
        Semantic Scholar paper ID.
    institutions : list[str]
        List of author institutions.
    keywords : list[str]
        Paper keywords or subjects.
    url : str, optional
        Primary paper URL.
    """

    title: str
    authors: list[str] = None
    year: Optional[int] = None
    journal: Optional[str] = None
    abstract: Optional[str] = None
    doi: Optional[str] = None
    arxiv_id: Optional[str] = None
    pubmed_id: Optional[str] = None
    pmc_id: Optional[str] = None
    openalex_id: Optional[str] = None
    semantic_scholar_id: Optional[str] = None
    cited_by_count: Optional[int] = None
    institutions: list[str] = None
    keywords: list[str] = None
    url: Optional[str] = None

    def __post_init__(self):
        """Initialize list fields."""
        if self.authors is None:
            self.authors = []
        if self.institutions is None:
            self.institutions = []
        if self.keywords is None:
            self.keywords = []

    def to_dict(self) -> dict[str, Any]:
        """
        Convert to dictionary representation.

        Returns
        -------
        dict
            Dictionary with all fields, excluding None values.
        """
        result = {}
        for key, value in self.__dict__.items():
            if value is not None:
                if isinstance(value, list) and not value:
                    continue
                result[key] = value
        return result


class PaperEnricher:
    """
    Comprehensive paper metadata enrichment using multiple APIs and strategies.

    Provides methods to extract identifiers from various paper sources and
    enrich metadata using Semantic Scholar and OpenAlex APIs.

    Parameters
    ----------
    cache_size : int
        Maximum number of API responses to cache (default: 1000).
    timeout : int
        Request timeout in seconds (default: 15).
    max_retries : int
        Maximum number of retries for failed requests (default: 3).
    user_agent : str, optional
        User-Agent header for requests.

    Attributes
    ----------
    _cache : dict
        Simple LRU cache for API responses.

    Examples
    --------
    Enrich by different identifiers:

    >>> enricher = PaperEnricher()
    >>> m1 = enricher.enrich_by_doi("10.1038/nature12373")
    >>> m2 = enricher.enrich_by_arxiv_id("2301.04821")
    >>> m3 = enricher.enrich_by_pmid("22460902")
    >>> m4 = enricher.enrich_by_url("https://biorxiv.org/content/...")

    Batch enrichment:

    >>> papers = [
    ...     {"url": "https://arxiv.org/abs/2301.04821"},
    ...     {"doi": "10.1103/PhysRevLett.123.021102"},
    ... ]
    >>> results = enricher.enrich_papers(papers)
    """

    def __init__(
        self,
        cache_size: int = 1000,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        user_agent: str | None = None,
        email: str | None = None,
        openalex_first: bool = True,
    ):
        """Initialize the paper enricher.

        Parameters
        ----------
        email : str, optional
            Contact email for polite pool access on OpenAlex (~10x faster).
        openalex_first : bool
            If True (default), try OpenAlex before Semantic Scholar.
            OpenAlex has much more generous rate limits (~10 req/s with email).
        """
        self.cache_size = cache_size
        self.timeout = timeout
        self.max_retries = max_retries
        self.user_agent = user_agent or "PaperTrail/1.0 (research-tool)"
        self.email = email
        self.openalex_first = openalex_first
        self._cache: dict[str, Any] = {}

        # Configure pyalex if available
        if HAS_PYALEX and email:
            pyalex.config.email = email
            pyalex.config.max_retries = max_retries
            pyalex.config.retry_backoff_factor = 0.5

    def enrich_papers(
        self, papers: list[dict[str, Any]], require_title: bool = False
    ) -> list[dict[str, Any]]:
        """
        Enrich a batch of papers using multiple strategies.

        For each paper, attempts enrichment in order:
        1. By DOI if provided
        2. By arXiv ID if provided
        3. By PubMed ID if provided
        4. By URL analysis
        5. By title search (if no structured ID found)

        Parameters
        ----------
        papers : list[dict]
            List of paper dictionaries with keys like: url, doi, arxiv_id,
            pubmed_id, title, etc.
        require_title : bool
            If True, only include papers with non-empty titles in results.

        Returns
        -------
        list[dict]
            List of enriched paper dictionaries. Each includes all original
            fields plus enriched metadata (title, authors, year, etc.).

        Notes
        -----
        This function applies exponential backoff between API calls to
        respect rate limits.
        """
        logger.info(f"Enriching batch of {len(papers)} papers")
        enriched = []
        backoff = INITIAL_BACKOFF

        for i, paper in enumerate(papers, 1):
            try:
                metadata = self._enrich_single_paper(paper)

                if metadata:
                    result = {**paper, **metadata.to_dict()}
                    if require_title and not result.get("title"):
                        logger.debug(f"Skipping paper {i} (no title): {paper}")
                        continue
                    enriched.append(result)
                    logger.debug(f"Enriched paper {i}/{len(papers)}: {metadata.title}")
                else:
                    logger.debug(f"Could not enrich paper {i}: {paper}")

            except Exception as e:
                logger.error(f"Error enriching paper {i}: {e}")

            # Apply backoff (less aggressive after success)
            if i < len(papers):
                time.sleep(backoff)

        logger.info(f"Successfully enriched {len(enriched)}/{len(papers)} papers")
        return enriched

    def enrich_by_doi(self, doi: str) -> Optional[PaperMetadata]:
        """
        Enrich a paper by DOI.

        Parameters
        ----------
        doi : str
            Digital Object Identifier (e.g., "10.1038/nature12373").

        Returns
        -------
        PaperMetadata, optional
            Enriched metadata, or None if not found.
        """
        # Normalize DOI format
        doi = self._normalize_doi(doi)
        if not doi:
            return None

        logger.debug(f"Enriching by DOI: {doi}")

        if self.openalex_first:
            # Try OpenAlex first (faster, more generous rate limits)
            metadata = self._enrich_from_openalex_by_doi(doi)
            if metadata:
                metadata.doi = doi
                return metadata
            # Fall back to Semantic Scholar
            metadata = self._enrich_from_semantic_scholar(f"DOI:{doi}")
            if metadata:
                metadata.doi = doi
                return metadata
        else:
            # Legacy order: S2 first
            metadata = self._enrich_from_semantic_scholar(f"DOI:{doi}")
            if metadata:
                metadata.doi = doi
                return metadata
            metadata = self._enrich_from_openalex_by_doi(doi)
            if metadata:
                metadata.doi = doi
                return metadata

        logger.warning(f"Could not enrich DOI: {doi}")
        return None

    def enrich_by_arxiv_id(self, arxiv_id: str) -> Optional[PaperMetadata]:
        """
        Enrich a paper by arXiv identifier.

        Parameters
        ----------
        arxiv_id : str
            arXiv ID (e.g., "2301.04821" or "2301.04821v1").

        Returns
        -------
        PaperMetadata, optional
            Enriched metadata, or None if not found.
        """
        arxiv_id = self._normalize_arxiv_id(arxiv_id)
        if not arxiv_id:
            return None

        logger.debug(f"Enriching by arXiv ID: {arxiv_id}")

        # Try OpenAlex first if configured (arXiv DOI format)
        if self.openalex_first:
            arxiv_doi = f"10.48550/arXiv.{arxiv_id}"
            metadata = self._enrich_from_openalex(arxiv_doi)
            if metadata:
                metadata.arxiv_id = arxiv_id
                return metadata

        metadata = self._enrich_from_semantic_scholar(f"ARXIV:{arxiv_id}")
        if metadata:
            metadata.arxiv_id = arxiv_id
            return metadata

        # Fallback to OpenAlex if not tried yet
        if not self.openalex_first:
            arxiv_doi = f"10.48550/arXiv.{arxiv_id}"
            metadata = self._enrich_from_openalex(arxiv_doi)
            if metadata:
                metadata.arxiv_id = arxiv_id
                return metadata

        logger.warning(f"Could not enrich arXiv ID: {arxiv_id}")
        return None

    def enrich_by_pmid(self, pmid: str) -> Optional[PaperMetadata]:
        """
        Enrich a paper by PubMed ID.

        Parameters
        ----------
        pmid : str
            PubMed ID (e.g., "22460902").

        Returns
        -------
        PaperMetadata, optional
            Enriched metadata, or None if not found.
        """
        pmid = str(pmid).strip()
        if not pmid or not pmid.isdigit():
            return None

        logger.debug(f"Enriching by PubMed ID: {pmid}")

        try:
            # Use PubMed EUtils to get paper info
            params = {
                "db": "pubmed",
                "id": pmid,
                "rettype": "json",
                "tool": "PaperTrail",
                "email": self.email or "paper.trail@example.com",
            }

            response = self._request_with_backoff(PUBMED_API, params=params)
            if not response:
                return None

            data = response.json()
            result = data.get("result", {})
            article = result.get(pmid, {})

            if not article:
                logger.warning(f"PubMed ID not found: {pmid}")
                return None

            # Extract metadata from PubMed response
            title = article.get("title", "Unknown Title")
            authors = [
                a.get("name", "") for a in article.get("authors", [])
            ]
            year = int(article.get("pubdate", "0").split()[0]) if article.get("pubdate") else None
            journal = article.get("source", "")

            metadata = PaperMetadata(
                title=title,
                authors=authors,
                year=year,
                journal=journal,
                pubmed_id=pmid,
            )

            # Try to get DOI and enrich further
            doi = article.get("uid")
            if doi and doi.startswith("10."):
                metadata = self.enrich_by_doi(doi) or metadata

            return metadata

        except Exception as e:
            logger.warning(f"Failed to enrich PubMed ID {pmid}: {e}")
            return None

    def enrich_by_title(self, title: str) -> Optional[PaperMetadata]:
        """
        Enrich a paper by title search.

        Uses title-based search via Semantic Scholar API. This is less
        reliable than identifier-based search.

        Parameters
        ----------
        title : str
            Paper title to search for.

        Returns
        -------
        PaperMetadata, optional
            Enriched metadata, or None if not found.
        """
        if not title or len(title) < 10:
            logger.warning(f"Title too short: {title}")
            return None

        logger.debug(f"Enriching by title: {title[:50]}...")

        try:
            url = f"{SEMANTIC_SCHOLAR_API}/search"
            params = {"query": title}

            response = self._request_with_backoff(url, params=params)
            if not response:
                return None

            data = response.json()
            papers = data.get("data", [])

            if not papers:
                logger.warning(f"No papers found for title: {title}")
                return None

            # Take the first result
            result = papers[0]
            return self._parse_semantic_scholar_response(result)

        except Exception as e:
            logger.warning(f"Failed title search for '{title}': {e}")
            return None

    def enrich_by_url(self, url: str) -> Optional[PaperMetadata]:
        """
        Enrich a paper by analyzing its URL and extracting identifiers.

        Attempts to extract DOI, arXiv ID, or PubMed ID from the URL,
        then uses those for enrichment.

        Parameters
        ----------
        url : str
            Paper URL.

        Returns
        -------
        PaperMetadata, optional
            Enriched metadata, or None if identifiers found and enrichment
            successful.
        """
        if not url:
            return None

        logger.debug(f"Enriching by URL: {url[:80]}...")

        # Try to extract identifiers from URL
        doi = self._extract_doi(url)
        if doi:
            return self.enrich_by_doi(doi)

        arxiv_id = self._extract_arxiv_id(url)
        if arxiv_id:
            return self.enrich_by_arxiv_id(arxiv_id)

        pmid = self._extract_pmid(url)
        if pmid:
            return self.enrich_by_pmid(pmid)

        pmc_id = self._extract_pmc_id(url)
        if pmc_id:
            return self.enrich_by_pmid(pmc_id)

        logger.debug(f"Could not extract identifiers from URL: {url}")
        return None

    def _enrich_single_paper(self, paper: dict[str, Any]) -> Optional[PaperMetadata]:
        """
        Internal method to enrich a single paper using multiple strategies.

        Parameters
        ----------
        paper : dict
            Paper dictionary with optional fields: doi, arxiv_id, pubmed_id,
            url, title, ids (dict with doi, arxiv_id, pmid keys).

        Returns
        -------
        PaperMetadata, optional
            Enriched metadata.
        """
        # Support nested 'ids' dict from merge output
        ids = paper.get("ids", {})

        # Try each enrichment strategy in order of specificity
        strategies = [
            ("doi", lambda: self.enrich_by_doi(paper.get("doi") or ids.get("doi", ""))),
            ("arxiv_id", lambda: self.enrich_by_arxiv_id(paper.get("arxiv_id") or ids.get("arxiv_id", ""))),
            ("pubmed_id", lambda: self.enrich_by_pmid(paper.get("pubmed_id") or ids.get("pmid", ""))),
            ("url", lambda: self.enrich_by_url(paper.get("url", ""))),
            ("title_openalex", lambda: self.enrich_by_title_openalex(paper.get("title", ""))),
            ("title_s2", lambda: self.enrich_by_title(paper.get("title", ""))),
        ]

        for strategy_name, strategy_fn in strategies:
            try:
                result = strategy_fn()
                if result:
                    logger.debug(f"Successfully enriched via {strategy_name}")
                    return result
            except Exception as e:
                logger.debug(f"Strategy '{strategy_name}' failed: {e}")

        return None

    def _enrich_from_semantic_scholar(
        self, paper_id: str
    ) -> Optional[PaperMetadata]:
        """
        Enrich from Semantic Scholar API.

        Parameters
        ----------
        paper_id : str
            Paper ID in format "DOI:...", "ARXIV:...", etc.

        Returns
        -------
        PaperMetadata, optional
        """
        # Check cache
        cache_key = f"s2:{paper_id}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            url = f"{SEMANTIC_SCHOLAR_API}/{paper_id}"
            params = {
                "fields": "title,authors,year,journal,abstract,paperId,externalIds"
            }

            response = self._request_with_backoff(url, params=params)
            if not response or response.status_code == 404:
                return None

            data = response.json()
            metadata = self._parse_semantic_scholar_response(data)

            if metadata:
                self._cache[cache_key] = metadata
                return metadata

        except Exception as e:
            logger.debug(f"Semantic Scholar lookup failed for {paper_id}: {e}")

        return None

    def _enrich_from_openalex_by_doi(self, doi: str) -> Optional[PaperMetadata]:
        """
        Enrich from OpenAlex API using DOI.

        Uses pyalex if available (recommended), falls back to raw HTTP.

        Parameters
        ----------
        doi : str
            Digital Object Identifier.

        Returns
        -------
        PaperMetadata, optional
        """
        # Check cache
        cache_key = f"oa:doi:{doi}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            if HAS_PYALEX:
                try:
                    data = Works()[f"https://doi.org/{doi}"]
                except (IndexError, KeyError):
                    data = None
                if data and data.get("title"):
                    metadata = self._parse_openalex_response(data)
                    if metadata:
                        self._cache[cache_key] = metadata
                        return metadata
            else:
                url = f"{OPENALEX_API}/doi:{doi}"
                response = self._request_with_backoff(url)
                if not response or response.status_code == 404:
                    return None
                data = response.json()
                metadata = self._parse_openalex_response(data)
                if metadata:
                    self._cache[cache_key] = metadata
                    return metadata

        except Exception as e:
            logger.debug(f"OpenAlex lookup failed for DOI {doi}: {e}")

        return None

    def _enrich_from_openalex_by_pmid(self, pmid: str) -> Optional[PaperMetadata]:
        """Enrich from OpenAlex by PubMed ID."""
        cache_key = f"oa:pmid:{pmid}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            if HAS_PYALEX:
                try:
                    data = Works()[f"pmid:{pmid}"]
                except (IndexError, KeyError):
                    data = None
                if data and data.get("title"):
                    metadata = self._parse_openalex_response(data)
                    if metadata:
                        self._cache[cache_key] = metadata
                        return metadata
            else:
                url = f"{OPENALEX_API}/pmid:{pmid}"
                response = self._request_with_backoff(url)
                if response and response.status_code < 400:
                    data = response.json()
                    metadata = self._parse_openalex_response(data)
                    if metadata:
                        self._cache[cache_key] = metadata
                        return metadata
        except Exception as e:
            logger.debug(f"OpenAlex PMID lookup failed for {pmid}: {e}")
        return None

    def enrich_by_title_openalex(self, title: str) -> Optional[PaperMetadata]:
        """
        Search OpenAlex by title (more reliable than S2 title search).

        Uses fuzzy matching to verify the result matches the query.

        Parameters
        ----------
        title : str
            Paper title to search for.

        Returns
        -------
        PaperMetadata, optional
        """
        if not title or len(title) < 10:
            return None

        cache_key = f"oa:title:{title[:80]}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        try:
            if HAS_PYALEX:
                results = Works().search(title).get(per_page=1)
                if results:
                    r = results[0]
                    if r.get("title") and self._title_similarity(title, r["title"]) > 0.5:
                        metadata = self._parse_openalex_response(r)
                        if metadata:
                            self._cache[cache_key] = metadata
                            return metadata
            else:
                from urllib.parse import quote
                url = f"{OPENALEX_API}?filter=title.search:{quote(title[:200])}&per_page=1"
                response = self._request_with_backoff(url)
                if response and response.status_code < 400:
                    data = response.json()
                    results = data.get("results", [])
                    if results and results[0].get("title"):
                        if self._title_similarity(title, results[0]["title"]) > 0.5:
                            metadata = self._parse_openalex_response(results[0])
                            if metadata:
                                self._cache[cache_key] = metadata
                                return metadata
        except Exception as e:
            logger.debug(f"OpenAlex title search failed for '{title[:50]}': {e}")
        return None

    @staticmethod
    def _title_similarity(a: str, b: str) -> float:
        """Compute word-level Jaccard similarity between two titles."""
        a_words = set(a.lower().split())
        b_words = set(b.lower().split())
        union = a_words | b_words
        if not union:
            return 0.0
        return len(a_words & b_words) / len(union)

    @staticmethod
    def _parse_semantic_scholar_response(data: dict[str, Any]) -> Optional[PaperMetadata]:
        """Parse Semantic Scholar API response into PaperMetadata."""
        if not data:
            return None

        title = data.get("title") or data.get("paperId")
        if not title:
            return None

        authors = [
            author.get("name", "") for author in data.get("authors", [])
        ]

        external_ids = data.get("externalIds", {}) or {}

        return PaperMetadata(
            title=title,
            authors=authors,
            year=data.get("year"),
            journal=(data.get("journal") or {}).get("name"),
            abstract=data.get("abstract"),
            semantic_scholar_id=data.get("paperId"),
            doi=external_ids.get("DOI"),
            arxiv_id=external_ids.get("ArXiv"),
            pubmed_id=external_ids.get("PubMed"),
        )

    @staticmethod
    def _parse_openalex_response(data: dict[str, Any]) -> Optional[PaperMetadata]:
        """Parse OpenAlex API response into PaperMetadata."""
        if not data:
            return None

        title = data.get("title")
        if not title:
            return None

        # Extract authors
        authors = [
            a.get("author", {}).get("display_name", "")
            for a in data.get("authorships", [])
        ]

        # Extract institutions
        institutions = list({
            inst.get("display_name", "")
            for a in data.get("authorships", [])
            for inst in a.get("institutions", [])
            if inst.get("display_name")
        })

        # Extract journal from primary location
        journal = None
        primary_loc = data.get("primary_location") or {}
        if primary_loc:
            source = primary_loc.get("source") or {}
            journal = source.get("display_name")

        # Reconstruct abstract if in inverted index format
        abstract = None
        if data.get("abstract_inverted_index"):
            abstract = PaperEnricher._reconstruct_abstract(
                data["abstract_inverted_index"]
            )

        # Extract IDs
        ids = data.get("ids", {}) or {}

        return PaperMetadata(
            title=title,
            authors=authors,
            year=data.get("publication_year"),
            journal=journal,
            abstract=abstract,
            openalex_id=data.get("id"),
            doi=ids.get("doi"),
            pubmed_id=ids.get("pubmed"),
            cited_by_count=data.get("cited_by_count"),
            institutions=institutions,
        )

    @staticmethod
    def _reconstruct_abstract(inverted_index: dict[str, list[int]]) -> str:
        """Reconstruct abstract from OpenAlex inverted index format."""
        if not inverted_index:
            return ""

        # Build position-to-word mapping
        words = {}
        for word, positions in inverted_index.items():
            for pos in positions:
                words[pos] = word

        # Reconstruct in order
        max_pos = max(words.keys()) if words else 0
        return " ".join(words.get(i, "") for i in range(max_pos + 1) if words.get(i, ""))

    def _request_with_backoff(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        max_retries: int | None = None,
    ) -> Optional[requests.Response]:
        """
        Make HTTP request with exponential backoff and retry logic.

        Parameters
        ----------
        url : str
            URL to request.
        params : dict, optional
            URL parameters.
        max_retries : int, optional
            Override default max retries.

        Returns
        -------
        requests.Response, optional
            Response object, or None if all retries failed.
        """
        max_retries = max_retries or self.max_retries
        backoff = INITIAL_BACKOFF

        for attempt in range(max_retries):
            try:
                headers = {"User-Agent": self.user_agent}
                response = requests.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.timeout,
                )

                # Success
                if response.status_code < 400:
                    return response

                # Rate limit - back off and retry
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        logger.debug(f"Rate limited, backing off {backoff}s")
                        time.sleep(backoff)
                        backoff = min(backoff * 2, 60)
                        continue
                    else:
                        return None

                # Client error - don't retry
                if response.status_code < 500:
                    return response

                # Server error - retry with backoff
                if attempt < max_retries - 1:
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60)
                    continue

                return None

            except requests.Timeout:
                if attempt < max_retries - 1:
                    logger.debug(f"Timeout, retrying in {backoff}s")
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60)
                    continue
                return None

            except requests.RequestException as e:
                logger.debug(f"Request failed: {e}")
                if attempt < max_retries - 1:
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60)
                    continue
                return None

        return None

    @staticmethod
    def _normalize_doi(doi: str) -> str | None:
        """Extract and normalize DOI."""
        if not doi:
            return None

        # Remove common URL prefixes
        for prefix in ("https://doi.org/", "http://doi.org/", "doi.org/", "doi:"):
            if doi.lower().startswith(prefix):
                doi = doi[len(prefix):]

        # Ensure it starts with 10.
        if not doi.startswith("10."):
            return None

        return doi.lower()

    @staticmethod
    def _normalize_arxiv_id(arxiv_id: str) -> str | None:
        """Extract and normalize arXiv ID."""
        if not arxiv_id:
            return None

        # Remove URL prefix
        for prefix in ("https://arxiv.org/abs/", "http://arxiv.org/abs/", "arxiv.org/abs/"):
            if arxiv_id.startswith(prefix):
                arxiv_id = arxiv_id[len(prefix):]

        # Ensure format: YYMM.NNNNN or YYMMNNNNv1
        arxiv_id = arxiv_id.strip()
        match = re.search(r"(\d{4}\.\d{4,5}(?:v\d+)?)", arxiv_id)

        return match.group(1) if match else None

    @staticmethod
    def _extract_doi(url: str) -> str | None:
        """Extract DOI from URL."""
        match = re.search(r"10\.\d{4,}/[^\s>\"']+", url)
        if match:
            doi = match.group(0).rstrip(".,;:)")
            return doi
        return None

    @staticmethod
    def _extract_arxiv_id(url: str) -> str | None:
        """Extract arXiv ID from URL."""
        match = re.search(r"arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,5}(?:v\d+)?)", url)
        return match.group(1) if match else None

    @staticmethod
    def _extract_pmid(url: str) -> str | None:
        """Extract PubMed ID from URL."""
        match = re.search(r"pubmed\.ncbi\.nlm\.nih\.gov/(\d+)", url)
        return match.group(1) if match else None

    @staticmethod
    def _extract_pmc_id(url: str) -> str | None:
        """Extract PubMed Central ID from URL."""
        match = re.search(r"pmc\.ncbi\.nlm\.nih\.gov/articles/PMC(\d+)", url)
        return match.group(1) if match else None


# Backward compatibility: export module-level functions for old tests
def _extract_doi(url: str) -> str | None:
    """Extract DOI from URL (backward compatibility wrapper)."""
    return PaperEnricher._extract_doi(url)


def _extract_arxiv_id(url: str) -> str | None:
    """Extract arXiv ID from URL (backward compatibility wrapper)."""
    return PaperEnricher._extract_arxiv_id(url)


# Also export the enrich_paper function that was in the old module
def enrich_paper(url: str, timeout: int = DEFAULT_TIMEOUT) -> dict[str, Any]:
    """
    Enrich a paper URL with metadata (backward compatibility wrapper).

    This is the old functional interface. For new code, use PaperEnricher class.
    """
    enricher = PaperEnricher(timeout=timeout)
    metadata = enricher.enrich_by_url(url)

    if not metadata:
        # Try other strategies
        metadata = enricher.enrich_by_title(url) or PaperMetadata(title="Unknown Title")

    # Return in old format
    result: dict[str, Any] = {
        "title": metadata.title,
        "authors": metadata.authors or [],
        "year": metadata.year,
        "journal": metadata.journal,
        "abstract": metadata.abstract,
        "openalex_link": metadata.openalex_id,
        "institutions": metadata.institutions or [],
    }

    # Remove None values
    return {k: v for k, v in result.items() if v is not None}


def fill_missing_metadata(
    papers: list[dict[str, Any]],
    email: str = "papertrail@example.com",
    fields: tuple[str, ...] = ("abstract", "authors", "affiliations", "journal", "year", "cited_by_count"),
) -> int:
    """
    Fill missing metadata for a list of papers using OpenAlex title search.

    This is a fast batch operation that uses OpenAlex's title search to find
    papers that are missing key fields. It modifies papers in-place.

    Parameters
    ----------
    papers : list[dict]
        Papers with at least 'title' and 'url' fields.
    email : str
        Email for OpenAlex polite pool (10 req/s vs 1 req/s).
    fields : tuple
        Which fields to fill if missing.

    Returns
    -------
    int
        Number of papers enriched.
    """
    headers = {"User-Agent": f"PaperTrail/1.0 (mailto:{email})"}
    enriched = 0

    needs = [p for p in papers if any(not p.get(f) for f in fields) and p.get("title")]
    logger.info("Filling missing metadata for %d papers via OpenAlex title search", len(needs))

    for p in needs:
        title = p.get("title", "")
        if len(title) < 10:
            continue

        # Try DOI first (faster)
        doi_match = re.search(r"(10\.\d{4,}/[^\s,\]>]+)", p.get("url", ""))
        doi = doi_match.group(1) if doi_match else None

        try:
            if doi:
                resp = requests.get(
                    f"{OPENALEX_API}/doi:{doi}",
                    headers=headers,
                    timeout=10,
                )
            else:
                # Pass the title as raw text — requests URL-encodes params itself.
                # Pre-quoting double-encodes spaces (%20→%2520) and matches nothing.
                resp = requests.get(
                    OPENALEX_API,
                    params={"filter": f"title.search:{title[:100]}", "per_page": 1},
                    headers=headers,
                    timeout=10,
                )

            if not resp.ok:
                continue

            data = resp.json()
            if not doi:
                results = data.get("results", [])
                data = results[0] if results else None
            if not data:
                continue

            changed = False
            if "year" in fields and not p.get("year") and data.get("publication_year"):
                p["year"] = data["publication_year"]
                changed = True
            if "journal" in fields and not p.get("journal"):
                src = data.get("primary_location", {}).get("source", {})
                if src.get("display_name"):
                    p["journal"] = src["display_name"]
                    changed = True
            if "authors" in fields and not p.get("authors") and data.get("authorships"):
                p["authors"] = [a["author"]["display_name"] for a in data["authorships"][:10]]
                changed = True
            if "affiliations" in fields and not p.get("affiliations") and data.get("authorships"):
                affs = list(dict.fromkeys(
                    inst.get("display_name", "")
                    for a in data["authorships"]
                    for inst in a.get("institutions", [])
                    if inst.get("display_name")
                ))
                if affs:
                    p["affiliations"] = affs
                    changed = True
            if "abstract" in fields and not p.get("abstract") and data.get("abstract_inverted_index"):
                inv = data["abstract_inverted_index"]
                words: dict[int, str] = {}
                for word, positions in inv.items():
                    for pos in positions:
                        words[pos] = word
                if words:
                    p["abstract"] = " ".join(words.get(i, "") for i in range(max(words) + 1))
                    changed = True
            if "cited_by_count" in fields and p.get("cited_by_count") is None and data.get("cited_by_count") is not None:
                p["cited_by_count"] = data["cited_by_count"]
                changed = True
            if not p.get("openalex_url") and data.get("id"):
                p["openalex_url"] = data["id"]

            if changed:
                enriched += 1

        except Exception as exc:
            logger.debug("OpenAlex error for '%s': %s", title[:40], exc)

        time.sleep(0.1)  # rate limit

    logger.info("Enriched %d / %d papers", enriched, len(needs))
    return enriched
