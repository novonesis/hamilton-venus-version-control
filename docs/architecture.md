# Architecture Overview

## High-Level Structure

```
Deployment/
├── main.py                  # Entry point: CLI vs GUI dispatch
├── cli.py                   # Argparse-based CLI workflow engine
├── config.py                # JSON-backed application configuration
├── logger_config.py         # Loguru setup (file + console + email sinks)
├── email_log_handler.py     # Email notification sink for Loguru
├── csv_operations.py        # CSV path-pair reader for Folder Sync
├── file_operations.py       # Safe copy + directory sync utilities
├── file_converter.py        # Subprocess wrapper for Hamilton converter
├── folder_structure_creator.py  # Versioned-method folder scaffolding
├── labware_sync.py          # .lay file parser + labware localisation
├── library_path_updater.py  # #include dependency resolver + library copy
├── monitoring.py            # Periodic sync loop (background thread)
├── string_search.py         # Full-text file search
└── gui/
    ├── __init__.py           # Package re-export
    ├── app.py                # Main Tk window + tab host
    ├── shared.py             # GUI sink factories + constants
    ├── markdown_renderer.py  # Markdown-to-Tkinter renderer
    ├── usage_guide_tab.py    # README usage display
    ├── folder_creation_tab.py
    ├── folder_sync_tab.py
    ├── conversion_tab.py
    ├── labware_tab.py
    ├── library_tab.py
    └── search_tab.py
```

## Key Design Patterns

- **Loguru with `logger.bind(tab=...)`** — each GUI tab gets an isolated
  log stream by binding a tab name and filtering the GUI sink accordingly.
- **TYPE_CHECKING guard** — heavy or circular imports (e.g. `FileMonitorApp`
  in tab files) are guarded behind `if TYPE_CHECKING:` to avoid runtime
  overhead and circular import errors.
- **`from __future__ import annotations`** — all files use PEP 563 deferred
  evaluation so that forward references and `str | None` syntax work on
  Python 3.8+.
