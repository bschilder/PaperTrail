# PaperTrail Pipeline Skill

Scrapes papers from Slack channels, enriches with metadata, computes embeddings,
and builds an interactive dashboard. Use this skill when asked to collect, export,
or analyze papers from Slack.

## Triggers

- "scrape papers from Slack"
- "export papers from paper channels"
- "make a spreadsheet of papers shared in Slack"
- "compile a reading list"
- "paper digest"
- "literature tracker"
- "build paper dashboard"

## Prerequisites

```bash
cd PaperTrail
pip install -e ".[all]" --break-system-packages
```

## Full Pipeline

### Step 1: Scrape Papers from Slack

Use the MCP Slack tools to read channel history, then extract paper URLs.

```python
import json, re
from papertrail.scraper import SlackPaperScraper

scraper = SlackPaperScraper()

# Use MCP tool: slack_read_channel(channel_id, limit=200, cursor=...)
# Paginate through ALL messages using the cursor from each response.
# For each message, extract paper URLs:

all_papers = []
for msg in messages:
    urls = scraper.extract_paper_urls([msg.get("text", "")])
    for url in urls:
        normalized = scraper.normalize_url(url)
        all_papers.append({
            "url": normalized,
            "channel": channel_name,
            "user": msg.get("user", ""),
            "date": msg.get("ts", ""),
            "text_snippet": msg.get("text", "")[:200],
        })

# Deduplicate by URL
seen = set()
unique = []
for p in all_papers:
    if p["url"] not in seen:
        seen.add(p["url"])
        unique.append(p)
```

**Koo Lab channels:**
- papers-dl: C0123Q7PGGP
- papers-genomics: C015BQ2BDF0
- papers-protein: C011SDT3KKQ
- papers-phenomics: C084KFWEVC2
- papers-ai-agents: C08C020L554
- papers-health: C09U8FW4YJV
- paper_digest_moon: C0AEX373E5Q

### Step 2: Extract Paper IDs

```python
# The scraper already normalizes URLs. Extract structured IDs:
for paper in unique:
    url = paper["url"]
    # arxiv
    m = re.search(r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+)', url)
    if m: paper["arxiv_id"] = m.group(1)
    # doi
    m = re.search(r'doi\.org/(10\.\d+/.+?)(?:\?|$)', url)
    if m: paper["doi"] = m.group(1)
    # pmid
    m = re.search(r'pubmed\.ncbi\.nlm\.nih\.gov/(\d+)', url)
    if m: paper["pmid"] = m.group(1)
```

### Step 3: Enrich with Metadata

```python
from papertrail.enricher import PaperEnricher

enricher = PaperEnricher(
    email="brian_schilder@alumni.brown.edu",  # OpenAlex polite pool
    openalex_first=True,  # OA is faster, S2 as fallback
)

# Batch enrich
enriched = enricher.enrich_papers(unique)

# For papers still missing abstracts, do a title search pass:
for paper in enriched:
    if paper.get("title") and not paper.get("abstract"):
        result = enricher.enrich_by_title_openalex(paper["title"])
        if result and result.abstract:
            paper["abstract"] = result.abstract
```

**Rate limit notes:**
- OpenAlex with email: ~10 req/s. Add 0.1s delay between calls.
- Semantic Scholar: ~3 req/s. Add 1.5s delay. Expect many 429s.
- Always use OpenAlex first — it's 10x faster.

### Step 4: Compute Embeddings

```python
from papertrail.embeddings import embed_texts

# Build text for embedding
texts = []
for p in enriched:
    parts = [p.get("title", ""), p.get("abstract", "")]
    texts.append(" ".join(part for part in parts if part).strip() or p.get("url", ""))

# Embed (auto-detects best backend: OpenAI > HF > fastembed > TF-IDF)
embeddings = embed_texts(texts)

# Or force a specific backend:
# embeddings = embed_texts(texts, backend="openai")
# embeddings = embed_texts(texts, backend="tfidf")
```

### Step 5: Project + Cluster

```python
from papertrail.projections import compute_projections, cluster_papers

projections = compute_projections(embeddings)  # PCA, t-SNE, UMAP
cluster_ids, cluster_labels = cluster_papers(embeddings, texts, n_clusters=15)

for i, p in enumerate(enriched):
    p["projections"] = {k: [float(v[i,0]), float(v[i,1])] for k, v in projections.items()}
    p["cluster_id"] = int(cluster_ids[i])
    p["cluster_label"] = cluster_labels[int(cluster_ids[i])]
```

### Step 6: Build Dashboard

```python
from papertrail.preview import build_preview

build_preview(enriched, output_path="papertrail_dashboard.html", title="Koo Lab PaperTrail")
```

### Step 7: Export to Excel (optional)

```python
import json
# Use the xlsx skill to create a spreadsheet from enriched data
with open("papers_enriched.json", "w") as f:
    json.dump(enriched, f, indent=2)
```

## CLI Alternative

```bash
papertrail scrape --token $SLACK_BOT_TOKEN -o raw.json
papertrail enrich raw.json -o enriched.json
papertrail embed enriched.json -o final.json --backend openai
papertrail build final.json -o dashboard.html
```

## Output Format

Each enriched paper has:
```json
{
  "url": "https://arxiv.org/abs/2301.04821",
  "channel": "papers-dl",
  "user": "U123...",
  "date": "2023-01-15",
  "title": "Paper Title",
  "authors": ["Author One", "Author Two"],
  "year": 2023,
  "abstract": "...",
  "journal": "Nature",
  "doi": "10.1038/...",
  "citation_count": 42,
  "projections": {"pca": [0.1, -0.3], "tsne": [12.5, -8.2], "umap": [3.1, 7.4]},
  "cluster_id": 5,
  "cluster_label": "single cell genomics"
}
```
