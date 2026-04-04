# Data API

The data module downloads and manages pre-scraped paper datasets from
PaperTrail GitHub Releases. This lets you skip the Slack scraping step
and jump straight to enrichment, embedding, or analysis.

## Quick Example

```python
from papertrail.data import download_release, load_papers, list_releases

# See what's available
for r in list_releases():
    print(r["tag"], r["date"], len(r["assets"]), "assets")

# Download the latest release (auto-detected)
data_dir = download_release()
# → ~/.papertrail/data/v0.1.0-data-2026-04-04/

# Load papers
papers = load_papers()
print(f"{len(papers)} papers loaded")

# Load a specific dataset
enriched = load_papers(which="enriched")
scrapes = load_papers(which="scrapes")  # dict of {filename: data}
```

## Functions

::: papertrail.data.list_releases
    options:
      show_root_heading: true
      heading_level: 3

::: papertrail.data.get_latest_release
    options:
      show_root_heading: true
      heading_level: 3

::: papertrail.data.download_release
    options:
      show_root_heading: true
      heading_level: 3

::: papertrail.data.load_papers
    options:
      show_root_heading: true
      heading_level: 3

::: papertrail.data.data_summary
    options:
      show_root_heading: true
      heading_level: 3

## Datasets

Each release may contain these assets:

| Asset | `which=` | Description |
|---|---|---|
| `all_papers_merged.json.gz` | `"merged"` | Deduplicated papers from all channels with extracted IDs |
| `enrich_checkpoint.json.gz` | `"enriched"` | Papers with metadata from OpenAlex + Semantic Scholar |
| `papers_enriched.json.gz` | `"enriched"` | Fully enriched papers (preferred over checkpoint) |
| `papers_final.json.gz` | `"final"` | Papers with embeddings, projections, and clusters |
| `channel_scrapes.tar.gz` | `"scrapes"` | Per-channel raw Slack scrapes (extracted to individual JSON files) |

## Storage

Downloaded files are stored at `~/.papertrail/data/{tag}/`. Each release
gets its own subdirectory, so multiple snapshots can coexist.

Compressed files (`.json.gz`, `.tar.gz`) are automatically decompressed
after download. The originals are kept alongside the decompressed versions.

## Authentication

Public repositories don't require authentication. For private repos or to
avoid rate limits, set `GITHUB_TOKEN` or `GH_TOKEN`:

```bash
export GITHUB_TOKEN="ghp_..."
```

## CLI Usage

```bash
# Download latest data
papertrail download

# Download specific release
papertrail download --tag v0.1.0-data-2026-04-04

# Download to custom directory
papertrail download --data-dir ./my_data

# List available releases
papertrail releases
```
