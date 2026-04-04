# Searching Papers

Use semantic search to find papers similar to a query. Powered by FAISS embeddings for sub-millisecond lookup.

## How It Works

The search system:

1. **Takes your query** (natural language text)
2. **Generates embedding** using the same backend as your papers
3. **Searches FAISS index** for nearest neighbors
4. **Returns ranked results** sorted by similarity
5. **Displays metadata** for each result

## Basic Usage

### Search from CLI

```bash
papertrail search -q "transformer attention mechanisms" -k 5
```

Returns top 5 most similar papers.

### Search Specific Field

```bash
# Search only abstracts
papertrail search -q "deep learning" -k 10 --field abstract

# Search only titles
papertrail search -q "neural networks" -k 5 --field title
```

### Combine with Papers File

```bash
# Search within specific paper collection
papertrail search -q "CRISPR gene editing" -k 10 \
  --papers papers_final.json
```

### Output Format

```bash
# Default: human-readable
papertrail search -q "attention" -k 5

# JSON output for programmatic use
papertrail search -q "attention" -k 5 --format json > results.json

# CSV output for spreadsheet
papertrail search -q "attention" -k 5 --format csv > results.csv
```

## Search Options

### Number of Results

```bash
# Get top 10 instead of default 5
papertrail search -q "prompt engineering" -k 10
```

### Similarity Threshold

Only return papers above a similarity score:

```bash
# Only return papers with score > 0.7
papertrail search -q "reinforcement learning" -k 5 --min-score 0.7
```

### Search in Embeddings Directory

If you have FAISS index files:

```bash
papertrail search -q "attention mechanisms" \
  --faiss-path ./faiss_index/ \
  --papers papers_final.json
```

### Use Specific Backend

```bash
# Use OpenAI backend (default)
papertrail search -q "transformers" --backend openai

# Use local backend (no API key)
papertrail search -q "transformers" --backend local
```

### Exclude Channels

Find papers but exclude certain channels:

```bash
papertrail search -q "deep learning" --exclude general announcements
```

### Filter by Date

```bash
# Papers from last 30 days
papertrail search -q "neural networks" --after 2024-02-04

# Papers from a date range
papertrail search -q "machine learning" \
  --after 2023-01-01 --before 2023-12-31
```

### Filter by Cluster

```bash
# Only search within cluster 2
papertrail search -q "clustering algorithms" --cluster 2
```

## Python API

Search programmatically:

```python
from papertrail.embeddings import VectorStore
from papertrail.cli import search

# Using VectorStore directly
store = VectorStore()
store.load("faiss_index/")

# Search by text query
results = store.search_text(
    query="transformer attention",
    top_k=5,
    min_score=0.5
)

for result in results:
    print(f"[{result['score']:.3f}] {result['title']}")
    print(f"  Authors: {', '.join(result['authors'][:3])}")
    print(f"  Abstract: {result['abstract'][:200]}...")
```

### Advanced Search

```python
import numpy as np
from papertrail.embeddings import VectorStore, Embedder

# Load store
store = VectorStore()
store.load("faiss_index/")

# Create embedder to convert query to vector
embedder = Embedder(backend="openai")

# Search by vector
query_vector = embedder.embed_text("attention mechanisms")
results = store.search_vector(
    query_vector,
    top_k=10
)

# Combine results
combined_results = []
for i, result in enumerate(results):
    result['rank'] = i + 1
    result['rank_score'] = 1.0 / (i + 1)  # Decay by rank
    combined_results.append(result)
```

## Search Examples

### Find Papers by Topic

```python
from papertrail.embeddings import VectorStore

store = VectorStore()
store.load("faiss_index/")

# Search for neuroscience papers
topics = [
    "single cell RNA sequencing",
    "neural circuits",
    "brain imaging"
]

for topic in topics:
    results = store.search_text(topic, top_k=3)
    print(f"\n{topic}:")
    for r in results:
        print(f"  [{r['score']:.3f}] {r['title']}")
```

### Find Similar Papers

```python
# Find papers similar to a specific paper
reference_paper = papers[0]
reference_vector = np.array(reference_paper["embedding"])

results = store.search_vector(reference_vector, top_k=10)
print(f"Papers similar to '{reference_paper['title']}':")
for r in results:
    print(f"  [{r['score']:.3f}] {r['title']}")
```

### Multi-Query Search

```python
# Search with multiple related queries
queries = [
    "attention mechanisms in neural networks",
    "transformer architecture",
    "self-attention algorithms"
]

# Combine results from multiple searches
all_results = []
for query in queries:
    results = store.search_text(query, top_k=5)
    all_results.extend(results)

# Deduplicate and re-rank
unique_results = {}
for r in all_results:
    key = r['doi'] or r['url']
    if key in unique_results:
        unique_results[key]['score'] += r['score']
    else:
        unique_results[key] = r

# Sort by combined score
final_results = sorted(
    unique_results.values(),
    key=lambda x: x['score'],
    reverse=True
)[:10]

for r in final_results:
    print(f"[{r['score']:.3f}] {r['title']}")
```

### Find Influential Papers

```python
# Search for papers, weighted by citations
results = store.search_text("deep learning", top_k=20)

# Re-rank by citations
results = sorted(
    results,
    key=lambda x: (x['score'], x.get('citation_count', 0)),
    reverse=True
)

print("Top cited papers on 'deep learning':")
for i, r in enumerate(results[:5], 1):
    print(f"{i}. [{r['score']:.3f}] {r['title']}")
    print(f"   Citations: {r.get('citation_count', 'N/A')}")
```

### Author-Based Search

```python
# Find papers by author and topic
target_author = "Yann LeCun"
topic = "deep learning"

results = store.search_text(topic, top_k=50)

# Filter by author
author_papers = [
    r for r in results
    if any(target_author.lower() in a['name'].lower()
           for a in r.get('authors', []))
]

print(f"Papers by {target_author} on '{topic}':")
for r in author_papers[:5]:
    print(f"  [{r['score']:.3f}] {r['title']}")
```

## Search Tips

### Query Tips

**Good queries:**
- "transformer attention mechanisms"
- "CRISPR gene editing"
- "single cell RNA sequencing"

**Bad queries:**
- "papers" (too generic)
- "a" (single letter)
- "this is some stuff about things" (too long)

**Best practice:** 2-5 keywords describing your topic.

### Interpreting Scores

Similarity scores range from 0 (no match) to 1 (perfect match):

- **0.8-1.0**: Directly relevant
- **0.7-0.8**: Closely related
- **0.6-0.7**: Somewhat related
- **0.5-0.6**: Tangentially related
- **<0.5**: Weak relevance

Thresholds vary by embedding backend:
- **OpenAI**: Generally higher scores (more discriminative)
- **HuggingFace**: Mid-range scores
- **Local**: Lower scores (less discriminative)

### Combine Search Results

```python
# Meta-search across multiple backends
results_openai = store_openai.search_text(query, top_k=10)
results_local = store_local.search_text(query, top_k=10)

# Combine and re-rank
combined = results_openai + results_local
# Deduplicate and average scores...
```

### Batch Search

```python
# Search for multiple topics at once
topics = [
    "deep learning",
    "machine learning",
    "neural networks"
]

all_results = {}
for topic in topics:
    all_results[topic] = store.search_text(topic, top_k=5)

# Display results
for topic, results in all_results.items():
    print(f"\n{topic}:")
    for r in results:
        print(f"  [{r['score']:.3f}] {r['title']}")
```

## In-Browser Search

The dashboard includes semantic search. To use it:

1. **Open** `dashboard.html` in your browser
2. **Find** the search box at the bottom
3. **Type** your query
4. **See** results ranked by similarity
5. **Click** a result to see full details

The in-browser search uses the embedded FAISS index, so results are instant even for 10,000+ papers.

## Troubleshooting

### Search returns no results

Check:
- Papers have embeddings (required)
- Query words are spelled correctly
- Try simpler/shorter query
- Check min-score threshold isn't too high

### Search is slow

Check:
- FAISS index is loaded
- Not doing computation on very large dataset (10,000+ papers)
- Try reducing top_k (fewer results to compute)

### Search results seem irrelevant

Try:
- Different query (be more specific)
- Different backend (OpenAI has best quality)
- Check if papers have abstracts (needed for good search)
- Lower min-score threshold

### "Embedding model not found" error

The embedding model needs to be available. For local backend:

```bash
# Download model first
papertrail embed --backend local papers.json -o /dev/null

# Then search
papertrail search -q "attention" --backend local
```

## Next Steps

- **[Building the Dashboard](dashboard.md)** — Interactive search interface
- **[Embeddings Guide](embeddings.md)** — How embeddings work
- **[API Reference: Embeddings](../api/embeddings.md)** — Detailed API
