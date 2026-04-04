# Contributing

We welcome contributions! This guide explains how to get involved with PaperTrail.

## Getting Started

### Fork and Clone

```bash
# Fork the repository on GitHub, then:
git clone https://github.com/your-username/PaperTrail.git
cd PaperTrail
```

### Set Up Development Environment

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # or venv\Scripts\activate on Windows

# Install in editable mode with dev dependencies
pip install -e ".[dev]"

# Set up pre-commit hooks (optional but recommended)
pre-commit install
```

### Verify Installation

```bash
# Run tests
pytest

# Serve docs locally
mkdocs serve
```

## Development Workflow

### 1. Create a Branch

```bash
git checkout -b feature/your-feature-name
```

Use descriptive names:
- `feature/add-bge-embeddings`
- `fix/handle-missing-dois`
- `docs/improve-quickstart`

### 2. Make Changes

Follow these guidelines:

#### Code Style

- Use [PEP 8](https://pep8.org/) style
- Format with `black`: `black papertrail/`
- Lint with `flake8`: `flake8 papertrail/`
- Type hints encouraged where helpful

```python
from typing import List, Dict, Optional

def search_papers(
    query: str,
    top_k: int = 5,
    min_score: Optional[float] = None
) -> List[Dict]:
    """Search papers by semantic similarity.

    Args:
        query: Search query text
        top_k: Number of results to return
        min_score: Minimum similarity score filter

    Returns:
        List of papers ranked by similarity
    """
    pass
```

#### Documentation

- Add docstrings to all functions and classes
- Use Google-style docstrings
- Include type hints in docstrings

```python
def enrich_papers(papers: List[Dict]) -> List[Dict]:
    """Enrich papers with metadata from external APIs.

    Fetches title, authors, abstract, and other metadata from
    Semantic Scholar and OpenAlex APIs.

    Args:
        papers: List of paper objects with at least 'url' or 'doi'

    Returns:
        List of enriched paper objects

    Raises:
        APIError: If external API calls fail
        ValueError: If papers list is empty

    Example:
        ```python
        papers = scraper.scrape()
        enriched = enricher.enrich_papers(papers)
        ```
    """
    pass
```

#### Tests

Add tests for new features. Tests go in `tests/`:

```python
# tests/test_scraper.py
def test_scrape_papers():
    """Test paper scraping from mock Slack."""
    scraper = Scraper(token="test-token")
    papers = scraper.scrape(channels=["test"])
    assert len(papers) > 0
    assert "url" in papers[0]

def test_scrape_empty_channel():
    """Test scraping channel with no papers."""
    scraper = Scraper(token="test-token")
    papers = scraper.scrape(channels=["empty"])
    assert len(papers) == 0
```

Run tests before committing:

```bash
pytest -v
```

### 3. Commit Changes

```bash
git add .
git commit -m "Add feature: description of changes"
```

Write good commit messages:
- First line: short summary (50 chars max)
- Blank line
- Detailed explanation (if needed)

Good messages:
```
Add local ONNX embedding backend

This adds support for running embeddings locally without API keys,
using the fastembed library with BAAI/bge-small-en-v1.5 models.
Useful for privacy-sensitive data and offline environments.
```

Bad messages:
```
fix stuff
update
changes
```

### 4. Push and Pull Request

```bash
git push origin feature/your-feature-name
```

Then open a Pull Request on GitHub. Include:
- Description of changes
- Why they're needed
- Any breaking changes
- Screenshots if UI changes

## Areas for Contribution

### Code

- **New embedding backends** — Add support for more models
- **Performance improvements** — Optimize vectorization, caching
- **Bug fixes** — See [Issues](https://github.com/bschilder/PaperTrail/issues)
- **New features** — See [Discussions](https://github.com/bschilder/PaperTrail/discussions)

### Documentation

- **Tutorials** — Step-by-step guides for specific workflows
- **API docs** — Improve docstrings and examples
- **Troubleshooting** — Common issues and solutions
- **Examples** — Real-world use cases

### Community

- **Answer questions** — Help others in Issues/Discussions
- **Report bugs** — File detailed issue reports
- **Suggest features** — Discuss ideas in Discussions
- **Share use cases** — Tell us how you use PaperTrail

## Testing

### Run Tests

```bash
# All tests
pytest

# Specific test file
pytest tests/test_scraper.py

# Specific test function
pytest tests/test_scraper.py::test_scrape_papers

# Verbose output
pytest -v

# Coverage report
pytest --cov=papertrail
```

### Write Tests

Create test files in `tests/`:

```python
# tests/test_embeddings.py
import pytest
from papertrail.embeddings import Embedder

def test_embed_papers():
    """Test embedding papers."""
    embedder = Embedder(backend="local")
    papers = [
        {"title": "Paper 1", "abstract": "Test abstract 1"},
        {"title": "Paper 2", "abstract": "Test abstract 2"},
    ]
    result = embedder.embed(papers)

    assert len(result) == 2
    assert "embedding" in result[0]
    assert len(result[0]["embedding"]) == 384  # Local backend dimensions

@pytest.mark.parametrize("backend", ["openai", "huggingface", "local"])
def test_embed_backends(backend):
    """Test all embedding backends."""
    embedder = Embedder(backend=backend)
    papers = [{"title": "Test", "abstract": "test"}]
    result = embedder.embed(papers)
    assert "embedding" in result[0]
```

## Documentation

Documentation is in the `docs/` directory using Markdown and mkdocs.

### Building Docs Locally

```bash
# Install mkdocs
pip install mkdocs mkdocs-material mkdocstrings

# Serve locally
mkdocs serve

# Build static HTML
mkdocs build
```

Then open `http://localhost:8000` in your browser.

### Writing Documentation

- Use clear, concise language
- Include code examples
- Explain the "why" not just the "how"
- Add admonitions for tips and warnings:

```markdown
!!!tip
    Use `--backend local` to avoid API costs during development.

!!!warning
    Never commit API keys to git. Always use environment variables.
```

## Release Process

Maintainers follow this process for releases:

1. **Update version** — `papertrail/__init__.py`
2. **Update changelog** — `CHANGELOG.md`
3. **Tag commit** — `git tag v0.1.0`
4. **Push tags** — `git push origin --tags`
5. **Build package** — `python -m build`
6. **Upload to PyPI** — `python -m twine upload dist/*`

## Code of Conduct

We're committed to providing a welcoming and inclusive community. Please:

- Be respectful and kind
- Welcome newcomers
- Give credit for contributions
- Report harassment to maintainers

## Getting Help

- **Questions?** — Ask in [GitHub Discussions](https://github.com/bschilder/PaperTrail/discussions)
- **Found a bug?** — [Open an Issue](https://github.com/bschilder/PaperTrail/issues/new)
- **Want to discuss features?** — [Start a Discussion](https://github.com/bschilder/PaperTrail/discussions/new)

## Useful Resources

- [GitHub Help](https://help.github.com/)
- [Python Style Guide (PEP 8)](https://pep8.org/)
- [mkdocs Documentation](https://www.mkdocs.org/)
- [Semantic Scholar API](https://api.semanticscholar.org/)
- [OpenAlex API](https://docs.openalex.org/)

## Examples of Great Contributions

### Adding a New Embedding Backend

```python
# papertrail/embeddings.py
class CustomEmbedder(BaseEmbedder):
    """Custom embedding backend."""

    def __init__(self, model_name: str = "custom-model"):
        """Initialize custom embedder.

        Args:
            model_name: Name of custom model to use
        """
        self.model = self.load_model(model_name)

    def embed_text(self, text: str) -> np.ndarray:
        """Embed text to vector."""
        return self.model.encode(text)
```

### Improving Documentation

```markdown
# Advanced: Custom Metadata Sources

You can extend PaperTrail to fetch metadata from custom APIs.

## Example: Adding a Custom API

```python
from papertrail.enricher import Enricher

class CustomEnricher(Enricher):
    def enrich_from_custom_api(self, paper):
        # Your custom logic here
        pass
```
```

### Fixing a Bug

```python
# Before
def parse_doi(url):
    # Naive parsing that breaks on some URLs
    return url.split("doi.org/")[1]

# After
def parse_doi(url: str) -> Optional[str]:
    """Extract DOI from URL.

    Args:
        url: URL that may contain a DOI

    Returns:
        DOI string or None if not found
    """
    import re
    match = re.search(r'(?:doi\.org/|DOI:\s*)(.+?)(?:\s|$)', url)
    return match.group(1) if match else None
```

## Thank You!

Thank you for contributing to PaperTrail! Your work helps the research community.

---

Questions? [Contact us](https://github.com/bschilder/PaperTrail/issues)
