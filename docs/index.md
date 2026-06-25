# PaperTrail

**Every paper your team shares — found and mapped.**

PaperTrail automatically discovers papers shared across your Slack workspace, enriches them with metadata, computes semantic embeddings, and builds an interactive visual dashboard with hierarchical topic clustering, AI-powered search, and full engagement metrics.

### Live Demos

- **Landing page** (lab picker): [papertrail-portal.vercel.app](https://papertrail-portal.vercel.app)
- Koo Lab — [Vercel](https://papertrail-portal.vercel.app/koolab/) · [GitHub Pages](https://bschilder.github.io/PaperTrail/koolab/)
- Standard Model Bio — [Vercel](https://papertrail-portal.vercel.app/standardmodelbio/) · [GitHub Pages](https://bschilder.github.io/PaperTrail/standardmodelbio/)

- **GitHub**: [bschilder/PaperTrail](https://github.com/bschilder/PaperTrail)
- **PyPI**: [papertrail-lab](https://pypi.org/project/papertrail-lab/)
- **Author**: Brian Schilder, [Koo Lab](https://cshlgenomics.cshl.edu/), Cold Spring Harbor Laboratory

---

## Features

### Web App (Dashboard)

A self-contained HTML file — no server required. See the full [Dashboard Guide](guide/dashboard.md).

![Map View](images/map-view.png)

- **Canvas scatter plot** with UMAP/t-SNE/PCA projections and hardware-accelerated rendering
- **Hierarchical topic clustering** — LLM-generated labels at 3 zoom levels (7 → 15 → 35 topics)
- **Topic connection lines** — configurable thickness, opacity, curve, and color
- **8 color modes**: Cluster, Channel, Year, Citations, Engagement, Density, Contributor, Journal
- **Smooth animations** — papers fade in/out when filtering, timeline playback with gradual dot appearance
- **3D WebGL view** powered by Three.js
- **Sortable table** with column filters, CSV/XLSX export, Slack message links
- **Leaderboard** — top contributors, most cited, most engaged
- **AI chatbot** — natural language search with tool use (HuggingFace, Claude, OpenAI)
- **Semantic search** — content-based similarity ranking
- **Time travel** — chronological animation with smooth fade-in
- **KDE density background** with 7 color palettes
- **Lasso & rectangle selection**
- **URL hash state** for shareable views
- **Dark theme** optimized for readability

### Backend (Python Pipeline)

A four-step CLI pipeline. See individual guides: [Scraping](guide/scraping.md) · [Enriching](guide/enriching.md) · [Embeddings](guide/embeddings.md) · [Dashboard](guide/dashboard.md)

```
Slack Workspace
      │
      ▼
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Scraper    │───▶│   Enricher   │───▶│  Embeddings  │───▶│   Preview    │
│              │    │              │    │              │    │              │
│ - Slack API  │    │ - Page scrape│    │ - TF-IDF/SVD │    │ - Map view   │
│ - 30+ domains│    │ - OpenAlex   │    │ - OpenAI     │    │ - 3D view    │
│ - Reactions  │    │ - Crossref   │    │ - HuggingFace│    │ - Table      │
│ - Replies    │    │ - bioRxiv API│    │ - Local ONNX │    │ - AI agent   │
└─────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
```

- **Multi-strategy enrichment cascade** — page scraping → DOI lookup (OpenAlex, Crossref) → bioRxiv/medRxiv API → title search → Google fallback. Handles Nature, arXiv, Cell, Science, OpenReview, and 30+ domains.
- **Junk title rejection** — automatically filters out erratum, corrigendum, correspondence, and site boilerplate
- **Dead link detection** — removes papers with 404/error pages
- **Hierarchical clustering on UMAP projections** — 3 levels with LLM-generated labels (HF → OpenAI fallback)
- **Automated weekly pipeline** via GitHub Actions — scrape, enrich, embed, build, deploy to **both Vercel and GitHub Pages**

---

## Quick Start

### Option 1: Automated (Fork & Configure)

1. **Fork** this repository
2. **Edit** `config.yml` with your Slack channels
3. **Add** `SLACK_BOT_TOKEN` as a GitHub Actions secret
4. *(Optional)* Add `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID` secrets to also deploy to Vercel
5. The pipeline runs weekly (Sunday 2am UTC) and deploys to Vercel + GitHub Pages

See [Configuration → Deployment](getting-started/configuration.md#deployment) for details.

### Option 2: CLI

```bash
# Install
pip install papertrail-lab[all]

# Run the full pipeline
papertrail run-pipeline -c config.yml -o build

# Or step by step:
papertrail scrape --token $SLACK_BOT_TOKEN -c CHANNEL_ID -o raw.json
papertrail enrich raw.json -o enriched.json
papertrail embed enriched.json -o final.json
papertrail build final.json -o dashboard.html
```

### Option 3: Python API

```python
from papertrail.pipeline import run_pipeline

run_pipeline(config_path="config.yml", output_dir="build")
```

---

## Configuration

Edit `config.yml` to set up your instance:

```yaml
title: "PaperTrail — My Lab"
slack_workspace_url: "https://mylab.slack.com"

channels:
  papers-dl: C0123Q7PGGP
  general: CP40S009F

embedding_backend: tfidf  # or openai, huggingface
openalex_email: "user@example.com"
schedule: "0 2 * * 0"  # Weekly Sunday 2am UTC
```

---

## Next Steps

- **[Dashboard Guide](guide/dashboard.md)** — Full walkthrough of all UI features
- **[Installation](getting-started/installation.md)** — Detailed setup
- **[Scraping Guide](guide/scraping.md)** — Slack integration details
- **[Enrichment Guide](guide/enriching.md)** — Metadata resolution strategies
- **[Embeddings Guide](guide/embeddings.md)** — Backend comparison
- **[API Reference](api/scraper.md)** — Python API docs
- **[Koo Lab Example](examples/koo-lab.md)** — Real-world deployment
- **[Contributing](contributing.md)** — Development setup

---

## License

MIT License. See [LICENSE](https://github.com/bschilder/PaperTrail/blob/main/LICENSE).
