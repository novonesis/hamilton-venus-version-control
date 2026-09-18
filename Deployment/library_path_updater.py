"""Resolves ``#include`` dependencies in Hamilton HSL source files and copies libraries locally.

This module implements the Library Sync workflow: it analyses a ``.hsl`` file's
``#include`` tree (recursively), copies every resolved dependency into the
method's ``Libraries/`` folder, and rewrites the include paths to point at the
local copies so the method is self-contained and portable.

Key classes:

* :class:`LibraryDependency` — a single ``#include`` directive and its resolution.
* :class:`DependencyAnalyzer` — parses a source file and builds a dependency tree.
* :class:`DependencyReport` / :class:`DependencyReportItem` — stores and formats the tree.
* :class:`HamiltonLibrarySync` — top-level orchestrator wiring analysis, copy, and rewrite.
"""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from loguru import Logger


# LibraryDependency represents a single #include dependency and its resolution status.
class LibraryDependency:
    """Represents a single ``#include`` dependency found in a source file.

    Attributes:
        raw_include_path: The path as written in the ``#include`` directive.
        base_path: The directory to resolve relative paths against.
        resolved_path: The resolved absolute path, or ``None`` if not found.
    """

    def __init__(self, raw_include_path: str, base_path: Path, source_filename: Path):
        self.raw_include_path = raw_include_path  # The path as written in the #include
        self.file_name = Path(raw_include_path).name  # The file name extracted from the path
        self.base_path = base_path  # The directory to resolve relative paths
        self.source_filename = source_filename  # The file containing the include statement
        self.resolved_path = self.resolve_path()  # The resolved absolute path, or None if not found
        self._sub_dependencies = None  # Deferred computation of nested dependencies

    @property
    def sub_dependencies(self):
        if self._sub_dependencies is None:
            self._sub_dependencies = self.get_sub_dependencies(self.resolved_path)
        return self._sub_dependencies

    def get_sub_dependencies(self, resolved_path):
        sub_deps = []
        if resolved_path is None:
            return sub_deps

        try:
            sub_analyzer = DependencyAnalyzer(resolved_path)
            sub_deps.extend(
                [item.dependency for item in sub_analyzer.get_report_items()]
            )  # Add sub-dependencies to the list
        except Exception:
            logger.error(f"Error resolving sub-dependencies for {resolved_path}")
        return sub_deps

    def is_path_relative(self):
        return not Path(self.raw_include_path).is_absolute()

    def resolve_path(self):
        include_path_str = self.raw_include_path

        # Handle the __filename__ placeholder — a Venus convention where the
        # include directive uses ``__filename__`` as a stand-in for the stem of
        # the source file that contains the directive.  For example, a file
        # ``MyLib.hsl`` containing ``#include __filename__ ".hsi"`` should
        # resolve to ``MyLib.hsi``.
        if "__filename__" in include_path_str:
            if self.source_filename and self.source_filename.name:
                include_path_str = include_path_str.replace(
                    "__filename__", self.source_filename.stem
                )  # Use stem to remove extension
            else:
                logger.warning(
                    f"Cannot resolve __filename__ placeholder for '{self.raw_include_path}': source filename not available."
                )
                return None

        include_path = Path(include_path_str)

        if self.is_path_relative():
            abs_path = self.base_path / include_path
            if abs_path.exists():
                return str(abs_path)
            # Fallback: try the standard Hamilton Library installation directory
            fallback_path = Path(r"C:\Program Files (x86)\HAMILTON\Library") / include_path
            if fallback_path.exists():
                return str(fallback_path)
            return None  # Not found
        else:
            if include_path.exists():
                return str(include_path)
            return None  # Not found

    def __repr__(self):
        loaded = self._sub_dependencies is not None
        count = len(self._sub_dependencies) if loaded else "not loaded"
        return (
            f"LibraryDependency(raw_include_path='{self.raw_include_path}', "
            f"resolved_path='{self.resolved_path}', sub_dependencies={count})"
        )


# DependencyAnalyzer is responsible for analyzing a source file and generating dependency report.
class DependencyAnalyzer:
    """Parses a source file to discover and resolve ``#include`` dependencies.

    Attributes:
        input_path: Path to the source file being analysed.
        full_path: Absolute path to the source file.
        base_path: Directory containing the source file (used for relative resolution).
        report: :class:`DependencyReport` storing the results.
    """

    def __init__(self, input_path: str):
        self.input_path = input_path
        self.full_path = Path(self.input_path).resolve()  # Absolute path to the file
        self.base_path = self.full_path.parent  # Directory containing the file
        self.report = DependencyReport(self.full_path)  # Init report object to store results

        # Check if the file extension is one we should analyze for includes
        allowed_extensions = [".hsl", ".hsi", ".hs_"]
        if self.full_path.suffix.lower() in allowed_extensions:
            self._load_file()  # Load the file to analyze dependencies
        else:
            logger.debug(f"Skipping dependency analysis for non-source file: {self.input_path}")

    def _load_file(self):
        try:
            # Use 'errors="ignore"' to handle potential encoding issues in source files
            with open(self.input_path, encoding="utf-8", errors="ignore") as file:
                for line in file:
                    self._extract_includes(line)  # Extract and analyze includes
        except FileNotFoundError:
            logger.error(f"The file '{self.input_path}' was not found.")
        except Exception as e:
            # Log the specific error but continue processing other files
            logger.error(f"An error occurred while reading {self.input_path}: {e}")

    def _extract_includes(self, line: str):
        # Pattern 1 — standard quoted include: #include "path/to/file.hsl"
        standard_include_pattern = r'.*#include\s+"([^"]+)"'
        match_standard = re.match(standard_include_pattern, line)

        if match_standard:
            include_path = match_standard.group(1)
            # Analyze dependencies for the found include
            dependency = LibraryDependency(include_path, self.base_path, self.full_path)
            self.report.add_library_dependency(dependency)  # Add to report
            return  # Found a standard include, no need to check for the new pattern

        # Pattern 2 — dynamic filename placeholder: #include __filename__ ".hsi"
        # Venus uses this convention so the include resolves to the stem of the
        # containing file (e.g. ``MyLib.hsl`` → ``MyLib.hsi``).
        new_include_pattern = r'.*#include\s+__filename__\s+"([^"]+)"'
        match_new = re.match(new_include_pattern, line)

        if match_new:
            extension = match_new.group(1)  # Capture the extension
            # Construct the raw include path using __filename__ and the captured extension
            include_path = (
                f"__filename__{extension}"  # Reconstruct the path as __filename__.extension
            )
            # Analyze dependencies for the found include
            dependency = LibraryDependency(include_path, self.base_path, self.full_path)
            self.report.add_library_dependency(dependency)  # Add to report

    def get_report_items(self):
        """Return the list of :class:`DependencyReportItem` objects."""
        return self.report.report_items


class DependencyReportItem:
    """A single node in the dependency report tree.

    Attributes:
        dependency: The :class:`LibraryDependency` object.
        level: Depth in the dependency tree (1 = direct dependency).
    """

    def __init__(self, dependency: LibraryDependency, level: int):
        self.dependency = dependency
        self.level = level

    def __repr__(self):
        return f"DependencyReportItem(level={self.level}, dependency={self.dependency})"


# DependencyReport holds and formats the results of dependency analysis.
class DependencyReport:
    """Accumulates and formats the full dependency tree for a source file.

    Dependencies are de-duplicated: if the same ``raw_include_path`` is
    encountered at multiple tree levels, only the deepest (or the resolved)
    version is kept.

    Attributes:
        source_file_path: Absolute path to the analysed source file.
        report_items: All discovered :class:`DependencyReportItem` entries.
    """

    MAX_DEPTH: int = 50

    def __init__(self, source_file_path: Path):
        self.source_file_path = source_file_path
        self.report_items: list[DependencyReportItem] = []  # List of LibraryDependency objects
        self.resolved_paths: set = set()  # Set to track resolved paths
        self.unresolved_paths: set = set()  # Set to track unresolved paths
        self._processed_resolved_paths: set[str] = set()  # Dedup by resolved physical path
        self.max_level = 0  # Maximum depth level in the dependency tree

    def add_library_dependency(self, dependency: LibraryDependency, current_level: int = 1):
        """Add a dependency to the report, de-duplicating by raw include path.

        If a dependency with the same ``raw_include_path`` already exists:

        * If the existing entry was *unresolved* and the new one is *resolved*,
          the existing entry is upgraded in-place.
        * Otherwise the duplicate is silently ignored.

        Sub-dependencies are added recursively up to :attr:`MAX_DEPTH`.

        Args:
            dependency: The dependency to add.
            current_level: Tree depth (1 = direct include).
        """
        if current_level >= self.MAX_DEPTH:
            logger.warning(
                f"Max dependency depth ({self.MAX_DEPTH}) reached at '{dependency.file_name}'"
            )
            return

        # Check if a dependency with the same raw include path already exists
        existing_item = None
        for item in self.report_items:
            if item.dependency.raw_include_path == dependency.raw_include_path:
                existing_item = item
                break

        if existing_item:
            # If the existing item is unresolved and the new one is resolved, update the existing one
            if (
                existing_item.dependency.resolved_path is None
                and dependency.resolved_path is not None
            ):
                # Remove from unresolved set and add to resolved set
                if existing_item.dependency.raw_include_path in self.unresolved_paths:
                    self.unresolved_paths.remove(existing_item.dependency.raw_include_path)
                self.resolved_paths.add(dependency.resolved_path)

                # Update the existing report item's dependency object
                existing_item.dependency = dependency
                # Update level if the new one is deeper
                if current_level > existing_item.level:
                    existing_item.level = current_level

                # Recursively add sub-dependencies of the newly resolved dependency
                if dependency.sub_dependencies:
                    for sub_dep in dependency.sub_dependencies:
                        self.add_library_dependency(sub_dep, existing_item.level + 1)

            # If the existing item is already resolved or the new one is also unresolved,
            # or the new one is resolved but the existing one is deeper in the tree,
            # we don't need to add or update, just ensure the resolved path is tracked.
            elif (
                dependency.resolved_path is not None
                and dependency.resolved_path not in self.resolved_paths
            ):
                self.resolved_paths.add(dependency.resolved_path)

            return  # Duplicate or updated, do not add a new item

        # If no existing item, add the new dependency
        if dependency.resolved_path is not None:
            self.resolved_paths.add(dependency.resolved_path)
        else:
            self.unresolved_paths.add(dependency.raw_include_path)

        self.report_items.append(DependencyReportItem(dependency, current_level))  # Add to report

        if current_level > self.max_level:
            self.max_level = current_level  # Update max level

        # Skip sub-dependency recursion if this resolved path was already fully traversed
        if dependency.resolved_path is not None:
            if dependency.resolved_path in self._processed_resolved_paths:
                return
            self._processed_resolved_paths.add(dependency.resolved_path)

        # Recursively add sub-dependencies
        if dependency.sub_dependencies:
            for sub_dep in dependency.sub_dependencies:
                self.add_library_dependency(
                    sub_dep, current_level + 1
                )  # Recursively add sub-dependencies

    def show_dependency_tree(self, show_level: int = 0, full_path: bool = False) -> str:
        """Render the dependency tree as an indented string.

        Args:
            show_level: Maximum depth to display (0 = unlimited).
            full_path: If ``True``, append the resolved absolute path.

        Returns:
            A multi-line string representation of the tree.
        """

        unit_indent = "   ."  # Four spaces
        tree_lines = []

        def build_tree_line(report_item: DependencyReportItem, level: int = 1):
            indent = unit_indent * (level - 1)

            # Use the filename from the resolved path if available, otherwise use the raw filename
            file_name_to_display = report_item.dependency.file_name
            optional_info = ""

            if report_item.dependency.resolved_path:
                file_name_to_display = Path(report_item.dependency.resolved_path).name
                if full_path:
                    optional_info = "(" + report_item.dependency.resolved_path + ")"
                tree_str = f"{indent}└──> {file_name_to_display} {optional_info}"
            else:
                if file_name_to_display is None:
                    file_name_to_display = "[UNKNOWN FILE]"
                tree_str = f"{indent}└──> {file_name_to_display} [UNRESOLVED] {optional_info}"

            # If level is 0, show all levels; else, limit to specified level
            if show_level == 0 or level <= show_level:
                return tree_str
            else:
                return None

        count = 0
        for report_item in self.report_items:
            tree_str = build_tree_line(report_item, report_item.level)
            if tree_str:
                if report_item.level == 1:
                    count += 1
                    tree_lines.append(str(count).rjust(3) + " " + tree_str)
                else:
                    tree_lines.append(unit_indent + tree_str)

        header = f"{self.source_file_path.name} ({count} primary dependencies, {len(self.unique_dependencies)} total dependencies, {self.max_level} levels)"
        return header + "\n" + "\n".join(tree_lines)

    def to_dict(self) -> dict:
        """Return the dependency tree as a JSON-serializable dict.

        The output is framework-agnostic and serves as the single source of
        truth for all tree rendering (tkinter today, pywebview tomorrow).
        """
        root: dict = {
            "source_file": str(self.source_file_path),
            "source_file_name": self.source_file_path.name,
            "primary_count": sum(1 for item in self.report_items if item.level == 1),
            "total_unique": len(self.unique_dependencies),
            "max_level": self.max_level,
            "dependencies": [],
        }
        stack: dict[int, list] = {0: root["dependencies"]}
        for item in self.report_items:
            node = {
                "file_name": item.dependency.file_name,
                "raw_include_path": item.dependency.raw_include_path,
                "resolved_path": item.dependency.resolved_path,
                "resolved": item.dependency.resolved_path is not None,
                "level": item.level,
                "children": [],
            }
            parent_level = item.level - 1
            parent_list = stack.get(parent_level, root["dependencies"])
            parent_list.append(node)
            stack[item.level] = node["children"]
        return root

    @property
    def unique_dependencies(self):
        return list(
            {
                report_item.dependency.resolved_path: report_item
                for report_item in self.report_items
                if report_item.dependency.resolved_path is not None
            }.values()
        )

    @property
    def unresolved_dependencies(self):
        return [
            report_item
            for report_item in self.report_items
            if not report_item.dependency.resolved_path
        ]

    @property
    def resolved_dependencies(self):
        return [
            report_item for report_item in self.report_items if report_item.dependency.resolved_path
        ]

    def __repr__(self):
        return self.show_dependency_tree()


class HamiltonLibrarySync:
    """Top-level orchestrator for copying and re-pathing Hamilton library files.

    Given a ``.hsl`` file, this class:

    1. Analyses its ``#include`` tree via :class:`DependencyAnalyzer`.
    2. Copies every resolved dependency (and same-basename companions) into
       the method's ``Libraries/`` folder.
    3. Rewrites ``#include`` paths in both the original file and the copies
       so they reference the local ``Libraries/`` copies.

    Attributes:
        file_path: Path to the ``.hsl`` file being processed.
        library_logger: Bound Loguru logger for progress messages.
    """

    def __init__(self, file_path: str, library_logger: Logger) -> None:
        """Initialise the sync tool.

        Args:
            file_path: Path to the Hamilton method file (``.hsl``).
            library_logger: Loguru logger instance for logging.
        """
        self.file_path = file_path  # Assuming this is something like .../methodName/Libraries/file
        self.library_logger = library_logger
        self.dependency_analyzer = None  # To store the DependencyAnalyzer instance

        # Step up two levels to get the methodName directory
        self.root_dir = os.path.abspath(os.path.join(os.path.dirname(self.file_path), ".."))

        # Now, construct the path to the Libraries folder within the methodName directory
        self.libraries_folder = os.path.join(self.root_dir, "Libraries")
        self.excluded_libraries = []  # commented out to keep versioning the shared libraries "HSLMECCLib", "HSLMETEDLib", "HSLPTLLib", "HSLSTCCLib"

    def normalize_path(self, mixed_path: str) -> str:
        """Normalise a path for Venus HSL files.

        Forward slashes become backslashes, then each backslash is doubled
        (Venus expects ``\\\\`` as path separators inside ``#include`` directives).

        Args:
            mixed_path: The path string to normalise.

        Returns:
            The doubled-backslash path string.
        """
        path_with_backslashes = mixed_path.replace("/", "\\")
        # Double each backslash for Venus HSL format (e.g. C:\\Users\\...)
        normalized_path = path_with_backslashes.replace("\\", "\\\\")
        return normalized_path

    def should_exclude_library(self, include_file_path: str) -> bool:
        """Check whether *include_file_path* matches an excluded library name.

        Args:
            include_file_path: The resolved file path to check.

        Returns:
            ``True`` if the path should be skipped.
        """
        return any(excluded_word in include_file_path for excluded_word in self.excluded_libraries)

    def update_path_for_all_files_in_versioned_library(self) -> None:
        """Rewrite ``#include`` paths in the selected HSL and all library files."""
        library_directory = self.libraries_folder

        if not os.path.exists(library_directory):
            self.library_logger.info("Library directory does not exist. Skipping update.")
            return

        # Ensure to update the selected HSL file paths
        self.update_file_paths_to_versioned_library_folder(self.file_path)

        # Update paths in all eligible library files within the library directory
        for filename in os.listdir(library_directory):
            if filename.endswith(".hsl") or filename.endswith(".hs_") or filename.endswith(".hsi"):
                file_path = os.path.join(library_directory, filename)
                self.update_file_paths_to_versioned_library_folder(file_path)

    def update_file_paths_to_versioned_library_folder(self, file_path: str) -> None:
        """Rewrite ``#include`` directives in *file_path* to use versioned library paths.

        Args:
            file_path: The HSL/HSI/HS_ file to update.
        """
        try:
            with open(file_path, encoding="utf-8", errors="ignore") as file:
                lines = file.readlines()

            updated_lines = []
            # Regex to match both standard #include "filename" and the new #include __filename__ ".hsi"
            include_pattern = re.compile(r'#include\s+(?:"([^"]+)"|([^"]+)\s+".hsi")')

            for line in lines:
                match = include_pattern.search(line)
                if match:
                    # Check if the line contains the dynamic filename placeholder
                    if "__filename__" in line:
                        # If it does, keep the original line and skip processing
                        updated_lines.append(line)
                        continue  # Move to the next line

                    # Check which group matched (standard or new pattern)
                    standard_path = match.group(1)
                    dynamic_basename = match.group(2)

                    included_file_raw_path = None
                    if standard_path:
                        included_file_raw_path = standard_path
                    elif dynamic_basename:
                        included_file_raw_path = (
                            dynamic_basename + ".hsi"
                        )  # Reconstruct the raw path for lookup

                    if included_file_raw_path:
                        # Get the resolved path using the dependency analyzer results
                        resolved_path = self._get_resolved_path_for_include(included_file_raw_path)

                        if resolved_path and not self.should_exclude_library(resolved_path):
                            # Construct the new absolute path to the file in the versioned Libraries folder
                            target_file_in_versioned_lib = os.path.join(
                                self.libraries_folder, os.path.basename(resolved_path)
                            )
                            new_include_path_absolute = os.path.abspath(
                                target_file_in_versioned_lib
                            )

                            # Normalize path separators and double backslashes
                            new_include_path_formatted = self.normalize_path(
                                new_include_path_absolute
                            )

                            # Replace the original include statement with the new absolute path in quotes.
                            # A lambda is used as the replacement argument to re.sub so that
                            # backslashes in new_include_path_formatted are treated as literal
                            # characters rather than regex back-references.
                            new_line = include_pattern.sub(
                                lambda m, path=new_include_path_formatted: f'#include "{path}"',
                                line,
                            )
                            updated_lines.append(new_line)
                        else:
                            # If resolved_path is None or excluded, keep the original line
                            updated_lines.append(line)
                    else:
                        # If no included_file_raw_path was determined, keep the original line
                        updated_lines.append(line)
                else:
                    # If no include pattern matched, keep the original line
                    updated_lines.append(line)

            if lines != updated_lines:
                self.library_logger.info(f"Writing updated lines back to {file_path}")
                with open(file_path, "w", encoding="utf-8") as file:
                    file.writelines(updated_lines)
            else:
                self.library_logger.info(f"Skipped writing: No changes needed for {file_path}")

        except Exception as e:
            self.library_logger.info(f"Error occurred during update operation for {file_path}: {e}")

    def _get_resolved_path_for_include(self, included_file_raw_path: str) -> str | None:
        """Look up the resolved path for a raw include directive.

        Searches the :class:`DependencyAnalyzer` report items for a matching
        ``raw_include_path`` and returns the resolved absolute path.

        Args:
            included_file_raw_path: The path string as written in the ``#include``.

        Returns:
            Absolute resolved path, or ``None`` if not found.
        """
        if not self.dependency_analyzer:
            self.library_logger.error("DependencyAnalyzer not initialized.")
            return None

        # Search through all report items to find the matching raw include path
        for dep_item in self.dependency_analyzer.report.report_items:
            if dep_item.dependency.raw_include_path == included_file_raw_path:
                return dep_item.dependency.resolved_path

        self.library_logger.warning(
            f"Could not find resolved path for include '{included_file_raw_path}'"
        )
        return None

    def _copy_related_files_by_basename(
        self, source_dir: str, basename: str, destination_dir: str
    ) -> None:
        """Copy all files sharing *basename* from *source_dir* to *destination_dir*.

        Only copies when the destination is missing or older than the source.

        Args:
            source_dir: Directory to search for matching files.
            basename: File stem to match (without extension).
            destination_dir: Where copies are placed.
        """
        if not os.path.exists(source_dir):
            self.library_logger.warning(f"Source directory does not exist: {source_dir}")
            return

        copied_or_skipped = False
        for file_name in os.listdir(source_dir):
            file_basename, _ = os.path.splitext(file_name)
            if file_basename == basename:
                copied_or_skipped = True
                source_file_path = os.path.join(source_dir, file_name)
                destination_file_path = os.path.join(destination_dir, file_name)

                try:
                    # Only copy if destination doesn't exist or is outdated
                    if not os.path.exists(destination_file_path):
                        shutil.copy2(source_file_path, destination_file_path)
                        self.library_logger.info(
                            f"Copied related file (new): {source_file_path} to {destination_file_path}"
                        )
                    elif os.path.getmtime(source_file_path) > os.path.getmtime(
                        destination_file_path
                    ):
                        shutil.copy2(source_file_path, destination_file_path)
                        self.library_logger.info(
                            f"Copied related file (updated): {source_file_path} to {destination_file_path}"
                        )
                    else:
                        self.library_logger.info(
                            f"Skipped - Related file already exists and is up to date: {destination_file_path}"
                        )
                except Exception as e:
                    self.library_logger.error(
                        f"Failed to copy related file {source_file_path}: {e}"
                    )

        if not copied_or_skipped:
            self.library_logger.warning(
                f"No files found with basename '{basename}' in '{source_dir}' to copy."
            )

    def copy_enu_files_to_libraries_folder(self) -> None:
        """Copy Hamilton ``Enu`` (language resource) files to the Libraries folder.

        These files live in the global Hamilton ``Library/`` directory and are
        needed at runtime for UI string localisation.
        """
        source_folder = r"C:\Program Files (x86)\HAMILTON\Library"
        destination_folder = self.libraries_folder

        if not os.path.exists(source_folder):
            self.library_logger.info(f"Source folder does not exist: {source_folder}")
            return

        for file_name in os.listdir(source_folder):
            if "Enu" in file_name:
                source_file_path = os.path.join(source_folder, file_name)
                destination_file_path = os.path.join(destination_folder, file_name)

                try:
                    if not os.path.exists(destination_file_path):
                        shutil.copy2(source_file_path, destination_file_path)
                        self.library_logger.info(
                            f"Copied Enu file (new): {source_file_path} to {destination_file_path}"
                        )
                    elif os.path.getmtime(source_file_path) > os.path.getmtime(
                        destination_file_path
                    ):
                        shutil.copy2(source_file_path, destination_file_path)
                        self.library_logger.info(
                            f"Copied Enu file (updated): {source_file_path} to {destination_file_path}"
                        )
                    else:
                        self.library_logger.info(
                            f"Skipped Enu file - already up to date: {destination_file_path}"
                        )
                except Exception as e:
                    self.library_logger.info(f"Failed to copy Enu file {source_file_path}: {e}")

    def initiate_library_files_update_process(self) -> None:
        """Run the full library sync pipeline.

        1. Analyse ``#include`` dependencies via :class:`DependencyAnalyzer`.
        2. Copy resolved files (and same-basename companions) to ``Libraries/``.
        3. Re-analyse all copied files to discover transitive dependencies.
        4. Rewrite ``#include`` paths in the original and copied files.
        5. Copy Hamilton ``Enu`` language-resource files.
        """
        # Check if a file has been selected before proceeding
        if not self.file_path:
            self.library_logger.info("No file selected. Operation aborted.")
            return

        # Convert from UNIX path format to current OS (Windows) path format
        self.file_path = os.path.abspath(self.file_path)

        try:
            # Use DependencyAnalyzer to get resolved dependencies from the initial file
            self.dependency_analyzer = DependencyAnalyzer(self.file_path)
            initial_resolved_dependencies = self.dependency_analyzer.report.resolved_dependencies

            # Ensure directory for 'Libraries' exists
            os.makedirs(self.libraries_folder, exist_ok=True)

            # Copy resolved dependency files and related files by basename to the versioned 'Libraries' folder
            copied_basenames = set()  # To avoid processing the same basename multiple times
            files_to_analyze_for_paths = (
                set()
            )  # Keep track of files copied to analyze their dependencies later

            # Add the initial file to the list of files to analyze for paths
            files_to_analyze_for_paths.add(self.file_path)

            for dep_item in initial_resolved_dependencies:
                source_file_path = dep_item.dependency.resolved_path
                if source_file_path and os.path.exists(source_file_path):
                    source_dir = os.path.dirname(source_file_path)
                    basename = os.path.splitext(os.path.basename(source_file_path))[0]

                    if basename not in copied_basenames:
                        # Copy related files by basename
                        self._copy_related_files_by_basename(
                            source_dir, basename, self.libraries_folder
                        )
                        copied_basenames.add(basename)

                        # Add the copied files to the list of files to analyze for paths
                        # We need to find the actual files copied, which might have different extensions
                        for copied_filename in os.listdir(self.libraries_folder):
                            copied_basename, _ = os.path.splitext(copied_filename)
                            if copied_basename == basename:
                                files_to_analyze_for_paths.add(
                                    os.path.join(self.libraries_folder, copied_filename)
                                )

            # Now, analyze dependencies for all files that were copied (and the initial file)
            # and add them to the main dependency_analyzer report.
            # This ensures that _get_resolved_path_for_include can find dependencies
            # within the copied files themselves.
            seen_realpaths = set()
            for file_path_to_analyze in files_to_analyze_for_paths:
                real_path = os.path.realpath(file_path_to_analyze)
                if real_path in seen_realpaths or not os.path.exists(real_path):
                    continue
                if real_path in self.dependency_analyzer.report._processed_resolved_paths:
                    continue
                seen_realpaths.add(real_path)
                try:
                    temp_analyzer = DependencyAnalyzer(real_path)
                    for dep_item in temp_analyzer.report.report_items:
                        self.dependency_analyzer.report.add_library_dependency(
                            dep_item.dependency, dep_item.level
                        )
                except Exception as e:
                    self.library_logger.error(
                        f"Error analyzing dependencies in copied file {real_path}: {e}"
                    )

            # Update include paths in the original file and copied files
            self.update_path_for_all_files_in_versioned_library()

            # Copy files containing 'Enu' to Libraries folder
            self.copy_enu_files_to_libraries_folder()

            self.library_logger.success(f"All libraries synchronized for {self.file_path}")

        except Exception as e:
            self.library_logger.error(f"An error occurred during the library update process: {e}")
