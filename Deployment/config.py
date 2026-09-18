"""Application configuration backed by a JSON file.

Provides a simple key-value store that persists to ``Data/config.json``
next to the running executable (or script).  Default values are defined in
:data:`DEFAULT_CONFIG` and are merged with any on-disk overrides at load time.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

DEFAULT_CONFIG = {
    "smtp_server": "",
    "smtp_port": 25,
    "smtp_sender": "",
    "smtp_recipient": "",
    "smtp_use_tls": False,
}


class AppConfig:
    """Application configuration backed by a JSON file."""

    def __init__(self) -> None:
        if getattr(sys, "frozen", False):
            base_path = os.path.dirname(sys.executable)
        else:
            base_path = os.path.dirname(os.path.abspath(__file__))
        self._config_path = os.path.join(base_path, "Data", "config.json")
        self._config: dict[str, Any] = dict(DEFAULT_CONFIG)
        self.load()

    def load(self) -> None:
        """Load configuration from disk, falling back to defaults."""
        if os.path.exists(self._config_path):
            try:
                with open(self._config_path, encoding="utf-8") as f:
                    stored = json.load(f)
                self._config.update(stored)
            except (json.JSONDecodeError, OSError):
                pass

    def save(self) -> None:
        """Persist current configuration to disk."""
        os.makedirs(os.path.dirname(self._config_path), exist_ok=True)
        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(self._config, f, indent=2)

    def get(self, key: str, default: Any = None) -> Any:
        """Return a config value, or *default* if the key is absent."""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a config value and persist to disk."""
        self._config[key] = value
        self.save()
