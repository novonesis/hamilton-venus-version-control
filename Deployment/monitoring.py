"""Periodic directory-sync monitoring loop for the Folder Sync tab.

Runs in a background thread, repeatedly synchronising every source/destination
pair read from a CSV file at a user-configured interval until a
:class:`threading.Event` signals it to stop.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from csv_operations import read_csv_paths
from file_operations import sync_directories
from loguru import logger

if TYPE_CHECKING:
    from collections.abc import Callable


def run_monitoring(
    csv_path: str,
    frequency: int,
    update_status_callback: Callable[[str], None],
    stop_event: threading.Event,
) -> None:
    """Run the directory-sync monitoring loop.

    Args:
        csv_path: Path to the CSV file listing source/destination directory pairs.
        frequency: Seconds to wait between sync cycles.
        update_status_callback: Called with a status string to update the GUI label.
        stop_event: Set this event to gracefully stop the loop.
    """
    logger.info("Monitoring thread started.")
    try:
        path_pairs = read_csv_paths(csv_path)
        if not path_pairs:
            logger.warning("No valid path pairs found. Stopping monitoring thread.")
            update_status_callback("No valid paths found.")
            return

        while not stop_event.is_set():
            for source, destination in path_pairs:
                if stop_event.is_set():
                    logger.info("Monitoring thread received stop signal.")
                    break
                logger.info(f"Synchronizing: {source} -> {destination}")
                sync_directories(source, destination)
                logger.info(f"Completed synchronization: {source} -> {destination}")

            if not stop_event.is_set():
                update_status_callback("Waiting for next cycle")
                logger.success(
                    f"Full cycle completed. Waiting {frequency} seconds for the next cycle."
                )
                stop_event.wait(timeout=frequency)

    except Exception as e:
        logger.error(f"Monitoring thread encountered an error: {e}")
        update_status_callback(f"Error: {e}")

    update_status_callback("Stopped")
    logger.info("Monitoring thread exiting.")
