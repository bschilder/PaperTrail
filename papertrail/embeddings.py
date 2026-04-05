"""
Embedding module with multiple backends and FAISS vector store.

Supported backends (in order of recommendation):
  1. OpenAI  (text-embedding-3-small) — fast, high quality, remote
  2. HuggingFace Inference API        — free tier, remote
  3. fastembed (local ONNX)            — offline fallback
  4. tfidf   (scikit-learn TF-IDF + SVD) — lightweight, no API keys needed

Embeddings are stored in a FAISS index for fast similarity search.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Literal

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Backend registry
# ---------------------------------------------------------------------------

Backend = Literal["openai", "huggingface", "local", "tfidf"]

DEFAULT_MODELS: dict[Backend, str] = {
    "openai": "text-embedding-3-small",
    "huggingface": "BAAI/bge-small-en-v1.5",
    "local": "BAAI/bge-small-en-v1.5",
    "tfidf": "tfidf-svd-128",
}

DIMENSIONS: dict[str, int] = {
    "text-embedding-3-small": 1536,
    "text-embedding-3-large": 3072,
    "text-embedding-ada-002": 1536,
    "BAAI/bge-small-en-v1.5": 384,
    "BAAI/bge-base-en-v1.5": 768,
    "BAAI/bge-large-en-v1.5": 1024,
    "tfidf-svd-128": 128,
    "tfidf-svd-256": 256,
}


def _detect_backend() -> Backend:
    """Auto-detect the best available backend.

    Priority: OpenAI > HuggingFace > fastembed > TF-IDF (always available).
    """
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN"):
        return "huggingface"
    try:
        import fastembed  # noqa: F401
        return "local"
    except ImportError:
        pass
    # TF-IDF is always available via scikit-learn
    logger.info("No API keys or fastembed found; falling back to TF-IDF + SVD")
    return "tfidf"


# ---------------------------------------------------------------------------
# Embed functions per backend
# ---------------------------------------------------------------------------

def _embed_openai(texts: list[str], model: str) -> np.ndarray:
    """Embed via OpenAI API."""
    import openai

    client = openai.OpenAI()
    # OpenAI supports batches up to 2048 texts
    all_embeddings = []
    batch_size = 512
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        resp = client.embeddings.create(input=batch, model=model)
        all_embeddings.extend([d.embedding for d in resp.data])
    return np.array(all_embeddings, dtype=np.float32)


def _embed_huggingface(texts: list[str], model: str) -> np.ndarray:
    """Embed via HuggingFace Inference API."""
    import requests

    token = os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN")
    url = f"https://api-inference.huggingface.co/pipeline/feature-extraction/{model}"
    headers = {"Authorization": f"Bearer {token}"} if token else {}

    all_embeddings = []
    batch_size = 64
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        for attempt in range(3):
            resp = requests.post(url, json={"inputs": batch}, headers=headers, timeout=120)
            if resp.status_code == 503 and "loading" in resp.text.lower():
                logger.warning("Model is loading, retrying in 5s (attempt %d/3)", attempt + 1)
                import time
                time.sleep(5)
                continue
            resp.raise_for_status()
            all_embeddings.extend(resp.json())
            break
        else:
            resp.raise_for_status()  # raise on final failure
    return np.array(all_embeddings, dtype=np.float32)


def _embed_local(texts: list[str], model: str) -> np.ndarray:
    """Embed locally via fastembed (ONNX)."""
    from fastembed import TextEmbedding

    embedding_model = TextEmbedding(model)
    return np.array(list(embedding_model.embed(texts)), dtype=np.float32)


def _embed_tfidf(texts: list[str], model: str) -> np.ndarray:
    """Embed via TF-IDF + Truncated SVD (lightweight, no API keys).

    This is a fallback for environments without API keys or GPU.
    The model string encodes the SVD dimension, e.g. 'tfidf-svd-128'.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import TruncatedSVD

    # Parse dimension from model name
    n_components = 128
    if model and "svd-" in model:
        try:
            n_components = int(model.split("svd-")[1])
        except (ValueError, IndexError):
            pass

    logger.info("TF-IDF vectorizing %d texts → SVD(%d)", len(texts), n_components)
    vectorizer = TfidfVectorizer(max_features=5000, stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(texts)

    # Reduce dimensionality
    n_components = min(n_components, tfidf_matrix.shape[1] - 1, tfidf_matrix.shape[0] - 1)
    if n_components < 2:
        # Too few documents/features, just return dense TF-IDF
        return tfidf_matrix.toarray().astype(np.float32)

    svd = TruncatedSVD(n_components=n_components, random_state=42)
    reduced = svd.fit_transform(tfidf_matrix)
    logger.info("SVD explained variance: %.2f%%", svd.explained_variance_ratio_.sum() * 100)
    return reduced.astype(np.float32)


_EMBED_FNS = {
    "openai": _embed_openai,
    "huggingface": _embed_huggingface,
    "local": _embed_local,
    "tfidf": _embed_tfidf,
}


# ---------------------------------------------------------------------------
# Main embedding function
# ---------------------------------------------------------------------------

def embed_texts(
    texts: list[str],
    backend: Backend | None = None,
    model: str | None = None,
) -> np.ndarray:
    """
    Embed a list of texts using the specified (or auto-detected) backend.

    Parameters
    ----------
    texts : list[str]
        The texts to embed.
    backend : str, optional
        One of "openai", "huggingface", "local". Auto-detected if omitted.
    model : str, optional
        Model name override. Uses sensible defaults per backend.

    Returns
    -------
    np.ndarray
        Embedding matrix of shape (len(texts), dim).
    """
    if backend is None:
        backend = _detect_backend()
    if model is None:
        model = DEFAULT_MODELS[backend]

    logger.info("Embedding %d texts with %s / %s", len(texts), backend, model)
    embeddings = _EMBED_FNS[backend](texts, model)
    logger.info("Embedding shape: %s", embeddings.shape)
    return embeddings


def list_backends() -> list[dict[str, Any]]:
    """
    Return available embedding backends and their status.

    Returns
    -------
    list[dict]
        Each dict has keys: ``name``, ``available`` (bool), ``model``.
    """
    backends = []
    for name, model in DEFAULT_MODELS.items():
        available = False
        if name == "openai":
            available = bool(os.getenv("OPENAI_API_KEY"))
        elif name == "huggingface":
            available = bool(os.getenv("HF_TOKEN") or os.getenv("HUGGINGFACEHUB_API_TOKEN"))
        elif name == "local":
            try:
                import fastembed  # noqa: F401
                available = True
            except ImportError:
                pass
        elif name == "tfidf":
            available = True  # always available
        backends.append({"name": name, "available": available, "model": model})
    return backends


# ---------------------------------------------------------------------------
# FAISS vector store
# ---------------------------------------------------------------------------

class VectorStore:
    """
    FAISS-backed vector store for paper embeddings.

    Stores embeddings alongside paper metadata for fast similarity search
    and retrieval.

    Examples
    --------
    >>> store = VectorStore(dimension=384)
    >>> store.add(embeddings, paper_ids)
    >>> results = store.search("deep learning genomics", top_k=5)
    """

    def __init__(self, dimension: int | None = None):
        import faiss

        self.dimension = dimension
        self.index: Any = None
        self.paper_ids: list[int] = []
        self.metadata: dict[int, dict] = {}
        self._faiss = faiss

    def build(
        self,
        embeddings: np.ndarray,
        paper_ids: list[int],
        metadata: dict[int, dict] | None = None,
    ) -> None:
        """Build the FAISS index from embeddings."""
        self.dimension = embeddings.shape[1]
        # Normalize for cosine similarity via inner product
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        normalized = (embeddings / np.clip(norms, 1e-10, None)).astype(np.float32)

        if np.any(np.isnan(normalized)):
            logger.warning("NaN values detected in embeddings, replacing with zeros")
            normalized = np.nan_to_num(normalized)

        self.index = self._faiss.IndexFlatIP(self.dimension)
        self.index.add(normalized)
        self.paper_ids = list(paper_ids)
        if metadata:
            self.metadata = metadata
        logger.info(
            "FAISS index built: %d vectors, %d dimensions", len(paper_ids), self.dimension
        )

    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
    ) -> list[dict]:
        """
        Search for the top_k most similar papers.

        Parameters
        ----------
        query_embedding : np.ndarray
            Query vector of shape (dim,) or (1, dim).
        top_k : int
            Number of results to return.

        Returns
        -------
        list[dict]
            List of {paper_id, score, **metadata} dicts.
        """
        if self.index is None:
            raise RuntimeError("Index not built. Call build() first.")

        q = query_embedding.reshape(1, -1).astype(np.float32)
        q = q / np.linalg.norm(q)
        scores, indices = self.index.search(q, top_k)

        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            pid = self.paper_ids[idx]
            entry = {"paper_id": pid, "score": float(score)}
            if pid in self.metadata:
                entry.update(self.metadata[pid])
            results.append(entry)
        return results

    def search_text(
        self,
        query: str,
        top_k: int = 10,
        backend: Backend | None = None,
        model: str | None = None,
    ) -> list[dict]:
        """Search by text query — embeds the query then searches."""
        q_emb = embed_texts([query], backend=backend, model=model)
        return self.search(q_emb[0], top_k=top_k)

    def save(self, path: str | Path) -> None:
        """Save index + metadata to disk."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)
        self._faiss.write_index(self.index, str(path / "index.faiss"))
        with open(path / "metadata.json", "w") as f:
            json.dump(
                {"paper_ids": self.paper_ids, "dimension": self.dimension, "metadata": {str(k): v for k, v in self.metadata.items()}},
                f,
            )
        logger.info("Saved FAISS index to %s", path)

    def load(self, path: str | Path) -> None:
        """Load index + metadata from disk."""
        path = Path(path)
        self.index = self._faiss.read_index(str(path / "index.faiss"))
        with open(path / "metadata.json") as f:
            data = json.load(f)
        self.paper_ids = data["paper_ids"]
        self.dimension = data["dimension"]
        self.metadata = {int(k): v for k, v in data.get("metadata", {}).items()}
        logger.info("Loaded FAISS index: %d vectors", len(self.paper_ids))
