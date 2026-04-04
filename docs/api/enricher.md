# Enricher API

The enricher module fetches paper metadata from OpenAlex and Semantic
Scholar. It tries multiple strategies (DOI, arXiv ID, PubMed ID, URL
analysis, title search) and merges results into a standardized
`PaperMetadata` dataclass.

## Quick Example

```python
from papertrail.enricher import PaperEnricher

enricher = PaperEnricher(
    email="you@example.com",  # enables OpenAlex polite pool (~10 req/s)
    openalex_first=True,       # try OpenAlex before Semantic Scholar
)

# Enrich a single paper by DOI
meta = enricher.enrich_by_doi("10.1038/nature12373")
print(meta.title, meta.authors, meta.year)

# Batch enrich from scraped data
papers = [
    {"url": "https://arxiv.org/abs/2301.04821", "ids": {"arxiv_id": "2301.04821"}},
    {"url": "https://doi.org/10.1103/PhysRevLett.123.021102", "ids": {"doi": "10.1103/PhysRevLett.123.021102"}},
]
enriched = enricher.enrich_papers(papers)
for p in enriched:
    print(p["title"], p.get("abstract", "")[:80])
```

## Data Classes

::: papertrail.enricher.PaperMetadata
    options:
      show_root_heading: true
      heading_level: 3
      members:
        - __post_init__
        - to_dict

## PaperEnricher

::: papertrail.enricher.PaperEnricher
    options:
      show_root_heading: true
      heading_level: 3
      members:
        - __init__
        - enrich_papers
        - enrich_by_doi
        - enrich_by_arxiv_id
        - enrich_by_pmid
        - enrich_by_title
        - enrich_by_title_openalex
        - enrich_by_url

## Enrichment Strategy Order

When calling `enrich_papers()`, each paper is tried against these
strategies in sequence. The first one that returns a result wins:

1. **DOI** → `enrich_by_doi()` (OpenAlex first if `openalex_first=True`)
2. **arXiv ID** → `enrich_by_arxiv_id()` (Semantic Scholar)
3. **PubMed ID** → `enrich_by_pmid()` (PubMed E-utilities)
4. **URL analysis** → `enrich_by_url()` (extracts IDs from URL, then retries above)
5. **Title search (OpenAlex)** → `enrich_by_title_openalex()` (fuzzy match)
6. **Title search (S2)** → `enrich_by_title()` (Semantic Scholar search)

## Input Format

`enrich_papers()` accepts a list of dicts. Each dict can have any of:

| Key | Type | Description |
|---|---|---|
| `url` | `str` | Paper URL (used for ID extraction and S2 URL lookup) |
| `doi` | `str` | Digital Object Identifier |
| `arxiv_id` | `str` | arXiv paper ID (e.g. `"2301.04821"`) |
| `pubmed_id` | `str` | PubMed ID |
| `title` | `str` | Paper title (for title-based search fallback) |
| `ids` | `dict` | Nested dict with `doi`, `arxiv_id`, `pmid` keys (from merge step) |

## Output: PaperMetadata Fields

| Field | Type | Source |
|---|---|---|
| `title` | `str` | All APIs |
| `authors` | `list[str]` | All APIs — **never truncated** |
| `year` | `int \| None` | All APIs |
| `journal` | `str \| None` | Primary location / venue |
| `abstract` | `str \| None` | S2, OpenAlex (reconstructed from inverted index) |
| `doi` | `str \| None` | Normalized (no URL prefix) |
| `arxiv_id` | `str \| None` | e.g. `"2301.04821"` |
| `pubmed_id` | `str \| None` | Numeric string |
| `pmc_id` | `str \| None` | e.g. `"PMC12345"` |
| `openalex_id` | `str \| None` | e.g. `"https://openalex.org/W1234567890"` |
| `semantic_scholar_id` | `str \| None` | S2 paper ID |
| `institutions` | `list[str]` | OpenAlex authorships |
| `keywords` | `list[str]` | Subject tags |
| `url` | `str \| None` | Primary paper URL |

## Rate Limiting

| API | Rate | Notes |
|---|---|---|
| OpenAlex (with email) | ~10 req/s | Set `email` param for polite pool |
| OpenAlex (without email) | ~1 req/s | Much slower |
| Semantic Scholar | ~3 req/s | Aggressive 429s, use 1.5s+ delay |
| PubMed E-utilities | ~3 req/s | NCBI standard limit |

## Backward Compatibility

::: papertrail.enricher.enrich_paper
    options:
      show_root_heading: true
      heading_level: 3
