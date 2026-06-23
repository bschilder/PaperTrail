#!/usr/bin/env python3
"""Build the PaperTrail lab-picker landing page.

Reads every ``config/*.yml`` workspace config, derives its slug (the same way
``pipeline.yml`` does — from ``slack_workspace_url``), counts papers from the
matching ``data/<slug>/papers_final.json`` if present, and writes a single
self-contained ``index.html`` that links to each workspace dashboard.

Usage:
    python scripts/build_landing.py --out vercel_site/index.html
"""

from __future__ import annotations

import argparse
import glob
import html
import json
from pathlib import Path

import yaml


def slug_from_config(cfg: dict, fallback: str) -> str:
    """Derive a workspace slug from the Slack workspace URL.

    Mirrors the logic in ``.github/workflows/pipeline.yml`` so the landing
    page links resolve to the same ``site/<slug>/`` directories the pipeline
    publishes.
    """
    url = cfg.get("slack_workspace_url", "")
    if "//" in url:
        return url.split("//")[1].split(".")[0]
    return fallback


def paper_count(slug: str) -> int | None:
    """Return the number of papers in ``data/<slug>/papers_final.json``."""
    path = Path("data") / slug / "papers_final.json"
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return len(json.load(f))
    except (json.JSONDecodeError, OSError):
        return None


def discover_workspaces(config_glob: str = "config/*.yml") -> list[dict]:
    workspaces = []
    for cfg_path in sorted(glob.glob(config_glob)):
        with open(cfg_path) as f:
            cfg = yaml.safe_load(f) or {}
        slug = slug_from_config(cfg, Path(cfg_path).stem)
        workspaces.append(
            {
                "slug": slug,
                "title": cfg.get("title", slug),
                "workspace_url": cfg.get("slack_workspace_url", ""),
                "count": paper_count(slug),
            }
        )
    return workspaces


def render(workspaces: list[dict]) -> str:
    cards = []
    for ws in workspaces:
        title = html.escape(ws["title"])
        slug = html.escape(ws["slug"], quote=True)
        count = ws["count"]
        count_str = f"{count:,} papers" if count is not None else "dashboard"
        cards.append(
            f"""      <a class="card" href="./{slug}/">
        <div class="card-title">{title}</div>
        <div class="card-meta">{count_str}</div>
        <div class="card-go">Open dashboard &rarr;</div>
      </a>"""
        )
    cards_html = "\n".join(cards)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>PaperTrail</title>
  <style>
    :root {{ color-scheme: dark; }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
      background: #0f0f17;
      color: #e0e0e0;
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 2rem 1.5rem;
    }}
    .hero {{ text-align: center; margin-bottom: 2.5rem; }}
    .logo {{ font-size: 3rem; margin-bottom: 0.5rem; }}
    h1 {{
      font-size: 2.25rem;
      font-weight: 700;
      background: linear-gradient(135deg, #64b5f6, #4a80d0);
      -webkit-background-clip: text;
      background-clip: text;
      -webkit-text-fill-color: transparent;
    }}
    .tagline {{ color: #a0a0b0; margin-top: 0.5rem; font-size: 1.05rem; }}
    .cards {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
      gap: 1.25rem;
      width: 100%;
      max-width: 720px;
    }}
    .card {{
      display: block;
      text-decoration: none;
      color: inherit;
      background: linear-gradient(135deg, #252540, #2a2a45);
      border: 1px solid #3a3a50;
      border-radius: 14px;
      padding: 1.5rem 1.5rem 1.25rem;
      transition: transform 0.15s ease, border-color 0.15s ease, box-shadow 0.15s ease;
    }}
    .card:hover {{
      transform: translateY(-3px);
      border-color: #64b5f6;
      box-shadow: 0 8px 28px rgba(100, 181, 246, 0.18);
    }}
    .card-title {{ font-size: 1.3rem; font-weight: 600; color: #fff; }}
    .card-meta {{ color: #64b5f6; margin-top: 0.4rem; font-size: 0.95rem; }}
    .card-go {{ color: #a0a0b0; margin-top: 1rem; font-size: 0.9rem; }}
    footer {{ margin-top: 2.5rem; color: #6a6a7a; font-size: 0.85rem; text-align: center; }}
    footer a {{ color: #64b5f6; text-decoration: none; }}
  </style>
</head>
<body>
  <div class="hero">
    <div class="logo">&#128218;</div>
    <h1>PaperTrail</h1>
    <p class="tagline">Interactive maps of papers shared across our Slack workspaces</p>
  </div>
  <div class="cards">
{cards_html}
  </div>
  <footer>
    Updated weekly &middot; <a href="https://github.com/bschilder/PaperTrail">github.com/bschilder/PaperTrail</a>
  </footer>
</body>
</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the PaperTrail landing page.")
    parser.add_argument("--out", default="vercel_site/index.html", help="Output HTML path.")
    parser.add_argument("--config-glob", default="config/*.yml", help="Glob for workspace configs.")
    args = parser.parse_args()

    workspaces = discover_workspaces(args.config_glob)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(render(workspaces))
    print(f"Wrote landing page with {len(workspaces)} workspace(s) -> {out}")
    for ws in workspaces:
        print(f"  - {ws['slug']}: {ws['title']} ({ws['count']} papers)")


if __name__ == "__main__":
    main()
