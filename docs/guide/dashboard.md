# Building the Dashboard

The dashboard builder creates a self-contained interactive HTML file for exploring papers. No server required!

## How It Works

The builder:

1. **Takes the final JSON** with embeddings and metadata
2. **Embeds data** in the HTML file (JSON + FAISS index)
3. **Includes JavaScript** for interactivity
4. **Generates visualization** with d3.js scatter plot
5. **Creates search index** for full-text search
6. **Exports single HTML file** ready to share

## Basic Usage

### Build Dashboard

```bash
papertrail build papers_final.json -o dashboard.html
```

Opens the dashboard in your browser:

```bash
# macOS
open dashboard.html

# Linux
xdg-open dashboard.html

# Windows
start dashboard.html
```

Or just double-click the file!

### Customize Title

```bash
papertrail build papers_final.json -o dashboard.html \
  --title "My Lab Papers"
```

### Add Description

```bash
papertrail build papers_final.json -o dashboard.html \
  --description "Papers shared in our Slack workspace"
```

## Dashboard Features

### Table View

- **Sortable columns**: Click header to sort
- **Searchable**: Use Ctrl+F in browser
- **Scrollable**: Vertical and horizontal scroll
- **Columns**: Title, authors, journal, year, citations, channel, date, engagement

Click a row to open the detail panel.

### Embedding Map

**2D Scatter Plot** of papers using d3.js:

- **Hover**: See paper title and details
- **Click**: Open detail panel
- **Zoom**: Scroll to zoom in/out
- **Pan**: Click and drag to move around

**Color by** dropdown to switch coloring:

- **Cluster**: k-means clusters (auto-computed)
- **Channel**: Slack channel
- **User**: Who shared it
- **Date**: Timeline gradient
- **Year**: Publication year
- **Citations**: Citation count gradient

**Projection** dropdown to switch 2D projections:

- **UMAP** (recommended)
- **t-SNE**
- **PCA**

### Detail Panel

Click a paper to see:

- Full title and authors
- Abstract
- Journal, year, citation count
- DOI, arXiv ID, URL
- Engagement metrics
- Channel and user who shared
- Direct link to original Slack message

### Semantic Search

Chat-style search interface:

1. **Type a query**: "transformer attention mechanisms"
2. **Results appear**: Similar papers ranked by relevance
3. **Click result**: Opens detail panel
4. **Autocomplete**: Suggests paper titles as you type

Uses FAISS index for sub-millisecond search across all embeddings.

## Advanced Options

### Customize Colors

```bash
papertrail build papers_final.json -o dashboard.html \
  --primary-color "#2196F3" \
  --accent-color "#FF9800"
```

### Set Default Projection

```bash
papertrail build papers_final.json -o dashboard.html \
  --default-projection tsne
```

### Set Default Coloring

```bash
papertrail build papers_final.json -o dashboard.html \
  --default-coloring channel
```

### Include Additional Metadata

Add custom fields to display:

```bash
papertrail build papers_final.json -o dashboard.html \
  --extra-fields "keywords,institution,funding"
```

### Data Size Optimization

For large datasets (10,000+ papers), compress data:

```bash
papertrail build papers_final.json -o dashboard.html --compress
```

Reduces file size significantly with minimal quality loss.

### Template Customization

Use a custom HTML template:

```bash
papertrail build papers_final.json -o dashboard.html \
  --template custom_template.html
```

## Sharing & Deployment

### Share Locally

```bash
# Simply copy the file
cp dashboard.html ~/Dropbox/papers_dashboard.html

# Or email it
mail -a dashboard.html user@example.com
```

### Host on Web Server

```bash
# Copy to web server
scp dashboard.html user@server.com:/var/www/html/papers.html
```

Then access at `https://server.com/papers.html`

### GitHub Pages

```bash
# Commit to repo
git add dashboard.html
git commit -m "Update paper dashboard"
git push

# View at https://username.github.io/repo/dashboard.html
```

### Google Drive / Dropbox

Simply upload the HTML file. These services will:

- Serve it directly
- Allow sharing via link
- Work in all browsers

## Customization

### Edit HTML Directly

The dashboard HTML is a single file. You can edit it:

```html
<!-- Change the title -->
<title>My Research Papers</title>

<!-- Modify colors in CSS -->
<style>
  .header { background-color: #2196F3; }
</style>

<!-- Add custom scripts -->
<script>
  // Your custom JavaScript here
</script>
```

### Modify Table Columns

Edit the data extraction section to show different fields:

```javascript
const columns = ["title", "authors", "year", "journal", "citations"];
```

### Customize Search

Modify search weighting:

```javascript
const searchWeights = {
  title: 2.0,
  abstract: 1.0,
  authors: 1.5,
  keywords: 1.0
};
```

## Performance Tips

### For Large Datasets (10,000+ papers)

1. **Enable compression**:
   ```bash
   papertrail build papers_final.json -o dashboard.html --compress
   ```

2. **Limit initial display** of table (lazy load):
   ```html
   <script>
     const INITIAL_ROWS = 100;  // Show first 100, load more on scroll
   </script>
   ```

3. **Use efficient projection** (PCA is fastest):
   ```bash
   papertrail build papers_final.json -o dashboard.html \
     --default-projection pca
   ```

### Browser Optimization

For very large datasets (20,000+ papers):

- Use Chrome/Edge (faster d3.js rendering)
- Close other tabs
- Increase browser memory: `--max-old-space-size=4096`

### File Size

Check file size:

```bash
ls -lh dashboard.html
```

Typical sizes:

- 100 papers: 2-5 MB
- 1,000 papers: 20-50 MB
- 10,000 papers: 200-500 MB

Compress with gzip for storage:

```bash
gzip -k dashboard.html  # Creates dashboard.html.gz
```

## Python API

Build dashboards programmatically:

```python
from papertrail.preview import DashboardBuilder

# Create builder
builder = DashboardBuilder()

# Build dashboard
builder.build(
    papers=papers_with_embeddings,
    output_path="dashboard.html",
    title="My Papers",
    description="Papers from our Slack workspace",
    default_coloring="cluster",
    default_projection="umap"
)
```

## Tips & Tricks

### Export Data from Dashboard

In browser console (F12):

```javascript
// Get all papers as JSON
const data = JSON.stringify(window.papers);
console.log(data);

// Copy to clipboard
copy(data);
```

### Embed Dashboard in Website

```html
<!-- In your website -->
<iframe src="dashboard.html" width="100%" height="800px"></iframe>
```

### Share with Export Settings

Create multiple dashboards with different defaults:

```bash
# One with cluster coloring
papertrail build papers_final.json -o dashboard_clusters.html \
  --default-coloring cluster

# One with channel coloring
papertrail build papers_final.json -o dashboard_channels.html \
  --default-coloring channel

# One with timeline coloring
papertrail build papers_final.json -o dashboard_timeline.html \
  --default-coloring date
```

### Add Search Filters

Modify HTML to add predefined search filters:

```javascript
// Quick filter buttons
const quickFilters = {
  "Deep Learning": "neural network deep learning",
  "Biology": "cell biology genetics",
  "Statistics": "statistical analysis hypothesis test"
};
```

### Track Search Popularity

```javascript
// Log popular searches
document.addEventListener("search", (e) => {
  console.log(`Searched for: ${e.detail.query}`);
});
```

## Troubleshooting

### Dashboard is slow

Check:

- File size (compress if >200MB)
- Number of papers (UMAP is slower for 10,000+)
- Browser (use Chrome/Edge)
- Try PCA projection instead of UMAP

### Search returns no results

Check:

- Papers have abstracts (required for search)
- Query words are spelled correctly
- Try shorter queries ("deep learning" vs "distributed deep learning systems")

### Maps doesn't show

Check:

- Papers have embeddings (required)
- Projection was computed (--projections umap)
- Browser JavaScript is enabled

### File size is huge

Solutions:
1. Compress: `--compress`
2. Use PCA (smaller embedding space)
3. Use HuggingFace backend (384D vs 1536D embeddings)
4. Reduce number of papers

### Colors don't match expectations

Check:

- Coloring dropdown is set correctly
- Papers have required metadata (channel, date, etc.)
- Color palette is appropriate for your data

## Next Steps

- **[Searching Papers](searching.md)** — Use semantic search API
- **[Koo Lab Example](../examples/koo-lab.md)** — Real-world dashboard example
- **[API Reference: Preview](../api/projections.md)** — Detailed Python API
