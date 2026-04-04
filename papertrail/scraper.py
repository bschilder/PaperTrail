"""
Slack paper scraper — finds papers shared in Slack channels and extracts
engagement metrics (reactions, thread replies).

Requires a Slack Bot Token with channels:history, channels:read,
reactions:read, and search:read scopes.
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

import requests

logger = logging.getLogger(__name__)

# URL patterns that indicate a paper link
PAPER_URL_PATTERNS = [
    r"doi\.org",
    r"arxiv\.org",
    r"biorxiv\.org",
    r"medrxiv\.org",
    r"pubmed\.ncbi\.nlm\.nih\.gov",
    r"nature\.com",
    r"cell\.com",
    r"science\.org",
    r"pnas\.org",
    r"springer\.com",
    r"wiley\.com",
    r"pmc\.ncbi\.nlm\.nih\.gov",
    r"academic\.oup\.com",
]

PAPER_URL_REGEX = re.compile("|".join(PAPER_URL_PATTERNS))


@dataclass
class SlackPaper:
    """A paper shared in a Slack message."""

    channel_id: str
    channel_name: str
    shared_by: str
    user_id: str
    date: str
    message_ts: str
    permalink: str
    text: str
    url: str
    reactions_count: int = 0
    replies_count: int = 0
    reaction_details: dict[str, int] = field(default_factory=dict)


class SlackScraper:
    """
    Scrapes papers from Slack channels.

    Parameters
    ----------
    token : str
        Slack Bot Token (xoxb-...).
    channels : list[str], optional
        Channel names to search. If None, searches all channels.
    search_queries : list[str], optional
        Custom search queries. Defaults to searching for common paper URLs.

    Examples
    --------
    >>> scraper = SlackScraper(token="xoxb-...")
    >>> papers = scraper.scrape()
    >>> print(f"Found {len(papers)} papers")
    """

    BASE_URL = "https://slack.com/api"

    def __init__(
        self,
        token: str,
        channels: list[str] | None = None,
        search_queries: list[str] | None = None,
    ):
        self.token = token
        self.channels = channels
        self.headers = {"Authorization": f"Bearer {token}"}
        self.search_queries = search_queries or [
            "has:link doi.org",
            "has:link arxiv.org",
            "has:link biorxiv.org",
            "has:link medrxiv.org",
            "has:link pubmed.ncbi",
            "has:link nature.com",
        ]
        self._channel_cache: dict[str, str] = {}
        self._user_cache: dict[str, str] = {}

    def _api(self, method: str, **params: Any) -> dict:
        """Make a Slack API call."""
        url = f"{self.BASE_URL}/{method}"
        resp = requests.get(url, headers=self.headers, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        if not data.get("ok"):
            raise RuntimeError(f"Slack API error: {data.get('error', 'unknown')}")
        return data

    def _get_channel_name(self, channel_id: str) -> str:
        """Look up channel name from ID."""
        if channel_id not in self._channel_cache:
            try:
                data = self._api("conversations.info", channel=channel_id)
                self._channel_cache[channel_id] = data["channel"]["name"]
            except Exception:
                self._channel_cache[channel_id] = channel_id
        return self._channel_cache[channel_id]

    def _get_user_name(self, user_id: str) -> str:
        """Look up user display name from ID."""
        if user_id not in self._user_cache:
            try:
                data = self._api("users.info", user=user_id)
                profile = data["user"]["profile"]
                self._user_cache[user_id] = (
                    profile.get("real_name")
                    or profile.get("display_name")
                    or user_id
                )
            except Exception:
                self._user_cache[user_id] = user_id
        return self._user_cache[user_id]

    def _extract_urls(self, text: str) -> list[str]:
        """Extract paper-like URLs from message text."""
        urls = re.findall(r"<(https?://[^>|]+)", text)
        return [u for u in urls if PAPER_URL_REGEX.search(u)]

    def _get_engagement(self, channel_id: str, message_ts: str) -> dict:
        """Get reactions and reply count for a message."""
        engagement = {"reactions_count": 0, "replies_count": 0, "reaction_details": {}}
        try:
            data = self._api(
                "conversations.replies",
                channel=channel_id,
                ts=message_ts,
                limit=1,
            )
            messages = data.get("messages", [])
            if messages:
                msg = messages[0]
                # Reactions
                for r in msg.get("reactions", []):
                    engagement["reaction_details"][r["name"]] = r["count"]
                    engagement["reactions_count"] += r["count"]
                # Replies (subtract 1 for parent message)
                engagement["replies_count"] = max(
                    0, msg.get("reply_count", 0)
                )
        except Exception as e:
            logger.warning("Failed to get engagement for %s: %s", message_ts, e)
        return engagement

    def scrape(self, with_engagement: bool = True) -> list[SlackPaper]:
        """
        Scrape all papers from Slack.

        Parameters
        ----------
        with_engagement : bool
            If True, fetch reaction/reply counts for each paper.

        Returns
        -------
        list[SlackPaper]
            List of papers found in Slack.
        """
        seen_urls: set[str] = set()
        papers: list[SlackPaper] = []

        for query in self.search_queries:
            logger.info("Searching: %s", query)
            page = 1
            while True:
                try:
                    data = self._api(
                        "search.messages",
                        query=query,
                        count=100,
                        page=page,
                    )
                except Exception as e:
                    logger.warning("Search failed for '%s': %s", query, e)
                    break

                messages = data.get("messages", {}).get("matches", [])
                if not messages:
                    break

                for msg in messages:
                    urls = self._extract_urls(msg.get("text", ""))
                    for url in urls:
                        if url in seen_urls:
                            continue
                        seen_urls.add(url)

                        channel_id = msg.get("channel", {}).get("id", "")
                        user_id = msg.get("user", "") or msg.get("username", "")
                        ts = msg.get("ts", "")

                        paper = SlackPaper(
                            channel_id=channel_id,
                            channel_name=self._get_channel_name(channel_id),
                            shared_by=self._get_user_name(user_id),
                            user_id=user_id,
                            date=self._ts_to_date(ts),
                            message_ts=ts,
                            permalink=msg.get("permalink", ""),
                            text=self._clean_text(msg.get("text", "")),
                            url=url,
                        )

                        if with_engagement:
                            eng = self._get_engagement(channel_id, ts)
                            paper.reactions_count = eng["reactions_count"]
                            paper.replies_count = eng["replies_count"]
                            paper.reaction_details = eng["reaction_details"]
                            time.sleep(0.3)  # Rate limit

                        papers.append(paper)

                paging = data.get("messages", {}).get("paging", {})
                if page >= paging.get("pages", 1):
                    break
                page += 1
                time.sleep(1)

        logger.info("Found %d unique papers", len(papers))
        return papers

    @staticmethod
    def _ts_to_date(ts: str) -> str:
        """Convert Slack timestamp to ISO date."""
        from datetime import datetime, timezone
        try:
            return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            return ""

    @staticmethod
    def _clean_text(text: str) -> str:
        """Remove Slack formatting from text."""
        text = re.sub(r"<[^>]+\|([^>]+)>", r"\1", text)  # <url|label> → label
        text = re.sub(r"<[^>]+>", "", text)  # Remove remaining URLs
        text = re.sub(r":[a-z_]+:", "", text)  # Remove emoji codes
        text = re.sub(r"<@[A-Z0-9]+(?:\|[^>]+)?>", "", text)  # Remove @mentions
        return text.strip()
