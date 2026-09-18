# Hamilton Method Versionator

A desktop tool for Hamilton Venus liquid-handling systems that transforms
non-versioned Hamilton methods into fully versioned, portable methods
seamlessly — including library dependency resolution, labware localisation,
and folder structure scaffolding.

For simple methods the tool handles the full migration in one pass. For more
complex methods with deep dependency trees, an iterative cycle of running the
tool, testing on a Hamilton system, manually importing missing files, and
re-running may be required until the method is fully functional.

## Features

- **Folder Architecture Creator** — scaffold the standard versioned-method
  folder tree with a single click.
- **Folder Sync** — CSV-driven periodic directory synchronisation.
- **File Converter** — headless binary-to-ASCII conversion via Hamilton's
  converter executable.
- **Labware Sync** — extract and localise `.lay` labware references so methods
  are self-contained.
- **Library Sync** — resolve `#include` dependency trees in `.hsl` files and
  copy all libraries into a portable `Libraries/` folder.
- **File Search** — full-text search across Hamilton method files.
- **CLI** — run the full pipeline from the command line for automation.

## Quick Start

```bash
# Install (Windows only — requires Hamilton Venus)
pip install .

# GUI mode
python Deployment/main.py

# CLI mode
python Deployment/main.py --method-root "C:/path/to/method" --hsl "file.hsl"
```

## Documentation

- [Architecture Overview](architecture.md)
- [API Reference — Core](api/core.md)
- [API Reference — GUI](api/gui.md)
- [Contributing](contributing.md)
