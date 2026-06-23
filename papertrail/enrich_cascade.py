"""
Multi-strategy enrichment cascade for paper metadata.

Strategy order:
1. Direct page scrape (HTML title/meta tags)
2. ID-based lookup (DOI → OpenAlex/Crossref, arXiv ID → OpenAlex/S2, bioRxiv API)
3. Web search fallback (Google → title → OpenAlex title search)
4. LLM verification (confirm match via snippet comparison)
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Optional
from urllib.parse import urlparse, quote

import requests

logger = logging.getLogger(__name__)

# Domain → journal mapping for fallback
DOMAIN_JOURNALS = {
    'arxiv.org': 'arXiv', 'www.arxiv.org': 'arXiv',
    'www.biorxiv.org': 'bioRxiv', 'biorxiv.org': 'bioRxiv',
    'www.medrxiv.org': 'medRxiv',
    'elifesciences.org': 'eLife', 'www.pnas.org': 'PNAS',
    'www.science.org': 'Science', 'link.springer.com': 'Springer',
}
NATURE_JOURNALS = {
    's41586': 'Nature', 's41587': 'Nature Biotechnology',
    's41588': 'Nature Genetics', 's41591': 'Nature Medicine',
    's41592': 'Nature Methods', 's42256': 'Nature Machine Intelligence',
    's43588': 'Nature Computational Science', 's41576': 'Nature Reviews Genetics',
    's41551': 'Nature Biomedical Engineering', 's41467': 'Nature Communications',
    's41568': 'Nature Reviews Cancer', 's42003': 'Communications Biology',
}

HEADERS = {"User-Agent": "PaperTrail/1.0 (https://github.com/bschilder/PaperTrail)"}


def _normalize_pdf_url(url: str) -> str:
    """Convert PDF URLs to their landing page equivalents."""
    # arxiv.org/pdf/XXXX.pdf → arxiv.org/abs/XXXX
    url = re.sub(r'(arxiv\.org)/pdf/(\d+\.\d+)(\.pdf)?$', r'\1/abs/\2', url)
    # biorxiv/medrxiv .full.pdf → remove suffix
    url = re.sub(r'(biorxiv\.org/content/.+?)\.full\.pdf$', r'\1', url)
    url = re.sub(r'(biorxiv\.org/content/.+?)\.full$', r'\1', url)
    url = re.sub(r'(medrxiv\.org/content/.+?)\.full\.pdf$', r'\1', url)
    return url


def enrich_url(url: str, email: str = "papertrail@example.com") -> dict[str, Any]:
    """
    Enrich a paper URL using a multi-strategy cascade.

    Returns a dict with: title, authors, year, journal, abstract,
    doi, cited_by_count (any field may be None).
    """
    # Normalize PDF URLs to landing pages first
    url = _normalize_pdf_url(url)
    result = {}

    # Strategy 1: Direct page scrape
    result = _scrape_page_metadata(url)
    if result.get("title") and result.get("abstract"):
        logger.debug("Enriched via page scrape: %s", url[:60])
        return result

    # Strategy 2: ID-based lookup
    ids = _extract_ids(url)

    if ids.get("doi"):
        r = _lookup_openalex_doi(ids["doi"], email)
        if r and r.get("title"):
            result = {**result, **{k: v for k, v in r.items() if v}}
            if result.get("title") and result.get("abstract"):
                logger.debug("Enriched via OpenAlex DOI: %s", url[:60])
                return result

    if ids.get("arxiv_id"):
        r = _lookup_openalex_arxiv(ids["arxiv_id"], email)
        if r and r.get("title"):
            result = {**result, **{k: v for k, v in r.items() if v}}
            if result.get("title"):
                logger.debug("Enriched via OpenAlex arXiv: %s", url[:60])
                return result

    if ids.get("biorxiv_doi"):
        r = _lookup_biorxiv_api(ids["biorxiv_doi"])
        if r and r.get("title"):
            result = {**result, **{k: v for k, v in r.items() if v}}
            if result.get("title"):
                logger.debug("Enriched via bioRxiv API: %s", url[:60])
                # Still try OpenAlex for citations/abstract
                if result.get("title") and not result.get("cited_by_count"):
                    oa = _lookup_openalex_title(result["title"], email)
                    if oa:
                        result = {**result, **{k: v for k, v in oa.items() if v and not result.get(k)}}
                return result

    if ids.get("doi") and not result.get("title"):
        r = _lookup_crossref(ids["doi"])
        if r and r.get("title"):
            result = {**result, **{k: v for k, v in r.items() if v}}

    # Elsevier/Cell PII → Crossref search
    if ids.get("pii") and not result.get("title"):
        r = _lookup_crossref_pii(ids["pii"])
        if r and r.get("title"):
            result = {**result, **{k: v for k, v in r.items() if v}}

    # Strategy 3: Use scraped title for OpenAlex lookup
    if result.get("title") and not result.get("abstract"):
        oa = _lookup_openalex_title(result["title"], email)
        if oa and oa.get("abstract"):
            result = {**result, **{k: v for k, v in oa.items() if v and not result.get(k)}}
            logger.debug("Enriched via title→OpenAlex: %s", url[:60])
            return result

    # Strategy 4: Google search as last resort
    if not result.get("title"):
        google_title = _google_search_title(url)
        if google_title:
            result["title"] = google_title
            oa = _lookup_openalex_title(google_title, email)
            if oa:
                result = {**result, **{k: v for k, v in oa.items() if v and not result.get(k)}}
                logger.debug("Enriched via Google→OpenAlex: %s", url[:60])

    # Final fallback: infer journal from URL domain
    if not result.get("journal"):
        result["journal"] = _infer_journal_from_url(url)

    # Reject junk titles — article types, site boilerplate, not real papers
    if result.get("title") and _is_junk_title(result["title"]):
        result["title"] = ""

    return result


# Titles that are article types or site boilerplate, not real paper titles
JUNK_TITLES = {
    'erratum', 'corrigendum', 'retraction', 'correction', 'publisher correction',
    'author correction', 'correspondence', 'letter', 'reply', 'comment',
    'editorial', 'news', 'research highlight', 'in brief', 'addendum',
    'contents', 'cover image', 'cover story', 'table of contents',
    'just a moment', 'access denied', 'page not found', '404', 'not found',
    'nature', 'science', 'cell', 'pnas', 'the lancet',
    'subscribe', 'sign in', 'log in', 'cookie policy',
}


def _is_junk_title(title: str) -> bool:
    """Check if a title is a generic article type or site boilerplate."""
    t = title.strip().lower()
    # Exact match against known junk
    if t in JUNK_TITLES:
        return True
    # Too short to be a real paper title (unless it's an acronym like "DINOv3")
    if len(t) < 8 and not any(c.isupper() for c in t[1:]):
        return True
    return False


def _infer_journal_from_url(url: str) -> str:
    """Infer journal name from URL domain."""
    try:
        domain = urlparse(url).netloc.lower()
    except:
        return ""
    if domain in DOMAIN_JOURNALS:
        return DOMAIN_JOURNALS[domain]
    if 'nature.com' in domain:
        m = re.search(r'/articles/(s\d{5})', url)
        if m:
            return NATURE_JOURNALS.get(m.group(1), 'Nature')
        return 'Nature'
    if 'cell.com' in domain:
        return 'Cell Press'
    if 'oup.com' in domain:
        return 'Oxford Academic'
    if 'openreview.net' in domain:
        return 'OpenReview'
    return ""


# ── Strategy 1: Direct page scrape ──────────────────────────────

def _scrape_page_metadata(url: str) -> dict[str, Any]:
    """Extract metadata from HTML meta tags."""
    try:
        resp = requests.get(url, timeout=10, headers=HEADERS, allow_redirects=True)
        if not resp.ok:
            return {}
        html = resp.text[:30000]  # Only need the head

        result = {}

        # citation_title (Google Scholar standard)
        m = re.search(r'<meta\s+name=["\']citation_title["\']\s+content=["\']([^"\']+)', html, re.I)
        if m:
            result["title"] = _clean_title(m.group(1))

        # og:title fallback
        if not result.get("title"):
            m = re.search(r'<meta\s+(?:property|name)=["\']og:title["\']\s+content=["\']([^"\']+)', html, re.I)
            if m:
                result["title"] = _clean_title(m.group(1))

        # <title> tag fallback
        if not result.get("title"):
            m = re.search(r'<title[^>]*>(.*?)</title>', html, re.I | re.DOTALL)
            if m:
                raw = m.group(1).strip()
                # Strip common suffixes like "| Nature" "| bioRxiv" "| arXiv"
                raw = re.sub(r'\s*[|\-–]\s*(Nature|bioRxiv|medRxiv|arXiv|Science|Cell|PNAS|PubMed).*$', '', raw)
                # Skip if it's just the site name
                if len(raw) > 15 and not raw.startswith('['):
                    result["title"] = _clean_title(raw)

        # Authors
        authors = re.findall(r'<meta\s+name=["\']citation_author["\']\s+content=["\']([^"\']+)', html, re.I)
        if authors:
            result["authors"] = [a.strip() for a in authors]

        # Year
        m = re.search(r'<meta\s+name=["\']citation_publication_date["\']\s+content=["\'](\d{4})', html, re.I)
        if m:
            result["year"] = int(m.group(1))

        # Journal
        m = re.search(r'<meta\s+name=["\']citation_journal_title["\']\s+content=["\']([^"\']+)', html, re.I)
        if m:
            result["journal"] = m.group(1).strip()

        # DOI
        m = re.search(r'<meta\s+name=["\']citation_doi["\']\s+content=["\']([^"\']+)', html, re.I)
        if m:
            result["doi"] = m.group(1).strip()

        # Abstract (og:description or citation_abstract)
        m = re.search(r'<meta\s+name=["\']citation_abstract["\']\s+content=["\']([^"\']+)', html, re.I)
        if not m:
            m = re.search(r'<meta\s+(?:property|name)=["\'](?:og:)?description["\']\s+content=["\']([^"\']+)', html, re.I)
        if m:
            abstract = m.group(1).strip()
            if len(abstract) > 50 and not _is_boilerplate(abstract):
                result["abstract"] = abstract

        return result

    except Exception as e:
        logger.debug("Page scrape failed for %s: %s", url[:60], e)
        return {}


# ── Strategy 2: ID-based lookups ────────────────────────────────

def _extract_ids(url: str) -> dict[str, str]:
    """Extract DOI, arXiv ID, bioRxiv DOI from a URL."""
    ids = {}
    parsed = urlparse(url)
    path = parsed.path

    # DOI — explicit in URL
    doi_match = re.search(r'(10\.\d{4,}/[^\s,\]>]+)', url)
    if doi_match:
        doi = re.sub(r'\.(pdf|html|xml|full)$', '', doi_match.group(1)).rstrip('.').rstrip('/')
        ids["doi"] = doi
        if '10.1101/' in doi or '10.64898/' in doi:
            ids["biorxiv_doi"] = doi

    # Domain-specific DOI extraction
    if not ids.get("doi"):
        # Nature: nature.com/articles/s41586-025-09922-y → 10.1038/s41586-025-09922-y
        m = re.search(r'nature\.com/articles/(s\d+[-\w.]+)', url, re.I)
        if m:
            ids["doi"] = "10.1038/" + m.group(1)

        # Science: science.org/doi/10.1126/... → DOI in path
        m = re.search(r'science\.org/doi/(10\.\d+/[^\s?#]+)', url, re.I)
        if m:
            ids["doi"] = m.group(1)

        # Cell/Elsevier PII → search Crossref
        m = re.search(r'(S\d{4}-\d{4}\(\d{2}\)\d{5}-\w)', url, re.I)
        if m:
            ids["pii"] = m.group(1)

        # PNAS: pnas.org/doi/10.1073/...
        m = re.search(r'pnas\.org/doi/(10\.\d+/[^\s?#]+)', url, re.I)
        if m:
            ids["doi"] = m.group(1)

        # OUP: academic.oup.com/*/article/doi/10.1093/...
        m = re.search(r'oup\.com/.*/(?:article|article-abstract)/.*?(10\.\d+/[^\s?#]+)', url, re.I)
        if m:
            ids["doi"] = m.group(1)

    # arXiv ID
    arxiv_match = re.search(r'arxiv\.org/(?:abs|pdf)/(\d{4}\.\d{4,})', url, re.I)
    if arxiv_match:
        ids["arxiv_id"] = re.sub(r'\.pdf$', '', arxiv_match.group(1))

    # OpenReview
    if 'openreview.net' in url:
        id_match = re.search(r'[?&]id=([^&]+)', url)
        if id_match:
            ids["openreview_id"] = id_match.group(1)

    return ids


def _lookup_openalex_doi(doi: str, email: str) -> Optional[dict]:
    """Look up a paper by DOI in OpenAlex."""
    try:
        headers = {**HEADERS, "User-Agent": f"PaperTrail/1.0 (mailto:{email})"}
        resp = requests.get(
            f"https://api.openalex.org/works/https://doi.org/{doi}",
            headers=headers, timeout=10,
        )
        if resp.ok:
            return _parse_openalex(resp.json())
    except Exception as e:
        logger.debug("OpenAlex DOI lookup failed: %s", e)
    return None


def _lookup_openalex_arxiv(arxiv_id: str, email: str) -> Optional[dict]:
    """Look up an arXiv paper in OpenAlex."""
    doi = f"10.48550/arXiv.{arxiv_id}"
    return _lookup_openalex_doi(doi, email)


def _lookup_openalex_title(title: str, email: str) -> Optional[dict]:
    """Search OpenAlex by title."""
    try:
        headers = {**HEADERS, "User-Agent": f"PaperTrail/1.0 (mailto:{email})"}
        resp = requests.get(
            "https://api.openalex.org/works",
            params={"filter": f"title.search:{quote(title[:100], safe='')}", "per_page": 1},
            headers=headers, timeout=10,
        )
        if resp.ok:
            results = resp.json().get("results", [])
            if results:
                return _parse_openalex(results[0])
    except Exception as e:
        logger.debug("OpenAlex title search failed: %s", e)
    return None


def _lookup_biorxiv_api(doi: str) -> Optional[dict]:
    """Look up a paper in the bioRxiv/medRxiv API."""
    # Strip version suffix (v1, v2 etc)
    doi = re.sub(r'v\d+$', '', doi)
    # Strip .full suffix
    doi = re.sub(r'\.full$', '', doi)

    for server in ("biorxiv", "medrxiv"):
        try:
            resp = requests.get(
                f"https://api.biorxiv.org/details/{server}/{doi}",
                timeout=10, headers=HEADERS,
            )
            if resp.ok:
                data = resp.json()
                coll = data.get("collection", [])
                if coll:
                    paper = coll[0]
                    return {
                        "title": paper.get("title", "").strip().rstrip('.'),
                        "authors": [a.strip() for a in paper.get("authors", "").split(";") if a.strip()],
                        "year": int(paper.get("date", "")[:4]) if paper.get("date") else None,
                        "journal": server.capitalize(),
                        "abstract": paper.get("abstract", ""),
                        "doi": paper.get("doi", doi),
                    }
        except Exception as e:
            logger.debug("bioRxiv API failed for %s: %s", doi, e)
    return None


def _lookup_crossref(doi: str) -> Optional[dict]:
    """Look up a paper by DOI in Crossref."""
    try:
        resp = requests.get(
            f"https://api.crossref.org/works/{doi}",
            headers=HEADERS, timeout=10,
        )
        if resp.ok:
            data = resp.json().get("message", {})
            title = data.get("title", [""])[0] if data.get("title") else ""
            authors = [
                f"{a.get('given', '')} {a.get('family', '')}".strip()
                for a in data.get("author", [])
            ]
            year = None
            for date_key in ("published-print", "published-online", "created"):
                dp = data.get(date_key, {}).get("date-parts", [[]])
                if dp and dp[0]:
                    year = dp[0][0]
                    break
            journal = data.get("container-title", [""])[0] if data.get("container-title") else ""
            return {
                "title": title,
                "authors": authors,
                "year": year,
                "journal": journal,
                "doi": doi,
            }
    except Exception as e:
        logger.debug("Crossref lookup failed: %s", e)
    return None


def _lookup_crossref_pii(pii: str) -> Optional[dict]:
    """Look up a paper by Elsevier PII in Crossref."""
    try:
        resp = requests.get(
            "https://api.crossref.org/works",
            params={"query": pii, "rows": 1},
            headers=HEADERS, timeout=10,
        )
        if resp.ok:
            items = resp.json().get("message", {}).get("items", [])
            if items:
                data = items[0]
                title = data.get("title", [""])[0] if data.get("title") else ""
                if title:
                    authors = [
                        f"{a.get('given', '')} {a.get('family', '')}".strip()
                        for a in data.get("author", [])
                    ]
                    year = None
                    for dk in ("published-print", "published-online", "created"):
                        dp = data.get(dk, {}).get("date-parts", [[]])
                        if dp and dp[0]:
                            year = dp[0][0]
                            break
                    return {
                        "title": title,
                        "authors": authors,
                        "year": year,
                        "journal": data.get("container-title", [""])[0] if data.get("container-title") else "",
                        "doi": data.get("DOI"),
                    }
    except Exception as e:
        logger.debug("Crossref PII lookup failed: %s", e)
    return None


# ── Strategy 3: Google search ───────────────────────────────────

def _google_search_title(url: str) -> Optional[str]:
    """Search Google for a URL and extract the title from results."""
    try:
        resp = requests.get(
            "https://www.google.com/search",
            params={"q": url},
            headers={**HEADERS, "User-Agent": "Mozilla/5.0 (compatible; PaperTrail/1.0)"},
            timeout=10,
        )
        if resp.ok:
            # Extract title from first result
            m = re.search(r'<h3[^>]*>(.*?)</h3>', resp.text, re.I | re.DOTALL)
            if m:
                title = re.sub(r'<[^>]+>', '', m.group(1)).strip()
                if len(title) > 10:
                    return _clean_title(title)
    except Exception as e:
        logger.debug("Google search failed: %s", e)
    return None


# ── Helpers ─────────────────────────────────────────────────────

def _parse_openalex(data: dict) -> dict[str, Any]:
    """Parse OpenAlex API response into a flat dict."""
    title = data.get("title", "")
    if not title:
        return {}

    authors = [
        a.get("author", {}).get("display_name", "")
        for a in data.get("authorships", [])
    ]

    journal = None
    primary_loc = data.get("primary_location") or {}
    if primary_loc:
        source = primary_loc.get("source") or {}
        journal = source.get("display_name")

    abstract = None
    if data.get("abstract_inverted_index"):
        words = {}
        for word, positions in data["abstract_inverted_index"].items():
            for pos in positions:
                words[pos] = word
        if words:
            abstract = " ".join(words.get(i, "") for i in range(max(words) + 1))

    ids = data.get("ids", {}) or {}
    return {
        "title": title,
        "authors": authors,
        "year": data.get("publication_year"),
        "journal": journal,
        "abstract": abstract,
        "doi": ids.get("doi", "").replace("https://doi.org/", "") if ids.get("doi") else None,
        "cited_by_count": data.get("cited_by_count"),
        "openalex_url": data.get("id"),
    }


BOILERPLATE_PHRASES = [
    'biorxiv', 'medrxiv', 'openrxiv', 'preprint server', 'operated by',
    'cold spring harbor', 'arxiv.org e-print', 'the international journal',
    'this is an open access', 'creative commons', 'all rights reserved',
]


def _is_boilerplate(text: str) -> bool:
    """Check if text is a site boilerplate, not a real abstract."""
    lower = text.lower()
    return any(bp in lower for bp in BOILERPLATE_PHRASES)


def clean_text_for_clustering(title: str, abstract: str, message: str) -> str:
    """
    Build clean text for embedding/clustering.
    Strips URLs, journal names, and boilerplate from inputs.
    """
    url_pattern = re.compile(r'https?://\S+|<[^>]+>')
    msg = url_pattern.sub('', message).strip()

    # Strip journal/server name fragments that pollute topic modeling
    noise = re.compile(
        r'\b(?:biorxiv|medrxiv|openrxiv|arxiv|doi\.org|nature\.com|'
        r'sciencedirect|springer|wiley|elsevier|pubmed|pmc|'
        r'preprint|server|nonprofit|operated)\b',
        re.I,
    )
    parts = []
    for text in [title, abstract, msg]:
        if text and not _is_boilerplate(text):
            cleaned = noise.sub('', text).strip()
            cleaned = re.sub(r'\s+', ' ', cleaned)
            if len(cleaned) > 5:
                parts.append(cleaned)
    return ' '.join(parts)


def _clean_title(title: str) -> str:
    """Clean up a title string."""
    title = re.sub(r'\s+', ' ', title).strip()
    # Remove HTML entities
    title = title.replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>')
    title = title.replace('&#39;', "'").replace('&quot;', '"')
    return title


# ── Batch enrichment ────────────────────────────────────────────

def is_dead_link(url: str) -> bool:
    """Check if a URL is genuinely dead (the resource does not exist).

    Only a true 404/410 (or an explicit "not found" body) counts as dead.
    403 (bot-blocked publisher), 401 (paywall), 429 (rate limited), and 5xx
    are NOT dead — they are real papers we simply can't fetch as a bot, and
    deleting them is the main cause of undercounting. Network failures are
    treated as "not dead" (conservative — keep the paper).
    """
    try:
        resp = requests.get(url, timeout=10, allow_redirects=True,
                           headers={**HEADERS, "User-Agent": "Mozilla/5.0 (PaperTrail/1.0)"})
        if resp.status_code in (404, 410):
            return True
        # Only inspect the body of otherwise-OK responses for soft-404 pages.
        if resp.status_code < 400:
            body = resp.text[:3000].lower()
            if any(s in body for s in ['page not found', 'error 404', 'does not exist',
                                        'no forum found', 'this page isn', 'we can\'t find']):
                return True
    except requests.RequestException:
        return False
    return False


def remove_dead_links(papers: list[dict]) -> int:
    """
    Remove papers with dead URLs from the list (in-place).
    Only checks papers that are untitled (no point checking papers with metadata).
    Returns number removed.
    """
    untitled = [p for p in papers if not p.get("title") or p["title"] in ("", "Untitled", "Unknown Title")]
    logger.info("Checking %d untitled papers for dead links...", len(untitled))

    dead_urls = set()
    for i, p in enumerate(untitled):
        if is_dead_link(p["url"]):
            dead_urls.add(p["url"])
        if (i + 1) % 25 == 0:
            logger.info("  %d/%d checked, %d dead", i + 1, len(untitled), len(dead_urls))

    before = len(papers)
    papers[:] = [p for p in papers if p["url"] not in dead_urls]
    removed = before - len(papers)
    logger.info("Removed %d dead links", removed)
    return removed


def enrich_papers_cascade(
    papers: list[dict],
    email: str = "papertrail@example.com",
    delay: float = 0.2,
) -> int:
    """
    Enrich a list of papers in-place using the cascade strategy.
    Only enriches papers missing title or with 'Untitled'/'Unknown Title'.

    Returns the number of papers enriched.
    """
    to_enrich = [
        p for p in papers
        if not p.get("title") or p["title"] in ("", "Untitled", "Unknown Title")
    ]
    logger.info("Enriching %d papers via cascade (%d already have titles)", len(to_enrich), len(papers) - len(to_enrich))

    enriched = 0
    for i, paper in enumerate(to_enrich):
        url = paper.get("url", "")
        if not url:
            continue

        meta = enrich_url(url, email=email)
        if meta.get("title") and meta["title"] not in ("", "Untitled", "Unknown Title"):
            for k, v in meta.items():
                if v is not None and v != "" and v != []:
                    paper[k] = v
            enriched += 1

        if delay:
            time.sleep(delay)
        if (i + 1) % 50 == 0:
            logger.info("  %d/%d processed, %d enriched", i + 1, len(to_enrich), enriched)

    logger.info("Enriched %d / %d papers", enriched, len(to_enrich))
    return enriched
