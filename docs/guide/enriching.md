# Enriching Metadata

The enricher fetches rich metadata for each paper using Semantic Scholar and OpenAlex APIs, populating title, authors, abstract, journal, and more.

## How It Works

The enricher:

1. **Identifies papers** using DOI, arXiv ID, or PubMed ID
2. **Queries Semantic Scholar API** first (comprehensive academic coverage)
3. **Falls back to OpenAlex API** if Semantic Scholar doesn't have it
4. **Extracts metadata**: title, authors, abstract, journal, year, citation count, institutions
5. **Handles failures** gracefully (missing papers get null fields)
6. **Exports enriched JSON** with all fields populated

## Basic Usage

### Enrich Papers

```bash
papertrail enrich papers_raw.json -o papers_enriched.json
```

Takes the raw JSON from the scraper and populates metadata fields.

### Dry Run

Preview enrichment without saving:

```bash
papertrail enrich papers_raw.json --dry-run
```

### Verbose Output

See which papers are being enriched:

```bash
papertrail enrich papers_raw.json -v -o papers_enriched.json
```

## Output Format

Enriched papers include these additional fields:

```json
{
  "papers": [
    {
      "doi": "10.1038/nature12373",
      "title": "Deep residual learning for image recognition",
      "authors": [
        {
          "name": "Kaiming He",
          "affiliation": "Microsoft Research"
        },
        {
          "name": "Xiangyu Zhang",
          "affiliation": "Microsoft Research"
        }
      ],
      "abstract": "Deeper neural networks are more difficult to train...",
      "journal": "Nature",
      "year": 2015,
      "citation_count": 85432,
      "is_open_access": true,
      "source_type": "doi",
      "url": "https://doi.org/10.1038/nature12373",
      "channel": "general",
      "user": "U123456",
      "timestamp": 1234567890,
      "reactions": {"thumbsup": 5},
      "engagement_score": 0.90
    }
  ]
}
```

### New Fields

| Field | Type | Description |
|-------|------|-------------|
| `title` | string | Paper title |
| `authors` | array | Author objects with name and affiliation |
| `abstract` | string | Full abstract text |
| `journal` | string | Journal name |
| `year` | integer | Publication year |
| `citation_count` | integer | Number of citations |
| `is_open_access` | boolean | Whether paper is open access |
| `semantic_scholar_id` | string | Semantic Scholar paper ID |
| `openalex_id` | string | OpenAlex paper ID |

## Advanced Options

### Batch Size

Control how many papers are enriched in parallel:

```bash
# Enrich 50 papers at a time (default: 10)
papertrail enrich papers_raw.json -o papers_enriched.json --batch-size 50
```

### Delay Between Requests

Add delays to avoid rate limiting:

```bash
# 0.5 second delay between API calls
papertrail enrich papers_raw.json -o papers_enriched.json --delay 0.5
```

### Skip Missing Papers

By default, papers without a DOI/arXiv ID are still processed (just won't be enriched). To skip them:

```bash
papertrail enrich papers_raw.json -o papers_enriched.json --require-identifier
```

### Cache Results

Enrichment is automatically cached. To clear cache and re-enrich:

```bash
papertrail enrich papers_raw.json -o papers_enriched.json --no-cache
```

### Only Enrich Specific Fields

Focus on a subset of metadata:

```bash
papertrail enrich papers_raw.json -o papers_enriched.json \
  --fields title,authors,abstract
```

## Handling Issues

### Papers Without Metadata

If a paper isn't found, the enricher:

- Logs a warning
- Leaves fields as `null` or empty arrays
- Continues with other papers

You can filter these out later:

```python
import json

with open("papers_enriched.json") as f:
    data = json.load(f)

# Keep only papers with abstracts
with_metadata = [p for p in data["papers"] if p.get("abstract")]
print(f"Papers with metadata: {len(with_metadata)}/{len(data['papers'])}")

data["papers"] = with_metadata

with open("papers_enriched_filtered.json", "w") as f:
    json.dump(data, f, indent=2)
```

### Rate Limiting

Semantic Scholar and OpenAlex have rate limits:

- **Semantic Scholar**: ~100 requests/second
- **OpenAlex**: ~10 requests/second

If you hit limits, PaperTrail will:

- Automatically wait and retry
- Show a warning
- Continue with other papers

To be conservative:

```bash
papertrail enrich papers_raw.json -o papers_enriched.json --delay 0.5
```

### Missing Authors or Institutions

Some papers may have partial author information. This is normal for:

- Very old papers
- Non-traditional publications
- Papers with privacy restrictions

### Open Access Detection

Open access detection relies on external APIs. It's not always accurate. Use for general reference only.

## Python API

Enrich papers programmatically:

```python
from papertrail.enricher import Enricher

# Create enricher
enricher = Enricher(verbose=True)

# Enrich papers (from scraper)
papers = enricher.enrich(
    papers,
    batch_size=20,
    delay=0.5
)

# Access enriched data
for paper in papers:
    if paper.get("abstract"):
        print(f"{paper['title']}")
        print(f"  Authors: {', '.join(a['name'] for a in paper['authors'][:3])}")
        print(f"  Citations: {paper['citation_count']}")
```

## Tips & Tricks

### Find Most Cited Papers

```python
import json
from operator import itemgetter

with open("papers_enriched.json") as f:
    papers = json.load(f)["papers"]

# Sort by citation count
sorted_papers = sorted(
    papers,
    key=lambda p: p.get("citation_count", 0),
    reverse=True
)

print("Most cited papers:")
for paper in sorted_papers[:10]:
    print(f"  {paper['citation_count']:5d}  {paper['title']}")
```

### Find Papers by Author

```python
import json

author_query = "Marie Curie"

with open("papers_enriched.json") as f:
    papers = json.load(f)["papers"]

for paper in papers:
    for author in paper.get("authors", []):
        if author_query.lower() in author.get("name", "").lower():
            print(f"{paper['title']}")
            break
```

### Extract Institutions

```python
import json
from collections import Counter

with open("papers_enriched.json") as f:
    papers = json.load(f)["papers"]

# Find most common institutions
institutions = []
for paper in papers:
    for author in paper.get("authors", []):
        if author.get("affiliation"):
            institutions.append(author["affiliation"])

counter = Counter(institutions)
print("Most common institutions:")
for inst, count in counter.most_common(10):
    print(f"  {count:3d}  {inst}")
```

### Find Open Access Papers

```python
import json

with open("papers_enriched.json") as f:
    papers = json.load(f)["papers"]

open_access = [p for p in papers if p.get("is_open_access")]
print(f"Open access: {len(open_access)}/{len(papers)} ({100*len(open_access)/len(papers):.1f}%)")
```

## Enrichment Sources

### Semantic Scholar

- API: [api.semanticscholar.org](https://api.semanticscholar.org)
- Coverage: Very broad (60M+ papers)
- Fields: Title, authors, abstract, journal, year, citations, open access
- Rate limit: ~100 req/sec (free tier)

### OpenAlex

- API: [api.openalex.org](https://docs.openalex.org)
- Coverage: Broad (~200M works)
- Fields: Title, authors, abstract, journal, year, citations, concepts
- Rate limit: ~10 req/sec (no auth needed)

Both APIs are free and don't require API keys. Authentication can increase rate limits.

## Next Steps

- **[Computing Embeddings](embeddings.md)** — Create semantic representations
- **[Building the Dashboard](dashboard.md)** — Visualize papers
- **[API Reference: Enricher](../api/enricher.md)** — Detailed Python API
