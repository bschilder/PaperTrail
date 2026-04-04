# Quick Reference: Slack Paper Scraper & Enricher

## File Locations

- **Scraper Module**: `/sessions/elegant-wonderful-wozniak/PaperTrail/papertrail/scraper.py` (790 lines)
- **Enricher Module**: `/sessions/elegant-wonderful-wozniak/PaperTrail/papertrail/enricher.py` (865 lines)
- **Full Guide**: `/sessions/elegant-wonderful-wozniak/PaperTrail/SCRAPER_AND_ENRICHER_GUIDE.md` (698 lines)

## Scraper Module: `SlackPaperScraper`

### Initialization
```python
from papertrail.scraper import SlackPaperScraper

scraper = SlackPaperScraper(
    token="xoxb-your-bot-token",
    rate_limit_delay=0.3
)
```

### Main Methods

| Method | Purpose | Returns |
|--------|---------|---------|
| `scrape_channel(channel_id, oldest=None, latest=None, include_replies=False)` | Scrape all papers from a channel | `list[SlackPaper]` |
| `extract_paper_urls(texts)` | Extract paper URLs from text | `list[str]` |
| `is_paper_url(url)` | Check if URL is a paper | `bool` |
| `normalize_url(url)` | Normalize URL for comparison | `str` |

### SlackPaper Data

```python
@dataclass
class SlackPaper:
    channel_id: str          # Channel ID
    channel_name: str        # Channel name
    shared_by: str          # Who shared it
    user_id: str            # User ID
    timestamp: str          # ISO format timestamp
    message_ts: str         # Slack timestamp
    permalink: str          # Link to message
    message_text: str       # Cleaned message text
    paper_url: str          # Extracted URL
    reactions_count: int    # Total reactions
    reply_count: int        # Thread replies
    reaction_details: dict  # {emoji: count}
```

### Supported Domains (29 total)

**Preprints**: arxiv.org, biorxiv.org, medrxiv.org, psyarxiv.org, eartharxiv.org

**Publishers**: nature.com, science.org, cell.com, pnas.org, springer.com, wiley.com, elsevier.com

**Public Access**: pubmed.ncbi.nlm.nih.gov, pmc.ncbi.nlm.nih.gov, plos.org, elifesciences.org

**Repositories**: researchgate.net, academia.edu, ssrn.com, and others

## Enricher Module: `PaperEnricher`

### Initialization
```python
from papertrail.enricher import PaperEnricher

enricher = PaperEnricher(
    cache_size=1000,
    timeout=15,
    max_retries=3
)
```

### Main Methods

| Method | Input | Returns |
|--------|-------|---------|
| `enrich_by_doi(doi)` | DOI string | `PaperMetadata \| None` |
| `enrich_by_arxiv_id(arxiv_id)` | arXiv ID | `PaperMetadata \| None` |
| `enrich_by_pmid(pmid)` | PubMed ID | `PaperMetadata \| None` |
| `enrich_by_title(title)` | Paper title | `PaperMetadata \| None` |
| `enrich_by_url(url)` | Paper URL | `PaperMetadata \| None` |
| `enrich_papers(papers, require_title=False)` | List of dicts | `list[dict]` |

### PaperMetadata Output

```python
@dataclass
class PaperMetadata:
    title: str                          # Paper title
    authors: list[str]                  # Author names
    year: Optional[int]                 # Publication year
    journal: Optional[str]              # Journal/venue
    abstract: Optional[str]             # Paper abstract
    doi: Optional[str]                  # DOI
    arxiv_id: Optional[str]             # arXiv ID
    pubmed_id: Optional[str]            # PubMed ID
    pmc_id: Optional[str]               # PMC ID
    openalex_id: Optional[str]          # OpenAlex ID
    semantic_scholar_id: Optional[str]  # S2 ID
    institutions: list[str]             # Author institutions
    keywords: list[str]                 # Keywords/subjects
    url: Optional[str]                  # Primary URL

    def to_dict(self) -> dict:          # Export as dict
```

## API Backends

| Backend | Coverage | Auth | Rate Limit |
|---------|----------|------|-----------|
| Semantic Scholar | DOI, arXiv, Title | None | Auto backoff |
| OpenAlex | DOI, Title | None | Auto backoff |
| PubMed | PMID, PMC ID | None | 3 req/sec |

## Usage Patterns

### Pattern 1: Simple Scraping
```python
scraper = SlackPaperScraper(token="xoxb-...")
papers = scraper.scrape_channel("C123456789")
print(f"Found {len(papers)} papers")
```

### Pattern 2: Enrich by Multiple Methods
```python
enricher = PaperEnricher()

# Try DOI first, then URL, then title
for paper in papers:
    meta = enricher.enrich_by_doi(paper.get("doi"))
    if not meta:
        meta = enricher.enrich_by_url(paper.get("url"))
    if not meta:
        meta = enricher.enrich_by_title(paper.get("title"))

    if meta:
        print(f"{meta.title} ({meta.year})")
```

### Pattern 3: Batch Processing
```python
papers_list = [
    {"url": "https://arxiv.org/abs/2301.04821"},
    {"doi": "10.1038/nature12373"},
    {"title": "Some Paper Title"},
]

enriched = enricher.enrich_papers(papers_list)
print(f"Enriched {len(enriched)} papers")
```

### Pattern 4: Scrape + Enrich Pipeline
```python
# Scrape
scraper = SlackPaperScraper(token="xoxb-...")
papers = scraper.scrape_channel("C123456789")

# Convert to enrichment format
paper_list = [
    {"url": p.paper_url, "shared_by": p.shared_by}
    for p in papers
]

# Enrich
enricher = PaperEnricher()
enriched = enricher.enrich_papers(paper_list)

# Export
import json
with open("papers.json", "w") as f:
    json.dump(enriched, f, indent=2)
```

## Backward Compatibility

```python
# Old interface still works:
from papertrail.scraper import SlackScraper  # Alias
scraper = SlackScraper(token="xoxb-...")

from papertrail.enricher import enrich_paper
meta = enrich_paper("https://arxiv.org/abs/2301.04821")

from papertrail.enricher import _extract_doi, _extract_arxiv_id
doi = _extract_doi(url)
arxiv = _extract_arxiv_id(url)
```

## Performance Tips

### For Large Batches
```python
# Increase cache and timeout
enricher = PaperEnricher(
    cache_size=5000,
    timeout=20,
    max_retries=5
)

# Process in chunks
chunk_size = 100
for i in range(0, len(papers), chunk_size):
    chunk = papers[i:i + chunk_size]
    enriched = enricher.enrich_papers(chunk)
```

### For Rate Limiting
```python
# Adjust scraper delay
scraper = SlackPaperScraper(
    token="xoxb-...",
    rate_limit_delay=1.0  # Slower for conservative scraping
)

# Enricher auto-backoffs on 429 responses
```

## Testing

Run tests:
```bash
cd /sessions/elegant-wonderful-wozniak/PaperTrail
pytest tests/test_scraper.py tests/test_enricher.py -v
```

All tests passing (5/5):
- ✓ test_paper_url_detection
- ✓ test_clean_text
- ✓ test_ts_to_date
- ✓ test_extract_doi
- ✓ test_extract_arxiv_id

## Environment

- **Python**: 3.9+
- **Dependencies**: requests, slack_sdk
- **APIs**: Free, no authentication required
- **Status**: Production-ready

## Further Documentation

See `/sessions/elegant-wonderful-wozniak/PaperTrail/SCRAPER_AND_ENRICHER_GUIDE.md` for:
- Detailed method documentation
- Advanced usage patterns
- Integration examples (CSV, SQLite, JSON)
- Troubleshooting guide
- Performance optimization
- Error handling strategies

## Common Issues

| Issue | Solution |
|-------|----------|
| No papers found | Check channel ID format (C...) and token scopes |
| Enrichment returns None | Try different strategies or check if paper exists in APIs |
| Rate limited | Increase delays or reduce batch size |
| Missing metadata | Some papers may not have complete info in APIs |

## Key Files

```
/sessions/elegant-wonderful-wozniak/PaperTrail/
├── papertrail/
│   ├── scraper.py          (790 lines - Slack scraping)
│   ├── enricher.py         (865 lines - Paper enrichment)
│   ├── __init__.py
│   └── ...other modules
├── tests/
│   ├── test_scraper.py     (Updated, all passing)
│   ├── test_enricher.py    (All passing)
│   └── ...other tests
├── SCRAPER_AND_ENRICHER_GUIDE.md    (Full documentation)
├── MODULES_QUICK_REFERENCE.md       (This file)
└── ...other files
```
