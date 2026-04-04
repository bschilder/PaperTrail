# Installation

This guide walks you through installing PaperTrail and its dependencies.

## System Requirements

- **Python**: 3.9 or later
- **OS**: Linux, macOS, or Windows
- **Slack**: Access to a Slack workspace with API permissions

## Installation Methods

### Option 1: Install with Pip (Recommended)

Install from PyPI with your preferred embedding backend:

=== "OpenAI (recommended)"
    ```bash
    pip install papertrail-lab[openai]
    ```

    Includes everything needed for OpenAI embeddings via `text-embedding-3-small`.

=== "HuggingFace Inference API"
    ```bash
    pip install papertrail-lab[huggingface]
    ```

    Uses HuggingFace Inference API with `BAAI/bge-small-en-v1.5` model.

=== "Local ONNX models"
    ```bash
    pip install papertrail-lab[local]
    ```

    Uses local fastembed with no API keys required.

=== "All backends"
    ```bash
    pip install papertrail-lab[all]
    ```

    Installs all embedding backends so you can switch between them.

=== "Minimal (no embeddings)"
    ```bash
    pip install papertrail-lab
    ```

    Installs only core dependencies. You'll need to add an embedding backend separately.

### Option 2: Install from Source

For development or latest features:

```bash
git clone https://github.com/bschilder/PaperTrail.git
cd PaperTrail
pip install -e ".[dev]"
```

The `-e` flag installs in editable mode, so changes to the code are immediately reflected.

## Verify Installation

Check that PaperTrail is installed correctly:

```bash
papertrail --version
```

You should see the version number (e.g., `PaperTrail version 0.1.0`).

## Next Steps

1. **[Configure Your Environment](configuration.md)** — Set up API tokens and credentials
2. **[Quick Start](quickstart.md)** — Run the pipeline for the first time
3. **[Troubleshooting](#troubleshooting)** — Resolve common installation issues

## Troubleshooting

### Error: `pip: command not found`

Python and pip may not be installed or not in your PATH. Install Python from [python.org](https://www.python.org/downloads/) or use a package manager:

=== "macOS"
    ```bash
    brew install python3
    ```

=== "Ubuntu/Debian"
    ```bash
    sudo apt-get install python3 python3-pip
    ```

=== "Windows"
    Download and run the Python installer from [python.org](https://www.python.org/downloads/).

### Error: `ModuleNotFoundError: No module named 'papertrail'`

The package wasn't installed correctly. Try reinstalling:

```bash
pip install --upgrade --force-reinstall papertrail-lab
```

If you're using a virtual environment, make sure it's activated:

```bash
# Create a virtual environment
python3 -m venv papertrail-env

# Activate it
source papertrail-env/bin/activate  # macOS/Linux
# or
papertrail-env\Scripts\activate  # Windows

# Then install
pip install papertrail-lab[all]
```

### Error: `No module named 'slack_sdk'` or `openai`

You installed the minimal package without a backend. Install a backend:

```bash
pip install papertrail-lab[openai]  # or [huggingface] or [local]
```

### Error: `ImportError` with embedding libraries

Make sure you installed the correct backend extras:

```bash
# For OpenAI
pip install papertrail-lab[openai]

# For HuggingFace
pip install papertrail-lab[huggingface]

# For local models
pip install papertrail-lab[local]
```

### Windows Users: Long Path Errors

If you encounter path length errors on Windows, enable long paths:

```powershell
# Run PowerShell as Administrator
New-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1 -PropertyType DWORD -Force
```

## Platform-Specific Notes

### macOS

If you're on Apple Silicon (M1/M2/M3), ensure you're using Python compiled for ARM64:

```bash
# Check your Python architecture
python3 -c "import platform; print(platform.machine())"
# Should output: arm64
```

If you get `x86_64` instead, reinstall Python from [python.org](https://www.python.org/downloads/) with the native ARM64 installer.

### Linux

For Debian/Ubuntu, you may need to install additional system dependencies:

```bash
sudo apt-get install build-essential python3-dev
```

### Windows

Use PowerShell or Windows Terminal for best compatibility. The `cmd.exe` command prompt may have issues with certain dependencies.

## Getting Help

If installation issues persist:

1. Check the [GitHub Issues](https://github.com/bschilder/PaperTrail/issues) page
2. Share your Python version and platform: `python3 --version && uname -a`
3. Include the full error traceback
4. [Open a new issue](https://github.com/bschilder/PaperTrail/issues/new) with details
