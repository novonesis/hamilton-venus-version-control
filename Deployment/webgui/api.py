"""Python API class exposed to JavaScript via pywebview's ``js_api``.

Every public method on :class:`VersionatorApi` is callable from the browser
as ``await pywebview.api.method_name(args)``.
"""

from __future__ import annotations

import os
import threading
from typing import Any

from loguru import logger

from webgui.log_bridge import LogBuffer, make_log_sink, make_tab_filter

VERSIONED_METHODS_PATH = "C:/Program Files (x86)/HAMILTON/Versioned_methods"
README_PATH = "README.md"

# Tab names used for log filtering (must match JS side)
TAB_NAMES = (
    "conversion",
    "labware",
    "library",
    "folder_sync",
)


class VersionatorApi:
    """The complete JS bridge for the Hamilton Method Versionator webgui.

    Instantiated once in ``app.py`` and passed to ``webview.create_window``
    as ``js_api``.  Each public method is available in JS as
    ``pywebview.api.<method>()``.
    """

    def __init__(self) -> None:
        self._window: Any = None  # set by app.py after window creation

        # Per-tab log buffers + Loguru sink IDs
        self._log_buffers: dict[str, LogBuffer] = {}
        self._sink_ids: dict[str, int] = {}
        for tab in TAB_NAMES:
            buf = LogBuffer()
            self._log_buffers[tab] = buf
            sid = logger.add(
                make_log_sink(buf),
                format="{time:HH:mm:ss} | {level} | {message}",
                filter=make_tab_filter(tab),
                level="INFO",
                enqueue=True,
            )
            self._sink_ids[tab] = sid

        # Task-running flags (one per tab, for UI polling)
        self._running: dict[str, bool] = {}

        # Monitoring state (Folder Sync tab)
        self._monitor_thread: threading.Thread | None = None
        self._monitor_stop: threading.Event = threading.Event()
        self._monitor_status: str = "Not Started"

        # Labware tab state
        self._labware_folder: str | None = None
        self._labware_resolved_paths: list[str] = []

        # Library tab state
        self._library_tree_data: dict | None = None

    # ── Lifecycle ──────────────────────────────────────────────────────

    def cleanup(self) -> None:
        """Remove all Loguru sinks. Called on window close."""
        for sid in self._sink_ids.values():
            try:
                logger.remove(sid)
            except ValueError:
                pass

    # ── Log polling ────────────────────────────────────────────────────

    def poll_logs(self, tab: str, last_seen: int) -> dict:
        """Return new log lines since *last_seen* for *tab*.

        Called by JS on a 200ms ``setInterval``.
        """
        buf = self._log_buffers.get(tab)
        if buf is None:
            return {"lines": [], "cursor": 0}
        lines, cursor = buf.read_new(last_seen)
        return {"lines": lines, "cursor": cursor}

    def clear_logs(self, tab: str) -> None:
        """Discard all buffered log lines for *tab*."""
        buf = self._log_buffers.get(tab)
        if buf:
            buf.clear()

    # ── Task state ─────────────────────────────────────────────────────

    def is_task_running(self, tab: str) -> bool:
        """Return whether a background task is active for *tab*."""
        return self._running.get(tab, False)

    # ── File / folder dialogs ──────────────────────────────────────────

    def pick_folder(self, initial_dir: str = "") -> str | None:
        """Open a native folder picker."""
        if not self._window:
            return None
        result = self._window.create_file_dialog(
            dialog_type=20,  # FOLDER_DIALOG
            directory=initial_dir or "",
        )
        if result and len(result) > 0:
            return result[0]
        return None

    def pick_file(self, file_types: str = "", initial_dir: str = "") -> str | None:
        """Open a native file picker.

        *file_types* is a pywebview filter string, e.g.
        ``"HSL Files (*.hsl)"`` or ``"CSV Files (*.csv)"``.
        """
        if not self._window:
            return None
        ft = tuple(file_types.split(";")) if file_types else ()
        result = self._window.create_file_dialog(
            dialog_type=10,  # OPEN_DIALOG
            directory=initial_dir or "",
            file_types=ft,
        )
        if result and len(result) > 0:
            return result[0]
        return None

    # ── Tab 1: Usage Guide ─────────────────────────────────────────────

    def get_usage_guide_markdown(self) -> str:
        """Return the ``## Usage`` section from ``README.md`` as raw markdown."""
        try:
            with open(README_PATH, encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            return "README.md not found. Ensure it is in the same directory as the application."
        except Exception as e:
            return f"Failed to read README.md: {e}"

        start = None
        for i, line in enumerate(lines):
            if line.strip().startswith("## ") and "Usage" in line.strip():
                start = i
                break
        if start is None:
            return "No Usage section found in README.md."

        end = len(lines)
        for i in range(start + 1, len(lines)):
            stripped = lines[i].strip()
            if stripped.startswith("## ") and not stripped.startswith("### "):
                end = i
                break

        return "".join(lines[start:end]).strip()

    # ── Tab 2: Folder Creator ──────────────────────────────────────────

    def browse_folder_creation(self) -> str | None:
        """Open a folder dialog for the destination path."""
        return self.pick_folder(VERSIONED_METHODS_PATH)

    def browse_med_file(self) -> str | None:
        """Open a file dialog for a ``.med`` file."""
        return self.pick_file(
            "Method Files (*.med)",
            "C:/Program Files (x86)/HAMILTON/Methods",
        )

    def create_folder_structure(self, dest: str, name: str, med: str, force: bool) -> dict:
        """Create the versioned-method folder structure.

        Returns ``{status, message}`` matching :class:`FolderCreationResult`.
        """
        from folder_structure_creator import create_folder_structure as _create

        result = _create(dest, name, med or None, force=force)
        return {"status": result.status, "message": result.message}

    # ── Tab 3: Folder Sync ─────────────────────────────────────────────

    def select_csv_file(self) -> str | None:
        """Open a file dialog for a CSV file."""
        return self.pick_file("CSV Files (*.csv)")

    def start_monitoring(self, csv_path: str, frequency: int) -> dict:
        """Start the monitoring thread. Returns ``{ok, message}``."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            return {"ok": False, "message": "Monitoring is already running."}
        if not csv_path:
            return {"ok": False, "message": "CSV path is required."}

        from monitoring import run_monitoring

        self._monitor_stop.clear()
        self._monitor_status = "Running"

        def status_cb(s: str) -> None:
            self._monitor_status = s

        self._monitor_thread = threading.Thread(
            target=run_monitoring,
            args=(csv_path, frequency, status_cb, self._monitor_stop),
            daemon=True,
        )
        self._monitor_thread.start()
        return {"ok": True, "message": "Monitoring started."}

    def stop_monitoring(self) -> dict:
        """Signal the monitoring thread to stop."""
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_stop.set()
            self._monitor_thread = None
            self._monitor_status = "Stopped"
            return {"ok": True, "message": "Monitoring stopped."}
        return {"ok": False, "message": "Monitoring is not running."}

    def get_monitoring_status(self) -> str:
        """Return current monitoring status string."""
        return self._monitor_status

    def is_monitoring_active(self) -> bool:
        """Return whether the monitoring thread is alive."""
        return bool(self._monitor_thread and self._monitor_thread.is_alive())

    # ── Tab 4: File Converter ──────────────────────────────────────────

    def select_conversion_folder(self) -> str | None:
        """Open a folder dialog for file conversion."""
        return self.pick_folder()

    def start_conversion(self, folder: str) -> dict:
        """Run the Hamilton file converter in a background thread."""
        if not folder:
            return {"ok": False, "message": "No folder selected."}
        if self._running.get("conversion"):
            return {"ok": False, "message": "Conversion already running."}

        from file_converter import run_conversion

        self._running["conversion"] = True
        self.clear_logs("conversion")

        def work() -> None:
            try:
                conversion_log = logger.bind(tab="conversion")
                conversion_log.info(f"Starting file conversion for: {folder}")
                run_conversion(folder, conversion_log)
                conversion_log.success("File conversion completed.")
            except Exception as e:
                logger.bind(tab="conversion").error(f"Conversion error: {e}")
            finally:
                self._running["conversion"] = False

        threading.Thread(target=work, daemon=True).start()
        return {"ok": True, "message": "Conversion started."}

    # ── Tab 5: Labware Sync ────────────────────────────────────────────

    def select_labware_folder(self) -> dict | None:
        """Open a folder dialog, resolve shortcuts, return metadata."""
        folder = self.pick_folder("C:/Program Files (x86)/HAMILTON/Versioned_methods")
        if not folder:
            return None

        self._labware_folder = folder
        labware_log = logger.bind(tab="labware")
        labware_log.info(f"Selected folder: {folder}")

        # Ensure shortcuts exist
        self._ensure_shortcuts_exist(folder, labware_log)

        # Resolve shortcuts
        shortcut_files = [f for f in os.listdir(folder) if f.endswith(".lnk")]
        self._labware_resolved_paths = []
        for sc in shortcut_files:
            sc_path = os.path.join(folder, sc)
            try:
                import win32com.client

                shell = win32com.client.Dispatch("WScript.Shell")
                shortcut = shell.CreateShortcut(sc_path)
                real_path = os.path.normpath(shortcut.TargetPath)
                if os.path.exists(real_path):
                    self._labware_resolved_paths.append(real_path)
                    labware_log.info(f"Resolved shortcut: {sc} -> {real_path}")
                else:
                    labware_log.warning(f"Resolved path does not exist: {real_path}")
            except Exception as e:
                labware_log.error(f"Failed to resolve shortcut {sc}: {e}")

        return {
            "folder": folder,
            "resolved_paths": self._labware_resolved_paths,
            "shortcut_count": len(shortcut_files),
        }

    def _ensure_shortcuts_exist(self, root_folder: str, labware_log: Any) -> None:
        """Create shortcuts if none exist (mirrors gui/labware_tab.py logic)."""
        shortcut_files = [f for f in os.listdir(root_folder) if f.endswith(".lnk")]
        if shortcut_files:
            labware_log.info("Shortcuts already exist. Skipping creation.")
            return

        libraries_folder = os.path.join(root_folder, "Libraries")
        if not os.path.exists(libraries_folder):
            labware_log.warning(f"No Libraries folder found in: {root_folder}")
            return

        from folder_structure_creator import create_shortcut

        med_files = [f for f in os.listdir(libraries_folder) if f.endswith(".med")]
        lay_files = [f for f in os.listdir(libraries_folder) if f.endswith(".lay")]

        if not med_files and not lay_files:
            labware_log.warning(f"No .med or .lay files found in {libraries_folder}")
            return

        labware_log.info(f"Found {len(med_files)} .med files and {len(lay_files)} .lay files")

        for med_file in med_files:
            base_name = os.path.splitext(med_file)[0]
            related = [f for f in os.listdir(libraries_folder) if f.startswith(base_name)]
            for file in related:
                source_path = os.path.join(libraries_folder, file)
                shortcut_path = os.path.join(root_folder, file + ".lnk")
                try:
                    create_shortcut(source_path, shortcut_path)
                    labware_log.info(f"Shortcut created: {shortcut_path} -> {source_path}")
                except Exception as e:
                    labware_log.error(f"Failed to create shortcut for {source_path}: {e}")

        for lay_file in lay_files:
            source_path = os.path.join(libraries_folder, lay_file)
            shortcut_path = os.path.join(root_folder, lay_file + ".lnk")
            try:
                create_shortcut(source_path, shortcut_path)
                labware_log.info(f"Shortcut created: {shortcut_path} -> {source_path}")
            except Exception as e:
                labware_log.error(f"Failed to create shortcut for {source_path}: {e}")

        labware_log.info("Shortcut creation completed.")

    def start_labware_processing(self) -> dict:
        """Run labware processing in a background thread."""
        if not self._labware_folder or not self._labware_resolved_paths:
            return {"ok": False, "message": "No valid folder or shortcuts selected."}
        if self._running.get("labware"):
            return {"ok": False, "message": "Labware processing already running."}

        from file_converter import run_conversion
        from labware_sync import LabwareFileProcessor

        self._running["labware"] = True
        self.clear_logs("labware")
        folder = self._labware_folder
        resolved = list(self._labware_resolved_paths)

        def work() -> None:
            labware_log = logger.bind(tab="labware")
            labware_log.info("Starting labware processing")
            try:
                libraries_folder = os.path.join(folder, "Libraries")
                run_conversion(libraries_folder, labware_log)

                processor = LabwareFileProcessor(labware_log)
                lay_files = [f for f in resolved if f.endswith(".lay")]

                if lay_files:
                    success = processor.start_processing_lay_files(folder)
                    if success:
                        labware_log.success("Successfully updated labware files")
                        labware_folder_path = os.path.join(folder, "Labware")
                        run_conversion(labware_folder_path, labware_log)
                        processor.log_paths_in_rck_and_tml_files(labware_folder_path)
                    else:
                        labware_log.error("Failed to update labware files")
                else:
                    labware_log.error("No .lay file found in resolved shortcuts.")
            except Exception as e:
                labware_log.error(f"Labware processing error: {e}")
            finally:
                self._running["labware"] = False

        threading.Thread(target=work, daemon=True).start()
        return {"ok": True, "message": "Labware processing started."}

    # ── Tab 6: Library Sync ────────────────────────────────────────────

    def select_hsl_file(self) -> str | None:
        """Open a file dialog for an ``.hsl`` file."""
        return self.pick_file(
            "HSL Files (*.hsl)",
            "C:/Program Files (x86)/HAMILTON/Versioned_methods",
        )

    def start_library_sync(self, hsl_path: str) -> dict:
        """Run the library sync pipeline in a background thread."""
        if not hsl_path:
            return {"ok": False, "message": "No HSL file selected."}
        if self._running.get("library"):
            return {"ok": False, "message": "Library sync already running."}

        from library_path_updater import HamiltonLibrarySync

        self._running["library"] = True
        self._library_tree_data = None
        self.clear_logs("library")

        def work() -> None:
            library_log = logger.bind(tab="library")
            try:
                updater = HamiltonLibrarySync(hsl_path, library_log)
                updater.initiate_library_files_update_process()

                if updater.dependency_analyzer and updater.dependency_analyzer.report:
                    self._library_tree_data = updater.dependency_analyzer.report.to_dict()
            except Exception as e:
                library_log.error(f"Library sync error: {e}")
            finally:
                self._running["library"] = False

        threading.Thread(target=work, daemon=True).start()
        return {"ok": True, "message": "Library sync started."}

    def get_library_tree_data(self) -> dict | None:
        """Return the dependency tree dict, or ``None`` if not yet available."""
        return self._library_tree_data

    # ── Tab 7: File Search ─────────────────────────────────────────────

    def select_search_folder(self) -> str | None:
        """Open a folder dialog for file search."""
        return self.pick_folder(VERSIONED_METHODS_PATH)

    def search_files(self, folder: str, query: str, include_auxiliary: bool) -> list[dict]:
        """Run a synchronous text search and return results.

        Returns a list of ``{path, line, content}`` dicts.
        """
        from string_search import search_files as _search

        results = _search(folder, query, include_auxiliary=include_auxiliary)
        return [{"path": r[0], "line": r[1], "content": r[2]} for r in results]
