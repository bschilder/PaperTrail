# Preview API

The preview module builds a self-contained interactive HTML dashboard
from enriched paper data with projections and clusters.

## Quick Example

```python
from papertrail.preview import build_preview

# papers: list of dicts with projections and cluster info
build_preview(
    papers,
    output_path="dashboard.html",
    title="Koo Lab PaperTrail",
)
```

## Functions

::: papertrail.preview.build_preview
    options:
      show_root_heading: true
      heading_level: 3

### build_preview

**Parameters:**

| Name | Type | Default | Description |
|---|---|---|---|
| `papers` | `list[dict[str, Any]]` | *(required)* | Enriched paper data. Each dict should contain the fields below. |
| `output_path` | `str` | `"papertrail.html"` | Path to write the generated HTML file. |
| `title` | `str` | `"PaperTrail"` | Dashboard title shown in the header and browser tab. |

**Returns:** `None`. Writes the HTML file to `output_path`.

## Expected Paper Format

Each dict in the `papers` list should have:

| Field | Type | Required | Description |
|---|---|---|---|
| `title` | `str` | Yes | Paper title. |
| `abstract` | `str` | No | Paper abstract. |
| `authors` | `list[str]` | No | Author names. |
| `year` | `int` | No | Publication year. |
| `journal` | `str` | No | Journal or venue. |
| `url` | `str` | Yes | Paper URL. |
| `channel` | `str` | No | Slack channel where paper was shared. |
| `shared_by` | `str` | No | User who shared the paper. |
| `date` | `str` | No | Date shared (ISO format). |
| `cluster_id` | `int` | Yes | Cluster assignment from `cluster_papers()`. |
| `cluster_label` | `str` | Yes | Human-readable cluster label. |
| `projections` | `dict` | Yes | 2D coordinates for each projection method. |

The `projections` field should be structured as:

```json
{
  "umap": [x, y],
  "tsne": [x, y],
  "pca": [x, y]
}
```

where `x` and `y` are floats.

## Dashboard Features

The generated HTML dashboard includes:

- **Map view**: Interactive D3.js scatter plot with UMAP/t-SNE/PCA toggle
- **Color modes**: Color by cluster, channel, user, or date
- **Table view**: Sortable, filterable table of all papers
- **Detail panel**: Click a point to see full paper metadata
- **Search**: Filter papers by keyword

The dashboard is fully self-contained (no external dependencies at
runtime) and can be opened directly in any browser.

## Template

The dashboard uses an HTML template at
`papertrail/templates/dashboard.html`. Paper data is injected as a
base64-encoded JSON blob to avoid `</script>` escaping issues. If the
template file is missing, a minimal fallback template is used.
