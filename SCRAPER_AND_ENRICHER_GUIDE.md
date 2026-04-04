# Slack Paper Scraper and Enricher Modules

Comprehensive, production-quality Python modules for discovering, extracting, and enriching academic papers shared in Slack channels.

## Overview

This package contains two main modules:

1. **`papertrail.scraper`** - Extracts paper URLs from Slack messages with full pagination support
2. **`papertrail.enricher`** - Enriches paper metadata using Semantic Scholar and OpenAlex APIs

Both modules are designed for:
- Production use with proper error handling and logging
- Agents and automated pipelines
- Research and analysis workflows
- Integration into larger systems

## Installation

Both modules are included in the PaperTrail package. Ensure dependencies are installed:

```bash
pip install slack_sdk requests
```

## Module 1: SlackPaperScraper

### Quick Start

```python
from papertrail.scraper import SlackPaperScraper

# Initialize scraper with Slack bot token
scraper = SlackPaperScraper(token="xoxb-your-token-here")

# Scrape a channel for papers
channel_id = "C123456789"
papers = scraper.scrape_channel(channel_id, include_replies=True)

# Print results
for paper in papers[:5]:
    print(f"{paper.shared_by}: {paper.paper_url}")
    print(f"  Reactions: {paper.reactions_count}, Replies: {paper.reply_count}")
```

### Core Methods

#### `scrape_channel(channel_id, oldest=None, latest=None, include_replies=False)`

Scrape all messages from a channel with full pagination and optional engagement metrics.

**Parameters:**
- `channel_id` (str): Channel ID to scrape (starts with 'C')
- `oldest` (str | float, optional): Oldest message timestamp to include
- `latest` (str | float, optional): Newest message timestamp to include
- `include_replies` (bool): Fetch reaction counts and thread reply metrics (slower)

**Returns:** List of `SlackPaper` objects with metadata

**Example:**
```python
# Scrape last 30 days of papers
import time
thirty_days_ago = time.time() - (30 * 24 * 3600)

papers = scraper.scrape_channel(
    "C123456789",
    oldest=thirty_days_ago,
    include_replies=True
)

print(f"Found {len(papers)} papers in last 30 days")
```

#### `extract_paper_urls(texts)`

Extract paper URLs from a list of text strings.

**Parameters:**
- `texts` (list[str]): List of text strings to search

**Returns:** List of deduplicated, normalized paper URLs

**Example:**
```python
message_texts = [
    "Check out this paper: https://arxiv.org/abs/2301.04821",
    "Also see https://doi.org/10.1038/nature12373"
]

urls = scraper.extract_paper_urls(message_texts)
# Returns: ['https://arxiv.org/abs/2301.04821', 'https://doi.org/10.1038/nature12373']
```

#### `is_paper_url(url)`

Check if a URL points to a paper or academic resource.

**Parameters:**
- `url` (str): URL to check

**Returns:** bool

**Example:**
```python
assert scraper.is_paper_url("https://arxiv.org/abs/2301.04821") == True
assert scraper.is_paper_url("https://google.com") == False
assert scraper.is_paper_url("https://doi.org/10.1234/example") == True
```

#### `normalize_url(url)`

Normalize a URL for consistent comparison and deduplication.

Removes:
- URL fragments
- Tracking parameters (utm_*, fbclid, etc.)
- Standardizes domain case

**Parameters:**
- `url` (str): URL to normalize

**Returns:** Normalized URL

**Example:**
```python
url1 = "https://arxiv.org/abs/2301.04821?utm_source=slack"
url2 = "https://arxiv.org/abs/2301.04821#section=intro"

norm1 = scraper.normalize_url(url1)
norm2 = scraper.normalize_url(url2)

print(norm1 == norm2)  # True - both point to same paper
```

### Paper Domains Covered

The scraper recognizes 29 major academic paper sources:

**Preprint Servers:**
- arxiv.org, biorxiv.org, medrxiv.org, psyarxiv.org, eartharxiv.org

**Major Publishers:**
- nature.com, science.org, cell.com, pnas.org, springer.com, wiley.com, elsevier.com

**Public Access:**
- pubmed.ncbi.nlm.nih.gov, pmc.ncbi.nlm.nih.gov, plos.org, elifesciences.org

**Repositories:**
- researchgate.net, academia.edu, ssrn.com

See `PAPER_DOMAINS` constant for complete list.

### SlackPaper Data Class

Each scrape returns a list of `SlackPaper` objects:

```python
@dataclass
class SlackPaper:
    channel_id: str              # Slack channel ID
    channel_name: str            # Human-readable channel name
    shared_by: str              # Name of person who shared
    user_id: str                # Slack user ID
    timestamp: str              # ISO format timestamp
    message_ts: str             # Slack message timestamp
    permalink: str              # Link to message in Slack
    message_text: str           # Message text (cleaned)
    paper_url: str              # Extracted paper URL
    reactions_count: int        # Total emoji reactions
    reply_count: int            # Replies in thread
    reaction_details: dict      # {emoji_name: count}
```

### Advanced Usage

#### Scrape Multiple Channels

```python
channels = ["C123456789", "C987654321"]
all_papers = []

for channel_id in channels:
    papers = scraper.scrape_channel(channel_id)
    all_papers.extend(papers)

print(f"Found {len(all_papers)} papers across {len(channels)} channels")
```

#### Filter by Date Range

```python
import time
from datetime import datetime, timedelta

# Papers from last week
one_week_ago = time.time() - (7 * 24 * 3600)

papers = scraper.scrape_channel(
    "C123456789",
    oldest=one_week_ago
)

# Or use ISO format
start = datetime.now() - timedelta(days=7)
papers = scraper.scrape_channel(
    "C123456789",
    oldest=start.timestamp()
)
```

#### Dedup by URL

```python
papers = scraper.scrape_channel("C123456789")

# Use a set to track unique URLs
seen_urls = set()
unique_papers = []

for paper in papers:
    if paper.paper_url not in seen_urls:
        seen_urls.add(paper.paper_url)
        unique_papers.append(paper)

print(f"Found {len(unique_papers)} unique papers")
```

## Module 2: PaperEnricher

### Quick Start

```python
from papertrail.enricher import PaperEnricher

# Initialize enricher (no API keys needed!)
enricher = PaperEnricher()

# Enrich by different identifiers
doi_meta = enricher.enrich_by_doi("10.1038/nature12373")
arxiv_meta = enricher.enrich_by_arxiv_id("2301.04821")
pmid_meta = enricher.enrich_by_pmid("22460902")

# Print results
print(f"Title: {doi_meta.title}")
print(f"Authors: {', '.join(doi_meta.authors)}")
print(f"Year: {doi_meta.year}")
print(f"Journal: {doi_meta.journal}")
```

### Core Methods

#### `enrich_by_doi(doi)`

Enrich a paper by DOI (Digital Object Identifier).

**Parameters:**
- `doi` (str): DOI in any format (with or without 'https://doi.org/' prefix)

**Returns:** `PaperMetadata` object or None

**Example:**
```python
# These all work:
meta1 = enricher.enrich_by_doi("10.1038/nature12373")
meta2 = enricher.enrich_by_doi("https://doi.org/10.1038/nature12373")
meta3 = enricher.enrich_by_doi("doi:10.1038/nature12373")

if meta1:
    print(f"{meta1.title} ({meta1.year})")
    print(f"Journal: {meta1.journal}")
```

#### `enrich_by_arxiv_id(arxiv_id)`

Enrich a paper by arXiv identifier.

**Parameters:**
- `arxiv_id` (str): arXiv ID (e.g., "2301.04821" or "2301.04821v2")

**Returns:** `PaperMetadata` object or None

**Example:**
```python
meta = enricher.enrich_by_arxiv_id("2301.04821")
print(f"Abstract: {meta.abstract[:200]}...")
```

#### `enrich_by_pmid(pmid)`

Enrich a paper by PubMed ID.

**Parameters:**
- `pmid` (str): PubMed ID (numeric)

**Returns:** `PaperMetadata` object or None

**Example:**
```python
meta = enricher.enrich_by_pmid("22460902")
print(f"Published in: {meta.journal}")
```

#### `enrich_by_title(title)`

Enrich a paper by title search (less reliable than ID-based lookup).

**Parameters:**
- `title` (str): Paper title (minimum 10 characters)

**Returns:** `PaperMetadata` object or None

**Example:**
```python
meta = enricher.enrich_by_title("Attention Is All You Need")
if meta:
    print(f"Authors: {', '.join(meta.authors)}")
```

#### `enrich_by_url(url)`

Enrich a paper by analyzing its URL and extracting identifiers.

Automatically detects and uses DOI, arXiv ID, or PubMed ID from the URL.

**Parameters:**
- `url` (str): Paper URL

**Returns:** `PaperMetadata` object or None

**Example:**
```python
# These URLs will be analyzed and enriched automatically:
meta1 = enricher.enrich_by_url("https://arxiv.org/abs/2301.04821")
meta2 = enricher.enrich_by_url("https://doi.org/10.1038/nature12373")
meta3 = enricher.enrich_by_url("https://pubmed.ncbi.nlm.nih.gov/22460902")
```

#### `enrich_papers(papers, require_title=False)`

Batch enrich multiple papers using multiple strategies.

For each paper, tries enrichment in order:
1. By DOI (if provided)
2. By arXiv ID
3. By PubMed ID
4. By URL analysis
5. By title search

**Parameters:**
- `papers` (list[dict]): List of paper dictionaries with keys: url, doi, arxiv_id, pubmed_id, title
- `require_title` (bool): Only include papers with titles in results

**Returns:** List of enriched paper dictionaries

**Example:**
```python
papers = [
    {"url": "https://arxiv.org/abs/2301.04821"},
    {"doi": "10.1103/PhysRevLett.123.021102"},
    {"title": "Attention Is All You Need"},
    {"pubmed_id": "22460902"},
]

enriched = enricher.enrich_papers(papers)

for paper in enriched:
    print(f"{paper['title']} ({paper.get('year')})")
    print(f"  Authors: {', '.join(paper.get('authors', [])[:3])}")
```

### PaperMetadata Structure

All enrichment methods return standardized `PaperMetadata` objects:

```python
@dataclass
class PaperMetadata:
    title: str                      # Paper title
    authors: list[str]              # Author names
    year: Optional[int]             # Publication year
    journal: Optional[str]          # Journal/venue name
    abstract: Optional[str]         # Paper abstract
    doi: Optional[str]              # Digital Object Identifier
    arxiv_id: Optional[str]         # arXiv ID
    pubmed_id: Optional[str]        # PubMed ID
    pmc_id: Optional[str]           # PubMed Central ID
    openalex_id: Optional[str]      # OpenAlex work ID
    semantic_scholar_id: Optional[str]  # Semantic Scholar ID
    institutions: list[str]         # Author institutions
    keywords: list[str]             # Paper keywords
    url: Optional[str]              # Primary paper URL

    def to_dict(self) -> dict:
        """Convert to dictionary, excluding None values."""
```

### Advanced Usage

#### Chain Scraping and Enrichment

```python
from papertrail.scraper import SlackPaperScraper
from papertrail.enricher import PaperEnricher

# Scrape papers
scraper = SlackPaperScraper(token="xoxb-...")
papers = scraper.scrape_channel("C123456789")

# Extract URLs and prepare for enrichment
paper_list = [
    {"url": p.paper_url, "shared_by": p.shared_by}
    for p in papers
]

# Enrich all
enricher = PaperEnricher()
enriched = enricher.enrich_papers(paper_list)

# Save results
import json
with open("enriched_papers.json", "w") as f:
    json.dump(enriched, f, indent=2)
```

#### Batch Enrichment with Progress

```python
from tqdm import tqdm

papers = [...]  # List of paper dictionaries

enriched = []
for paper in tqdm(papers, desc="Enriching papers"):
    # Try different strategies
    if paper.get("doi"):
        meta = enricher.enrich_by_doi(paper["doi"])
    elif paper.get("url"):
        meta = enricher.enrich_by_url(paper["url"])
    else:
        meta = enricher.enrich_by_title(paper.get("title", ""))

    if meta:
        enriched.append({**paper, **meta.to_dict()})

print(f"Successfully enriched {len(enriched)}/{len(papers)} papers")
```

#### Error Handling and Fallbacks

```python
papers = [
    {"url": "https://arxiv.org/abs/2301.04821"},
    {"title": "Some Paper Title"},  # May not have URL
    {"doi": "10.1234/invalid"},      # May fail
]

enriched = []
for paper in papers:
    try:
        # Try primary method
        if paper.get("doi"):
            meta = enricher.enrich_by_doi(paper["doi"])
        elif paper.get("url"):
            meta = enricher.enrich_by_url(paper["url"])
        else:
            meta = None

        # Fallback to title search
        if not meta and paper.get("title"):
            meta = enricher.enrich_by_title(paper["title"])

        if meta:
            enriched.append({**paper, **meta.to_dict()})
        else:
            print(f"Could not enrich: {paper}")

    except Exception as e:
        print(f"Error enriching {paper}: {e}")
        continue

print(f"Enriched {len(enriched)} papers")
```

### API Backends

The enricher uses two free APIs:

1. **Semantic Scholar API** (https://api.semanticscholar.org)
   - Covers: DOI, arXiv IDs, title search
   - Returns: Title, authors, year, abstract, citations
   - No authentication required

2. **OpenAlex API** (https://api.openalex.org)
   - Covers: DOI-based lookups
   - Returns: Title, authors, institutions, keywords
   - No authentication required

Both APIs are free and don't require API keys. They respect rate limits with automatic backoff.

## Integration Examples

### Export to CSV

```python
import csv
from papertrail.scraper import SlackPaperScraper
from papertrail.enricher import PaperEnricher

scraper = SlackPaperScraper(token="xoxb-...")
enricher = PaperEnricher()

# Scrape and enrich
papers = scraper.scrape_channel("C123456789")
paper_list = [{"url": p.paper_url, "shared_by": p.shared_by} for p in papers]
enriched = enricher.enrich_papers(paper_list)

# Export to CSV
with open("papers.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=[
        "title", "authors", "year", "journal", "doi", "shared_by"
    ])
    writer.writeheader()
    for paper in enriched:
        authors = ", ".join(paper.get("authors", [])[:5])
        writer.writerow({
            "title": paper.get("title"),
            "authors": authors,
            "year": paper.get("year"),
            "journal": paper.get("journal"),
            "doi": paper.get("doi"),
            "shared_by": paper.get("shared_by"),
        })
```

### Create a Paper Database

```python
import sqlite3
from papertrail.scraper import SlackPaperScraper
from papertrail.enricher import PaperEnricher

# Create database
conn = sqlite3.connect("papers.db")
cursor = conn.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS papers (
        id INTEGER PRIMARY KEY,
        title TEXT,
        authors TEXT,
        year INTEGER,
        journal TEXT,
        doi TEXT UNIQUE,
        url TEXT UNIQUE,
        shared_by TEXT,
        shared_date TEXT,
        reactions INTEGER,
        replies INTEGER
    )
""")

# Scrape and enrich
scraper = SlackPaperScraper(token="xoxb-...")
enricher = PaperEnricher()

papers = scraper.scrape_channel("C123456789")

for paper in papers:
    meta = enricher.enrich_by_url(paper.paper_url)
    if meta:
        cursor.execute("""
            INSERT OR REPLACE INTO papers
            (title, authors, year, journal, doi, url, shared_by, shared_date, reactions, replies)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            meta.title,
            ", ".join(meta.authors),
            meta.year,
            meta.journal,
            meta.doi,
            paper.paper_url,
            paper.shared_by,
            paper.timestamp,
            paper.reactions_count,
            paper.reply_count,
        ))

conn.commit()
conn.close()
print("Database created!")
```

## Performance & Rate Limiting

### Scraper Performance

- **Full pagination**: Automatically handles Slack API pagination
- **Rate limiting**: 0.3s delay between API calls (configurable)
- **Caching**: Caches channel names and user profiles to reduce API calls
- **Typical speed**: 100-200 papers per minute

### Enricher Performance

- **API backoff**: Exponential backoff on rate limits (429)
- **Caching**: Stores API responses to avoid redundant lookups
- **Timeout**: 15 seconds per request (configurable)
- **Retries**: 3 retry attempts with exponential backoff
- **Typical speed**: 10-20 papers per second

### Optimize for Large Batches

```python
enricher = PaperEnricher(
    cache_size=5000,      # Larger cache for big batches
    timeout=20,           # Longer timeout for slow networks
    max_retries=5,        # More retries for flaky connections
)

# Process in chunks to manage memory
chunk_size = 100
for i in range(0, len(papers), chunk_size):
    chunk = papers[i:i + chunk_size]
    enriched = enricher.enrich_papers(chunk)
    # Process chunk
```

## Backward Compatibility

The modules maintain compatibility with legacy code:

```python
# Old interface still works:
from papertrail.scraper import SlackScraper
scraper = SlackScraper(token="xoxb-...")  # Works!

# Old function interface:
from papertrail.enricher import enrich_paper
meta = enrich_paper("https://arxiv.org/abs/2301.04821")

# Old helper functions:
from papertrail.enricher import _extract_doi, _extract_arxiv_id
doi = _extract_doi("https://doi.org/10.1234/example")
arxiv = _extract_arxiv_id("https://arxiv.org/abs/2301.04821")
```

## Troubleshooting

### Scraper Issues

**No papers found:**
- Check channel ID format (must start with 'C')
- Verify token has `channels:history` and `channels:read` scopes
- Check if channel has any messages

**Rate limiting:**
- Increase `rate_limit_delay` parameter
- Batch requests to multiple channels

**User/channel name resolution fails:**
- Verify token has `users:read` scope
- Some names may not resolve for private channels

### Enricher Issues

**Enrichment returns None:**
- Paper may not be in Semantic Scholar or OpenAlex databases
- Try different identification strategies
- Check URL format is correct

**Rate limited (429 errors):**
- Module auto-retries with exponential backoff
- Reduce batch size if persistent
- Add delay between batches

**Missing authors/abstract:**
- Not all papers have complete metadata in the APIs
- Some preprints may have more metadata than published papers

## See Also

- Slack Bot Token: https://api.slack.com/authentication/basics
- Semantic Scholar API: https://api.semanticscholar.org/
- OpenAlex API: https://openalex.org/
- PubMed API: https://www.ncbi.nlm.nih.gov/books/NBK25497/

## Contributing

Both modules are designed to be extended. Key extension points:

- Add new `PAPER_DOMAINS` for additional paper sources
- Implement additional `enrich_by_*` methods
- Add new API backends to `PaperEnricher`
- Customize scraper search queries

## License

MIT License - See LICENSE file for details.
