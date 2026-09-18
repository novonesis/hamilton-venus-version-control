"""Subprocess wrapper for Hamilton's binary-to-ASCII file converter.

Calls the headless ``Hamilton_file_converter_headless.exe`` on a user-selected
folder, streaming its stdout to the application logger in real time.
"""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Logger


def is_writable(path: str) -> bool:
    """Check whether *path* is writable by the current user.

    Args:
        path: The file or folder path to check.

    Returns:
        ``True`` if the path is writable, ``False`` otherwise.
    """
    return os.access(path, os.W_OK)


def try_change_permissions(path: str) -> bool:
    """Attempt to make *path* writable by granting owner read+write.

    Args:
        path: The file or folder path to change permissions on.

    Returns:
        ``True`` if permissions were successfully changed, ``False`` otherwise.
    """
    try:
        # Make the file writable by changing the permissions
        os.chmod(path, stat.S_IWUSR | stat.S_IRUSR)  # Grant write and read permission to the owner
        return True
    except PermissionError as e:
        # Log the error if we don't have sufficient permissions
        from loguru import logger

        logger.error(f"Permission denied: {e}. Could not change permissions for {path}.")
        return False
    except Exception as e:
        from loguru import logger

        logger.error(f"Failed to change permissions for {path}: {e}")
        return False


def check_and_fix_permissions(folder_path: str, conversion_logger: Logger) -> bool:
    """Walk *folder_path* and ensure every file is writable.

    Files that are read-only are fixed in-place via :func:`try_change_permissions`.

    Args:
        folder_path: The directory tree to check.
        conversion_logger: Logger instance for progress messages.

    Returns:
        ``True`` once the walk completes (individual failures are logged but
        do not abort the scan).
    """
    for root, _dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            if not is_writable(file_path):
                conversion_logger.warning(f"File {file_path} is read-only or not writable.")

                # Try to change permissions
                if try_change_permissions(file_path):
                    conversion_logger.info(f"Permissions changed for file {file_path}.")
                else:
                    conversion_logger.error(
                        f"Failed to change permissions for {file_path}. Skipping this file."
                    )
                    continue  # Continue processing other files, don't abort
    return True


def run_conversion(selected_folder_path: str, conversion_logger: Logger) -> None:
    """Run Hamilton's headless file converter on *selected_folder_path*.

    The converter executable is expected to be on ``PATH`` or in the working
    directory.  Its stdout is streamed line-by-line to *conversion_logger*.

    Args:
        selected_folder_path: Folder containing files to convert.
        conversion_logger: Logger instance for progress and error messages.
    """

    # Check if folder and files are writable, and try to fix permissions if needed
    check_and_fix_permissions(selected_folder_path, conversion_logger)

    # Create a temporary log file to capture conversion output
    temp_log_file = tempfile.NamedTemporaryFile(delete=False)
    log_file_path = temp_log_file.name
    temp_log_file.close()  # Close the file to allow the subprocess to write to it

    conversion_logger.info(
        f"File Converter - Starting conversion for folder: {selected_folder_path}"
    )

    try:
        # Execute the conversion process as a subprocess.
        #
        # S603/S607: the converter is invoked by bare filename, so it is
        # resolved against the working directory and then PATH. That is
        # deliberate: the executable ships alongside the application in the
        # same distribution folder (see the README's build section), and the
        # app is launched from that folder. The arguments are a user-chosen
        # folder path and a log path this module generated, never shell input,
        # and shell=False keeps them as argv entries rather than a command
        # string. Resolving the executable to an absolute path relative to the
        # bundle would be more robust and is tracked as a follow-up.
        process = subprocess.Popen(  # noqa: S603
            [r"Hamilton_file_converter_headless.exe", selected_folder_path, log_file_path],  # noqa: S607
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )

        # Read and log the conversion output in real-time
        while True:
            output = process.stdout.readline()
            if output == "" and process.poll() is not None:
                break
            if output:
                log_message = output.strip()
                conversion_logger.info(log_message)

        # Determine the outcome of the conversion process based on its return code
        rc = process.poll()
        if rc == 0:
            success_message = "File Converter - Conversion completed successfully."
            conversion_logger.success(success_message)
        else:
            failure_message = f"File Converter - Conversion failed with return code {rc}."
            conversion_logger.error(failure_message)

    except Exception as e:
        error_message = f"File Converter - An error occurred during conversion: {str(e)}"
        conversion_logger.error(error_message)

    finally:
        # Cleanup: Remove the temporary log file
        if os.path.exists(log_file_path):
            os.remove(log_file_path)
