# Koo Lab Demo

Learn how the Koo Lab at Cold Spring Harbor Laboratory uses PaperTrail to track and visualize papers shared across their Slack workspace.

## Background

The Koo Lab is a computational biology group at Cold Spring Harbor Laboratory focused on genomics, deep learning, and protein structure prediction. The lab maintains an active Slack workspace where researchers share and discuss papers across multiple channels:

- **#papers-genomics** — Genomics, sequencing, variant calling
- **#papers-dl** — Deep learning, neural networks, AI
- **#papers-protein** — Protein folding, structure prediction, AlphaFold
- **#papers-systems** — Systems biology, network analysis
- **#papers-statistics** — Statistical methods, Bayesian inference
- Plus 7 additional domain-specific channels

## The Problem

With papers shared across 12 channels, the lab needed:

1. **Discovery** — Find papers relevant to current projects
2. **Contextualization** — Understand relationships between papers
3. **Visualization** — See reading patterns and research trends
4. **Searchability** — Quickly locate papers by topic

Manual approaches (email threads, shared drives) didn't scale.

## The Solution

PaperTrail was built to solve this. Here's how the lab uses it:

## Setup

### 1. Create Slack Bot

Lab admin created a bot in Slack with these scopes:

- `channels:history` — Read message history
- `channels:read` — List channels
- `users:read` — Get user information
- `reactions:read` — Track engagement

```bash
export SLACK_BOT_TOKEN="xoxb-your-lab-token"
```

### 2. Install PaperTrail

```bash
pip install papertrail-lab[openai]

export OPENAI_API_KEY="sk-your-key"
```

### 3. Configure for Lab

No special configuration needed! PaperTrail auto-detects the Slack workspace and OpenAI key.

## Workflow

### Monthly Paper Collection

Once a month, the lab admin runs:

```bash
# Scrape all papers shared in the last month
papertrail scrape -o papers_raw.json -d 30 -v

# Enrich with metadata
papertrail enrich papers_raw.json -o papers_enriched.json

# Compute embeddings (using OpenAI for best quality)
papertrail embed papers_enriched.json -o papers_final.json --backend openai

# Build interactive dashboard
papertrail build papers_final.json -o koolab_papers.html --title "Koo Lab Papers"
```

### Share with Lab

```bash
# Host on lab website
cp koolab_papers.html /var/www/html/papers/

# Or share via email
mail -s "Updated paper collection" lab@example.com < koolab_papers.html

# Or upload to Slack
# Use Slack file upload to share with team
```

## Results

Over the past year, the pipeline has collected:

- **129 papers** from 12 channels
- **847 total shares** (some papers shared multiple times)
- **3,214 reactions** (engagement)
- **892 thread replies** (discussions)

### Distribution

| Channel | Papers | Reactions | Top Paper |
|---------|--------|-----------|-----------|
| #papers-dl | 45 | 1,203 | "Attention Is All You Need" |
| #papers-genomics | 38 | 789 | "A Genome Map of Human Chromosome 1" |
| #papers-protein | 23 | 456 | "AlphaFold2 Structure Prediction" |
| #papers-systems | 12 | 298 | "Network Biology" |
| #papers-statistics | 11 | 234 | "Bayesian Inference" |
| Others | 0 | 234 | Various |

## Using the Dashboard

### Discovery

Researchers open `koolab_papers.html` to:

1. **Explore by cluster** — See natural groupings of papers by topic
2. **Color by channel** — Understand which domains papers come from
3. **Color by date** — Track reading activity over time
4. **Search for topics** — "single cell RNA", "CRISPR", "transformer"

### Typical Workflows

**Find papers on deep learning:**
```
1. Click "Color by: Cluster"
2. Hover over clusters to find deep learning
3. Click papers to see details
```

**Find papers by recent activity:**
```
1. Click "Color by: Date"
2. Hover over recent papers (blue)
3. Click to open detail panel
```

**Semantic search:**
```
1. Type in search box: "generative models"
2. See papers ranked by relevance
3. Click result to read full metadata
```

### Key Insights

By analyzing the dashboard, the lab discovered:

1. **Research clusters naturally form** — Papers group by methodology, not just topic
2. **Reading patterns shift** — Interest in transformers increased 40% in 2023
3. **Cross-channel discussions** — Same papers appear in multiple channels
4. **Influential papers** — Certain papers have much higher engagement

## Customization

The lab tailored PaperTrail for their needs:

### Custom Colors

```bash
papertrail build papers_final.json \
  --title "Koo Lab Papers" \
  --primary-color "#0066CC" \
  --accent-color "#FF6600"
```

### Multiple Dashboards

```bash
# One dashboard per research area
papertrail scrape -c papers-dl -o dl.json && \
papertrail enrich dl.json -o dl_enriched.json && \
papertrail embed dl_enriched.json -o dl_final.json && \
papertrail build dl_final.json -o dashboard_dl.html --title "Deep Learning Papers"
```

### Integration with Lab Wiki

```html
<!-- In lab wiki -->
<iframe src="https://lab.example.com/papers/koolab_papers.html"
        width="100%" height="800px"></iframe>
```

## Tips for Your Lab

If you want to set up something similar:

### 1. Start Small

Test with one channel first:
```bash
papertrail scrape -c general -o test.json
```

### 2. Establish Cadence

Run monthly (or weekly) on a schedule:
```bash
# Create a cron job
0 9 1 * * cd /path/to/papers && ./run_pipeline.sh
```

### 3. Share Results

Make the dashboard easily accessible:

- Host on your lab website
- Share link in Slack
- Include in lab newsletter
- Add to onboarding docs

### 4. Gather Feedback

Ask lab members:

- Is the dashboard useful?
- Missing features?
- Different visualizations?
- Custom search queries?

### 5. Extend

Use the Python API to build custom analyses:
```python
import json

with open("papers_final.json") as f:
    papers = json.load(f)["papers"]

# Custom analysis: papers by year and channel
from collections import defaultdict
by_year_channel = defaultdict(list)
for p in papers:
    key = (p.get("year"), p.get("channel"))
    by_year_channel[key].append(p)

for (year, channel), papers_list in sorted(by_year_channel.items()):
    print(f"{year} - {channel}: {len(papers_list)} papers")
```

## Troubleshooting

### Bot can't read channels

Make sure bot was invited to all channels. In Slack:
```
/invite @papertrail_bot
```

### Missing papers

Check:

- Papers have shareable links
- Bot was added before papers were shared
- Look at scraper verbose output: `papertrail scrape -v`

### Dashboard is slow

If you have 500+ papers:

- Compress: `--compress`
- Use PCA projection instead of UMAP
- Split into multiple dashboards by channel

### Embeddings cost too much

Switch to local backend:
```bash
papertrail embed papers_enriched.json --backend local
```

## Results & Impact

The Koo Lab has found PaperTrail valuable for:

- **Onboarding** — New lab members explore research landscape
- **Literature reviews** — Comprehensive view of field progress
- **Collaboration** — Shared understanding across team
- **Grant writing** — Demonstrate knowledge of state-of-art
- **Publication planning** — Identify gaps in research

## Next Steps

- Set up your own workspace (see [Quick Start](../getting-started/quickstart.md))
- Read [Scraping Papers](../guide/scraping.md) for detailed guidance
- Explore [Python API](../api/scraper.md) for custom analysis
- [Contact us](https://github.com/bschilder/PaperTrail) with questions

## Questions?

For issues or feature requests:

- [GitHub Issues](https://github.com/bschilder/PaperTrail/issues)
- [Email](mailto:bschilder@cshl.edu)

---

Built with love at Cold Spring Harbor Laboratory.
