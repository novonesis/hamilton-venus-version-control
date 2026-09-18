"""Processes Hamilton ``.lay`` deck-layout files to localise labware references.

Parses labware file references inside ``.lay`` files, copies the referenced
labware (``.rck``, ``.tml``, and companion files) into a local ``Labware/``
folder, and rewrites the paths so that the method is self-contained and
portable across Hamilton workstations.
"""

from __future__ import annotations

import os
import re
import shutil
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger


class LabwareFileProcessor:
    """Orchestrates labware extraction and path rewriting for ``.lay`` files.

    Typical usage::

        processor = LabwareFileProcessor(logger)
        processor.start_processing_lay_files("/path/to/method_root")
    """

    def __init__(self, labware_logger: Logger) -> None:
        """Initialise the processor with a bound Loguru logger.

        Args:
            labware_logger: Logger instance (usually ``logger.bind(tab="labware")``).
        """
        self.labware_logger = labware_logger

    @staticmethod
    def copy_newer_files(source_dir: str, dest_dir: str, logger: Logger) -> None:
        """Recursively copy files from *source_dir* when newer than *dest_dir*.

        Args:
            source_dir: The source directory from which to copy files.
            dest_dir: The destination directory to copy files to.
            logger: Logger instance for logging messages.
        """
        for root, _dirs, files in os.walk(source_dir):
            relative_path = os.path.relpath(root, source_dir)
            dest_path = os.path.join(dest_dir, relative_path)
            if not os.path.exists(dest_path):
                os.makedirs(dest_path)
            for file in files:
                src_file = os.path.join(root, file)
                dest_file = os.path.join(dest_path, file)
                try:
                    # Copy if destination file does not exist or if source file is newer
                    if not os.path.exists(dest_file) or os.path.getmtime(
                        src_file
                    ) > os.path.getmtime(dest_file):
                        shutil.copy2(src_file, dest_file)  # copy2 to preserve metadata
                        logger.info(
                            f"MLStar Base folder - Copied updated file: {src_file} to {dest_file}"
                        )
                except Exception as e:
                    logger.error(
                        f"MLStar Base folder - Failed to copy {src_file} to {dest_file}: {e}"
                    )

    def process_lay_file(self, lay_file_path: str, target_folder: str) -> None:
        """Process a single ``.lay`` file: copy labware and rewrite paths.

        For every labware reference found, the referenced file (plus any
        companion files sharing the same base name) is copied into
        ``<target_folder>/Labware/``, and the path inside the ``.lay`` is
        updated to point at the local copy.

        Args:
            lay_file_path: Absolute path to the ``.lay`` file.
            target_folder: Method root folder (``Labware/`` is created inside).
        """
        base_path = r"C:\Program Files (x86)\HAMILTON\LabWare"  # Base path for labware files
        labware_folder = os.path.join(target_folder, "Labware")

        # Create 'Labware' folder if it doesn't exist
        if not os.path.exists(labware_folder):
            os.makedirs(labware_folder)
            self.labware_logger.info(f"Created Labware folder at {labware_folder}")

        mlstar_labware_files = r"C:\Program Files (x86)\HAMILTON\LabWare\ML_STAR"
        self.copy_newer_files(mlstar_labware_files, labware_folder, self.labware_logger)

        try:
            with open(lay_file_path, "rb") as file:  # Open in binary mode
                raw_lines = file.readlines()

            lines = []
            for raw_line in raw_lines:
                try:
                    line = raw_line.decode("ascii")  # Try to decode as ASCII
                    # Check for non-printable characters
                    if not all(
                        32 <= ord(char) <= 126 or ord(char) == 10 or ord(char) == 13
                        for char in line
                    ):
                        raise ValueError("Non-printable ASCII or non-ASCII character detected")
                    lines.append(line)
                except UnicodeDecodeError as decode_error:
                    raise ValueError("Non-ASCII character detected") from decode_error

        except ValueError as ve:
            self.labware_logger.error(
                f"Invalid characters detected in {lay_file_path}: {ve}. Please ensure the file is in the correct format."
            )
            raise ve
        except Exception as e:
            self.labware_logger.error(f"Error opening {lay_file_path}: {e}")
            return

        modified_lines = []  # Stores modified lines with updated paths
        for line in lines:
            # Regex matches labware file references in the Hamilton .lay format:
            #   Labware.<N>.File, "<relative/path/to/labware.rck>"
            # Groups: (1) full key e.g. "Labware.3.File", (2) index "3",
            #         (3) the quoted relative path.
            match = re.search(r'(Labware\.(\d+)\.File), "(.*?)"', line)
            if match:
                # Extract and construct new file paths
                labware_ref, labware_num, relative_path = match.groups()
                full_path = os.path.join(base_path, relative_path.replace("/", "\\"))
                dest_path = os.path.join(labware_folder, os.path.basename(relative_path)).replace(
                    "/", "\\"
                )

                # Double backslashes for the .lay format (Venus expects \\ as separator)
                new_path_for_lay = dest_path.replace("\\", "\\\\")

                base_name = os.path.splitext(os.path.basename(relative_path))[0]
                source_dir = os.path.dirname(full_path)

                # Copy all files with the same base name but different extensions, independent of cap letters
                for item in os.listdir(source_dir):
                    if os.path.splitext(item)[0].lower() == base_name.lower():
                        item_full_path = os.path.join(source_dir, item)
                        item_dest_path = os.path.join(labware_folder, item)

                        if not os.path.exists(item_dest_path):
                            try:
                                shutil.copy(item_full_path, item_dest_path)
                                self.labware_logger.info(f"Copied to {item_dest_path}")
                            except shutil.SameFileError:
                                self.labware_logger.warning(f"Skipped, same file: {item_dest_path}")
                            except PermissionError:
                                self.labware_logger.error(
                                    f"Permission denied. Could not access {item_dest_path}"
                                )
                            except Exception as e:
                                self.labware_logger.error(f"Error processing {item_dest_path}: {e}")
                        else:
                            self.labware_logger.info(f"Skipped, already present: {item_dest_path}")

                # Update the path in the .lay file regardless of whether the copy was performed
                line = re.sub(f'{labware_ref}, ".*?"', f'{labware_ref}, "{new_path_for_lay}"', line)

            modified_lines.append(line)

        # Writes the modified lines back to the .lay file
        with open(lay_file_path, "w") as file:
            file.writelines(modified_lines)
        self.update_labware_in_lay_file(lay_file_path)

    def start_processing_lay_files(self, root_folder: str) -> bool:
        """Find and process the single ``.lay`` file inside ``<root_folder>/Libraries``.

        Args:
            root_folder: Method root folder (must contain a ``Libraries/`` sub-directory).

        Returns:
            ``True`` on success, ``False`` if no (or multiple) ``.lay`` files are found
            or if processing fails.
        """
        # Define the Libraries folder path
        libraries_folder = os.path.join(root_folder, "Libraries")

        # Ensure the Libraries folder exists
        if not os.path.exists(libraries_folder):
            self.labware_logger.error(
                "Error: Libraries folder not found. Please ensure the folder exists."
            )
            return False

        # Search for .lay files in the Libraries folder
        lay_files = [f for f in os.listdir(libraries_folder) if f.endswith(".lay")]

        if len(lay_files) > 1:
            self.labware_logger.error(
                "Error: Multiple .lay files found in Libraries folder. Please ensure there is only one .lay file."
            )
            return False
        elif len(lay_files) == 0:
            self.labware_logger.error(
                "Error: No .lay file found in Libraries folder. Please ensure a .lay file is present."
            )
            return False

        # Get the full path of the .lay file in the Libraries folder
        lay_file_path = os.path.join(libraries_folder, lay_files[0])

        try:
            # Process the .lay file with the libraries folder as the target
            # This ensures labware is copied to and paths are updated within
            # the versioned Libraries folder structure.
            self.process_lay_file(lay_file_path, root_folder)
        except ValueError as ve:
            self.labware_logger.error(f"Processing stopped due to error: {ve}")
            return False
        except Exception as e:
            self.labware_logger.error(f"Error processing {lay_file_path}: {e}")
            return False

        self.labware_logger.info(".lay file processing complete.")
        return True

    def update_labware_in_lay_file(self, lay_file_path: str) -> None:
        """Normalise backslashes in labware paths to the Venus double-backslash format.

        Venus ``.lay`` files use doubled backslashes (``\\\\``) as path
        separators.  This method first collapses any existing doubles to
        singles, then re-doubles them — ensuring a consistent result
        regardless of whether paths already had mixed escaping.

        Args:
            lay_file_path: Path to the ``.lay`` file to finalise.
        """
        try:
            with open(lay_file_path) as file:
                content = file.read()

            # Step 1: collapse all doubled backslashes to single
            normalized_content = content.replace("\\\\", "\\")

            # Step 2: re-double every backslash for Venus format
            modified_content = normalized_content.replace("\\", "\\\\")

            with open(lay_file_path, "w") as file:
                file.write(modified_content)

            self.labware_logger.info("Labware paths in .lay updated")
        except Exception as e:
            self.labware_logger.error(f"Error finalizing .lay file: {e}")

    def log_paths_in_rck_and_tml_files(self, folder_path: str) -> None:
        """Rewrite labware paths inside ``.rck`` and ``.tml`` files to be relative.

        For each ``.rck``/``.tml`` file in *folder_path*, lines containing
        quoted paths (recognised by embedded ``\\\\``) are resolved, the
        referenced labware is copied locally, and the original absolute path
        is replaced with a relative ``.\\\\..<basename>`` reference.

        Args:
            folder_path: The ``Labware/`` folder to process.
        """
        base_labware_path = "C:\\Program Files (x86)\\HAMILTON\\LabWare"
        # GRU paths use an alternate Venus installation convention for labware on shared drives
        gru_sw_prefix = "C:\\\\GRU\\\\SW\\\\HxStarLabwareFiles\\\\Labware\\\\"
        labware_folder = folder_path

        # Ensure the labware folder exists
        os.makedirs(labware_folder, exist_ok=True)

        for file_name in os.listdir(folder_path):
            if file_name.endswith(".rck") or file_name.endswith(".tml"):
                file_path = os.path.join(folder_path, file_name)
                try:
                    with open(file_path) as file:
                        lines = file.readlines()

                    modified_lines = []
                    for line in lines:
                        # Replace syntax with backslashes and quotes for "\"PLT_CAR_LIGHT_A01\"" type error
                        line = re.sub(r"\\\"([^\"]+)\\\"", r"\1", line)

                        # Skip lines with "Rel" — these already use relative references
                        if "Rel" in line:
                            modified_lines.append(line)
                            continue

                        # Match any quoted string that contains double-backslashes (i.e. a path)
                        match = re.search(r'"([^"]*\\\\[^"]*)"', line)
                        if match:
                            quoted_path = match.group(1)
                            self._resolve_and_copy_labware_path(
                                quoted_path, base_labware_path, gru_sw_prefix, labware_folder
                            )

                            basename = os.path.basename(quoted_path)
                            new_relative_path = f".\\\\{basename}"
                            line = line.replace(quoted_path, new_relative_path)

                        modified_lines.append(line)

                    with open(file_path, "w") as file:
                        file.writelines(modified_lines)

                except Exception as e:
                    self.labware_logger.error(f"Error processing {file_path}: {e}")
                    continue

        self.labware_logger.info("All Labware files paths updated")

    def _resolve_and_copy_labware_path(
        self,
        quoted_path: str,
        base_labware_path: str,
        gru_sw_prefix: str,
        labware_folder: str,
    ) -> None:
        """Resolve a labware path reference to an absolute path and copy matching files.

        Handles four path resolution strategies in priority order:

        1. **GRU paths** — ``C:\\GRU\\SW\\HxStarLabwareFiles\\...`` are trimmed
           to a relative path and resolved against *base_labware_path*.
        2. **Relative ``.\\.``** — leading ``.\\`` is stripped and appended to
           *base_labware_path*.
        3. **Absolute ``C:\\...``** — used as-is.
        4. **Fallback** — treated as relative to *base_labware_path*.

        Args:
            quoted_path: The raw path string extracted from the ``.rck``/``.tml`` file.
            base_labware_path: Hamilton's standard LabWare installation directory.
            gru_sw_prefix: The GRU shared-drive prefix to strip.
            labware_folder: Local destination folder for copied labware.
        """
        if "GRU" in quoted_path:
            # GRU shared-drive convention: strip the GRU prefix and resolve
            # against the standard Hamilton LabWare directory
            trimmed_path = quoted_path[len(gru_sw_prefix) :].replace("/", "\\")
            absolute_path = base_labware_path + "\\" + trimmed_path
        elif quoted_path.startswith(".\\"):
            # Relative path starting with .\ — resolve against base labware
            relative_path = quoted_path[2:].replace("/", "\\")
            absolute_path = base_labware_path + "\\" + relative_path
        elif quoted_path.startswith("..\\"):
            absolute_path = base_labware_path + "\\" + quoted_path[3:].replace("/", "\\")
        elif quoted_path.startswith("C:\\"):
            # Already an absolute Windows path
            absolute_path = quoted_path.replace("/", "\\")
        else:
            # Fallback: treat as relative to the base labware directory
            absolute_path = base_labware_path + "\\" + quoted_path.lstrip("\\").replace("/", "\\")

        self.copy_files_with_basename(absolute_path, labware_folder)

    def copy_files_with_basename(self, path: str, labware_folder: str) -> None:
        """Copy a file and all same-basename companions to *labware_folder*.

        Args:
            path: Absolute path to the primary file.
            labware_folder: Destination folder for the copies.
        """
        directory, basename = os.path.split(path)
        basename_without_ext = os.path.splitext(basename)[0]

        if not os.path.isdir(directory):
            self.labware_logger.warning(f"Directory does not exist: {directory}")
            return

        for file in os.listdir(directory):
            if os.path.splitext(file)[0].lower() == basename_without_ext.lower():
                source_file_path = os.path.join(directory, file)
                destination_file_path = os.path.join(labware_folder, file)

                if not os.path.exists(destination_file_path):
                    try:
                        shutil.copy(source_file_path, destination_file_path)
                        self.labware_logger.info(
                            f"Copied: {source_file_path} to {destination_file_path}"
                        )
                    except Exception as e:
                        self.labware_logger.error(f"Failed to copy {source_file_path}: {e}")
                else:
                    self.labware_logger.info(
                        f"Skipped, file already exists: {destination_file_path}"
                    )
