# PaperTrail

**Scrape, enrich, embed, and visualize papers shared in Slack.**

PaperTrail automatically discovers papers shared across your Slack workspace, enriches them with metadata from Semantic Scholar and OpenAlex, computes semantic embeddings, and serves an interactive dashboard with table view, 2D embedding map, and semantic search.

[Documentation](https://bschilder.github.io/PaperTrail) · [Report Bug](https://github.com/bschilder/PaperTrail/issues) · [Request Feature](https://github.com/bschilder/PaperTrail/issues)

---

## Features

- **Slack Scraping** — Finds papers across all channels by detecting DOI, arXiv, bioRxiv, PubMed, and other scholarly URLs. Tracks engagement (reactions + thread replies).
- **Metadata Enrichment** — Fetches title, authors, abstract, journal, year, and institutions from Semantic Scholar and OpenAlex.
- **LLM Embeddings** — Generates semantic embeddings via OpenAI, HuggingFace Inference API, or local ONNX models (fastembed). Stored in a FAISS vector database for fast similarity search.
- **Interactive Dashboard** — Self-contained HTML file with sortable table, d3.js scatter plot (UMAP/t-SNE/PCA), color-by-cluster/channel/user/date, detail panel, and chat with autocomplete.
- **CLI Pipeline** — Four-step pipeline: `scrape → enrich → embed → build`.

## Quickstart

### Install

```bash
pip install papertrail-lab[all]
```

Or install with a specific embedding backend:

```bash
pip install papertrail-lab[openai]    # OpenAI embeddings (recommended)
pip install papertrail-lab[huggingface]  # HuggingFace Inference API
pip install papertrail-lab[local]     # Local ONNX (no API key needed)
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

# Step 3: Compute embeddings, projections, clusters, and FAISS index
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
│ - Slack API  │    │ - Semantic   │    │ - OpenAI     │    │ - Table view │
│ - URL detect │    │   Scholar    │    │ - HuggingFace│    │ - Map view   │
│ - Engagement │    │ - OpenAlex   │    │ - Local ONNX │    │ - Chat       │
│   metrics    │    │              │    │ - FAISS store│    │ - Detail     │
└─────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

## Embedding Backends

| Backend | Model | Dimensions | Speed | Quality | API Key Required |
|---------|-------|-----------|-------|---------|-----------------|
| **OpenAI** (default) | `text-embedding-3-small` | 1536 | Fast | Excellent | Yes (`OPENAI_API_KEY`) |
| **HuggingFace** | `BAAI/bge-small-en-v1.5` | 384 | Fast | Very Good | Optional (`HF_TOKEN`) |
| **Local** | `BAAI/bge-small-en-v1.5` | 384 | Medium | Very Good | No |

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
