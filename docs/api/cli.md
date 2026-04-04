# CLI Reference

The `papertrail` command-line interface provides the main entry point for all PaperTrail operations.

## Commands

### scrape

Scrape papers from your Slack workspace.

```bash
papertrail scrape [OPTIONS]
```

**Options:**

- `-o, --output TEXT` — Output file path (default: `papers_raw.json`)
- `-c, --channels TEXT` — Specific channels to scrape (space-separated)
- `--exclude TEXT` — Channels to exclude (space-separated)
- `-d, --days INTEGER` — Only scrape last N days
- `--after DATE` — Only scrape papers after this date (YYYY-MM-DD)
- `--before DATE` — Only scrape papers before this date (YYYY-MM-DD)
- `--min-engagement INTEGER` — Minimum engagement threshold
- `--delay FLOAT` — Delay between API requests (seconds)
- `--batch-size INTEGER` — Batch size for processing
- `--checkpoint FILE` — Save/resume from checkpoint
- `--dry-run` — Preview without downloading
- `-v, --verbose` — Verbose output
- `--format TEXT` — Output format (json, csv)
- `--help` — Show help message

**Example:**

```bash
papertrail scrape -o papers.json -c general papers --days 30 -v
```

### enrich

Enrich papers with metadata from Semantic Scholar and OpenAlex.

```bash
papertrail enrich INPUT_FILE [OPTIONS]
```

**Arguments:**

- `INPUT_FILE` — Input JSON file from scraper

**Options:**

- `-o, --output TEXT` — Output file path (default: `papers_enriched.json`)
- `--batch-size INTEGER` — Batch size for API requests (default: 10)
- `--delay FLOAT` — Delay between requests (seconds)
- `--no-cache` — Ignore cache and re-enrich
- `--require-identifier` — Skip papers without DOI/arXiv ID
- `--fields TEXT` — Only enrich specific fields (comma-separated)
- `--dry-run` — Preview without saving
- `-v, --verbose` — Verbose output
- `--help` — Show help message

**Example:**

```bash
papertrail enrich papers_raw.json -o papers_enriched.json --batch-size 20 --delay 0.5 -v
```

### embed

Compute embeddings, projections, clusters, and FAISS index.

```bash
papertrail embed INPUT_FILE [OPTIONS]
```

**Arguments:**

- `INPUT_FILE` — Input JSON file from enricher

**Options:**

- `-o, --output TEXT` — Output file path (default: `papers_final.json`)
- `--backend TEXT` — Embedding backend (openai, huggingface, local; default: auto-detect)
- `--batch-size INTEGER` — Batch size for embedding (default: 32)
- `--delay FLOAT` — Delay between requests (seconds)
- `--n-clusters INTEGER` — Number of k-means clusters (default: 5)
- `-p, --projections TEXT` — Projections to compute (comma-separated: umap,tsne,pca; default: all)
- `--text-fields TEXT` — Text fields to embed (default: abstract,title)
- `--faiss-path TEXT` — Save FAISS index to this directory
- `--no-cache` — Don't use cached models
- `--dry-run` — Preview without saving
- `-v, --verbose` — Verbose output
- `--help` — Show help message

**Example:**

```bash
papertrail embed papers_enriched.json -o papers_final.json --backend openai --n-clusters 8 -p umap,tsne
```

### build

Build an interactive HTML dashboard.

```bash
papertrail build INPUT_FILE [OPTIONS]
```

**Arguments:**

- `INPUT_FILE` — Input JSON file with embeddings

**Options:**

- `-o, --output TEXT` — Output HTML file (default: `dashboard.html`)
- `--title TEXT` — Dashboard title
- `--description TEXT` — Dashboard description
- `--default-coloring TEXT` — Default color scheme (cluster, channel, user, date, year, citations)
- `--default-projection TEXT` — Default projection (umap, tsne, pca)
- `--primary-color TEXT` — Primary color (hex code)
- `--accent-color TEXT` — Accent color (hex code)
- `--extra-fields TEXT` — Extra metadata fields to display
- `--compress` — Compress data for smaller file size
- `--template TEXT` — Custom HTML template
- `--faiss-path TEXT` — Path to FAISS index
- `-v, --verbose` — Verbose output
- `--help` — Show help message

**Example:**

```bash
papertrail build papers_final.json -o dashboard.html --title "My Papers" --default-coloring cluster --default-projection umap
```

### search

Search papers by semantic similarity.

```bash
papertrail search [OPTIONS]
```

**Options:**

- `-q, --query TEXT` — Search query (required)
- `-k, --top-k INTEGER` — Number of results (default: 5)
- `--papers FILE` — Papers JSON file (default: `papers_final.json`)
- `--faiss-path TEXT` — FAISS index directory
- `--backend TEXT` — Embedding backend (auto-detect by default)
- `--field TEXT` — Search field (default: abstract,title)
- `--min-score FLOAT` — Minimum similarity score
- `--exclude TEXT` — Exclude channels
- `--cluster INTEGER` — Filter by cluster
- `--after DATE` — Only papers after this date
- `--before DATE` — Only papers before this date
- `--format TEXT` — Output format (text, json, csv; default: text)
- `-v, --verbose` — Verbose output
- `--help` — Show help message

**Example:**

```bash
papertrail search -q "transformer attention mechanisms" -k 10 --format json
```

## Global Options

These options work with all commands:

- `--help` — Show help message and exit
- `--version` — Show version and exit
- `-q, --quiet` — Suppress output
- `-v, --verbose` — Verbose output

## Environment Variables

PaperTrail uses these environment variables:

| Variable | Purpose | Example |
|----------|---------|---------|
| `SLACK_BOT_TOKEN` | Slack API token (required) | `xoxb-...` |
| `OPENAI_API_KEY` | OpenAI API key (for OpenAI embeddings) | `sk-...` |
| `HF_TOKEN` | HuggingFace API token (for HuggingFace embeddings) | `hf_...` |

## Exit Codes

- `0` — Success
- `1` — General error
- `2` — Configuration error (missing tokens, invalid input)
- `3` — API error (Slack, OpenAI, HuggingFace)
- `4` — File error (can't read/write files)

## Examples

### Complete Pipeline

```bash
# Set environment variables
export SLACK_BOT_TOKEN="xoxb-your-token"
export OPENAI_API_KEY="sk-your-key"

# Run full pipeline
papertrail scrape -o papers_raw.json && \
papertrail enrich papers_raw.json -o papers_enriched.json && \
papertrail embed papers_enriched.json -o papers_final.json && \
papertrail build papers_final.json -o dashboard.html

# Open dashboard
open dashboard.html
```

### Scrape Specific Channels

```bash
papertrail scrape -c papers-ml papers-bio papers-physics -o papers.json -v
```

### Enrich with Custom Rate Limiting

```bash
papertrail enrich papers_raw.json -o enriched.json --delay 1.0 --batch-size 5
```

### Embed with Local Backend

```bash
papertrail embed papers_enriched.json -o final.json --backend local --n-clusters 10
```

### Search with Multiple Options

```bash
papertrail search -q "deep learning" -k 20 --min-score 0.7 --format csv
```

## Tips

- Use `--dry-run` to preview operations without making changes
- Use `--verbose` (-v) to see detailed progress
- Redirect output: `papertrail scrape -o papers.json 2>&1 | tee output.log`
- Chain commands with `&&` to stop on first error
- Use quotes for arguments with spaces: `--title "My Paper Collection"`
