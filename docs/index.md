# PaperTrail

**Every paper your team shares — found and mapped.**

PaperTrail automatically discovers papers shared across your Slack workspace, enriches them with metadata from Semantic Scholar and OpenAlex, computes semantic embeddings, and serves an interactive dashboard with table view, 2D embedding map, and semantic search.

- **GitHub**: [bschilder/PaperTrail](https://github.com/bschilder/PaperTrail)
- **PyPI**: [papertrail-lab](https://pypi.org/project/papertrail-lab/)
- **Author**: Brian Schilder, [Koo Lab](https://cshlgenomics.cshl.edu/), Cold Spring Harbor Laboratory

---

## Features

PaperTrail provides a complete end-to-end pipeline for paper discovery and analysis:

- **Slack Scraping** — Automatically detects papers from shared links (DOI, arXiv, bioRxiv, PubMed, and other scholarly URLs) across all channels. Tracks engagement metrics like reactions and thread replies.

- **Metadata Enrichment** — Fetches rich metadata including title, authors, abstract, journal, year, and affiliated institutions from Semantic Scholar and OpenAlex APIs.

- **LLM Embeddings** — Generates high-quality semantic embeddings via OpenAI (default), HuggingFace Inference API, or local ONNX models. Stored in a FAISS vector database for sub-millisecond similarity search.

- **Interactive Dashboard** — Self-contained HTML file with sortable table, d3.js scatter plot (UMAP/t-SNE/PCA projections), color-by filters (cluster/channel/user/date), detail panel, and semantic search chat with autocomplete.

- **CLI Pipeline** — Simple four-step workflow: `scrape → enrich → embed → build`.

---

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

---

## Embedding Backends

PaperTrail supports multiple embedding backends. Choose based on your needs:

| Backend | Model | Dimensions | Speed | Quality | API Key |
|---------|-------|-----------|-------|---------|---------|
| **OpenAI** (default) | `text-embedding-3-small` | 1536 | Fast | Excellent | `OPENAI_API_KEY` |
| **HuggingFace** | `BAAI/bge-small-en-v1.5` | 384 | Fast | Very Good | `HF_TOKEN` (optional) |
| **Local** | `BAAI/bge-small-en-v1.5` | 384 | Medium | Very Good | None required |

The embedding backend is auto-detected based on available API keys. You can also override it explicitly with the `--backend` flag.

---

## Quick Start

### 1. Install

=== "With OpenAI embeddings (recommended)"
    ```bash
    pip install papertrail-lab[openai]
    ```

=== "With HuggingFace embeddings"
    ```bash
    pip install papertrail-lab[huggingface]
    ```

=== "With local embeddings (no API keys)"
    ```bash
    pip install papertrail-lab[local]
    ```

=== "With all backends"
    ```bash
    pip install papertrail-lab[all]
    ```

### 2. Configure

Set your API tokens as environment variables:

=== "OpenAI"
    ```bash
    export SLACK_BOT_TOKEN="xoxb-your-token-here"
    export OPENAI_API_KEY="sk-..."
    ```

=== "HuggingFace"
    ```bash
    export SLACK_BOT_TOKEN="xoxb-your-token-here"
    export HF_TOKEN="hf_..."
    ```

=== "Local (no API keys needed)"
    ```bash
    export SLACK_BOT_TOKEN="xoxb-your-token-here"
    ```

### 3. Run the Pipeline

```bash
# Step 1: Scrape papers from Slack
papertrail scrape -o papers_raw.json

# Step 2: Enrich with metadata
papertrail enrich papers_raw.json -o papers_enriched.json

# Step 3: Compute embeddings and projections
papertrail embed papers_enriched.json -o papers_final.json --backend openai

# Step 4: Build the interactive dashboard
papertrail build papers_final.json -o dashboard.html
```

Then open `dashboard.html` in your browser to explore your papers!

### 4. Search Papers

```bash
papertrail search -q "transformer attention mechanisms" -k 5
```

---

## Next Steps

- **[Installation Guide](getting-started/installation.md)** — Detailed setup instructions
- **[Configuration](getting-started/configuration.md)** — API tokens and environment setup
- **[Quick Start](getting-started/quickstart.md)** — Step-by-step walkthrough
- **[User Guide](guide/scraping.md)** — In-depth usage documentation
- **[API Reference](api/scraper.md)** — Python API documentation
- **[Koo Lab Demo](examples/koo-lab.md)** — Real-world example and use case

---

## Development

Interested in contributing? Set up the development environment:

```bash
git clone https://github.com/bschilder/PaperTrail.git
cd PaperTrail
pip install -e ".[dev]"

# Run tests
pytest

# Serve docs locally
mkdocs serve
```

See [Contributing](contributing.md) for more information.

---

## License

MIT License. See [LICENSE](https://github.com/bschilder/PaperTrail/blob/main/LICENSE) for details.
