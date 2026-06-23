# PaperTrail

**Every paper your team shares — found and mapped.**

PaperTrail automatically discovers papers shared across your Slack workspace, enriches them with metadata, computes LLM semantic embeddings, and builds an interactive visual dashboard with hierarchical topic clustering, AI-powered search, and full engagement metrics.

### Live Demos

- **Landing page** (lab picker): [papertrail-xi.vercel.app](https://papertrail-xi.vercel.app)
- Koo Lab Dashboard — [Vercel](https://papertrail-xi.vercel.app/koolab/) · [GitHub Pages](https://bschilder.github.io/PaperTrail/koolab/)
- Standard Model Bio Dashboard — [Vercel](https://papertrail-xi.vercel.app/standardmodelbio/) · [GitHub Pages](https://bschilder.github.io/PaperTrail/standardmodelbio/)

[Documentation](https://bschilder.github.io/PaperTrail) · [Report Bug](https://github.com/bschilder/PaperTrail/issues) · [Request Feature](https://github.com/bschilder/PaperTrail/issues)

---

## Features

### Interactive Dashboard

A self-contained HTML file — no server required.

- **Canvas scatter plot** with UMAP/t-SNE/PCA projections (hardware-accelerated)
- **Hierarchical topic clustering** — LLM-generated labels at 3 zoom levels
- **Topic connection lines** — configurable thickness, opacity, curve, color
- **8 color modes**: Cluster, Channel, Year, Citations, Engagement, Density, Contributor, Journal
- **Embedding-based semantic search** — cosine similarity on LLM vectors (BGE-small)
- **AI chatbot** — natural language queries with tool use (HuggingFace, Claude, OpenAI)
- **3D WebGL view**, sortable table, leaderboard, time travel animation
- **Smooth animations** — papers fade in/out on filter, timeline playback
- **Dark theme**, CSV/XLSX export, keyboard shortcuts, shareable URL state

### Backend Pipeline

- **Multi-strategy enrichment** — page scraping → OpenAlex → Crossref → bioRxiv API → Google fallback
- **LLM embeddings** — HuggingFace BGE-small (384d) for projections + client-side search
- **Hierarchical clustering** on UMAP projections with LLM-generated topic labels
- **Dead link detection**, junk title filtering, URL normalization
- **Automated weekly pipeline** via GitHub Actions → deploys to **both Vercel and GitHub Pages**

### Multi-Workspace Support

Run PaperTrail across multiple Slack workspaces from a single repo:

```
config/
├── koolab.yml              # Koo Lab workspace
├── standardmodelbio.yml    # Standard Model Bio workspace
└── yourlab.yml             # Add your own!
```

Each workspace gets its own data directory and dashboard, published at
`/<workspace>/` on both the Vercel app and GitHub Pages. A generated landing
page (`scripts/build_landing.py`) links to every workspace dashboard.

---

## Quickstart

### Option 1: Fork & Configure (Recommended)

1. **Fork** this repository
2. **Create** a Slack bot app ([guide](https://bschilder.github.io/PaperTrail/guide/dashboard/))
3. **Add** your config to `config/yourworkspace.yml`:
   ```yaml
   title: "PaperTrail — My Lab"
   slack_workspace_url: "https://mylab.slack.com"
   channels: {}  # empty = auto-discover all public channels
   embedding_backend: huggingface
   slack_token_secret: SLACK_BOT_TOKEN
   ```
4. **Set** GitHub secret: `gh secret set SLACK_BOT_TOKEN`
5. **Trigger**: `gh workflow run pipeline.yml`

Dashboard deploys to both `https://<project>.vercel.app/<workspace>/` and
`https://<user>.github.io/PaperTrail/<workspace>/`. For Vercel deployment, also
set the `VERCEL_TOKEN`, `VERCEL_ORG_ID`, and `VERCEL_PROJECT_ID` secrets (see
[Configuration → Deployment](https://bschilder.github.io/PaperTrail/getting-started/configuration/)).

### Option 2: CLI

```bash
pip install papertrail-lab[all]

# Full pipeline
papertrail run-pipeline -c config/myworkspace.yml -o build/myworkspace

# Or step by step
papertrail scrape --token $SLACK_BOT_TOKEN -c CHANNEL_ID -o raw.json
papertrail enrich raw.json -o enriched.json
papertrail embed enriched.json -o final.json
papertrail build final.json -o dashboard.html
```

---

## Architecture

```
Slack Workspaces (multiple)
      │
      ▼
┌─────────────┐    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│   Scraper    │───▶│   Enricher   │───▶│  Embeddings  │───▶│   Dashboard  │
│              │    │              │    │              │    │              │
│ - Slack API  │    │ - Page scrape│    │ - HuggingFace│    │ - UMAP map   │
│ - 30+ domains│    │ - OpenAlex   │    │ - OpenAI     │    │ - 3D view    │
│ - Reactions  │    │ - Crossref   │    │ - Local ONNX │    │ - Table      │
│ - Auto-join  │    │ - bioRxiv API│    │ - TF-IDF     │    │ - AI agent   │
│              │    │ - Dead links │    │ - 3-level     │    │ - Semantic   │
│              │    │ - Junk filter│    │   clustering  │    │   search     │
└─────────────┘    └──────────────┘    └──────────────┘    └──────────────┘
                                              │
                                    GitHub Actions (weekly cron)
                                              │
                                  ┌───────────┴───────────┐
                                  ▼                       ▼
                               Vercel               GitHub Pages
                          /koolab/  /standardmodelbio/  (+ lab-picker landing)
```

## Project Structure

```
PaperTrail/
├── config/                      # Per-workspace configurations
│   ├── koolab.yml
│   └── standardmodelbio.yml
├── data/                        # Per-workspace paper data
│   ├── koolab/papers_final.json
│   └── standardmodelbio/papers_final.json
├── papertrail/                  # Python package
│   ├── scraper.py               # Slack scraping + URL extraction
│   ├── enricher.py              # Metadata enrichment (OpenAlex + PubMed)
│   ├── enrich_cascade.py        # Multi-strategy enrichment cascade
│   ├── embeddings.py            # Embedding backends
│   ├── projections.py           # Projections + hierarchical clustering
│   ├── pipeline.py              # Automated pipeline runner
│   ├── preview.py               # Dashboard builder
│   ├── cli.py                   # CLI commands
│   └── templates/dashboard.html # Dashboard template (~10K lines)
├── .github/workflows/
│   ├── pipeline.yml             # Weekly pipeline + deploy (Vercel + GitHub Pages)
│   ├── docs.yml                 # Documentation deploy
│   └── ci.yml                   # Tests
├── scripts/
│   └── build_landing.py         # Generates the lab-picker landing page
├── docs/                        # MkDocs documentation
└── pyproject.toml               # Package config
```

## Development

```bash
git clone https://github.com/bschilder/PaperTrail.git
cd PaperTrail
pip install -e ".[all,dev]"
pytest
mkdocs serve
```

## License

MIT License. See [LICENSE](LICENSE).
