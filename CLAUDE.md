# CLAUDE.md — Agent Instructions for PaperTrail

PaperTrail scrapes papers shared in Slack, enriches them with metadata, computes
semantic embeddings, and builds an interactive visualization dashboard.

## Repository Structure

```
PaperTrail/
├── papertrail/                  # Python package
│   ├── __init__.py
│   ├── scraper.py               # Slack channel scraping + URL extraction
│   ├── enricher.py              # Metadata enrichment (OpenAlex + PubMed)
│   ├── embeddings.py            # Embedding backends (OpenAI, HF, fastembed, TF-IDF)
│   ├── projections.py           # PCA, t-SNE, UMAP projections + K-Means clustering
│   ├── preview.py               # Interactive HTML dashboard builder
│   ├── cli.py                   # Click CLI (papertrail scrape/enrich/embed/build/search)
│   └── templates/
│       └── dashboard.html       # Dashboard HTML template (uses {{DATA_B64}} placeholder)
├── skills/                      # Claude Code / Cowork skill files
│   ├── papertrail-pipeline/
│   │   └── SKILL.md             # Full pipeline skill for agents
│   └── paper-metadata-scraper/
│       └── SKILL.md             # Multi-strategy metadata resolution cascade
├── pyproject.toml               # Package config and dependencies
├── tests/                       # Unit tests
├── docs/                        # MkDocs documentation
└── papertrail_dashboard.html    # Pre-built dashboard (Koo Lab, 1,072 papers)
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
    openalex_first=True,         # OpenAlex is faster, PubMed as fallback
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

### Dashboard Template (papertrail/templates/dashboard.html)

The dashboard is a self-contained HTML file with:
- **Canvas-based scatter plot** with hardware-accelerated rendering
- **Three projections**: UMAP, t-SNE, PCA (toggle in real time)
- **Six color modes**: Cluster, Channel, User, Date, Year, Citations
- **Lasso & rectangle selection** with coordinate normalization via `canvasCoords(e)`
- **Detail panel** inline in the left sidebar (not a right overlay)
- **AI chatbot** with Claude API tool use (`search_papers` tool)
- **Base64 data injection**: `preview.py` encodes JSON → base64 → replaces `{{DATA_B64}}`

Important implementation detail: The canvas uses CSS `width:100%; height:100%` but
the buffer dimensions differ from CSS pixels. The `canvasCoords(e)` helper normalizes
mouse events from CSS pixel space to canvas buffer space. All mouse handlers
(mousedown, mousemove, mouseup, wheel) must use this helper.

### Enrichment Strategy (enricher.py + skills/paper-metadata-scraper/)

The enricher uses a multi-strategy cascade:
1. **Extract identifiers from URL** — DOIs, arXiv IDs, Elsevier PIIs, PMC IDs, OpenReview IDs
2. **Batch OpenAlex lookup** — up to 40 DOIs per request (10-40x faster than individual)
3. **Individual OpenAlex** — DOI, arXiv DOI (`10.48550/arXiv.{id}`), or PMC ID
4. **PubMed E-utilities** — best for Elsevier/Cell PIIs (format: `S{4}-{4}({2}){5}-{1}`)
5. **Web search fallback** — for OpenReview, conference proceedings
6. **URL-based fallback** — generates readable titles from URL structure

**Important**: Always set `email` parameter when creating `PaperEnricher` — this
gives you access to OpenAlex's polite pool with ~10 req/s vs ~1 req/s without.

OpenAlex returns abstracts as inverted indexes — `enricher._reconstruct_abstract()`
handles this conversion automatically.

### Embedding Backends (embeddings.py)

Priority order for auto-detection:
1. **OpenAI** (`OPENAI_API_KEY` env var) — best quality, ~$0.02/1M tokens
2. **HuggingFace Inference API** (`HF_TOKEN` env var) — free tier available
3. **fastembed** (local ONNX) — offline, needs `pip install fastembed`
4. **TF-IDF + SVD** — always available, no API keys, lightweight fallback (128 dims)

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

**Koo Lab channels** (CSHL, workspace: koolab.slack.com):
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
- **PubMed (NCBI)**: 3 req/s without API key, 10 req/s with free API key.
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

## Design Inspirations

The dashboard draws from several best-in-class data visualization tools:

- **DataMapPlot** ([github](https://github.com/TutteInstitute/datamapplot),
  [docs](https://datamapplot.readthedocs.io/)) — Hierarchical cluster labels
  sized proportionally to cluster population, geographic-map aesthetic with
  labels at centroids, overlap avoidance.

- **CellXGene** — Canvas-based scatter plot with lasso/rect selection, detail
  panel for selected items, projection switching (UMAP/t-SNE/PCA).

- **Nomic Atlas** ([github](https://github.com/nomic-ai/nomic),
  [HF](https://huggingface.co/nomic-ai)) — Embedding-based paper maps,
  interactive topic exploration, Nomic embed models for scientific text.

- **Connected Papers** — Paper relationship visualization, citation-based
  graph exploration.

- **Semantic Scholar** — Paper metadata, abstract previews, citation counts,
  author information display patterns.

### Embedding Model Sources

Models are drawn from multiple providers (see `embeddings.py:MODEL_REGISTRY`):
- **OpenAI**: text-embedding-3-small/large, o3-embedding
- **Nomic AI**: nomic-embed-text-v1/v1.5, modernbert-embed-base
- **BAAI**: bge-small/base/large-en-v1.5
- **Alibaba NLP**: gte-Qwen2 (1.5B, 7B), gte-large-en-v1.5
- **Sentence Transformers**: all-MiniLM-L6-v2, all-mpnet-base-v2

## Common Pitfalls

1. **Elsevier/Cell PIIs**: These are the hardest to resolve. PubMed E-utilities is the
   most reliable strategy. OpenAlex and Semantic Scholar often can't resolve raw PIIs.
2. **Canvas coordinate mismatch**: CSS pixels != canvas buffer pixels. Always use
   `canvasCoords(e)` in mouse handlers, never raw `e.offsetX/Y`.
3. **S2 rate limiting**: If you see lots of 429s, switch to OpenAlex-first strategy
   or increase delay between S2 calls to 2+ seconds.
4. **Missing abstracts**: Many papers lack abstracts in S2. Use OpenAlex title search
   as a second pass to recover them.
5. **fastembed OOM**: On memory-constrained environments, use TF-IDF backend instead.
6. **OpenAlex abstract format**: Abstracts come as inverted indexes, not plain text.
   The enricher handles reconstruction automatically.
