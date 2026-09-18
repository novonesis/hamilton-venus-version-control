"""Low-level file and directory synchronisation utilities.

Provides helpers for safe file copying and bi-directional directory sync
(copy new/updated files, delete orphans) used by the Folder Sync tab and
the monitoring loop.
"""

from __future__ import annotations

import os
import shutil

from loguru import logger


def is_temporary_file(file_path: str) -> bool:
    """Return ``True`` if *file_path* looks like a temporary or lock file.

    Args:
        file_path: The path (or filename) to check.

    Returns:
        ``True`` for ``.tmp`` suffixes and ``~$`` prefixes (Office lock files).
    """
    return file_path.endswith(".tmp") or file_path.startswith("~$")


def safe_copy(src_file_path: str, dest_file_path: str) -> None:
    """Copy a file from *src_file_path* to *dest_file_path* with safety checks.

    Skips temporary files and non-existent sources.  Existing destinations
    trigger a warning but are overwritten.

    Args:
        src_file_path: The source file to copy.
        dest_file_path: The destination path.
    """
    try:
        if not os.path.exists(src_file_path) or is_temporary_file(src_file_path):
            logger.error(f"Source file does not exist or is a temporary file: {src_file_path}")
            return
        if os.path.exists(dest_file_path):
            logger.warning(
                f"File {os.path.basename(dest_file_path)} already exists in destination."
            )
        shutil.copy2(src_file_path, dest_file_path)  # copy2 preserves metadata
        logger.info(f"Copied '{src_file_path}' to '{dest_file_path}'")
    except Exception as e:
        logger.error(f"Failed to copy file: {e}")


def sync_directories(source_folder: str, dest_folder: str) -> None:
    """Synchronise *source_folder* into *dest_folder*.

    New and updated files are copied; files that no longer exist in the source
    are deleted from the destination.

    Args:
        source_folder: The authoritative source directory.
        dest_folder: The mirror directory to synchronise.
    """
    source_paths: set[str] = set()
    dest_paths: set[str] = set()

    # Build sets of relative paths for source and destination
    try:
        for subdir, dirs, files in os.walk(source_folder):
            for item in dirs + files:
                source_paths.add(os.path.relpath(os.path.join(subdir, item), source_folder))
    except Exception as e:
        logger.error(f"Error reading source directory '{source_folder}'. Error: {e}")
        return

    try:
        for subdir, dirs, files in os.walk(dest_folder):
            for item in dirs + files:
                dest_paths.add(os.path.relpath(os.path.join(subdir, item), dest_folder))
    except Exception as e:
        logger.error(f"Error reading destination directory '{dest_folder}'. Error: {e}")
        return

    # Determine which files need to be copied, updated, or deleted
    to_copy = source_paths - dest_paths
    to_delete = dest_paths - source_paths
    to_update = {
        f
        for f in source_paths & dest_paths
        if os.stat(os.path.join(source_folder, f)).st_mtime
        > os.stat(os.path.join(dest_folder, f)).st_mtime
    }

    # Perform file operations based on the determination above
    for rel_path in to_copy.union(to_update):
        src_path = os.path.join(source_folder, rel_path)
        dest_path = os.path.join(dest_folder, rel_path)
        try:
            if os.path.isdir(src_path):
                os.makedirs(dest_path, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                safe_copy(src_path, dest_path)
        except OSError as e:
            logger.error(f"OSError during file/directory operation. Error: {e}")

    # Delete obsolete items in the destination
    for rel_path in to_delete:
        dest_path = os.path.join(dest_folder, rel_path)
        try:
            if os.path.exists(dest_path):
                if os.path.isdir(dest_path):
                    shutil.rmtree(dest_path)
                    logger.info(f"Deleted directory: '{dest_path}'")
                else:
                    os.remove(dest_path)
                    logger.info(f"Deleted file: '{dest_path}'")
        except OSError as e:
            logger.error(f"Error deleting file/directory '{dest_path}'. Error: {e}")

    logger.info("Synchronization complete.")
