# CLAUDE.md — Agent Instructions for PaperTrail

PaperTrail scrapes papers shared in Slack, enriches them with metadata, computes
semantic embeddings, and builds an interactive visualization dashboard.

## Repository Structure

```
PaperTrail/
├── papertrail/           # Python package
│   ├── __init__.py
│   ├── scraper.py        # Slack channel scraping + URL extraction
│   ├── enricher.py       # Metadata enrichment (OpenAlex + Semantic Scholar)
│   ├── embeddings.py     # Embedding backends (OpenAI, HF, fastembed, TF-IDF)
│   ├── projections.py    # PCA, t-SNE, UMAP projections + K-Means clustering
│   ├── preview.py        # Interactive HTML dashboard builder
│   └── cli.py            # Click CLI (papertrail scrape/enrich/embed/build/search)
├── skills/               # Claude Code skill files for agents
│   └── papertrail-pipeline/
│       └── SKILL.md      # Full pipeline skill for Cowork/Claude Code agents
├── pyproject.toml        # Package config and dependencies
├── tests/                # Unit tests
└── docs/                 # MkDocs documentation
```

## Quick Start (for agents)

### 1. Install

```bash
cd PaperTrail
pip install -e ".[all]" --break-system-packages
```

### 2. Full Pipeline

```python
import json
from papertrail.scraper import SlackPaperScraper
from papertrail.enricher import PaperEnricher
from papertrail.embeddings import embed_texts

# --- SCRAPE ---
scraper = SlackPaperScraper(token="xoxb-...")
papers = scraper.scrape_channel("C0123Q7PGGP")  # papers-dl

# --- ENRICH ---
enricher = PaperEnricher(
    email="user@example.com",    # Required for OpenAlex polite pool (10x faster)
    openalex_first=True,         # OpenAlex is faster, S2 as fallback
)
enriched = enricher.enrich_papers([p.__dict__ for p in papers])

# --- EMBED ---
texts = [f"{p.get('title','')} {p.get('abstract','')}" for p in enriched]
embeddings = embed_texts(texts)  # Auto-detects best backend

# --- SAVE ---
with open("papers_final.json", "w") as f:
    json.dump(enriched, f, indent=2)
```

### 3. CLI Usage

```bash
# Scrape
papertrail scrape --token $SLACK_BOT_TOKEN -o papers_raw.json

# Enrich
papertrail enrich papers_raw.json -o papers_enriched.json

# Embed + cluster
papertrail embed papers_enriched.json -o papers_final.json --backend openai

# Build dashboard
papertrail build papers_final.json -o dashboard.html

# Semantic search
papertrail search --query "single cell RNA sequencing" -k 10
```

## Key Design Decisions

### Enrichment Strategy (enricher.py)

The enricher tries multiple strategies in order:
1. **OpenAlex by DOI** (fastest, most generous rate limits with email)
2. **OpenAlex by PMID**
3. **Semantic Scholar by arXiv ID** (better arXiv coverage than OA)
4. **Semantic Scholar by DOI**
5. **URL analysis** → extract IDs → retry above strategies
6. **OpenAlex title search** (fuzzy match, last resort)
7. **S2 title search** (final fallback)

**Important**: Always set `email` parameter when creating `PaperEnricher` — this
gives you access to OpenAlex's polite pool with ~10 req/s vs ~1 req/s without.

OpenAlex returns abstracts as inverted indexes — `enricher._reconstruct_abstract()`
handles this conversion automatically.

The `pyalex` package is the recommended way to access OpenAlex (handles rate
limiting, retries, pagination). Falls back to raw HTTP if pyalex is not installed.

### Embedding Backends (embeddings.py)

Priority order for auto-detection:
1. **OpenAI** (`OPENAI_API_KEY` env var) — best quality, ~$0.02/1M tokens
2. **HuggingFace Inference API** (`HF_TOKEN` env var) — free tier available
3. **fastembed** (local ONNX) — offline, needs `pip install fastembed`
4. **TF-IDF + SVD** — always available, no API keys, lightweight fallback

To force a specific backend:
```python
embeddings = embed_texts(texts, backend="tfidf")  # or "openai", "huggingface"
```

### Scraper (scraper.py)

The `SlackPaperScraper` class handles:
- Full pagination via cursor-based API
- URL extraction from Slack message format (`<url|label>`)
- Paper domain detection (30+ academic domains)
- URL normalization (removes tracking params, normalizes arxiv/doi)
- Optional engagement metrics (reactions, reply counts)

**Koo Lab channels** (CSHL):
| Channel | ID |
|---|---|
| papers-dl | C0123Q7PGGP |
| papers-genomics | C015BQ2BDF0 |
| papers-protein | C011SDT3KKQ |
| papers-phenomics | C084KFWEVC2 |
| papers-ai-agents | C08C020L554 |
| papers-health | C09U8FW4YJV |
| paper_digest_moon | C0AEX373E5Q |

### Projections (projections.py)

Computes 2D projections for visualization:
- PCA (fast, linear)
- t-SNE (perplexity=30, max_iter=1000)
- UMAP (n_neighbors=15, min_dist=0.1)

K-Means clustering with TF-IDF-based cluster labels.

## MCP Tool Integration

When running inside Claude Code / Cowork with Slack MCP tools available, you can
use MCP tools instead of direct API access:

```
slack_read_channel(channel_id, limit=200, cursor=...)
```

The scraper's URL extraction and domain filtering logic works the same way —
just feed message texts through `SlackPaperScraper.extract_paper_urls()`.

## Rate Limiting Notes

- **OpenAlex**: ~10 req/s with email (polite pool), ~1/s without. Use pyalex.
- **Semantic Scholar**: ~3 req/s unauthenticated. Very aggressive 429s. Add 1.5s+ between calls.
- **Slack API**: Standard tier 1 rate limits (~1 req/s for conversations.history)

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `SLACK_BOT_TOKEN` | For scraping | Slack Bot Token (xoxb-...) |
| `OPENAI_API_KEY` | For OpenAI embeddings | OpenAI API key |
| `HF_TOKEN` | For HF embeddings | HuggingFace API token |

## Testing

```bash
pytest tests/ -v
```

## Common Pitfalls

1. **S2 rate limiting**: If you see lots of 429s, switch to OpenAlex-first strategy
   or increase delay between S2 calls to 2+ seconds.
2. **Missing abstracts**: Many papers lack abstracts in S2. Use OpenAlex title search
   as a second pass to recover them.
3. **fastembed OOM**: On memory-constrained environments, use TF-IDF backend instead.
4. **FAISS not installed**: FAISS is optional. The VectorStore class requires it, but
   embeddings work fine without it.
5. **OpenAlex abstract format**: Abstracts come as inverted indexes, not plain text.
   The enricher handles reconstruction automatically.
