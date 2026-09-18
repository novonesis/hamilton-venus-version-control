# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

Nothing yet.

## [1.0.0] - 2026-08-25

First public release. Prepared against the SOP-C open sourcing workflow; tag
`v1.0.0` is cut at publication, after the Line of Business VP's approval.

### Added
- `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `CHANGELOG.md` for open-source launch
- README with logo, badges, features table, quick start, and architecture overview
- `SECURITY.md` with a private vulnerability reporting route
- `.governance/` folder holding the SOP-C release record, classification,
  declassification justification and audit trail. Internal only: excluded from
  the public mirror by `.gitattributes`, `scripts/publish.sh` and the
  `.githooks/pre-push` leak guard
- `scripts/publish.sh`, the only sanctioned route to the public GitHub mirror.
  Builds the public tree with `git archive`, severing internal history
- `.python-version` pinning the interpreter so `uv` provisions 3.13 everywhere
- Ruff lint and format gates, and a `uv lock --check` gate, in CI

### Changed
- Dependencies moved from `[project.optional-dependencies]` to
  `[dependency-groups]`, the uv house standard
- CI now runs `uv lock --check` then `uv sync --frozen` rather than an
  unpinned `uv sync --extra test`, so a dependency change cannot land unlocked
- Whole codebase formatted with `ruff format`; imports sorted

### Fixed
- `labware_sync.py` re-raised a `ValueError` inside an `except UnicodeDecodeError`
  without chaining, discarding the original traceback
- `library_path_updater.py` built a `re.sub` replacement lambda closing over a
  loop variable; the value is now bound explicitly at definition

### Removed
- Tracked runtime log trees (`Data/logs/`, `Deployment/Data/Logs/`) containing
  developer machine paths and hardware IDs
- Tracked PyInstaller build intermediates and bytecode caches for Python 3.8,
  3.9 and 3.10
- `winshell` runtime dependency, imported once and never used
- Obsolete `hamilton_git_environment.yml` conda environment, superseded by uv

## [0.9.0] - 2026-02-19

### Added
- Apache 2.0 LICENSE file
- `config.py` with JSON-backed configuration system (`Data/config.json`)
- Comprehensive `.gitignore` for Python projects

### Changed
- Refactored `gui.py` God class (~1,190 lines) into `gui/` package with 10 modular files
- Unified all logging to Loguru-only (removed dual logging pattern across all modules)
- SMTP settings now read from config instead of hardcoded values
- "For Anders" tab renamed to "Usage Guide"
- `.spec` file path fixed to `'.'` (was hardcoded corporate path)

### Removed
- Corporate references (SMTP server, sender address, DevOps mentions)
- Unused dependencies: `pandas`, `Pillow`, `ipykernel`, `pyodbc`
- Unused imports: `pandas` from `library_path_updater.py`, `PIL` from `gui.py`, `csv` from `library_path_updater.py`

### Fixed
- Nested function scope bug: `start_flashing`/`_toggle_flash`/`stop_flashing` promoted to proper class methods
- `clear_log_area` cross-tab side effect: each tab now clears only its own log area
- Email handler now gracefully skips when SMTP is unconfigured

## [0.8.0] - 2025-05-22

### Added
- Tree view for library dependency visualization
- Dynamic path resolution for `__filename__` patterns
- Button deactivation during processing to prevent re-trigger errors
- Safety check preventing selection of `.med` shortcut in library sync

### Fixed
- Labware library versioning bug replacing `.lay` file on first library sync
- Path display for library updater
- Log UUID generation process

### Changed
- Migrated to UV environment from conda/pip
- Repackaged `.exe` builds with UV workflow
