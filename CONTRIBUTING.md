# Contributing to Hamilton Method Versionator

Thank you for your interest in contributing! Whether you're reporting a bug, suggesting a feature, or submitting code, your help is appreciated.

## How this repository relates to ours

You should know this before you invest time, because it changes what happens
to your commits.

This GitHub repository is a **published mirror**. Day-to-day development
happens in an internal Novonesis repository, and each release is published
here as **one commit**, built from that internal repository and delivered
through a release pull request. The mirror holds one commit per release,
not the commit-by-commit history of the work.

What that means in practice:

- **Your contribution is still wanted, and it still gets merged.** A
  maintainer reviews it here, then carries the change into the internal
  repository. It becomes public at the next release.
- **Expect your commits to appear squashed** into that release commit rather
  than preserved individually. Attribution goes in the release notes and in
  [`CHANGELOG.md`](CHANGELOG.md), not in the mirror's git history.
- **A release restates the whole tree.** The release commit's content is
  exactly the internal repository's, so a change merged here without first
  being carried across would be undone by the next release. That is why a
  maintainer brings your change across rather than simply pressing merge.
- **Forks and open pull requests keep working.** Each release builds on the
  mirror's own history, so you rebase onto a new release the ordinary way. If
  a release lands while your pull request is open and it conflicts, that is a
  mechanical consequence of the mirror, not a judgment on your work: say so on
  the pull request and a maintainer will bring the change across by hand.

If any of this is a problem for what you are trying to do, open an issue and
say so. It is a constraint we can talk about, not a wall.

## How to Report Bugs

Open a [GitHub Issue](../../issues/new) and include:

- A clear description of the bug
- Steps to reproduce the behavior
- Expected behavior vs. actual behavior
- Hamilton Venus version (e.g., Venus 4.8)
- Windows version (e.g., Windows 11 23H2)
- Whether you are running from source or the `.exe`

## How to Suggest Features

Open a [GitHub Issue](../../issues/new) describing:

- The use case or problem you're trying to solve
- Your proposed solution (if you have one)
- Any alternatives you considered

Please open an issue before starting work on a large change so we can discuss the approach.

## Development Setup

### Requirements

- **Windows 10/11** with Hamilton Venus installed (needed for full testing)
- **Python 3.13**, pinned in `.python-version`; uv installs it for you
- **[UV](https://docs.astral.sh/uv/)** package manager

### Getting started

```bash
# Clone the repository
git clone https://github.com/novozymes-digital/hamilton-venus-version-control.git
cd hamilton-venus-version-control

# Install dependencies, including the dev group (pytest, ruff)
uv sync

# Enable the repository's git hooks
git config core.hooksPath .githooks

# Run the app from source
uv run python Deployment/main.py
```

## Code Style

Formatting and linting are enforced by [ruff](https://docs.astral.sh/ruff/),
configured in `pyproject.toml`, and CI fails on either. Run
`uv run ruff format .` and `uv run ruff check .` before you push. Beyond that:

- **Follow existing patterns** in the codebase
- **Use Loguru** for logging (`from loguru import logger`), not `import logging`
- **Use `logger.bind(tab="name")`** for tab-specific logging, so the line
  reaches the right panel of the GUI
- **GUI actions live in `Deployment/webgui/api.py`**, as methods on the API
  object pywebview exposes to the frontend in `Deployment/webgui/assets/`.
  Keep the logic in the core modules and the API methods thin
- Keep functions focused and modular

## Pull Request Process

1. **Fork** the repository and create a feature branch from `main`
2. Make your changes in the feature branch
3. Run the checks CI will run, and make sure they pass:

   ```powershell
   uv sync --frozen
   uv run pytest              # test suite, with coverage
   uv run ruff check .        # lint
   uv run ruff format .       # formatting
   ```

   The tests import Windows-only modules (`pywin32`), so they run on Windows.
   `uv run ruff check .` and `uv run ruff format --check .` run anywhere.
4. Ensure the app still starts from source (`uv run python Deployment/main.py`)
5. Submit a pull request with:
   - A clear description of what changed and why
   - A reference to any related issue (e.g., `Closes #42`)

## Building the Executable

To build the packaged `.exe`:

```powershell
uv run pyinstaller --distpath . Deployment/Hamilton_Method_Versionator.spec
```

Run this from the repository root. The generated executable needs `Hamilton_file_converter_headless.exe` and `README.md` in the same directory to function correctly.

## Reporting a security issue

Do **not** open a public issue for a security vulnerability. Follow
[SECURITY.md](SECURITY.md), which routes reports privately.

## Code of Conduct

Please read and follow our [Code of Conduct](CODE_OF_CONDUCT.md). We are committed to providing a welcoming and inclusive experience for everyone.
