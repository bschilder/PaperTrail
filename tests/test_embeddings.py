"""Tests for the embeddings module."""

import numpy as np
import pytest


def test_vector_store_build_and_search():
    """Test FAISS vector store build and search."""
    pytest.importorskip("faiss")
    from papertrail.embeddings import VectorStore

    dim = 8
    n = 10
    rng = np.random.RandomState(42)
    embeddings = rng.randn(n, dim).astype(np.float32)
    paper_ids = list(range(n))
    metadata = {i: {"title": f"Paper {i}"} for i in range(n)}

    store = VectorStore(dimension=dim)
    store.build(embeddings, paper_ids, metadata)

    # Search with the first embedding — should return itself as top result
    results = store.search(embeddings[0], top_k=3)
    assert len(results) == 3
    assert results[0]["paper_id"] == 0
    assert results[0]["score"] > 0.9


def test_vector_store_save_load(tmp_path):
    """Test FAISS index persistence."""
    pytest.importorskip("faiss")
    from papertrail.embeddings import VectorStore

    dim = 4
    embeddings = np.eye(dim, dtype=np.float32)
    paper_ids = [10, 20, 30, 40]

    store = VectorStore()
    store.build(embeddings, paper_ids)
    store.save(tmp_path / "test_index")

    store2 = VectorStore()
    store2.load(tmp_path / "test_index")
    assert store2.paper_ids == paper_ids
    assert store2.dimension == dim
