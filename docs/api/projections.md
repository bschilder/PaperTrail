# Projections API

The projections module computes 2D projections from high-dimensional
embedding vectors and clusters papers using K-Means with TF-IDF-based
label generation.

## Quick Example

```python
from papertrail.projections import compute_projections, cluster_papers

# embeddings: np.ndarray of shape (n_papers, dim)
projections = compute_projections(embeddings)
# → {"pca": (n, 2), "tsne": (n, 2), "umap": (n, 2)}

texts = ["paper abstract one...", "paper abstract two..."]
cluster_ids, labels = cluster_papers(embeddings, texts, n_clusters=15)
# cluster_ids: np.ndarray of shape (n,) with int cluster assignments
# labels: {0: "Genomics / Regulation / Enhancer", 1: "Protein / Structure / Folding", ...}
```

## Functions

::: papertrail.projections.compute_projections
    options:
      show_root_heading: true
      heading_level: 3

### compute_projections

**Parameters:**

| Name | Type | Default | Description |
|---|---|---|---|
| `embeddings` | `np.ndarray` | *(required)* | Embedding matrix of shape `(n_papers, dim)`. Any dimensionality. |
| `seed` | `int` | `42` | Random seed for reproducibility across PCA, t-SNE, and UMAP. |

**Returns:** `dict[str, np.ndarray]` with keys:

| Key | Shape | Algorithm | Notes |
|---|---|---|---|
| `"pca"` | `(n, 2)` | PCA | Fast, linear. Reports explained variance ratio. |
| `"tsne"` | `(n, 2)` | t-SNE | `perplexity=min(30, n-1)`, `metric="cosine"`. |
| `"umap"` | `(n, 2)` | UMAP | `n_neighbors=15`, `min_dist=0.1`, `metric="cosine"`. Falls back to t-SNE if `umap-learn` is not installed. |

---

::: papertrail.projections.cluster_papers
    options:
      show_root_heading: true
      heading_level: 3

### cluster_papers

**Parameters:**

| Name | Type | Default | Description |
|---|---|---|---|
| `embeddings` | `np.ndarray` | *(required)* | Embedding matrix of shape `(n_papers, dim)`. |
| `texts` | `list[str]` | *(required)* | Paper texts (title + abstract) for generating cluster labels via TF-IDF. |
| `n_clusters` | `int` | `10` | Number of K-Means clusters. |
| `seed` | `int` | `42` | Random seed. |

**Returns:** `tuple[np.ndarray, dict[int, str]]`

| Element | Type | Description |
|---|---|---|
| `cluster_ids` | `np.ndarray` | Integer array of shape `(n_papers,)`. Each value is a cluster ID from `0` to `n_clusters - 1`. |
| `labels` | `dict[int, str]` | Mapping of cluster ID → human-readable label. Labels are the top 3 TF-IDF terms for that cluster, title-cased and joined with " / " (e.g. `"Genomics / Regulation / Enhancer"`). |

## Dependencies

| Package | Required | Notes |
|---|---|---|
| `scikit-learn` | Yes | PCA, t-SNE, K-Means, TF-IDF |
| `umap-learn` | Optional | If missing, UMAP slot uses a second t-SNE with different perplexity |
