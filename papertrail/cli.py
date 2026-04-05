"""
PaperTrail CLI — Every paper your team shares, found and mapped.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import click

from papertrail import __version__

logger = logging.getLogger("papertrail")


@click.group()
@click.version_option(version=__version__)
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
def main(verbose: bool) -> None:
    """PaperTrail — Every paper your team shares, found and mapped."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")


@main.command()
@click.option("--token", envvar="SLACK_BOT_TOKEN", help="Slack Bot Token.")
@click.option("--channel", "-c", required=True, help="Slack channel ID to scrape.")
@click.option("--output", "-o", default="papers_raw.json", help="Output JSON path.")
@click.option("--engagement/--no-engagement", default=True, help="Fetch engagement metrics.")
def scrape(token: str, channel: str, output: str, engagement: bool) -> None:
    """Scrape papers from a Slack channel."""
    from papertrail.scraper import SlackPaperScraper

    if not token:
        raise click.ClickException("Set SLACK_BOT_TOKEN or pass --token.")

    scraper = SlackPaperScraper(token=token)
    papers = scraper.scrape_channel(channel, include_replies=engagement)

    data = [
        {
            "channel": p.channel_name,
            "shared_by": p.shared_by,
            "timestamp": p.timestamp,
            "slack_link": p.permalink,
            "url": p.paper_url,
            "text": p.message_text,
            "reactions_count": p.reactions_count,
            "reply_count": p.reply_count,
            "reaction_details": p.reaction_details,
        }
        for p in papers
    ]

    with open(output, "w") as f:
        json.dump(data, f, indent=2)
    click.echo(f"Scraped {len(data)} papers → {output}")


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", default="papers_enriched.json", help="Output JSON path.")
def enrich(input_file: str, output: str) -> None:
    """Enrich scraped papers with metadata from Semantic Scholar & OpenAlex."""
    from tqdm import tqdm

    from papertrail.enricher import enrich_paper

    with open(input_file) as f:
        papers = json.load(f)

    for paper in tqdm(papers, desc="Enriching"):
        metadata = enrich_paper(paper["url"])
        paper.update(metadata)

    with open(output, "w") as f:
        json.dump(papers, f, indent=2)
    click.echo(f"Enriched {len(papers)} papers → {output}")


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", default="papers_embedded.json", help="Output JSON path.")
@click.option(
    "--backend",
    type=click.Choice(["openai", "huggingface", "local", "tfidf"]),
    default=None,
    help="Embedding backend (auto-detected if omitted).",
)
@click.option("--model", default=None, help="Model name override.")
@click.option("--n-clusters", default="auto", help="Number of clusters ('auto' for silhouette-based).")
@click.option("--faiss-dir", default="faiss_index", help="FAISS index output directory.")
def embed(
    input_file: str,
    output: str,
    backend: str | None,
    model: str | None,
    n_clusters: str | int,
    faiss_dir: str,
) -> None:
    """Compute embeddings, projections, clusters, and build FAISS index."""
    import numpy as np
    from tqdm import tqdm

    from papertrail.embeddings import VectorStore, embed_texts
    from papertrail.projections import cluster_papers, compute_projections, compute_projections_3d

    with open(input_file) as f:
        papers = json.load(f)

    click.echo(f"Processing {len(papers)} papers...")

    # Build text representations
    texts = []
    for p in tqdm(papers, desc="Building texts"):
        parts = [p.get("title", ""), p.get("abstract", ""), p.get("text", "")]
        texts.append(" ".join(part for part in parts if part))

    # Embed
    embeddings = embed_texts(texts, backend=backend, model=model)

    # Project (2D + 3D)
    projections = compute_projections(embeddings)
    click.echo("Computing 3D projections...")
    projections_3d = compute_projections_3d(embeddings)

    # Cluster
    cluster_ids, cluster_labels = cluster_papers(
        embeddings, texts, n_clusters=n_clusters
    )

    # Update papers
    for i, p in enumerate(papers):
        p["projections"] = {
            k: [float(v[i, 0]), float(v[i, 1])] for k, v in projections.items()
        }
        # Add 3D projections
        for k, v in projections_3d.items():
            p["projections"][k] = [float(v[i, 0]), float(v[i, 1]), float(v[i, 2])]
        p["cluster_id"] = int(cluster_ids[i])
        p["cluster_label"] = cluster_labels[int(cluster_ids[i])]

    # Build FAISS index
    store = VectorStore()
    metadata = {i: {"title": p.get("title", ""), "url": p.get("url", "")} for i, p in enumerate(papers)}
    store.build(embeddings, list(range(len(papers))), metadata)
    store.save(faiss_dir)

    # Save
    with open(output, "w") as f:
        json.dump(papers, f, indent=2)

    click.echo(f"Embedded {len(papers)} papers → {output}")
    click.echo(f"FAISS index → {faiss_dir}/")
    click.echo(f"Clusters: {len(set(cluster_ids))}")


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", default="papertrail.html", help="Output HTML path.")
@click.option("--title", default="PaperTrail", help="Dashboard title.")
def build(input_file: str, output: str, title: str) -> None:
    """Build the interactive HTML dashboard."""
    from papertrail.preview import build_preview

    with open(input_file) as f:
        papers = json.load(f)

    build_preview(papers, output_path=output, title=title)
    click.echo(f"Dashboard → {output}")


@main.command()
@click.argument("input_file", type=click.Path(exists=True))
@click.option("--output", "-o", default=None, help="Output JSON path (default: overwrite input).")
@click.option("--email", default="papertrail@example.com", help="Email for OpenAlex polite pool.")
def fill(input_file: str, output: str | None, email: str) -> None:
    """Fill missing metadata using OpenAlex title search."""
    from papertrail.enricher import fill_missing_metadata

    with open(input_file) as f:
        papers = json.load(f)

    click.echo(f"Filling metadata for {len(papers)} papers...")
    count = fill_missing_metadata(papers, email=email)

    out = output or input_file
    with open(out, "w") as f:
        json.dump(papers, f, indent=2)
    click.echo(f"Enriched {count} papers → {out}")


@main.command()
@click.option("--query", "-q", prompt="Search query", help="Text to search for.")
@click.option("--faiss-dir", default="faiss_index", help="FAISS index directory.")
@click.option("--top-k", "-k", default=5, help="Number of results.")
@click.option("--backend", default=None, help="Embedding backend.")
def search(query: str, faiss_dir: str, top_k: int, backend: str | None) -> None:
    """Search papers by semantic similarity."""
    from papertrail.embeddings import VectorStore

    store = VectorStore()
    store.load(faiss_dir)
    results = store.search_text(query, top_k=top_k, backend=backend)

    for i, r in enumerate(results, 1):
        click.echo(f"{i}. [{r['score']:.3f}] {r.get('title', 'Unknown')}")
        click.echo(f"   {r.get('url', '')}")


@main.command()
@click.option("--tag", default=None, help="Release tag (default: latest).")
@click.option("--data-dir", default=None, help="Download directory.")
@click.option("--force", is_flag=True, help="Re-download existing files.")
def download(tag: str | None, data_dir: str | None, force: bool) -> None:
    """Download paper data from a GitHub Release."""
    from papertrail.data import download_release

    dest = download_release(tag=tag, data_dir=data_dir, force=force)
    click.echo(f"Data downloaded → {dest}")


@main.command()
def releases() -> None:
    """List available data releases on GitHub."""
    from papertrail.data import list_releases

    rels = list_releases()
    if not rels:
        click.echo("No data releases found.")
        return
    for r in rels:
        n_assets = len(r["assets"])
        click.echo(f"  {r['tag']}  ({r['date']})  {n_assets} assets  {r['description']}")


if __name__ == "__main__":
    main()
