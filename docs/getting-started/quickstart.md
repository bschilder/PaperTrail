# Quick Start

Get PaperTrail running in 5 minutes!

## Prerequisites

- Python 3.9+
- [Installed PaperTrail](installation.md)
- [Configured API tokens](configuration.md)

## Step 1: Verify Setup

Make sure your credentials are available:

```bash
# Check Slack token
echo $SLACK_BOT_TOKEN

# Check embedding backend token (OpenAI or HuggingFace)
echo $OPENAI_API_KEY  # or
echo $HF_TOKEN
```

If either is missing, see [Configuration](configuration.md).

## Step 2: Scrape Papers from Slack

Download all papers shared in your Slack workspace:

```bash
papertrail scrape -o papers_raw.json
```

This will:
- Connect to your Slack workspace
- Scan all channels for paper links (DOI, arXiv, bioRxiv, PubMed, etc.)
- Track engagement (reactions, thread replies, etc.)
- Save results to `papers_raw.json`

**Output:** A JSON file with ~20 fields per paper including URL, channel, user, timestamp, and engagement metrics.

**Tips:**
- First run may take a while if you have many channels
- Add `-v` for verbose output to see progress
- Use `--channels channel1 channel2` to limit to specific channels

## Step 3: Enrich with Metadata

Fetch rich metadata from Semantic Scholar and OpenAlex:

```bash
papertrail enrich papers_raw.json -o papers_enriched.json
```

This will:
- Look up each paper by DOI or URL
- Fetch title, authors, abstract, journal, year, citations
- Get institutional affiliations
- Handle missing metadata gracefully

**Output:** Enriched JSON with metadata for searchable/displayable fields.

**Tips:**
- This step is cached, so re-running is fast
- Enrichment APIs are free and have generous rate limits

## Step 4: Compute Embeddings

Generate semantic embeddings and 2D projections:

```bash
papertrail embed papers_enriched.json -o papers_final.json --backend openai
```

This will:
- Embed paper abstracts using your chosen backend
- Compute UMAP/t-SNE/PCA 2D projections
- Cluster papers using k-means
- Build a FAISS index for fast similarity search

**Output:** Complete dataset with embeddings, projections, and clusters.

**Available backends:**

=== "OpenAI (recommended)"
    ```bash
    papertrail embed papers_enriched.json -o papers_final.json --backend openai
    ```

    Uses `text-embedding-3-small` (1536 dimensions).

=== "HuggingFace"
    ```bash
    papertrail embed papers_enriched.json -o papers_final.json --backend huggingface
    ```

    Uses `BAAI/bge-small-en-v1.5` (384 dimensions).

=== "Local"
    ```bash
    papertrail embed papers_enriched.json -o papers_final.json --backend local
    ```

    Uses local fastembed (no API keys).

**Tips:**
- First run downloads models (may be slow)
- Subsequent runs are much faster (models cached)
- Embedding takes 10-30s depending on paper count and backend

## Step 5: Build the Dashboard

Create an interactive HTML dashboard:

```bash
papertrail build papers_final.json -o dashboard.html
```

This will:
- Generate a self-contained HTML file
- Include table view with all papers
- Add d3.js scatter plot with 2D embedding map
- Build search index and FAISS embeddings
- Create semantic search chat interface

**Output:** A single `dashboard.html` file. No server needed!

## Step 6: Explore

Open the dashboard in your browser:

```bash
# macOS
open dashboard.html

# Linux
xdg-open dashboard.html

# Windows
start dashboard.html

# Or just double-click it in your file explorer
```

You'll see:

- **Table View** — Sortable columns for title, authors, year, journal, etc.
- **Embedding Map** — 2D scatter plot of all papers (hover for details)
- **Color by** — Switch between cluster, channel, user, date
- **Projections** — Toggle between UMAP, t-SNE, PCA
- **Semantic Search** — Type a query to find similar papers
- **Detail Panel** — Click a paper to see full metadata

## Complete Pipeline

Run the entire pipeline at once:

```bash
papertrail scrape -o papers_raw.json && \
papertrail enrich papers_raw.json -o papers_enriched.json && \
papertrail embed papers_enriched.json -o papers_final.json --backend openai && \
papertrail build papers_final.json -o dashboard.html
```

Then open `dashboard.html` in your browser!

## Next Steps

- **[User Guide](../guide/scraping.md)** — In-depth documentation for each step
- **[API Reference](../api/scraper.md)** — Python API for custom workflows
- **[Troubleshooting](#troubleshooting)** — Resolve common issues

## Troubleshooting

### Error: `SLACK_BOT_TOKEN not found`

Set your Slack token:

```bash
export SLACK_BOT_TOKEN="xoxb-..."
```

See [Configuration](configuration.md) for details.

### Error: `No papers found`

Check that:
- Your Slack token is valid
- Your bot has permission to read channels
- Papers have been shared in your workspace (check a channel manually)
- Try limiting to a specific channel: `papertrail scrape --channels general`

### Error: `Embedding failed`

Check:
- Your embedding backend token is set (`OPENAI_API_KEY` or `HF_TOKEN`)
- You have internet connection
- API rate limits aren't exceeded (try adding `--delay 1.0`)
- Local backend doesn't require any keys: `--backend local`

### Error: `Build failed`

Check:
- Input file `papers_final.json` exists and is valid
- You have write permission in the output directory
- Disk has enough space for HTML file

### Papers are missing

If you expect more papers, check:
- Bot can read all channels (not just public ones)
- Bot was added to private channels
- Papers have recognizable URLs (DOI, arXiv, bioRxiv, PubMed)
- Check scraper output with `--verbose` flag

## FAQ

**Q: Do I need an API key for everything?**

A: Only for Slack (required) and embedding backend (optional if using local). Metadata enrichment APIs are free.

**Q: Can I re-run just one step?**

A: Yes! You can scrape, enrich, and embed separately, or skip steps.

**Q: Can I customize the dashboard?**

A: The HTML is self-contained, so you can edit it. See [Building the Dashboard](../guide/dashboard.md) for details.

**Q: How do I update with new papers?**

A: Re-run the full pipeline. PaperTrail handles duplicates automatically.

**Q: Can I use this without Slack?**

A: Not currently, but you can manually create a JSON file matching the scraper output format and enrich/embed from there.

## Getting Help

- Check [GitHub Issues](https://github.com/bschilder/PaperTrail/issues)
- See [Configuration](configuration.md) for setup issues
- Read [Troubleshooting](#troubleshooting) above
- [Open an issue](https://github.com/bschilder/PaperTrail/issues/new) with details
