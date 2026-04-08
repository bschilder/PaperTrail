"""
Comprehensive Slack paper scraper module for discovering academic papers shared in Slack.

This module provides a flexible, well-documented interface for scraping papers from Slack
channels with support for both direct Slack API access (via slack_sdk) and MCP tool integration.

Key features:
- Full pagination support for channel history
- Multiple paper domain detection
- URL normalization and deduplication
- Rate limiting and error recovery
- Configurable filtering patterns
- Comprehensive metadata extraction
- Thread engagement metrics (reactions, replies)

Requires appropriate Slack Bot Token scopes:
  - channels:history
  - channels:read
  - reactions:read
  - users:read

Example:
    >>> from papertrail.scraper import SlackPaperScraper
    >>> scraper = SlackPaperScraper(token="xoxb-...")
    >>> papers = scraper.scrape_channel("C123456789")
    >>> print(f"Found {len(papers)} papers")
    >>> urls = scraper.extract_paper_urls([m['text'] for m in papers])
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Union
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)

# Known academic paper hosting domains
PAPER_DOMAINS = {
    # Preprint servers
    "arxiv.org",
    "biorxiv.org",
    "medrxiv.org",
    "psyarxiv.org",
    "eartharxiv.org",
    "ecoevo.org",  # EcoEvoRxiv

    # Publisher DOI resolvers
    "doi.org",

    # Major publishers
    "nature.com",
    "science.org",
    "cell.com",
    "pnas.org",
    "springer.com",
    "wiley.com",
    "elsevier.com",
    "academic.oup.com",
    "tandfonline.com",
    "jstor.org",
    "plos.org",
    "elifesciences.org",

    # PubMed/PMC
    "pubmed.ncbi.nlm.nih.gov",
    "pmc.ncbi.nlm.nih.gov",
    "ncbi.nlm.nih.gov",

    # Institutional repositories
    "researchgate.net",
    "academia.edu",
    "github.com",  # Code often accompanies papers

    # Other preprint/publication platforms
    "ssrn.com",
    "paperswitchcode.com",
    "openreview.net",
    "arxiv-vanity.com",
}

# Patterns to exclude from paper URL detection
EXCLUDE_PATTERNS = [
    r"slack\.com",
    r"youtu(?:\.be|be\.com)",
    r"twitter\.com|x\.com",
    r"github\.com/?$",  # Plain GitHub homepage
    r"imgur\.com",
    r"imgur\.com/\w{5,7}$",  # Imgur image links
]

EXCLUDE_REGEX = re.compile("|".join(f"(?:{p})" for p in EXCLUDE_PATTERNS), re.IGNORECASE)

# Backward compatibility: export regex for old tests
PAPER_URL_REGEX = re.compile(
    "|".join(PAPER_DOMAINS),
    re.IGNORECASE
)


@dataclass
class SlackPaper:
    """
    Represents a paper shared in a Slack message.

    Attributes
    ----------
    channel_id : str
        Slack channel ID where paper was shared.
    channel_name : str
        Human-readable channel name.
    shared_by : str
        Display name of user who shared the paper.
    user_id : str
        Slack user ID of the person who shared.
    timestamp : str
        ISO format timestamp when paper was shared.
    message_ts : str
        Slack message timestamp (for accessing thread).
    permalink : str
        Direct link to the Slack message.
    message_text : str
        Full message text where paper was mentioned.
    paper_url : str
        Extracted and normalized paper URL.
    reactions_count : int
        Total number of emoji reactions on this message.
    reply_count : int
        Number of replies in the thread.
    reaction_details : dict[str, int]
        Mapping of emoji names to reaction counts.
    """

    channel_id: str
    channel_name: str
    shared_by: str
    user_id: str
    timestamp: str
    message_ts: str
    permalink: str
    message_text: str
    paper_url: str
    reactions_count: int = 0
    reply_count: int = 0
    reaction_details: dict[str, int] = field(default_factory=dict)


class SlackPaperScraper:
    """
    Comprehensive Slack paper scraper with pagination, filtering, and enrichment.

    This is the main scraper class. For backward compatibility with older code,
    the original SlackScraper class is still available as an alias.

    Supports two modes of operation:
    1. Direct Slack API access via slack_sdk.WebClient (recommended)
    2. MCP tool integration for remote/constrained environments

    Parameters
    ----------
    token : str, optional
        Slack Bot Token (xoxb-...). Required for direct API mode.
    channels : list[str], optional
        List of channel IDs or names to scrape. If None, will scrape
        all channels accessible to the bot token.
    search_queries : list[str], optional
        Custom Slack search queries to use. Defaults to searching common
        paper domains.
    rate_limit_delay : float
        Delay in seconds between API calls (default: 0.3 seconds).
    use_mcp : bool
        If True, attempt to use MCP tools instead of direct Slack API.

    Attributes
    ----------
    BASE_URL : str
        Slack API base URL.

    Examples
    --------
    Scrape specific channel:

    >>> scraper = SlackPaperScraper(token="xoxb-...")
    >>> papers = scraper.scrape_channel("C123456789")
    >>> print(f"Found {len(papers)} papers")

    Extract URLs from message text:

    >>> messages = scraper.scrape_channel("C123456789")
    >>> texts = [m.message_text for m in messages]
    >>> urls = scraper.extract_paper_urls(texts)
    >>> print(f"Paper URLs: {urls}")

    Normalize URLs for deduplication:

    >>> url1 = "https://doi.org/10.1234/example"
    >>> url2 = "https://example.com?utm_source=slack"
    >>> norm1 = scraper.normalize_url(url1)
    >>> norm2 = scraper.normalize_url(url2)
    """

    BASE_URL = "https://slack.com/api"

    def __init__(
        self,
        token: str | None = None,
        channels: list[str] | None = None,
        search_queries: list[str] | None = None,
        rate_limit_delay: float = 0.3,
        use_mcp: bool = False,
        custom_domains: set[str] | None = None,
    ):
        """Initialize the Slack paper scraper."""
        self.token = token
        self.channels = channels
        self.rate_limit_delay = rate_limit_delay
        self.use_mcp = use_mcp

        # Instance-level domain set (don't mutate module-level PAPER_DOMAINS)
        self._paper_domains = PAPER_DOMAINS | (custom_domains or set())

        # Default search queries targeting known paper domains
        self.search_queries = search_queries or self._build_default_queries()

        # Initialize API headers if using direct access
        if token and not use_mcp:
            self.headers = {"Authorization": f"Bearer {token}"}
        else:
            self.headers = {}

        # Caches for reducing API calls
        self._channel_cache: dict[str, str] = {}
        self._user_cache: dict[str, str] = {}
        self._conversation_cache: dict[str, dict[str, Any]] = {}

        # Validate token with auth.test (optional, don't crash on failure)
        if token and not use_mcp:
            try:
                resp = requests.get(
                    f"{self.BASE_URL}/auth.test",
                    headers=self.headers,
                    timeout=10,
                )
                data = resp.json()
                if not data.get("ok"):
                    logger.warning("Slack token validation failed: %s", data.get("error", "unknown"))
                else:
                    logger.info("Authenticated as %s in team %s", data.get("user"), data.get("team"))
            except Exception as e:
                logger.warning("Could not validate Slack token: %s", e)

    @staticmethod
    def _build_default_queries() -> list[str]:
        """Build default search queries from known paper domains."""
        queries = []
        # Add queries for most common domains
        priority_domains = [
            "doi.org", "arxiv.org", "biorxiv.org", "medrxiv.org",
            "pubmed.ncbi", "nature.com", "science.org"
        ]
        for domain in priority_domains:
            queries.append(f"has:link {domain}")
        return queries

    def _api_call(self, method: str, **params: Any) -> dict[str, Any]:
        """
        Make a Slack API call with error handling and rate limiting.

        Parameters
        ----------
        method : str
            Slack API method name (e.g., "conversations.history").
        **params
            Parameters to pass to the API method.

        Returns
        -------
        dict
            Parsed JSON response from Slack API.

        Raises
        ------
        RuntimeError
            If the API returns an error.
        """
        url = f"{self.BASE_URL}/{method}"

        try:
            resp = requests.get(
                url,
                headers=self.headers,
                params=params,
                timeout=30
            )
            resp.raise_for_status()

            data = resp.json()
            if not data.get("ok"):
                error_msg = data.get("error", "unknown error")
                logger.warning(f"Slack API error for {method}: {error_msg}")
                raise RuntimeError(f"Slack API error: {error_msg}")

            return data

        except requests.RequestException as e:
            logger.error(f"Request failed for {method}: {e}")
            raise RuntimeError(f"API request failed: {e}") from e

    def scrape_channel(
        self,
        channel_id: str,
        oldest: str | float | None = None,
        latest: str | float | None = None,
        include_replies: bool = False,
    ) -> list[SlackPaper]:
        """
        Scrape all messages from a channel with full pagination.

        Fetches complete message history with automatic pagination and
        optional engagement metrics (reactions, thread replies).

        Parameters
        ----------
        channel_id : str
            The channel ID to scrape (must start with 'C').
        oldest : str | float, optional
            Oldest message timestamp to include (Unix timestamp or
            ISO format string). If None, starts from channel creation.
        latest : str | float, optional
            Newest message timestamp to include (Unix timestamp or
            ISO format string). If None, includes through current time.
        include_replies : bool
            If True, fetch and include thread reply counts and
            reaction details (slower, more API calls).

        Returns
        -------
        list[SlackPaper]
            List of papers found in the channel, deduplicated by URL.
            Sorted by most recent first.

        Notes
        -----
        This method automatically handles pagination. The Slack API
        returns messages in batches, and this method continues fetching
        until all messages are retrieved.
        """
        logger.info(f"Scraping channel {channel_id} (replies={include_replies})")

        # Auto-join channel if bot is not a member
        try:
            resp = requests.post(
                f"{self.BASE_URL}/conversations.join",
                headers={**self.headers, "Content-Type": "application/json"},
                json={"channel": channel_id},
                timeout=10,
            )
            data = resp.json()
            if data.get("ok"):
                logger.info(f"Joined channel {channel_id}")
            elif data.get("error") not in ("already_in_channel", "method_not_supported_for_channel_type"):
                logger.warning(f"Could not join channel {channel_id}: {data.get('error')}")
        except Exception as e:
            logger.warning(f"Could not join channel {channel_id}: {e}")

        papers: list[SlackPaper] = []
        seen_urls: set[str] = set()
        cursor = None
        message_count = 0

        # Get channel info for the human-readable name
        channel_info = self._get_channel_info(channel_id)
        channel_name = channel_info.get("name", channel_id)

        while True:
            try:
                # Fetch messages with pagination
                params = {
                    "channel": channel_id,
                    "limit": 200,  # Max per request
                }

                if oldest:
                    params["oldest"] = oldest
                if latest:
                    params["latest"] = latest
                if cursor:
                    params["cursor"] = cursor

                response = self._api_call("conversations.history", **params)
                messages = response.get("messages", [])

                if not messages:
                    logger.debug(f"No more messages in {channel_id}")
                    break

                message_count += len(messages)
                logger.debug(f"Processing {len(messages)} messages (total: {message_count})")

                # Process each message
                for msg in messages:
                    # Skip bot messages and reactions
                    if msg.get("subtype") in ("bot_message", "message_changed", "message_deleted"):
                        continue

                    # Extract paper URLs from message text
                    text = msg.get("text", "")
                    urls = self.extract_paper_urls([text])

                    for url in urls:
                        # Normalize and deduplicate
                        normalized_url = self.normalize_url(url)
                        if normalized_url in seen_urls:
                            continue
                        seen_urls.add(normalized_url)

                        # Get user and timestamp info
                        user_id = msg.get("user", "") or msg.get("username", "")
                        ts = msg.get("ts", "")

                        paper = SlackPaper(
                            channel_id=channel_id,
                            channel_name=channel_name,
                            shared_by=self._get_user_name(user_id),
                            user_id=user_id,
                            timestamp=self._ts_to_iso(ts),
                            message_ts=ts,
                            permalink=msg.get("permalink", ""),
                            message_text=self._clean_slack_text(text),
                            paper_url=normalized_url,
                        )

                        # Optionally fetch engagement metrics
                        if include_replies:
                            engagement = self._get_engagement(channel_id, ts)
                            paper.reactions_count = engagement["reactions_count"]
                            paper.reply_count = engagement["reply_count"]
                            paper.reaction_details = engagement["reaction_details"]
                            time.sleep(self.rate_limit_delay)

                        papers.append(paper)

                # Check for more pages
                cursor = response.get("response_metadata", {}).get("next_cursor")
                if not cursor:
                    break

                time.sleep(self.rate_limit_delay)

            except Exception as e:
                logger.error(f"Error scraping channel {channel_id}: {e}")
                break

        logger.info(
            f"Scraped {len(papers)} unique papers from {channel_name} "
            f"({message_count} messages total)"
        )
        return papers

    def extract_paper_urls(self, texts: list[str]) -> list[str]:
        """
        Extract paper URLs from a list of text strings.

        Searches for URLs containing known paper domains and filters
        out common false positives (images, social media, etc.).

        Parameters
        ----------
        texts : list[str]
            List of text strings to search for paper URLs.

        Returns
        -------
        list[str]
            List of extracted URLs, deduplicated and normalized.

        Notes
        -----
        This method:
        - Extracts URLs from Slack message format: <url|label>
        - Filters for known paper domains
        - Removes common false positives
        - Normalizes URLs for comparison
        """
        all_urls: set[str] = set()

        for text in texts:
            # Extract URLs from Slack format <url|label>
            slack_urls = re.findall(r"<(https?://[^>|]+)", text)

            # Also look for plain URLs
            plain_urls = re.findall(r"https?://[^\s<>]+", text)

            for url in slack_urls + plain_urls:
                # Clean up common artifacts
                url = url.rstrip(".,;:)'\">")

                # Check if it's a paper URL
                if self.is_paper_url(url):
                    normalized = self.normalize_url(url)
                    all_urls.add(normalized)

        return sorted(list(all_urls))

    @staticmethod
    def is_paper_url(url: str) -> bool:
        """
        Check if a URL points to a paper or academic resource.

        Parameters
        ----------
        url : str
            URL to check.

        Returns
        -------
        bool
            True if URL matches known paper domains and doesn't match
            exclusion patterns.
        """
        # Check exclusion patterns first
        if EXCLUDE_REGEX.search(url):
            return False

        # Check for known paper domains
        parsed = urlparse(url.lower())
        domain = parsed.netloc.lstrip("www.")

        # Check exact match or subdomain match
        for paper_domain in self._paper_domains:
            if domain == paper_domain or domain.endswith(f".{paper_domain}"):
                return True

        # Also check if URL contains a DOI
        if re.search(r"10\.\d{4,}/[^\s>]+", url):
            return True

        return False

    @staticmethod
    def normalize_url(url: str) -> str:
        """
        Normalize a URL for consistent comparison and deduplication.

        Parameters
        ----------
        url : str
            URL to normalize.

        Returns
        -------
        str
            Normalized URL with:
            - Lowercase scheme and domain
            - Removed tracking parameters
            - Removed fragments
            - Trailing slashes standardized

        Notes
        -----
        This removes common tracking parameters like utm_* and fbclid
        to ensure papers shared from different sources are deduplicated.
        """
        try:
            # Strip pipe-concatenated labels from Slack <url|label> format
            if '|' in url:
                url = url.split('|')[0]

            parsed = urlparse(url)

            # Remove fragment
            parsed = parsed._replace(fragment="")

            # Remove tracking parameters
            params = parsed.query.split("&")
            params = [
                p for p in params
                if not p.startswith(("utm_", "fbclid", "gclid", "msclkid"))
            ]

            # Reconstruct query string
            new_query = "&".join(params)
            parsed = parsed._replace(query=new_query)

            # Lowercase scheme and host only, preserve path case
            parsed = parsed._replace(
                scheme=parsed.scheme.lower(),
                netloc=parsed.netloc.lower(),
            )
            normalized = parsed.geturl()

            # Remove trailing slash for consistency
            if normalized.endswith("/") and parsed.path != "/":
                normalized = normalized.rstrip("/")

            return normalized

        except Exception as e:
            logger.warning(f"Error normalizing URL {url}: {e}")
            return url

    def _get_channel_info(self, channel_id: str) -> dict[str, Any]:
        """
        Fetch channel information including name and topic.

        Parameters
        ----------
        channel_id : str
            Channel ID to look up.

        Returns
        -------
        dict
            Channel information with keys: id, name, topic, purpose, etc.
        """
        if channel_id in self._conversation_cache:
            return self._conversation_cache[channel_id]

        try:
            response = self._api_call("conversations.info", channel=channel_id)
            channel_info = response.get("channel", {})
            self._channel_cache[channel_id] = channel_info.get("name", channel_id)
            self._conversation_cache[channel_id] = channel_info
            return channel_info
        except Exception as e:
            logger.warning(f"Failed to get info for channel {channel_id}: {e}")
            self._channel_cache[channel_id] = channel_id
            return {"id": channel_id, "name": channel_id}

    def _get_user_name(self, user_id: str) -> str:
        """
        Get human-readable user display name from user ID.

        Parameters
        ----------
        user_id : str
            Slack user ID (U...).

        Returns
        -------
        str
            Display name if available, otherwise user ID.
        """
        if not user_id:
            return "unknown"

        if user_id in self._user_cache:
            return self._user_cache[user_id]

        try:
            response = self._api_call("users.info", user=user_id)
            user_info = response.get("user", {})
            profile = user_info.get("profile", {})

            # Try different name fields in order of preference
            name = (
                profile.get("real_name")
                or profile.get("display_name")
                or user_info.get("name")
                or user_id
            )

            self._user_cache[user_id] = name
            return name

        except Exception as e:
            logger.debug(f"Failed to get user name for {user_id}: {e}")
            self._user_cache[user_id] = user_id
            return user_id

    def _get_engagement(
        self, channel_id: str, message_ts: str
    ) -> dict[str, Any]:
        """
        Get engagement metrics (reactions and reply count) for a message.

        Parameters
        ----------
        channel_id : str
            Channel containing the message.
        message_ts : str
            Message timestamp.

        Returns
        -------
        dict
            Dictionary with keys: reactions_count, reply_count, reaction_details
        """
        engagement: dict[str, Any] = {
            "reactions_count": 0,
            "reply_count": 0,
            "reaction_details": {},
        }

        try:
            response = self._api_call(
                "conversations.replies",
                channel=channel_id,
                ts=message_ts,
                limit=1,
            )

            messages = response.get("messages", [])
            if messages:
                msg = messages[0]

                # Count reactions
                for reaction in msg.get("reactions", []):
                    name = reaction.get("name", "")
                    count = reaction.get("count", 0)
                    engagement["reaction_details"][name] = count
                    engagement["reactions_count"] += count

                # Get reply count (subtract 1 for parent message)
                reply_count = msg.get("reply_count", 0)
                engagement["reply_count"] = max(0, reply_count)

        except Exception as e:
            logger.debug(f"Failed to get engagement for {message_ts}: {e}")

        return engagement

    @staticmethod
    def _ts_to_iso(ts: str) -> str:
        """
        Convert Slack timestamp to ISO 8601 format.

        Parameters
        ----------
        ts : str
            Slack message timestamp (Unix timestamp as string with decimals).

        Returns
        -------
        str
            ISO 8601 formatted timestamp, or empty string if conversion fails.
        """
        try:
            timestamp = float(ts)
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            return dt.isoformat()
        except (ValueError, TypeError):
            logger.warning(f"Could not convert timestamp {ts}")
            return ""

    @staticmethod
    def _ts_to_date(ts: str) -> str:
        """
        Convert Slack timestamp to ISO date string (YYYY-MM-DD).

        This is the old interface for backward compatibility.

        Parameters
        ----------
        ts : str
            Slack message timestamp (Unix timestamp as string with decimals).

        Returns
        -------
        str
            ISO date string (YYYY-MM-DD), or empty string if conversion fails.
        """
        try:
            timestamp = float(ts)
            dt = datetime.fromtimestamp(timestamp, tz=timezone.utc)
            return dt.strftime("%Y-%m-%d")
        except (ValueError, TypeError):
            logger.warning(f"Could not convert timestamp {ts}")
            return ""

    @staticmethod
    def _clean_slack_text(text: str) -> str:
        """
        Remove Slack formatting and special characters from message text.

        Parameters
        ----------
        text : str
            Raw message text from Slack.

        Returns
        -------
        str
            Cleaned text with Slack formatting removed.

        Notes
        -----
        Removes:
        - <url|label> Slack URL format
        - <@user> mentions
        - Emoji codes like :smile:
        - Remaining angle brackets
        """
        # Remove <url|label> format
        text = re.sub(r"<[^>]+\|([^>]+)>", r"\1", text)

        # Remove user mentions <@userid|name>
        text = re.sub(r"<@[A-Z0-9]+(?:\|[^>]+)?>", "", text)

        # Remove emoji codes :emoji_name:
        text = re.sub(r":[a-z_]+:", "", text)

        # Remove remaining angle bracket URLs
        text = re.sub(r"<[^>]+>", "", text)

        # Clean up whitespace
        text = re.sub(r"\s+", " ", text)

        return text.strip()

    @staticmethod
    def _clean_text(text: str) -> str:
        """
        Alias for _clean_slack_text for backward compatibility.
        """
        return SlackPaperScraper._clean_slack_text(text)


# Backward compatibility alias for older code
SlackScraper = SlackPaperScraper
