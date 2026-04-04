# Scraping Papers

The scraper discovers papers shared in your Slack workspace by detecting scholarly URLs and tracking engagement metrics.

## How It Works

The scraper:

1. **Connects to Slack** via the Bot API using your `SLACK_BOT_TOKEN`
2. **Scans all channels** for paper-like URLs
3. **Detects paper sources**: DOI, arXiv, bioRxiv, medRxiv, PubMed, IEEE Xplore, SSRN, etc.
4. **Extracts URLs** and parses identifiers (DOI, arXiv ID, PubMed ID, etc.)
5. **Tracks engagement**: Reactions, thread replies, user mentions
6. **Exports JSON** with ~20 fields per paper

## Basic Usage

### Scrape All Papers

```bash
papertrail scrape -o papers_raw.json
```

This scans all channels your bot can access and exports to `papers_raw.json`.

### Scrape Specific Channels

Limit to one or more channels:

```bash
papertrail scrape --channels general papers science -o papers_raw.json
```

### Dry Run

Preview what will be scraped without downloading:

```bash
papertrail scrape --dry-run
```

### Verbose Output

See detailed progress:

```bash
papertrail scrape -v -o papers_raw.json
```

## Output Format

The JSON file contains papers with the following structure:

```json
{
  "papers": [
    {
      "doi": "10.1038/nature12373",
      "url": "https://doi.org/10.1038/nature12373",
      "arxiv_id": null,
      "biorxiv_id": null,
      "source_type": "doi",
      "title": null,
      "authors": [],
      "abstract": null,
      "journal": null,
      "year": null,
      "channel": "general",
      "user": "U123456",
      "timestamp": 1234567890,
      "message_permalink": "https://myworkspace.slack.com/archives/C123456/p1234567890",
      "reactions": {"thumbsup": 2, "heart": 1},
      "thread_replies": 3,
      "thread_reply_users": ["U123456", "U234567"],
      "engagement_score": 0.85
    }
  ],
  "metadata": {
    "workspace": "my-workspace",
    "bot_user_id": "U7XXXXXXX",
    "scanned_channels": 45,
    "papers_found": 342,
    "timestamp": 1234567890
  }
}
```

### Fields Explained

| Field | Type | Description |
|-------|------|-------------|
| `doi` | string | Digital Object Identifier (e.g., `10.1038/nature12373`) |
| `url` | string | Full URL to the paper |
| `arxiv_id` | string | arXiv identifier (e.g., `2301.12345`) |
| `biorxiv_id` | string | bioRxiv identifier (e.g., `2023.01.23.525139`) |
| `source_type` | string | Where the URL came from: `doi`, `arxiv`, `biorxiv`, `pubmed`, etc. |
| `title` | string | Paper title (populated by enricher, null initially) |
| `authors` | array | Paper authors (populated by enricher, empty initially) |
| `abstract` | string | Paper abstract (populated by enricher, null initially) |
| `journal` | string | Journal name (populated by enricher, null initially) |
| `year` | integer | Publication year (populated by enricher, null initially) |
| `channel` | string | Slack channel where shared |
| `user` | string | Slack user ID who shared it |
| `timestamp` | integer | Unix timestamp of message |
| `message_permalink` | string | Link to original Slack message |
| `reactions` | object | Emoji reactions with counts |
| `thread_replies` | integer | Number of replies in thread |
| `thread_reply_users` | array | User IDs who replied in thread |
| `engagement_score` | float | Normalized engagement (0-1) |

## Advanced Options

### Time Range

Scrape only papers from a specific date range:

```bash
# Last 7 days
papertrail scrape --days 7 -o papers_raw.json

# Specific date range
papertrail scrape --after 2024-01-01 --before 2024-03-31 -o papers_raw.json
```

### Minimum Engagement

Only include papers with minimum engagement:

```bash
# At least 2 reactions or 1 thread reply
papertrail scrape --min-engagement 2 -o papers_raw.json
```

### Exclude Channels

Skip certain channels:

```bash
papertrail scrape --exclude random introductions -o papers_raw.json
```

### Custom Output Format

Export to CSV instead of JSON:

```bash
papertrail scrape --format csv -o papers_raw.csv
```

### Resume from Checkpoint

If scraping is interrupted, resume from where you left off:

```bash
papertrail scrape --checkpoint scrape.checkpoint -o papers_raw.json
```

This saves progress and can resume if interrupted.

## Supported Paper Sources

The scraper detects papers from these sources:

| Source | URL Pattern | ID Example |
|--------|------------|-----------|
| **DOI** | `doi.org/10.xxxx/...` | `10.1038/nature12373` |
| **arXiv** | `arxiv.org/abs/...` | `2301.12345` |
| **bioRxiv** | `biorxiv.org/content/...` | `2023.01.23.525139` |
| **medRxiv** | `medrxiv.org/content/...` | `2023.01.23.v1` |
| **PubMed** | `pubmed.ncbi.nlm.nih.gov/...` | `12345678` |
| **IEEE Xplore** | `ieeexplore.ieee.org/document/...` | `9999999` |
| **SSRN** | `ssrn.com/abstract=...` | `4123456` |
| **PaperWithCode** | `paperswithcode.com/paper/...` | URL-based |

## Handling Issues

### No Papers Found

Check that:
- Your bot token is valid and has proper scopes
- Bot was added to channels
- Papers have shareable links
- Try a specific channel: `papertrail scrape --channels general`

### Duplicate Papers

Duplicates can occur if the same paper is shared multiple times. The enricher and embedder handle this automatically, but you can deduplicate manually:

```python
import json

with open("papers_raw.json") as f:
    data = json.load(f)

# Deduplicate by DOI or URL
seen = set()
unique = []
for paper in data["papers"]:
    key = paper.get("doi") or paper.get("url")
    if key not in seen:
        seen.add(key)
        unique.append(paper)

data["papers"] = unique

with open("papers_raw_unique.json", "w") as f:
    json.dump(data, f, indent=2)
```

### Missing User Information

If user information isn't populated, check:
- Bot has `users:read` scope
- Workspace has those users
- Users aren't deactivated

### Rate Limits

Slack API has rate limits. If you hit them, PaperTrail will:
- Automatically retry with exponential backoff
- Show a warning
- Continue with available data

To be conservative, add a delay:

```bash
papertrail scrape --delay 1.0 -o papers_raw.json
```

## Python API

Use the scraper programmatically:

```python
from papertrail.scraper import Scraper

# Create scraper
scraper = Scraper(token="xoxb-...", verbose=True)

# Scrape papers
papers = scraper.scrape(
    channels=["general", "papers"],
    days=7,
    min_engagement=1
)

# Access results
for paper in papers:
    print(f"{paper['url']}: {paper['engagement_score']:.2f}")

# Export
scraper.export_json(papers, "output.json")
scraper.export_csv(papers, "output.csv")
```

## Tips & Tricks

### Filter by Channel Category

Group channels and scrape selectively:

```bash
# Scrape only paper discussion channels
papertrail scrape --channels papers-* -o papers_raw.json
```

### Check Engagement Trends

```python
import json
from collections import Counter

with open("papers_raw.json") as f:
    papers = json.load(f)["papers"]

# Most common channels
channels = Counter(p["channel"] for p in papers)
print(f"Most active: {channels.most_common(5)}")

# Average engagement
avg_engagement = sum(p["engagement_score"] for p in papers) / len(papers)
print(f"Average engagement: {avg_engagement:.2f}")
```

### Export Just URLs

```bash
papertrail scrape -o papers_raw.json && \
python3 << 'EOF'
import json
with open("papers_raw.json") as f:
    papers = json.load(f)["papers"]
with open("urls.txt", "w") as f:
    for p in papers:
        if p["url"]:
            f.write(p["url"] + "\n")
EOF
```

## Next Steps

- **[Enriching Metadata](enriching.md)** — Add titles, authors, abstracts
- **[Computing Embeddings](embeddings.md)** — Generate semantic embeddings
- **[Building the Dashboard](dashboard.md)** — Create interactive visualization
- **[API Reference: Scraper](../api/scraper.md)** — Detailed Python API
