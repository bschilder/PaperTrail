"""
Dimensionality reduction and clustering for paper embeddings.

Computes UMAP, t-SNE, and PCA projections from high-dimensional
embeddings, plus content-based clustering with auto-generated labels.
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.manifold import TSNE

logger = logging.getLogger(__name__)


def compute_projections(
    embeddings: np.ndarray,
    seed: int = 42,
) -> dict[str, np.ndarray]:
    """
    Compute 2D projections from embedding matrix.

    Parameters
    ----------
    embeddings : np.ndarray
        Matrix of shape (n_papers, dim).
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    dict[str, np.ndarray]
        Keys "umap", "tsne", "pca", each mapping to (n_papers, 2) arrays.
    """
    n = embeddings.shape[0]
    results = {}

    # PCA
    logger.info("Computing PCA...")
    pca = PCA(n_components=2, random_state=seed)
    results["pca"] = pca.fit_transform(embeddings)
    logger.info(
        "PCA variance explained: %.1f%%",
        sum(pca.explained_variance_ratio_) * 100,
    )

    # t-SNE
    logger.info("Computing t-SNE...")
    perplexity = min(30, n - 1)
    if perplexity < 5:
        logger.warning("t-SNE perplexity is very low (%d). Results may be unreliable with so few samples.", perplexity)
    tsne = TSNE(
        n_components=2,
        perplexity=perplexity,
        random_state=seed,
        metric="cosine",
    )
    results["tsne"] = tsne.fit_transform(embeddings)

    # UMAP
    logger.info("Computing UMAP...")
    try:
        import umap

        reducer = umap.UMAP(
            n_components=2,
            n_neighbors=15,
            min_dist=0.1,
            random_state=seed,
            metric="cosine",
        )
        results["umap"] = reducer.fit_transform(embeddings)
    except ImportError:
        logger.warning("umap-learn not installed; using t-SNE fallback for UMAP slot")
        tsne_alt = TSNE(
            n_components=2,
            perplexity=min(15, n - 1),
            random_state=seed + 1,
            metric="cosine",
        )
        results["umap"] = tsne_alt.fit_transform(embeddings)

    return results


def cluster_papers(
    embeddings: np.ndarray,
    texts: list[str],
    n_clusters: int = 10,
    seed: int = 42,
) -> tuple[np.ndarray, dict[int, str]]:
    """
    Cluster papers and generate labels from TF-IDF top terms.

    Parameters
    ----------
    embeddings : np.ndarray
        Embedding matrix.
    texts : list[str]
        Paper texts for label generation.
    n_clusters : int
        Number of clusters.
    seed : int
        Random seed.

    Returns
    -------
    tuple[np.ndarray, dict[int, str]]
        Cluster IDs array and {cluster_id: label} dict.
    """
    kmeans = KMeans(n_clusters=n_clusters, random_state=seed, n_init=10)
    cluster_ids = kmeans.fit_predict(embeddings)

    # Generate labels from TF-IDF
    tfidf = TfidfVectorizer(max_features=200, stop_words="english")
    tfidf_matrix = tfidf.fit_transform(texts)
    feature_names = tfidf.get_feature_names_out()

    labels: dict[int, str] = {}
    for cid in range(n_clusters):
        mask = cluster_ids == cid
        if mask.sum() == 0:
            labels[cid] = f"Cluster {cid}"
            continue
        mean_tfidf = tfidf_matrix[mask].mean(axis=0).A1
        top_idx = mean_tfidf.argsort()[-3:][::-1]
        top_terms = [feature_names[i] for i in top_idx if mean_tfidf[i] > 0]
        labels[cid] = " / ".join(t.title() for t in top_terms) or f"Cluster {cid}"

    return cluster_ids, labels
