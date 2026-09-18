"""Pywebview window launcher for the Hamilton Method Versionator.

Creates a native window rendering the HTML/CSS/JS shell from
``webgui/assets/`` with :class:`VersionatorApi` as the JavaScript bridge.
"""

from __future__ import annotations

import os
import sys

import webview

from webgui.api import VERSIONED_METHODS_PATH, VersionatorApi


def _assets_dir() -> str:
    """Return the absolute path to the ``assets/`` directory.

    Handles both normal execution and PyInstaller frozen bundles.
    """
    if getattr(sys, "frozen", False):
        base = os.path.join(sys._MEIPASS, "webgui", "assets")
    else:
        base = os.path.join(os.path.dirname(__file__), "assets")
    return base


def start_app() -> None:
    """Create the pywebview window and start the event loop."""
    # Ensure the Versioned_methods directory exists
    if not os.path.exists(VERSIONED_METHODS_PATH):
        os.makedirs(VERSIONED_METHODS_PATH, exist_ok=True)

    assets = _assets_dir()
    index_path = os.path.join(assets, "index.html")

    api = VersionatorApi()

    window = webview.create_window(
        "Hamilton Method Versionator",
        url=index_path,
        js_api=api,
        width=1100,
        height=700,
        min_size=(800, 500),
    )
    api._window = window

    def on_closing() -> None:
        api.cleanup()
        if api._monitor_thread and api._monitor_thread.is_alive():
            api._monitor_stop.set()

    window.events.closing += on_closing

    webview.start()
