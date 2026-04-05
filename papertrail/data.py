"""
Download and manage PaperTrail data from GitHub Releases.

Provides helper functions to fetch pre-scraped paper datasets from
the PaperTrail GitHub repository releases, decompress them, and
load them into Python for immediate use.

Example
-------
>>> from papertrail.data import load_papers, download_release
>>> # Download latest release data (auto-detects most recent)
>>> download_release()
>>> papers = load_papers()
>>> print(f"Loaded {len(papers)} papers")

>>> # Download a specific release
>>> download_release(tag="v0.1.0-data-2026-04-04")

>>> # List available releases
>>> from papertrail.data import list_releases
>>> for r in list_releases():
...     print(r["tag"], r["date"], r["description"])
"""

from __future__ import annotations

import gzip
import json
import logging
import os
import shutil
import sys
import tarfile
from pathlib import Path
from typing import Any, Optional
from urllib.parse import urljoin

import requests

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

GITHUB_REPO = "bschilder/PaperTrail"
GITHUB_API = "https://api.github.com"
DEFAULT_DATA_DIR = Path.home() / ".papertrail" / "data"

# Known asset filenames and their descriptions
KNOWN_ASSETS = {
    "all_papers_merged.json.gz": {
        "description": "Merged & deduplicated papers from all channels",
        "type": "papers",
        "compressed": True,
    },
    "enrich_checkpoint.json.gz": {
        "description": "Partially enriched papers with metadata",
        "type": "enriched",
        "compressed": True,
    },
    "channel_scrapes.tar.gz": {
        "description": "Per-channel raw scrape files",
        "type": "scrapes",
        "compressed": True,
    },
    "papers_enriched.json.gz": {
        "description": "Fully enriched papers",
        "type": "enriched",
        "compressed": True,
    },
    "papers_final.json.gz": {
        "description": "Final papers with embeddings and clusters",
        "type": "final",
        "compressed": True,
    },
}


def _get_headers() -> dict[str, str]:
    """Build request headers, including GitHub token if available."""
    headers = {"Accept": "application/vnd.github+json"}
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


# ---------------------------------------------------------------------------
# Release discovery
# ---------------------------------------------------------------------------


def list_releases(
    repo: str = GITHUB_REPO,
    data_only: bool = True,
) -> list[dict[str, Any]]:
    """
    List available data releases from the GitHub repository.

    Parameters
    ----------
    repo : str
        GitHub repository in ``owner/name`` format.
    data_only : bool
        If True, only return releases whose tag contains ``data``
        (filters out code-only releases).

    Returns
    -------
    list[dict]
        Each dict has keys: ``tag``, ``date``, ``description``,
        ``assets`` (list of filenames), ``url`` (HTML URL).
    """
    url = f"{GITHUB_API}/repos/{repo}/releases"
    resp = requests.get(url, headers=_get_headers(), timeout=15)
    resp.raise_for_status()

    releases = []
    for r in resp.json():
        tag = r.get("tag_name", "")
        if data_only and "data" not in tag:
            continue
        releases.append({
            "tag": tag,
            "date": r.get("published_at", "")[:10],
            "description": r.get("name", ""),
            "assets": [a["name"] for a in r.get("assets", [])],
            "url": r.get("html_url", ""),
            "api_url": r.get("url", ""),
        })

    return releases


def get_latest_release(repo: str = GITHUB_REPO) -> Optional[dict[str, Any]]:
    """
    Get the most recent data release.

    Parameters
    ----------
    repo : str
        GitHub repository in ``owner/name`` format.

    Returns
    -------
    dict or None
        Release info dict (same format as ``list_releases``), or
        None if no data releases exist.
    """
    releases = list_releases(repo=repo, data_only=True)
    return releases[0] if releases else None


# ---------------------------------------------------------------------------
# Download
# ---------------------------------------------------------------------------


def download_release(
    tag: Optional[str] = None,
    data_dir: Optional[str | Path] = None,
    repo: str = GITHUB_REPO,
    assets: Optional[list[str]] = None,
    force: bool = False,
) -> Path:
    """
    Download release assets from GitHub and decompress them.

    Parameters
    ----------
    tag : str, optional
        Release tag (e.g. ``"v0.1.0-data-2026-04-04"``). If None,
        downloads the latest data release.
    data_dir : str or Path, optional
        Directory to store downloaded files. Defaults to
        ``~/.papertrail/data/{tag}/``.
    repo : str
        GitHub repository in ``owner/name`` format.
    assets : list[str], optional
        Specific asset filenames to download. If None, downloads all
        assets in the release.
    force : bool
        If True, re-download even if files already exist locally.

    Returns
    -------
    Path
        Directory containing the downloaded (and decompressed) files.

    Raises
    ------
    ValueError
        If no matching release is found.
    requests.HTTPError
        If a download fails.
    """
    # Resolve tag
    if tag is None:
        latest = get_latest_release(repo=repo)
        if latest is None:
            raise ValueError(f"No data releases found in {repo}")
        tag = latest["tag"]
        logger.info("Using latest release: %s", tag)

    # Resolve data directory
    if data_dir is None:
        data_dir = DEFAULT_DATA_DIR / tag
    else:
        data_dir = Path(data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    # Fetch release info
    url = f"{GITHUB_API}/repos/{repo}/releases/tags/{tag}"
    resp = requests.get(url, headers=_get_headers(), timeout=15)
    resp.raise_for_status()
    release = resp.json()

    release_assets = release.get("assets", [])
    if not release_assets:
        raise ValueError(f"Release {tag} has no assets")

    # Filter assets if specified
    if assets:
        release_assets = [a for a in release_assets if a["name"] in assets]

    downloaded = []
    for asset in release_assets:
        name = asset["name"]
        download_url = asset["browser_download_url"]
        dest = data_dir / name

        # Skip if already downloaded
        if dest.exists() and not force:
            logger.info("Already exists: %s", dest)
            downloaded.append(dest)
            continue

        logger.info("Downloading %s ...", name)
        resp = requests.get(download_url, stream=True, timeout=60)
        resp.raise_for_status()

        total_size = int(resp.headers.get("content-length", 0))
        if tqdm is not None and total_size > 0:
            with open(dest, "wb") as f, tqdm(
                total=total_size, unit="B", unit_scale=True, desc=name
            ) as pbar:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
                    pbar.update(len(chunk))
        else:
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=8192):
                    f.write(chunk)
        downloaded.append(dest)
        logger.info("Saved %s (%d KB)", dest, dest.stat().st_size // 1024)

    # Decompress
    for path in downloaded:
        _decompress(path, data_dir)

    logger.info("All files saved to %s", data_dir)
    return data_dir


def _decompress(path: Path, dest_dir: Path) -> None:
    """Decompress a .gz or .tar.gz file in place."""
    name = path.name

    if name.endswith(".tar.gz") or name.endswith(".tgz"):
        logger.info("Extracting %s ...", name)
        with tarfile.open(path, "r:gz") as tar:
            if sys.version_info >= (3, 12):
                tar.extractall(dest_dir, filter="data")
            else:
                tar.extractall(dest_dir)

    elif name.endswith(".json.gz"):
        out_path = dest_dir / name.replace(".gz", "")
        if out_path.exists():
            return
        logger.info("Decompressing %s ...", name)
        with gzip.open(path, "rb") as gz_in:
            with open(out_path, "wb") as f_out:
                shutil.copyfileobj(gz_in, f_out)


# ---------------------------------------------------------------------------
# Load
# ---------------------------------------------------------------------------


def load_papers(
    data_dir: Optional[str | Path] = None,
    tag: Optional[str] = None,
    which: str = "merged",
) -> list[dict[str, Any]]:
    """
    Load papers from a downloaded release.

    Parameters
    ----------
    data_dir : str or Path, optional
        Directory containing downloaded data files. If None, uses
        ``~/.papertrail/data/{tag}/``.
    tag : str, optional
        Release tag. Used to locate the data directory if ``data_dir``
        is not specified. If both are None, uses the latest release.
    which : str
        Which dataset to load:

        - ``"merged"`` — raw merged papers (``all_papers_merged.json``)
        - ``"enriched"`` — papers with metadata (``enrich_checkpoint.json``
          or ``papers_enriched.json``)
        - ``"final"`` — papers with embeddings (``papers_final.json``)
        - ``"scrapes"`` — per-channel scrapes (returns a dict of
          ``{filename: data}``)

    Returns
    -------
    list[dict] or dict
        Paper records. For ``which="scrapes"``, returns a dict mapping
        filenames to their contents.

    Raises
    ------
    FileNotFoundError
        If the data directory or expected files don't exist.
        Suggests running ``download_release()`` first.
    """
    # Resolve directory
    if data_dir is None:
        if tag is None:
            latest = get_latest_release()
            if latest:
                tag = latest["tag"]
            else:
                raise FileNotFoundError(
                    "No data found. Run papertrail.data.download_release() first."
                )
        data_dir = DEFAULT_DATA_DIR / tag

    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(
            f"Data directory not found: {data_dir}\n"
            f"Run: papertrail.data.download_release(tag='{tag}')"
        )

    # Map 'which' to filenames
    file_map = {
        "merged": ["all_papers_merged.json"],
        "enriched": ["papers_enriched.json", "enrich_checkpoint.json"],
        "final": ["papers_final.json"],
    }

    if which == "scrapes":
        # Load all per-channel files
        result = {}
        for f in data_dir.glob("scrape_*.json"):
            with open(f) as fh:
                result[f.name] = json.load(fh)
        for f in data_dir.glob("*_full_urls.json"):
            with open(f) as fh:
                result[f.name] = json.load(fh)
        if not result:
            raise FileNotFoundError(
                f"No scrape files found in {data_dir}. "
                f"Make sure channel_scrapes.tar.gz was downloaded and extracted."
            )
        return result

    candidates = file_map.get(which, [f"{which}.json"])
    for fname in candidates:
        path = data_dir / fname
        if path.exists():
            logger.info("Loading %s", path)
            with open(path) as f:
                return json.load(f)

    raise FileNotFoundError(
        f"No file found for '{which}' in {data_dir}. "
        f"Tried: {candidates}. Run download_release() first."
    )


def data_summary(data_dir: Optional[str | Path] = None, tag: Optional[str] = None) -> dict[str, Any]:
    """
    Summarize available data in a release directory.

    Parameters
    ----------
    data_dir : str or Path, optional
        Directory to inspect.
    tag : str, optional
        Release tag (used to locate directory if data_dir is None).

    Returns
    -------
    dict
        Summary with keys: ``tag``, ``files`` (list of dicts with name,
        size_kb, records), ``total_papers``, ``enriched_count``.
    """
    if data_dir is None:
        if tag is None:
            latest = get_latest_release()
            tag = latest["tag"] if latest else "unknown"
        data_dir = DEFAULT_DATA_DIR / tag

    data_dir = Path(data_dir)
    if not data_dir.exists():
        return {"tag": tag, "files": [], "total_papers": 0, "enriched_count": 0}

    files = []
    total_papers = 0
    enriched_count = 0

    for f in sorted(data_dir.glob("*.json")):
        try:
            with open(f) as fh:
                data = json.load(fh)
            n = len(data) if isinstance(data, list) else 0
            files.append({
                "name": f.name,
                "size_kb": f.stat().st_size // 1024,
                "records": n,
            })
            if f.name == "all_papers_merged.json":
                total_papers = n
            if "enriched" in f.name or "checkpoint" in f.name:
                enriched_count = max(enriched_count, n)
        except Exception:
            files.append({"name": f.name, "size_kb": f.stat().st_size // 1024, "records": -1})

    return {
        "tag": tag,
        "data_dir": str(data_dir),
        "files": files,
        "total_papers": total_papers,
        "enriched_count": enriched_count,
    }
