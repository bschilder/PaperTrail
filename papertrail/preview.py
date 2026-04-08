"""
Build a self-contained interactive HTML dashboard for PaperTrail.

Features:
  - Sortable/filterable table view
  - Interactive 2D map view (d3.js) with UMAP/t-SNE/PCA projections
  - Color by cluster, channel, user, or date
  - Detail panel with full paper metadata
  - Chat panel with @user and #channel autocomplete
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TEMPLATE_PATH = Path(__file__).parent / "templates" / "dashboard.html"


def build_preview(
    papers: list[dict[str, Any]],
    output_path: str = "papertrail.html",
    title: str = "PaperTrail",
    slack_workspace_url: str | None = None,
) -> None:
    """
    Build the interactive HTML dashboard.

    Parameters
    ----------
    papers : list[dict]
        Enriched paper data with projections and clusters.
    output_path : str
        Where to write the HTML file.
    title : str
        Dashboard title.
    """
    # Prepare data payload
    channels = sorted({p.get("channel", "") for p in papers})
    users = sorted({p.get("shared_by", "") for p in papers})
    clusters = {}
    for p in papers:
        cid = str(p.get("cluster_id", 0))
        if cid not in clusters:
            clusters[cid] = {
                "label": p.get("cluster_label", f"Cluster {cid}"),
                "size": 0,
            }
        clusters[cid]["size"] += 1

    data = {
        "papers": papers,
        "embeddings": {
            proj: {
                "x": [p["projections"][proj][0] for p in papers],
                "y": [p["projections"][proj][1] for p in papers],
            }
            for proj in ["umap", "tsne", "pca"]
            if all("projections" in p and proj in p.get("projections", {}) for p in papers)
        },
        "clusters": clusters,
        "mentions": {"channels": channels, "users": users},
    }

    # Load template
    if TEMPLATE_PATH.exists():
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
    else:
        logger.warning("Template not found at %s, using inline template", TEMPLATE_PATH)
        template = _FALLBACK_TEMPLATE

    # Inject data — use proper encoding to avoid </script> issues
    import base64

    data_json = json.dumps(data, ensure_ascii=True)
    data_b64 = base64.b64encode(data_json.encode()).decode()

    html = template.replace("{{TITLE}}", title)
    html = html.replace("{{DATA_B64}}", data_b64)
    if slack_workspace_url:
        html = html.replace("{{SLACK_WORKSPACE_URL}}", slack_workspace_url)
    else:
        html = html.replace("{{SLACK_WORKSPACE_URL}}", "")

    # HF_TOKEN placeholder — never inject real tokens into static HTML
    # Users enter their key via the settings modal at runtime
    html = html.replace("{{HF_TOKEN}}", "")

    Path(output_path).write_text(html, encoding="utf-8")
    logger.info("Dashboard written to %s (%d KB)", output_path, len(html) // 1024)


_FALLBACK_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{{TITLE}}</title></head>
<body><h1>{{TITLE}}</h1>
<p>Template not found. Place dashboard.html in papertrail/templates/.</p>
<script>
const DATA = JSON.parse(atob("{{DATA_BASE64}}"));
console.log("Papers loaded:", DATA.papers.length);
</script></body></html>
"""
