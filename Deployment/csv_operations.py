"""Reads source/destination directory pairs from a CSV file for the sync engine."""

from __future__ import annotations

import csv
import os

from loguru import logger


def read_csv_paths(csv_path: str) -> list[tuple[str, str]]:
    """
    Reads source and destination directory paths from a CSV file.
    Validates the existence of each path before adding to the list.
    """
    path_pairs = []
    try:
        with open(csv_path, newline="", encoding="utf-8") as csvfile:
            reader = csv.reader(csvfile)
            header = next(reader, None)  # Skip the header row if present.
            if header is None:
                logger.warning(f"CSV file is empty: {csv_path}")
                return path_pairs
            for row in reader:
                source, destination = row[:2]
                # Check if both source and destination paths exist.
                if os.path.exists(source) and os.path.exists(destination):
                    path_pairs.append((source, destination))
                    logger.info(f"Valid paths: Source: {source}, Destination: {destination}")
                else:
                    logger.warning(
                        f"Invalid path pair skipped: Source: {source}, Destination: {destination}"
                    )
    except Exception as e:
        logger.error(f"Error reading CSV file at {csv_path}: {e}")
    return path_pairs
