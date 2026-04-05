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


def compute_projections_3d(
    embeddings: np.ndarray,
    seed: int = 42,
) -> dict[str, np.ndarray]:
    """
    Compute 3D projections from embedding matrix.

    Parameters
    ----------
    embeddings : np.ndarray
        Matrix of shape (n_papers, dim).
    seed : int
        Random seed for reproducibility.

    Returns
    -------
    dict[str, np.ndarray]
        Keys "umap3d", "tsne3d", "pca3d", each mapping to (n_papers, 3) arrays.
    """
    n = embeddings.shape[0]
    results = {}

    # PCA-3D
    logger.info("Computing PCA-3D...")
    pca3 = PCA(n_components=3, random_state=seed)
    results["pca3d"] = pca3.fit_transform(embeddings)

    # t-SNE-3D
    logger.info("Computing t-SNE-3D...")
    perplexity = min(30, n - 1)
    tsne3 = TSNE(
        n_components=3,
        perplexity=perplexity,
        random_state=seed,
        metric="cosine",
    )
    results["tsne3d"] = tsne3.fit_transform(embeddings)

    # UMAP-3D
    logger.info("Computing UMAP-3D...")
    try:
        import umap

        reducer3 = umap.UMAP(
            n_components=3,
            n_neighbors=15,
            min_dist=0.1,
            random_state=seed,
            metric="cosine",
        )
        results["umap3d"] = reducer3.fit_transform(embeddings)
    except ImportError:
        logger.warning("umap-learn not installed; using t-SNE-3D fallback for UMAP-3D slot")
        results["umap3d"] = results["tsne3d"].copy()

    return results


def estimate_n_clusters(embeddings: np.ndarray, min_k: int = 5, max_k: int = 30, seed: int = 42) -> int:
    """
    Estimate optimal cluster count using silhouette score.

    Tests k from min_k to max_k and returns the k with highest silhouette.
    """
    from sklearn.metrics import silhouette_score

    n = embeddings.shape[0]
    max_k = min(max_k, n - 1)
    if max_k <= min_k:
        return min_k

    best_k, best_score = min_k, -1
    for k in range(min_k, max_k + 1, 2):  # step by 2 for speed
        kmeans = KMeans(n_clusters=k, random_state=seed, n_init=5, max_iter=100)
        labels = kmeans.fit_predict(embeddings)
        score = silhouette_score(embeddings, labels, sample_size=min(1000, n))
        logger.info("k=%d silhouette=%.3f", k, score)
        if score > best_score:
            best_score = score
            best_k = k

    logger.info("Optimal k=%d (silhouette=%.3f)", best_k, best_score)
    return best_k


def cluster_papers(
    embeddings: np.ndarray,
    texts: list[str],
    n_clusters: int | str = "auto",
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
    n_clusters : int or "auto"
        Number of clusters. "auto" uses silhouette-based estimation.
    seed : int
        Random seed.

    Returns
    -------
    tuple[np.ndarray, dict[int, str]]
        Cluster IDs array and {cluster_id: label} dict.
    """
    if n_clusters == "auto":
        n_clusters = estimate_n_clusters(embeddings, seed=seed)
        logger.info("Auto-detected %d clusters", n_clusters)
    else:
        n_clusters = int(n_clusters)

    kmeans = KMeans(n_clusters=n_clusters, random_state=seed, n_init=10)
    cluster_ids = kmeans.fit_predict(embeddings)

    # Generate labels from TF-IDF
    tfidf = TfidfVectorizer(max_features=500, stop_words="english")
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
