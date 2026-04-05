# Paper Metadata Scraper Skill

Resolves paper titles and metadata from URLs using a multi-strategy cascade.
Use when papers have URLs but are missing titles, authors, journals, years, or
other bibliographic metadata.

## Triggers

- "find titles for untitled papers"
- "enrich paper metadata"
- "scrape paper titles from URLs"
- "fix missing paper metadata"
- "resolve paper titles"
- "look up paper info from links"

## Strategy Cascade

Try each strategy in order until the title is found. Each strategy is fast and
free (no API keys required).

### 1. Extract identifiers from URL

Extract DOIs, arXiv IDs, PII numbers, PMC IDs, and OpenReview IDs from the URL
pattern:

```python
import re

def extract_identifiers(url):
    ids = {}

    # DOI (various formats)
    m = re.search(r'(10\.\d{4,}/[^\s?#]+)', url)
    if m: ids['doi'] = m.group(1).rstrip('/')

    # arXiv
    m = re.search(r'arxiv\.org/(?:abs|pdf)/(\d+\.\d+)', url)
    if m: ids['arxiv'] = m.group(1)

    # bioRxiv/medRxiv DOI
    m = re.search(r'(?:bio|med)rxiv\.org/content/(?:10\.1101/)?(\d[\d.]+)', url)
    if m: ids['doi'] = f"10.1101/{m.group(1).split('v')[0]}"

    # bioRxiv PDF with just ID
    m = re.search(r'biorxiv\.org/content/biorxiv/early/\d+/\d+/\d+/(\d+)', url)
    if m: ids['doi'] = f"10.1101/{m.group(1)}"

    # Nature articles -> DOI
    m = re.search(r'nature\.com/articles/(s?\d[\w-]+)', url)
    if m: ids['doi'] = f"10.1038/{m.group(1)}"

    # Elsevier/Cell PII
    m = re.search(r'pii/(S[\dX()-]+)', url)
    if m: ids['pii'] = m.group(1).replace('(','').replace(')','').replace('-','')
    # Also from Cell.com URLs
    m = re.search(r'fulltext/(S[\dX()-]+)', url)
    if m: ids['pii'] = m.group(1).replace('(','').replace(')','').replace('-','')
    m = re.search(r'abstract/(S[\dX()-]+)', url)
    if m: ids['pii'] = m.group(1).replace('(','').replace(')','').replace('-','')

    # PMC ID
    m = re.search(r'PMC(\d+)', url)
    if m: ids['pmcid'] = f"PMC{m.group(1)}"

    # OpenReview
    m = re.search(r'openreview\.net/(?:forum|pdf)\?id=([\w-]+)', url)
    if m: ids['openreview'] = m.group(1)

    # HuggingFace papers (-> arXiv)
    m = re.search(r'huggingface\.co/papers/(\d+\.\d+)', url)
    if m: ids['arxiv'] = m.group(1)

    # PNAS old URLs
    m = re.search(r'pnas\.org/content/(\d+)/(\d+)/(\w+)', url)
    if m: ids['pnas_vol_page'] = (m.group(1), m.group(3))

    # Science/Science Advances
    m = re.search(r'science(?:mag)?\.org/content/\d+/\d+/([\w.]+)', url)
    if m:
        artid = m.group(1)
        if artid.startswith('eab') or artid.startswith('eaa') or artid.startswith('abc'):
            ids['doi'] = f"10.1126/science.{artid}"
        elif artid.startswith('aba') or artid.startswith('eaba'):
            # Could be Science Advances
            ids['doi'] = f"10.1126/sciadv.{artid}"

    # GitHub repos
    m = re.search(r'github\.com/([^/]+/[^/]+)', url)
    if m: ids['github'] = m.group(1)

    return ids
```

### 2. OpenAlex lookup (fastest, most reliable)

OpenAlex is free, no auth, handles DOIs and many other IDs:

```python
import urllib.request, urllib.parse, json, time

def lookup_openalex(identifiers):
    """Try OpenAlex with extracted identifiers."""
    headers = {"User-Agent": "PaperTrail/1.0 (mailto:your@email.com)"}

    # Try DOI first
    if 'doi' in identifiers:
        doi = identifiers['doi']
        url = f"https://api.openalex.org/works/https://doi.org/{doi}"
        url += "?select=title,doi,publication_year,authorships,primary_location"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
            if result.get('title'):
                return parse_openalex_work(result)
        except: pass

    # Try PMC ID
    if 'pmcid' in identifiers:
        pmcid = identifiers['pmcid']
        url = f"https://api.openalex.org/works?filter=ids.pmcid:{pmcid}&select=title,doi,publication_year,authorships,primary_location"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
            works = result.get('results', [])
            if works and works[0].get('title'):
                return parse_openalex_work(works[0])
        except: pass

    # Try arXiv -> DOI
    if 'arxiv' in identifiers:
        arxiv_doi = f"10.48550/arXiv.{identifiers['arxiv']}"
        url = f"https://api.openalex.org/works/https://doi.org/{arxiv_doi}"
        url += "?select=title,doi,publication_year,authorships,primary_location"
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                result = json.loads(resp.read())
            if result.get('title'):
                return parse_openalex_work(result)
        except: pass

    return None

def parse_openalex_work(work):
    """Extract metadata from an OpenAlex work object."""
    meta = {'title': work.get('title')}
    if work.get('publication_year'):
        meta['year'] = work['publication_year']
    if work.get('authorships'):
        meta['authors'] = ', '.join(
            a.get('author', {}).get('display_name', '')
            for a in work['authorships'][:30]
        )
    loc = work.get('primary_location', {})
    if loc and loc.get('source', {}).get('display_name'):
        meta['journal'] = loc['source']['display_name']
    if work.get('doi'):
        meta['doi'] = work['doi'].replace('https://doi.org/', '')
    return meta
```

### 3. Batch OpenAlex (for many DOIs at once)

When you have many papers, batch DOI lookups are much faster:

```python
def batch_openalex_lookup(doi_to_idx, data, batch_size=40):
    """Look up many DOIs at once via OpenAlex filter API."""
    headers = {"User-Agent": "PaperTrail/1.0 (mailto:your@email.com)"}
    doi_list = list(doi_to_idx.items())

    for batch_start in range(0, len(doi_list), batch_size):
        batch = doi_list[batch_start:batch_start + batch_size]
        doi_filter = "|".join(f"https://doi.org/{doi}" for doi, _ in batch)
        url = (f"https://api.openalex.org/works?"
               f"filter=doi:{urllib.parse.quote(doi_filter)}"
               f"&per_page=50&select=doi,title,publication_year,authorships,primary_location")
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())
            for work in result.get('results', []):
                work_doi = work.get('doi', '').replace('https://doi.org/', '')
                if work_doi in doi_to_idx and work.get('title'):
                    idx = doi_to_idx[work_doi]
                    meta = parse_openalex_work(work)
                    data[idx].update({k: v for k, v in meta.items() if v})
        except: pass
        time.sleep(0.2)
```

### 4. PubMed lookup (for Elsevier/Cell PIIs and other biomedical papers)

PubMed is the best fallback for Cell/Elsevier PIIs that other APIs can't handle:

```python
def lookup_pubmed(identifiers):
    """Search PubMed by formatted PII, DOI, or PMC ID."""

    # Format PII for PubMed search
    search_term = None
    if 'pii' in identifiers:
        pii = identifiers['pii']
        if len(pii) > 16:
            # S0092867422000034 -> S0092-8674(22)00003-4
            d = pii[1:]  # strip S
            formatted = f"S{d[0:4]}-{d[4:8]}({d[8:10]}){d[10:-1]}-{d[-1]}"
            search_term = formatted
    elif 'doi' in identifiers:
        search_term = identifiers['doi']
    elif 'pmcid' in identifiers:
        search_term = identifiers['pmcid']

    if not search_term:
        return None

    try:
        # Step 1: Search
        encoded = urllib.parse.quote(search_term)
        esearch = (f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
                   f"esearch.fcgi?db=pubmed&term={encoded}&retmode=json")
        req = urllib.request.Request(esearch)
        with urllib.request.urlopen(req, timeout=10) as resp:
            result = json.loads(resp.read())

        ids = result.get('esearchresult', {}).get('idlist', [])
        if not ids:
            return None

        time.sleep(0.4)  # NCBI rate limit: 3 req/sec without API key

        # Step 2: Get details
        pmid = ids[0]
        efetch = (f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
                  f"esummary.fcgi?db=pubmed&id={pmid}&retmode=json")
        req = urllib.request.Request(efetch)
        with urllib.request.urlopen(req, timeout=10) as resp:
            detail = json.loads(resp.read())

        info = detail.get('result', {}).get(pmid, {})
        title = info.get('title', '').rstrip('.')
        if not title:
            return None

        meta = {'title': title}
        authors = info.get('authors', [])
        if authors:
            meta['authors'] = ', '.join(a.get('name', '') for a in authors)
        if info.get('fulljournalname'):
            meta['journal'] = info['fulljournalname']
        pubdate = info.get('pubdate', '')
        m = re.search(r'(\d{4})', pubdate)
        if m: meta['year'] = int(m.group(1))

        return meta
    except:
        return None
```

**Important:** PubMed has a rate limit of 3 requests/second without an API key.
Add `time.sleep(0.35)` between requests, or register for an NCBI API key and
add `&api_key=YOUR_KEY` for 10 req/sec.

### 5. Web Search fallback (for truly stubborn papers)

When all APIs fail, search the URL itself to find the title from Google/Bing
snippets. Works well for OpenReview, conference proceedings, etc:

```python
# Use WebSearch tool (in Cowork/Claude Code) or any search API:
# Query: "openreview.net {paper_id}" or just the full URL
# The title usually appears in the first search result snippet
```

### 6. URL-based fallback titles

For papers that can't be resolved through any API, generate a readable fallback:

```python
def fallback_title_from_url(url):
    """Generate a reasonable fallback title from URL structure."""
    if 'github.com' in url:
        m = re.search(r'github\.com/([^/]+/[^/]+)', url)
        if m: return f"{m.group(1)} (GitHub)"
    if 'huggingface.co' in url:
        m = re.search(r'huggingface\.co/([^/]+/[^/?#]+)', url)
        if m: return f"{m.group(1)} (HuggingFace)"
    if 'openreview.net' in url:
        m = re.search(r'id=([\w-]+)', url)
        if m: return f"OpenReview: {m.group(1)}"
    # Last resort: use last meaningful path segment
    path = url.split('?')[0].rstrip('/').split('/')[-1]
    path = re.sub(r'\.full\.pdf$|\.pdf$|\.html$|\.full$', '', path)
    path = path.replace('-', ' ').replace('_', ' ')
    if len(path) > 5:
        return path
    return None
```

## Complete Pipeline

```python
def resolve_paper_metadata(paper):
    """Resolve metadata for a single paper using the full cascade."""
    url = paper.get('url', '')
    if not url:
        return paper

    # Step 1: Extract identifiers
    ids = extract_identifiers(url)

    # Step 2: OpenAlex (handles DOIs, arXiv, PMC)
    meta = lookup_openalex(ids)
    if meta and meta.get('title'):
        paper.update({k: v for k, v in meta.items() if v and not paper.get(k)})
        return paper

    # Step 3: PubMed (handles Elsevier PIIs, DOIs, PMC)
    meta = lookup_pubmed(ids)
    if meta and meta.get('title'):
        paper.update({k: v for k, v in meta.items() if v and not paper.get(k)})
        return paper

    # Step 4: URL-based fallback
    if not paper.get('title'):
        fallback = fallback_title_from_url(url)
        if fallback:
            paper['title'] = fallback

    return paper

def resolve_all_papers(papers, batch_first=True):
    """Resolve metadata for all papers, using batch APIs where possible."""

    # Collect DOIs for batch lookup
    if batch_first:
        doi_map = {}
        for i, p in enumerate(papers):
            if p.get('title'): continue
            ids = extract_identifiers(p.get('url', ''))
            if 'doi' in ids:
                doi_map[ids['doi']] = i

        if doi_map:
            batch_openalex_lookup(doi_map, papers)

    # Resolve remaining one by one
    for i, p in enumerate(papers):
        if p.get('title'): continue
        resolve_paper_metadata(p)
        time.sleep(0.2)  # Rate limiting

    return papers
```

## Rate Limits

| API | Free Limit | With Key |
|-----|-----------|----------|
| OpenAlex | 10 req/sec, 100K/day | Same (polite pool: email in User-Agent) |
| PubMed (NCBI) | 3 req/sec | 10 req/sec (free API key) |
| Semantic Scholar | 1 req/sec | 10 req/sec (free API key) |
| CrossRef | 50 req/sec (polite) | Same (email in User-Agent) |

## Notes

- **Elsevier/Cell PIIs** are the hardest to resolve. PubMed is the most reliable
  strategy for these. OpenAlex and Semantic Scholar often can't resolve raw PIIs.
- **OpenReview** papers are not indexed by PubMed. Use web search or the
  OpenReview API (v1: `api.openreview.net/notes?id={ID}`).
- **Batch OpenAlex** is 10-40x faster than individual lookups for DOI-based papers.
- Always include a `User-Agent` with a contact email for polite API access.
