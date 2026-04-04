# Scraper API

The scraper module discovers academic papers shared in Slack channels.
It handles full pagination, URL extraction from Slack message formatting,
domain-based filtering across 30+ academic publishers, and URL
normalization for deduplication.

## Quick Example

```python
from papertrail.scraper import SlackPaperScraper

scraper = SlackPaperScraper(token="xoxb-...")
papers = scraper.scrape_channel("C0123Q7PGGP")
print(f"Found {len(papers)} papers")

# Extract URLs from raw text
urls = scraper.extract_paper_urls(["Check out https://arxiv.org/abs/2301.04821"])
# → ['https://arxiv.org/abs/2301.04821']
```

## Constants

::: papertrail.scraper.PAPER_DOMAINS
    options:
      show_root_heading: true
      heading_level: 3

::: papertrail.scraper.EXCLUDE_PATTERNS
    options:
      show_root_heading: true
      heading_level: 3

## Data Classes

::: papertrail.scraper.SlackPaper
    options:
      show_root_heading: true
      heading_level: 3
      members: []

## SlackPaperScraper

::: papertrail.scraper.SlackPaperScraper
    options:
      show_root_heading: true
      heading_level: 3
      members:
        - __init__
        - scrape_channel
        - extract_paper_urls
        - is_paper_url
        - normalize_url

## Type Reference

| Type | Description |
|---|---|
| `SlackPaper` | Dataclass representing a paper found in Slack. Fields: `channel_id`, `channel_name`, `shared_by`, `user_id`, `timestamp`, `message_ts`, `permalink`, `message_text`, `paper_url`, `reactions_count`, `reply_count`, `reaction_details`. |
| `list[SlackPaper]` | Returned by `scrape_channel()`. Each entry is a unique paper URL found in the channel. |
| `list[str]` | Returned by `extract_paper_urls()`. Deduplicated, normalized paper URLs. |
