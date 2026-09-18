"""Case-insensitive full-text search across Hamilton method files and folders."""

from __future__ import annotations

import os

from loguru import logger


def search_files(
    folder_path: str,
    search_string: str,
    include_auxiliary: bool = False,
) -> list[tuple[str, int, str]]:
    """
    Searches for a given string in files within the specified folder and its subfolders,
    ignoring case.

    Parameters:
        folder_path (str): The path to the folder where the search will be performed.
        search_string (str): The string to search for in the files.
        include_auxiliary (bool): If True, also search .trc, .log, .txt, and .adp files.

    Returns:
        list of tuples: A list of matching files and their details as tuples:
                        (file_path, line_number, line_content)
    """
    matching_files = []
    lower_search_string = search_string.lower()  # Convert the search string to lowercase

    for root, _dirs, files in os.walk(folder_path):
        for file in files:
            if not include_auxiliary and file.endswith((".trc", ".log", ".txt", ".adp")):
                continue
            try:
                file_path = os.path.join(root, file)
                with open(file_path, errors="ignore") as f:
                    for line_num, line in enumerate(f, start=1):
                        if lower_search_string in line.lower():  # Compare lowercased values
                            matching_files.append((file_path, line_num, line.strip()))
            except Exception as e:
                logger.error(f"Error reading file {file}: {e}")

    return matching_files
