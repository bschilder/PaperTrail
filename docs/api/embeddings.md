# Embeddings API

The embeddings module computes vector representations of paper text
using multiple backends. It also provides a FAISS-backed vector store
for similarity search.

## Quick Example

```python
from papertrail.embeddings import embed_texts, VectorStore

# Embed paper texts (auto-detects best backend)
texts = ["Attention is all you need", "Deep learning for genomics"]
embeddings = embed_texts(texts)
# → np.ndarray of shape (2, dim)

# Force a specific backend
embeddings = embed_texts(texts, backend="tfidf")       # no API keys needed
embeddings = embed_texts(texts, backend="openai")       # requires OPENAI_API_KEY
embeddings = embed_texts(texts, backend="huggingface")  # requires HF_TOKEN

# Semantic search with FAISS
store = VectorStore()
store.build(embeddings, paper_ids=[0, 1], metadata={0: {"title": "..."}, 1: {"title": "..."}})
results = store.search_text("transformer architectures", top_k=5)
```

## Backend Priority

Auto-detection checks for available backends in this order:

| Priority | Backend | Env Variable | Model | Dimensions |
|---|---|---|---|---|
| 1 | `openai` | `OPENAI_API_KEY` | `text-embedding-3-small` | 1536 |
| 2 | `huggingface` | `HF_TOKEN` | `BAAI/bge-small-en-v1.5` | 384 |
| 3 | `local` | *(fastembed installed)* | `BAAI/bge-small-en-v1.5` | 384 |
| 4 | `tfidf` | *(always available)* | `tfidf-svd-128` | 128 |

## Functions

::: papertrail.embeddings.embed_texts
    options:
      show_root_heading: true
      heading_level: 3

### embed_texts

**Parameters:**

| Name | Type | Default | Description |
|---|---|---|---|
| `texts` | `list[str]` | *(required)* | Texts to embed. Each string is typically `"{title} {abstract}"`. |
| `backend` | `"openai" \| "huggingface" \| "local" \| "tfidf" \| None` | `None` | Embedding backend. Auto-detected if `None`. |
| `model` | `str \| None` | `None` | Model name override. Uses default for the backend if `None`. |

**Returns:** `np.ndarray` of shape `(len(texts), dim)` where `dim` depends on the backend/model.

---

## VectorStore

::: papertrail.embeddings.VectorStore
    options:
      show_root_heading: true
      heading_level: 3
      members:
        - __init__
        - build
        - search
        - search_text
        - save
        - load

### VectorStore Methods

#### `build(embeddings, paper_ids, metadata=None)`

| Parameter | Type | Description |
|---|---|---|
| `embeddings` | `np.ndarray` | Matrix of shape `(n, dim)`. Automatically L2-normalized for cosine similarity. |
| `paper_ids` | `list[int]` | Integer ID for each paper (used as lookup keys). |
| `metadata` | `dict[int, dict] \| None` | Optional mapping of `paper_id → {title, url, ...}` for search results. |

**Returns:** `None`. Builds the FAISS index in-place.

#### `search(query_embedding, top_k=10)`

| Parameter | Type | Description |
|---|---|---|
| `query_embedding` | `np.ndarray` | Query vector of shape `(dim,)` or `(1, dim)`. |
| `top_k` | `int` | Number of nearest neighbors to return. |

**Returns:** `list[dict]` — each dict has `paper_id` (int), `score` (float, cosine similarity), plus any fields from `metadata`.

#### `search_text(query, top_k=10, backend=None, model=None)`

Convenience method that embeds the query string first, then searches.

| Parameter | Type | Description |
|---|---|---|
| `query` | `str` | Natural language search query. |
| `top_k` | `int` | Number of results. |
| `backend` | `Backend \| None` | Embedding backend (must match the one used to build the index). |
| `model` | `str \| None` | Model override. |

**Returns:** `list[dict]` — same format as `search()`.

#### `save(path)` / `load(path)`

| Parameter | Type | Description |
|---|---|---|
| `path` | `str \| Path` | Directory to save/load from. Creates `index.faiss` and `metadata.json`. |

## TF-IDF Backend Details

The TF-IDF backend uses scikit-learn's `TfidfVectorizer` (5000 features,
English stop words removed) followed by `TruncatedSVD` for dimensionality
reduction. The model string encodes the target dimension:

- `"tfidf-svd-128"` → 128 dimensions (default)
- `"tfidf-svd-256"` → 256 dimensions

This backend requires no API keys and works offline, making it suitable for
CI/CD pipelines and memory-constrained environments.
