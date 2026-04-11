# PaperTrail

**Every paper your team shares — found and mapped.**

PaperTrail automatically discovers papers shared across your Slack workspace, enriches them with metadata from OpenAlex and PubMed, computes semantic embeddings, and serves an interactive CellXGene-style dashboard with a canvas-based 2D embedding map, sortable table, and AI-powered chatbot search.

### [Live Demo: Koo Lab Dashboard](https://bschilder.github.io/PaperTrail/koolab/)

[Documentation](https://bschilder.github.io/PaperTrail) · [Report Bug](https://github.com/bschilder/PaperTrail/issues) · [Request Feature](https://github.com/bschilder/PaperTrail/issues)

---

## Features

- **Slack Scraping** — Finds papers across all configured channels by detecting DOI, arXiv, bioRxiv, PubMed, Nature, Cell, Science, OpenReview, and 30+ other scholarly URL patterns. Tracks engagement (reactions + thread replies).
- **Multi-Strategy Metadata Enrichment** — Cascading resolution pipeline: extract identifiers from URLs, batch OpenAlex lookup, individual OpenAlex/PubMed fallback, web search, and URL-based fallbacks. Handles tricky Elsevier/Cell PIIs via PubMed E-utilities.
- **Semantic Embeddings** — Generates embeddings via OpenAI, HuggingFace Inference API, local ONNX models (fastembed), or TF-IDF + SVD fallback (no API key needed).
- **Interactive Dashboard** — Self-contained HTML file with canvas-based scatter plot (UMAP/t-SNE/PCA), lasso and rectangle selection, zoom/pan, color-by-cluster/channel/user/date/year/citations, sortable table view, AI chatbot with Claude API integration, and inline detail panel.
- **CLI Pipeline** — Four-step pipeline: `scrape → enrich → embed → build`.

## Dashboard

The dashboard is a single self-contained HTML file that works offline. It includes:

- **Canvas scatter plot** with hardware-accelerated rendering for 1,000+ papers
- **Three projection methods**: UMAP (default), t-SNE, PCA — toggle in real time
- **Six color modes**: Cluster, Channel, User, Date, Year, Citations
- **Lasso & rectangle selection** with inline paper list in the sidebar
- **"Select Top N" slider** for quick filtering by citation count or relevance
- **Sortable/filterable table view** with all metadata columns
- **AI chatbot** (optional) powered by Claude API with `search_papers` tool use
- **Export to Excel** with one click
- **Dark theme** optimized for readability

Data is base64-encoded and embedded directly in the HTML — no server needed.

## Quickstart

### Install

```bash
pip install papertrail-lab[all]
```

Or install with a specific embedding backend:

```bash
pip install papertrail-lab[openai]      # OpenAI embeddings (recommended)
pip install papertrail-lab[huggingface] # HuggingFace Inference API
pip install papertrail-lab[local]       # Local ONNX (no API key needed)
```

### Configure

```bash
export SLACK_BOT_TOKEN="xoxb-your-token-here"
export OPENAI_API_KEY="sk-..."  # for OpenAI embeddings (default)
# OR
export HF_TOKEN="hf_..."  # for HuggingFace embeddings
```

### Run the Pipeline

```bash
# Step 1: Scrape papers from Slack
papertrail scrape -o papers_raw.json

# Step 2: Enrich with metadata
papertrail enrich papers_raw.json -o papers_enriched.json

# Step 3: Compute embeddings, projections, clusters
papertrail embed papers_enriched.json -o papers_final.json --backend openai

# Step 4: Build the interactive dashboard
papertrail build papers_final.json -o dashboard.html
```

### Search Papers

```bash
papertrail search -q "transformer attention mechanisms" -k 5
```

## Architecture

```
Slack Workspace
      │
      ▼
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Scraper    │───▶│   Enricher   │───▶│  Embeddings  │───▶│   Preview    │
│              │    │              │    │              │    │              │
│ - Slack API  │    │ - OpenAlex   │    │ - OpenAI     │    │ - Canvas map │
│ - URL detect │    │ - PubMed     │    │ - HuggingFace│    │ - Table view │
│ - Engagement │    │ - Web search │    │ - Local ONNX │    │ - AI chatbot │
│   metrics    │    │ - Fallbacks  │    │ - TF-IDF/SVD │    │ - Selection  │
└─────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

## Metadata Enrichment Cascade

PaperTrail resolves paper metadata using a multi-strategy pipeline (see `skills/paper-metadata-scraper/SKILL.md` for full details):

1. **Extract identifiers** from URL — DOIs, arXiv IDs, Elsevier PIIs, PMC IDs, OpenReview IDs
2. **Batch OpenAlex lookup** — resolves up to 40 DOIs per request (fastest path)
3. **Individual OpenAlex lookup** — DOI, arXiv DOI, or PMC ID
4. **PubMed E-utilities** — best for Elsevier/Cell PIIs that other APIs can't handle
5. **Web search fallback** — for OpenReview, conference proceedings, etc.
6. **URL-based fallback** — generates readable titles from URL structure

All APIs are free and require no API keys. Adding a contact email to the User-Agent header gives access to OpenAlex's polite pool (10 req/s vs 1 req/s).

## Embedding Backends

| Backend | Model | Dimensions | Speed | Quality | API Key Required |
|---------|-------|-----------|-------|---------|-----------------|
| **OpenAI** (default) | `text-embedding-3-small` | 1536 | Fast | Excellent | Yes (`OPENAI_API_KEY`) |
| **HuggingFace** | `BAAI/bge-small-en-v1.5` | 384 | Fast | Very Good | Optional (`HF_TOKEN`) |
| **Local** | `BAAI/bge-small-en-v1.5` | 384 | Medium | Very Good | No |
| **TF-IDF + SVD** | N/A | 128 | Fast | Good | No |

The embedding backend is auto-detected based on available API keys. Override with `--backend`.

## FAISS Vector Store

Embeddings are stored in a FAISS index for sub-millisecond similarity search:

```python
from papertrail.embeddings import VectorStore

store = VectorStore()
store.load("faiss_index/")
results = store.search_text("single cell RNA sequencing", top_k=5)
for r in results:
    print(f"[{r['score']:.3f}] {r['title']}")
```

## Project Structure

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
│       └── dashboard.html       # Dashboard HTML template ({{DATA_B64}} placeholder)
├── skills/                      # Claude Code / Cowork skill files
│   ├── papertrail-pipeline/     # Full pipeline skill
│   │   └── SKILL.md
│   └── paper-metadata-scraper/  # Metadata resolution cascade skill
│       └── SKILL.md
├── docs/                        # MkDocs documentation
├── tests/                       # Unit tests
├── pyproject.toml               # Package config and dependencies
└── papertrail_dashboard.html    # Pre-built dashboard (Koo Lab, 1,072 papers)
```

## Development

```bash
git clone https://github.com/bschilder/PaperTrail.git
cd PaperTrail
pip install -e ".[dev]"

# Run tests
pytest

# Serve docs locally
mkdocs serve
```

## License

MIT License. See [LICENSE](LICENSE).
