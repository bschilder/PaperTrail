"""
PaperTrail automated pipeline — scrape, enrich, embed, build.

Reads config.yml for channel list and settings. Designed to run
in GitHub Actions or locally via `papertrail run-pipeline`.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.yml") -> dict:
    """Load pipeline configuration from YAML file."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")
    with open(path) as f:
        return yaml.safe_load(f)


def run_pipeline(
    config_path: str = "config.yml",
    output_dir: str = "build",
    skip_scrape: bool = False,
    data_file: str | None = None,
) -> Path:
    """
    Run the full PaperTrail pipeline.

    Parameters
    ----------
    config_path : str
        Path to config.yml.
    output_dir : str
        Directory for intermediate and final outputs.
    skip_scrape : bool
        If True, skip scraping and use existing data_file.
    data_file : str or None
        Path to existing papers JSON to use instead of scraping.

    Returns
    -------
    Path
        Path to the built dashboard HTML file.
    """
    import os
    import sys

    # Ensure logs are flushed immediately in CI
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s", stream=sys.stderr, force=True)

    config = load_config(config_path)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    logger.info("Pipeline started — output_dir=%s, skip_scrape=%s", output_dir, skip_scrape)

    raw_path = out / "papers_raw.json"
    enriched_path = out / "papers_enriched.json"
    final_path = out / "papers_final.json"
    dashboard_path = out / "dashboard.html"

    # ── Step 1: Scrape ──────────────────────────────────────────
    if skip_scrape and data_file:
        logger.info("Skipping scrape, using %s", data_file)
        with open(data_file) as f:
            all_papers = json.load(f)
    elif skip_scrape and raw_path.exists():
        logger.info("Skipping scrape, using existing %s", raw_path)
        with open(raw_path) as f:
            all_papers = json.load(f)
    else:
        from papertrail.scraper import SlackPaperScraper

        token = os.environ.get("SLACK_BOT_TOKEN")
        if not token:
            raise RuntimeError("SLACK_BOT_TOKEN not set")

        channels = config.get("channels", {})
        if not channels:
            raise RuntimeError("No channels configured in config.yml")

        scraper = SlackPaperScraper(token=token)
        all_papers = []

        for name, channel_id in channels.items():
            logger.info("Scraping #%s (%s)...", name, channel_id)
            try:
                papers = scraper.scrape_channel(channel_id, include_replies=True)
            except Exception as e:
                logger.error("Error scraping #%s: %s — skipping", name, e)
                continue
            for p in papers:
                all_papers.append({
                    "channel": p.channel_name,
                    "shared_by": p.shared_by,
                    "timestamp": p.timestamp,
                    "slack_link": p.permalink,
                    "url": p.paper_url,
                    "text": p.message_text,
                    "reactions_count": p.reactions_count,
                    "reply_count": p.reply_count,
                    "reaction_details": p.reaction_details,
                })
            logger.info("  → %d papers from #%s", len(papers), name)

        # Deduplicate by URL
        seen = set()
        deduped = []
        for p in all_papers:
            if p["url"] not in seen:
                seen.add(p["url"])
                deduped.append(p)
            else:
                # Merge channels for duplicates
                for existing in deduped:
                    if existing["url"] == p["url"]:
                        if p["channel"] != existing["channel"]:
                            existing.setdefault("channels", [existing["channel"]])
                            if p["channel"] not in existing["channels"]:
                                existing["channels"].append(p["channel"])
                        break
        all_papers = deduped
        logger.info("Total: %d unique papers after dedup", len(all_papers))

        with open(raw_path, "w") as f:
            json.dump(all_papers, f, indent=2)

    # ── Step 2: Enrich ──────────────────────────────────────────
    logger.info("Enriching %d papers...", len(all_papers))
    from papertrail.enricher import enrich_paper

    for paper in all_papers:
        if paper.get("title") and paper.get("abstract"):
            continue  # Already enriched
        metadata = enrich_paper(paper["url"])
        paper.update(metadata)

    # Fill missing metadata via OpenAlex title search
    from papertrail.enricher import fill_missing_metadata

    email = os.environ.get("OPENALEX_EMAIL") or config.get("openalex_email", "papertrail@example.com")
    fill_count = fill_missing_metadata(all_papers, email=email)
    logger.info("Enriched %d additional papers via title search", fill_count)

    with open(enriched_path, "w") as f:
        json.dump(all_papers, f, indent=2)

    # ── Step 3: Embed ───────────────────────────────────────────
    logger.info("Computing embeddings...")
    import numpy as np
    from papertrail.embeddings import embed_texts
    from papertrail.projections import (
        cluster_papers,
        compute_projections,
        compute_projections_3d,
    )

    texts = []
    for p in all_papers:
        parts = [p.get("title", ""), p.get("abstract", ""), p.get("text", "")]
        texts.append(" ".join(part for part in parts if part))

    backend = config.get("embedding_backend", None)
    embeddings = embed_texts(texts, backend=backend)

    # 2D + 3D projections
    projections = compute_projections(embeddings)
    projections_3d = compute_projections_3d(embeddings)

    # Cluster
    cluster_ids, cluster_labels = cluster_papers(embeddings, texts, n_clusters="auto")

    for i, p in enumerate(all_papers):
        p["projections"] = {
            k: [float(v[i, 0]), float(v[i, 1])] for k, v in projections.items()
        }
        for k, v in projections_3d.items():
            p["projections"][k] = [float(v[i, 0]), float(v[i, 1]), float(v[i, 2])]
        p["cluster_id"] = int(cluster_ids[i])
        p["cluster_label"] = cluster_labels[int(cluster_ids[i])]

    with open(final_path, "w") as f:
        json.dump(all_papers, f, indent=2)
    logger.info("Embedded %d papers → %s", len(all_papers), final_path)

    # ── Step 4: Build Dashboard ─────────────────────────────────
    logger.info("Building dashboard...")
    from papertrail.preview import build_preview

    title = config.get("title", "PaperTrail")
    slack_url = config.get("slack_workspace_url")
    build_preview(
        all_papers,
        output_path=str(dashboard_path),
        title=title,
        slack_workspace_url=slack_url,
    )
    logger.info("Dashboard → %s (%d KB)", dashboard_path, dashboard_path.stat().st_size // 1024)

    return dashboard_path
