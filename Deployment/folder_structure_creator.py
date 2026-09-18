"""Creates the standard versioned-method folder scaffold on disk.

Given a destination path and a method name, this module builds the canonical
folder layout (Libraries, Labware, Documentation, Data, Other) together with
a README, ``.gitignore``, and optional Win32 shortcuts from a ``.med`` file.
"""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from typing import Literal

import pythoncom
from loguru import logger
from win32com.client import Dispatch


@dataclass
class FolderCreationResult:
    """Result of a :func:`create_folder_structure` call.

    Attributes:
        status: One of ``"success"``, ``"error"``, ``"cancelled"``, or
            ``"confirm_needed"``.
        message: Human-readable explanation of the outcome.
    """

    status: Literal["success", "error", "cancelled", "confirm_needed"]
    message: str


def create_shortcut(source_file_path: str, shortcut_path: str) -> None:
    """Create a Windows ``.lnk`` shortcut pointing to *source_file_path*.

    Args:
        source_file_path: The target file the shortcut will point to.
        shortcut_path: Where the ``.lnk`` file will be written.
    """
    try:
        pythoncom.CoInitialize()  # Initialize COM library
        shell = Dispatch("WScript.Shell")
        shortcut = shell.CreateShortCut(shortcut_path)
        shortcut.TargetPath = source_file_path
        shortcut.save()
        logger.info(f"Shortcut created: {shortcut_path} -> {source_file_path}")
    except Exception as e:
        logger.error(f"Failed to create shortcut for {source_file_path}: {e}")


def copy_files_to_libraries(source_file_path: str, libraries_folder: str) -> None:
    """Copy method-related files to the *Libraries* folder.

    Looks for files sharing the same base name as *source_file_path* with
    Hamilton method extensions (``.med``, ``.hsl``, ``.sub``, ``.stp``, ``.res``)
    and copies any that exist into *libraries_folder*.

    Args:
        source_file_path: Path to the primary method file.
        libraries_folder: Destination ``Libraries`` folder.
    """
    base_name, _ = os.path.splitext(os.path.basename(source_file_path))
    directory = os.path.dirname(source_file_path)
    # Hamilton method files that should travel together
    extensions = [".med", ".hsl", ".sub", ".stp", ".res"]

    for ext in extensions:
        file_to_copy = os.path.join(directory, base_name + ext)
        if os.path.exists(file_to_copy):
            # Copy the file to the Libraries folder
            destination_path = os.path.join(libraries_folder, os.path.basename(file_to_copy))
            shutil.copy(file_to_copy, destination_path)
            logger.info(f"Copied {file_to_copy} to {destination_path}")


def copy_related_files_and_create_shortcuts(
    source_file_path: str,
    libraries_folder: str,
    destination_folder: str,
) -> None:
    """Copy method files to *Libraries* and create shortcuts in *destination_folder*.

    This is the high-level orchestrator: it copies related files, creates
    ``.lnk`` shortcuts pointing back at them, and handles any ``.lay`` file
    referenced inside the companion ``.hsl``.

    Args:
        source_file_path: Path to the ``.med`` file being versioned.
        libraries_folder: The ``Libraries`` sub-folder inside the method root.
        destination_folder: The method root where shortcuts are placed.
    """
    # Copy the files to the Libraries folder
    copy_files_to_libraries(source_file_path, libraries_folder)

    # Now create shortcuts in the original destination folder pointing to files in Libraries
    base_name, _ = os.path.splitext(os.path.basename(source_file_path))
    extensions = [".med", ".hsl", ".sub", ".stp", ".res"]

    for ext in extensions:
        file_to_copy = os.path.join(libraries_folder, base_name + ext)
        if os.path.exists(file_to_copy):
            shortcut_name = base_name + ext + ".lnk"  # Name the shortcut with a ".lnk" extension
            shortcut_path = os.path.join(destination_folder, shortcut_name)
            create_shortcut(file_to_copy, shortcut_path)

    # After copying and creating shortcuts for related files, handle the .lay file
    hsl_file_path = os.path.join(libraries_folder, base_name + ".hsl")
    if os.path.exists(hsl_file_path):
        source_folder = os.path.dirname(source_file_path)  # The original source folder
        copy_lay_file_from_hsl_and_create_shortcut(
            hsl_file_path, libraries_folder, destination_folder, source_folder
        )


def copy_lay_file_from_hsl_and_create_shortcut(
    hsl_file_path: str,
    libraries_folder: str,
    destination_folder: str,
    source_folder: str,
) -> None:
    """Extract the ``.lay`` file referenced in an ``.hsl`` file and version it.

    Parses *hsl_file_path* for the ``global device ML_STAR`` declaration,
    extracts the ``.lay`` filename from the quoted string, copies it into
    *libraries_folder*, and creates a shortcut in *destination_folder*.

    Args:
        hsl_file_path: Path to the ``.hsl`` file (already in Libraries).
        libraries_folder: Where the ``.lay`` copy will be placed.
        destination_folder: Where the shortcut will be created.
        source_folder: Original folder containing the ``.hsl`` source.
    """
    lay_file_name = None
    with open(hsl_file_path) as hsl_file:
        for line in hsl_file:
            # The .hsl file declares the deck layout via:
            #   global device ML_STAR ("deckName.lay", ...) ...
            # We extract the filename from the first quoted string on that line.
            if "global device ML_STAR" in line and ".lay" in line:
                lay_file_name = line.split('"')[1]
                break

    if lay_file_name:
        # First, check if the .lay file exists in the same source folder as the original .hsl file
        lay_file_path = os.path.join(source_folder, lay_file_name)

        if os.path.exists(lay_file_path):
            # Copy the lay file to the Libraries folder
            destination_path = os.path.join(libraries_folder, os.path.basename(lay_file_path))
            shutil.copy(lay_file_path, destination_path)
            logger.info(f"Copied {lay_file_path} to {destination_path}")

            # Create a shortcut in the destination folder
            shortcut_name = os.path.basename(lay_file_name) + ".lnk"
            shortcut_path = os.path.join(destination_folder, shortcut_name)
            create_shortcut(destination_path, shortcut_path)
        else:
            logger.warning(f"Referenced .lay file '{lay_file_name}' not found in {source_folder}.")
    else:
        logger.warning("No .lay file reference found in the .hsl file.")


def create_folder_structure(
    destination_path: str,
    method_name: str,
    med_file_path: str | None = None,
    force: bool = False,
) -> FolderCreationResult:
    """Create the canonical Hamilton versioned-method folder tree.

    Builds the following structure under ``destination_path/method_name``::

        <method_name>/
        ├── Libraries/
        ├── Labware/
        ├── Documentation/
        ├── Data/
        ├── Other/
        ├── README.md
        └── .gitignore

    If *med_file_path* is supplied, the ``.med`` and its companion files are
    copied into ``Libraries/`` with shortcuts placed in the method root.

    Args:
        destination_path: Parent directory for the new method folder.
        method_name: Name of the method (becomes the folder name).
        med_file_path: Optional path to the ``.med`` file to version.
        force: If ``True``, overwrite an existing folder without prompting.

    Returns:
        A :class:`FolderCreationResult` indicating the outcome.
    """
    # Check if the destination directory exists
    if not os.path.exists(destination_path):
        logger.error("Target directory does not exist.")
        return FolderCreationResult("error", "Target directory does not exist.")

    # Construct the path for the root method folder
    root_folder_path = os.path.join(destination_path, method_name)
    if os.path.exists(root_folder_path):
        logger.warning(f"The folder '{method_name}' already exists at the destination.")
        if not force:
            return FolderCreationResult(
                "confirm_needed",
                "The folder already exists. Do you want to continue?",
            )

    try:
        # Create the root method folder
        os.makedirs(root_folder_path, exist_ok=True)

        # Define the Libraries folder
        libraries_folder = os.path.join(root_folder_path, "Libraries")
        os.makedirs(libraries_folder, exist_ok=True)

        # Define the names of subfolders to create within the method folder
        folders = [
            "Labware",
            "Documentation",
            "Libraries",
            "Data",
            "Other",
        ]

        # Create each subfolder and an empty text file within it
        for folder in folders:
            folder_path = os.path.join(root_folder_path, folder)
            os.makedirs(folder_path, exist_ok=True)
            file_path = os.path.join(folder_path, f"{folder}.txt")
            with open(file_path, "w") as f:
                f.write("")

        # Create a README file with detailed information about the method folder structure
        readme_path = os.path.join(root_folder_path, "README.md")
        with open(readme_path, "w") as readme:
            readme_content = f"""# {method_name}

This folder should contain all files important for a method to be running on any Hamilton install.
Fake files used to generate the folder structure can be removed once the folder contains other files. The files are the following:
1. .med and .lay associated with the method. Ideally, there should be only one of each. If the method requires different .med/lay, it should ideally be placed in a new Method folder to keep containment and avoid problems.
2. Accessory files for the method: .res, .hsl, and .stp.
3. Documentation folder containing all documents relative to the method. This can be URS, text documentation, calculations, etc... anything helping contextualize the method or have on all setups is great to have here.
4. Labware folder which is synced via a custom script in the Utilities to make sure the custom labware of the method is available for Venus.
5. Library folder which contains all required libraries for the method, using relative path created via the script in utilities.

You are encouraged to add to this readme file to contextualize what lives in this method. This could be seen as a snapshot/summary of what the documentation folder should contain (description of the method, customer...)."""

            readme.write(readme_content)

        # Create a .gitignore file
        gitignore_path = os.path.join(root_folder_path, ".gitignore")
        with open(gitignore_path, "w") as gitignore:
            gitignore_content = "/**/~*.*"
            gitignore.write(gitignore_content)

        # Copy the .med file and related files to the Libraries folder, and create shortcuts in the root folder
        if med_file_path:
            copy_related_files_and_create_shortcuts(
                med_file_path, libraries_folder, root_folder_path
            )

        msg = f"Folder structure created successfully for the method {method_name}."
        logger.success(f"{msg} in directory {destination_path}")
        return FolderCreationResult("success", msg)

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return FolderCreationResult("error", f"An error occurred: {e}")
