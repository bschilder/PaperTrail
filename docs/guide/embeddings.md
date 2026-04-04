# Computing Embeddings

The embeddings module generates semantic vector representations of papers and computes 2D projections, clusters, and a FAISS index for similarity search.

## How It Works

The embedder:

1. **Extracts text** from paper abstracts, titles, and keywords
2. **Generates embeddings** using your chosen backend:
   - OpenAI `text-embedding-3-small` (default)
   - HuggingFace `BAAI/bge-small-en-v1.5`
   - Local fastembed (no API key)
3. **Computes 2D projections** for visualization:
   - UMAP (recommended)
   - t-SNE
   - PCA
4. **Clusters papers** using k-means
5. **Builds FAISS index** for fast similarity search
6. **Exports** complete dataset with all computed features

## Basic Usage

### Embed Papers

```bash
papertrail embed papers_enriched.json -o papers_final.json --backend openai
```

Computes embeddings and saves to `papers_final.json`.

### Choose Backend

=== "OpenAI (recommended, default)"
    ```bash
    papertrail embed papers_enriched.json -o papers_final.json --backend openai
    ```

=== "HuggingFace"
    ```bash
    papertrail embed papers_enriched.json -o papers_final.json --backend huggingface
    ```

=== "Local (no API key)"
    ```bash
    papertrail embed papers_enriched.json -o papers_final.json --backend local
    ```

### Dry Run

Preview embeddings without saving:

```bash
papertrail embed papers_enriched.json --dry-run
```

### Verbose Output

See detailed progress:

```bash
papertrail embed papers_enriched.json -o papers_final.json -v
```

## Embedding Backends

Choose based on your needs:

| Feature | OpenAI | HuggingFace | Local |
|---------|--------|------------|-------|
| **Model** | `text-embedding-3-small` | `BAAI/bge-small-en-v1.5` | `BAAI/bge-small-en-v1.5` |
| **Dimensions** | 1536 | 384 | 384 |
| **Quality** | Excellent | Very Good | Very Good |
| **Speed** | Very Fast | Fast | Medium |
| **Cost** | $0.02/million tokens | Free | Free |
| **API Key** | `OPENAI_API_KEY` | `HF_TOKEN` | None |
| **Requires Network** | Yes | Yes | No |

### OpenAI

Best overall quality and speed. Requires `OPENAI_API_KEY`.

```bash
export OPENAI_API_KEY="sk-..."
papertrail embed papers.json -o papers_final.json --backend openai
```

**Pros:**
- Highest quality embeddings
- Very fast
- 1536-dimensional space captures fine-grained semantics

**Cons:**
- Costs $0.02 per million tokens (~$2 for 10,000 papers)
- Requires API key and internet connection
- Subject to rate limits

**Cost estimate:**
- 100 papers: ~$0.01
- 1,000 papers: ~$0.10
- 10,000 papers: ~$1.00

### HuggingFace Inference API

Good quality, free but requires `HF_TOKEN` for higher rate limits.

```bash
export HF_TOKEN="hf_..."
papertrail embed papers.json -o papers_final.json --backend huggingface
```

**Pros:**
- Free (after HuggingFace account creation)
- Good quality
- Can use without API key (limited rate limit)

**Cons:**
- Slightly lower quality than OpenAI
- Requires internet connection
- Rate limits can be restrictive on free tier

### Local ONNX Models

No API key required. Best for privacy and offline use.

```bash
papertrail embed papers.json -o papers_final.json --backend local
```

**Pros:**
- No API keys required
- Completely offline
- Best for sensitive data
- Full control over models

**Cons:**
- Slower (10-30 seconds for 100 papers)
- Uses more CPU/memory
- First run downloads ~100MB model

## Output Format

Embedded papers include vectors and projections:

```json
{
  "papers": [
    {
      "doi": "10.1038/nature12373",
      "title": "Deep residual learning for image recognition",
      "abstract": "...",
      "embedding": [0.123, -0.456, 0.789, ...],
      "cluster": 3,
      "umap_x": 2.34,
      "umap_y": -1.56,
      "tsne_x": 45.2,
      "tsne_y": 32.1,
      "pca_x": 1.23,
      "pca_y": 0.45,
      "channel": "papers-ai",
      "timestamp": 1234567890
    }
  ],
  "metadata": {
    "embedding_backend": "openai",
    "embedding_model": "text-embedding-3-small",
    "embedding_dimensions": 1536,
    "n_clusters": 5,
    "clustering_method": "kmeans"
  }
}
```

### New Fields

| Field | Type | Description |
|-------|------|-------------|
| `embedding` | array | Semantic vector (1536 for OpenAI, 384 for others) |
| `cluster` | integer | Cluster assignment (0-based) |
| `umap_x`, `umap_y` | float | 2D UMAP coordinates |
| `tsne_x`, `tsne_y` | float | 2D t-SNE coordinates |
| `pca_x`, `pca_y` | float | 2D PCA coordinates |

## Advanced Options

### Number of Clusters

Control k-means clustering:

```bash
# Use 10 clusters instead of default 5
papertrail embed papers.json -o papers_final.json --n-clusters 10
```

### Projection Methods

Choose which 2D projections to compute (all by default):

```bash
# Only compute UMAP (faster)
papertrail embed papers.json -o papers_final.json --projections umap

# Multiple projections
papertrail embed papers.json -o papers_final.json --projections umap,tsne
```

Available: `umap`, `tsne`, `pca`

### Batch Size

Control embedding batch size:

```bash
# Larger batches = faster but use more memory
papertrail embed papers.json -o papers_final.json --batch-size 128
```

### Delay Between Requests

Add delays for rate-limited APIs:

```bash
# 1 second delay between requests
papertrail embed papers.json -o papers_final.json --delay 1.0
```

### Text Fields

Control which fields are used for embeddings:

```bash
# Use abstract only (default uses abstract + title)
papertrail embed papers.json -o papers_final.json --text-fields abstract

# Use multiple fields
papertrail embed papers.json -o papers_final.json --text-fields abstract,title,keywords
```

### FAISS Index Options

Control FAISS index creation:

```bash
# Use different distance metric
papertrail embed papers.json -o papers_final.json --faiss-metric ip  # inner product

# Save FAISS index separately
papertrail embed papers.json -o papers_final.json --faiss-path ./faiss_index/
```

## Using Embeddings

### Similarity Search

```python
from papertrail.embeddings import VectorStore
import numpy as np

# Load FAISS index
store = VectorStore()
store.load("faiss_index/")

# Search by text
results = store.search_text("transformer attention mechanisms", top_k=5)
for r in results:
    print(f"[{r['score']:.3f}] {r['title']}")

# Search by vector
query_vector = np.array([...])  # your embedding
results = store.search_vector(query_vector, top_k=5)
```

### Analyze Clusters

```python
import json
from collections import Counter

with open("papers_final.json") as f:
    papers = json.load(f)["papers"]

# Papers per cluster
clusters = Counter(p["cluster"] for p in papers)
print(f"Clusters: {sorted(clusters.items())}")

# Papers in cluster 0
cluster_0 = [p for p in papers if p["cluster"] == 0]
print(f"Cluster 0: {len(cluster_0)} papers")
for p in cluster_0[:3]:
    print(f"  - {p['title']}")
```

### Visualize Embeddings

```python
import json
import matplotlib.pyplot as plt

with open("papers_final.json") as f:
    papers = json.load(f)["papers"]

# Extract coordinates
x = [p["umap_x"] for p in papers]
y = [p["umap_y"] for p in papers]
clusters = [p["cluster"] for p in papers]

# Plot
plt.figure(figsize=(12, 8))
scatter = plt.scatter(x, y, c=clusters, cmap="tab10", alpha=0.6)
plt.colorbar(scatter, label="Cluster")
plt.xlabel("UMAP X")
plt.ylabel("UMAP Y")
plt.title("Paper Embeddings")
plt.tight_layout()
plt.savefig("embeddings_plot.png")
```

## Python API

Use embeddings programmatically:

```python
from papertrail.embeddings import Embedder

# Create embedder
embedder = Embedder(backend="openai", verbose=True)

# Embed papers
papers = embedder.embed(
    papers,
    n_clusters=5,
    projections=["umap", "tsne"]
)

# Get embeddings
for paper in papers:
    vector = paper["embedding"]
    print(f"{paper['title']}: {len(vector)} dimensions")

# Build FAISS index
faiss_index = embedder.build_faiss_index(papers)
faiss_index.save("faiss_index/")
```

## Tips & Tricks

### Embedding Strategies

**For semantic similarity:**
Use abstracts + titles with OpenAI for best results.

**For speed:**
Use local backend with just abstracts.

**For research:**
Experiment with multiple backends and compare cluster assignments.

### Handling Large Datasets

For 10,000+ papers:
1. Use local backend for speed
2. Increase batch size to 256
3. Skip some projections: `--projections umap`
4. Run on GPU-enabled machine if available

### Re-embedding Specific Papers

If you've updated some papers, re-embed them:

```bash
# Re-embed all papers
papertrail embed papers_enriched.json -o papers_final.json --no-cache
```

### Combining Embeddings

If you have multiple embedding sets, combine them:

```python
import json
import numpy as np

# Load both
with open("openai_final.json") as f:
    openai_papers = json.load(f)["papers"]
with open("local_final.json") as f:
    local_papers = json.load(f)["papers"]

# Average embeddings (if same papers)
combined = []
for op, lp in zip(openai_papers, local_papers):
    op_embed = np.array(op["embedding"])
    lp_embed = np.array(lp["embedding"])

    # Normalize
    op_embed = op_embed / np.linalg.norm(op_embed)
    lp_embed = lp_embed / np.linalg.norm(lp_embed)

    # Average
    combined_embed = (op_embed + lp_embed) / 2
    op["embedding"] = combined_embed.tolist()
    combined.append(op)

# Save
with open("combined_final.json", "w") as f:
    json.dump({"papers": combined}, f)
```

## Troubleshooting

### Error: `OPENAI_API_KEY not found`

Set your API key:

```bash
export OPENAI_API_KEY="sk-..."
```

Or use a different backend:

```bash
papertrail embed papers.json -o papers_final.json --backend local
```

### Error: `Out of memory`

Reduce batch size:

```bash
papertrail embed papers.json -o papers_final.json --batch-size 32
```

Or skip some projections:

```bash
papertrail embed papers.json -o papers_final.json --projections umap
```

### Error: `Rate limit exceeded`

Add delays:

```bash
papertrail embed papers.json -o papers_final.json --delay 2.0
```

### Embeddings seem low quality

Check:

- You're using the right backend (OpenAI is best)
- Papers have abstracts (required for good embeddings)
- Text is in English (models are trained on English)

Try a different backend for comparison.

## Next Steps

- **[Building the Dashboard](dashboard.md)** — Visualize embeddings
- **[Searching Papers](searching.md)** — Use FAISS for semantic search
- **[API Reference: Embeddings](../api/embeddings.md)** — Detailed Python API
