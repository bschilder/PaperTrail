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

    if n <= 1:
        logger.warning("Only %d paper(s), returning zero projections", n)
        results["pca"] = np.zeros((n, 2))
        results["tsne"] = np.zeros((n, 2))
        results["umap"] = np.zeros((n, 2))
        return results

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
    perplexity = min(30, max(1, n - 1))
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

    if n <= 1:
        logger.warning("Only %d paper(s), returning zero 3D projections", n)
        results["pca3d"] = np.zeros((n, 3))
        results["tsne3d"] = np.zeros((n, 3))
        results["umap3d"] = np.zeros((n, 3))
        return results

    # PCA-3D
    logger.info("Computing PCA-3D...")
    pca3 = PCA(n_components=3, random_state=seed)
    results["pca3d"] = pca3.fit_transform(embeddings)

    # t-SNE-3D
    logger.info("Computing t-SNE-3D...")
    perplexity = min(30, max(1, n - 1))
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
    min_k = min(min_k, max(2, n - 1))
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
    papers: list[dict] | None = None,
    projections: dict[str, np.ndarray] | None = None,
    cluster_on_projections: bool = True,
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
    papers : list[dict], optional
        Paper dicts for LLM label generation.
    projections : dict[str, np.ndarray], optional
        2D projection arrays (e.g. {"umap": array, "tsne": array}).
    cluster_on_projections : bool
        If True and projections are available, cluster on the 2D
        projection (default: UMAP) instead of high-dimensional
        embeddings. This makes clusters align visually with the map.

    Returns
    -------
    tuple[np.ndarray, dict[int, str]]
        Cluster IDs array and {cluster_id: label} dict.
    """
    # Choose clustering input
    cluster_input = embeddings
    if cluster_on_projections and projections:
        # Prefer UMAP, fall back to t-SNE, then PCA
        for proj_key in ("umap", "tsne", "pca"):
            if proj_key in projections:
                cluster_input = projections[proj_key]
                logger.info("Clustering on %s projections (%d dims)", proj_key, cluster_input.shape[1])
                break

    if n_clusters == "auto":
        n_clusters = estimate_n_clusters(cluster_input, seed=seed)
        logger.info("Auto-detected %d clusters", n_clusters)
    else:
        n_clusters = int(n_clusters)

    kmeans = KMeans(n_clusters=n_clusters, random_state=seed, n_init=10)
    cluster_ids = kmeans.fit_predict(cluster_input)

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

    # Try LLM-based label refinement
    refined = refine_cluster_labels_llm(cluster_ids, labels, texts, papers=papers)
    if refined:
        labels = refined

    return cluster_ids, labels


def cluster_papers_hierarchical(
    embeddings: np.ndarray,
    texts: list[str],
    papers: list[dict] | None = None,
    projections: dict[str, np.ndarray] | None = None,
    levels: list[int] | None = None,
    seed: int = 42,
) -> list[dict]:
    """
    Compute hierarchical clusters at multiple zoom levels.

    Returns a list of level dicts, each with:
      - cluster_ids: np.ndarray of cluster assignments
      - labels: dict[int, str] of cluster labels
      - n_clusters: int
      - sizes: dict[int, int] of papers per cluster
      - centroids: dict[int, tuple[float, float]] of 2D centroids

    Parameters
    ----------
    levels : list[int], optional
        Number of clusters at each level. Defaults to [5, 12, 25].
    """
    if levels is None:
        n = embeddings.shape[0]
        # Scale levels to dataset size
        levels = [
            max(3, min(7, n // 200)),     # Level 0: broad topics
            max(8, min(15, n // 80)),      # Level 1: medium topics
            max(16, min(35, n // 30)),     # Level 2: fine-grained
        ]
    logger.info("Hierarchical clustering with levels: %s", levels)

    # Determine clustering input
    cluster_input = embeddings
    proj_key_used = None
    if projections:
        for proj_key in ("umap", "tsne", "pca"):
            if proj_key in projections:
                cluster_input = projections[proj_key]
                proj_key_used = proj_key
                break

    result_levels = []
    for level_idx, k in enumerate(levels):
        k = min(k, embeddings.shape[0] - 1)
        if k < 2:
            k = 2

        kmeans = KMeans(n_clusters=k, random_state=seed, n_init=10)
        cluster_ids = kmeans.fit_predict(cluster_input)

        # TF-IDF labels
        tfidf = TfidfVectorizer(max_features=500, stop_words="english")
        tfidf_matrix = tfidf.fit_transform(texts)
        feature_names = tfidf.get_feature_names_out()

        labels: dict[int, str] = {}
        for cid in range(k):
            mask = cluster_ids == cid
            if mask.sum() == 0:
                labels[cid] = f"Cluster {cid}"
                continue
            mean_tfidf = tfidf_matrix[mask].mean(axis=0).A1
            top_idx = mean_tfidf.argsort()[-3:][::-1]
            top_terms = [feature_names[i] for i in top_idx if mean_tfidf[i] > 0]
            labels[cid] = " / ".join(t.title() for t in top_terms) or f"Cluster {cid}"

        # LLM refinement
        refined = refine_cluster_labels_llm(cluster_ids, labels, texts, papers=papers)
        if refined:
            labels = refined

        # Compute 2D centroids for label placement
        centroids = {}
        proj_2d = projections.get(proj_key_used) if projections and proj_key_used else None
        if proj_2d is not None:
            for cid in range(k):
                mask = cluster_ids == cid
                if mask.sum() > 0:
                    cx = float(proj_2d[mask, 0].mean())
                    cy = float(proj_2d[mask, 1].mean())
                    centroids[cid] = (cx, cy)

        sizes = {cid: int((cluster_ids == cid).sum()) for cid in range(k)}

        result_levels.append({
            "cluster_ids": cluster_ids,
            "labels": labels,
            "n_clusters": k,
            "sizes": sizes,
            "centroids": centroids,
        })
        logger.info("Level %d: %d clusters — %s", level_idx, k, labels)

    return result_levels


def refine_cluster_labels_llm(
    cluster_ids: np.ndarray,
    tfidf_labels: dict[int, str],
    texts: list[str],
    papers: list[dict] | None = None,
) -> dict[int, str] | None:
    """
    Use an LLM to generate better cluster labels from sample titles.

    Tries HuggingFace (HF_TOKEN) first, falls back to OpenAI (OPENAI_API_KEY).
    Returns None if no LLM is available.
    """
    import os

    hf_token = os.environ.get("HF_TOKEN")
    openai_key = os.environ.get("OPENAI_API_KEY")

    if not hf_token and not openai_key:
        logger.info("No LLM token available, using TF-IDF cluster labels")
        return None

    # Build prompt with sample titles per cluster
    # Prefer actual paper titles over raw text (which may be just URLs)
    cluster_info = []
    for cid, label in sorted(tfidf_labels.items()):
        mask = cluster_ids == cid
        indices = np.where(mask)[0]
        samples = []
        for idx in indices:
            if len(samples) >= 8:
                break
            # Try paper title first, fall back to text
            title = None
            if papers and idx < len(papers):
                t = papers[idx].get("title", "")
                if t and t != "Unknown Title" and len(t) > 10:
                    title = t[:120]
            if not title:
                t = texts[idx].split(".")[0].strip()[:100]
                if t and len(t) > 10 and not t.startswith("http"):
                    title = t
            if title:
                samples.append(title)
        if not samples:
            samples = ["(no titled papers in this cluster)"]
        cluster_info.append(f"Cluster {cid} ({int(mask.sum())} papers, TF-IDF: \"{label}\"):\n  " + "\n  ".join(samples[:6]))

    prompt = (
        "You are labeling topic clusters of academic papers. "
        "For each cluster below, generate a short (2-4 word) descriptive topic label "
        "based on the sample paper titles. Output ONLY a JSON object mapping cluster ID to label, nothing else.\n\n"
        + "\n\n".join(cluster_info)
    )

    try:
        import json as _json
        import requests

        if hf_token:
            logger.info("Generating cluster labels via HuggingFace LLM...")
            resp = requests.post(
                "https://router.huggingface.co/v1/chat/completions",
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {hf_token}"},
                json={
                    "model": "Qwen/Qwen3-8B",
                    "messages": [{"role": "user", "content": prompt + "\n\n/no_think"}],
                    "max_tokens": 512,
                },
                timeout=60,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]
        else:
            logger.info("Generating cluster labels via OpenAI...")
            resp = requests.post(
                "https://api.openai.com/v1/chat/completions",
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {openai_key}"},
                json={
                    "model": "gpt-4o-mini",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 512,
                },
                timeout=60,
            )
            resp.raise_for_status()
            content = resp.json()["choices"][0]["message"]["content"]

        # Strip thinking tags and parse JSON
        import re
        content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
        content = re.sub(r"<think>[\s\S]*", "", content).strip()
        # Extract JSON from markdown code block if present
        json_match = re.search(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", content)
        if json_match:
            content = json_match.group(1)

        refined = _json.loads(content)
        labels = {int(k): str(v) for k, v in refined.items()}
        logger.info("LLM cluster labels: %s", labels)
        return labels

    except Exception as e:
        logger.warning("LLM cluster labeling failed: %s, using TF-IDF labels", e)
        return None
