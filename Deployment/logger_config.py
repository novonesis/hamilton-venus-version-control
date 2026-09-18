"""Configures Loguru with three sinks: rotating log file, stderr console, and email on ERROR.

The log file is named after the machine's MAC-derived hardware ID so that
logs from different workstations do not collide when stored in a shared folder.
"""

from __future__ import annotations

import os
import sys
import uuid
from typing import TYPE_CHECKING

from config import AppConfig
from email_log_handler import ErrorEmailLogHandler
from loguru import logger

if TYPE_CHECKING:
    from loguru import Logger

# Flag to prevent duplicate logger initialization
_logger_initialized = False


def get_cpu_id() -> str:
    """Return a unique hardware ID derived from the network MAC address."""
    try:
        node = uuid.getnode()
        return f"{node:012x}"
    except Exception:
        return "error_retrieving_id"


def setup_logger() -> Logger:
    """Configure and return the application-wide Loguru logger.

    Three sinks are added in order:

    1. **File** -- rotating 10 MB log in ``Data/Logs/<cpu_id>_versioning_logs.txt``
    2. **Console** -- stderr at DEBUG level
    3. **Email** -- sends an email with the log file attached on every ERROR record
       (only when an SMTP recipient is configured in ``config.json``)
    """
    global _logger_initialized
    if _logger_initialized:
        # Skip reinitialization if already set up
        return logger

    # Fetch CPU ID for unique log file naming
    cpu_id = get_cpu_id() or "default_id"

    # Log an error if CPU ID retrieval failed
    if cpu_id in ["error_retrieving_id", "unknown_id", "unsupported_os"]:
        logger.error(f"Failed to retrieve unique CPU ID. Reason: {cpu_id}")

    # Set base path relative to the executable or script
    if getattr(sys, "frozen", False):  # If running as a PyInstaller executable
        base_path = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))

    # Define log file path in a Data/Logs directory relative to base path
    log_file_path = os.path.join(base_path, "Data", "Logs", f"{cpu_id}_versioning_logs.txt")

    # Ensure the log directory exists
    try:
        os.makedirs(os.path.dirname(log_file_path), exist_ok=True)
    except Exception as e:
        print(f"Error creating log file directory: {e}")
        log_file_path = None

    # Remove default handlers to avoid duplicate logging
    logger.remove()

    # Step 1: File logging with rotation and error handling
    if log_file_path:
        try:
            logger.add(
                log_file_path,
                format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {module}:{function}:{line} - {message}",
                enqueue=True,
                rotation="10MB",
                level="DEBUG",  # Set level to DEBUG to capture all messages
            )
            print(f"Logging to file: {log_file_path}")
        except Exception as e:
            print(f"Error setting up file logger: {e}")

    # Step 2: Console logging
    try:
        logger.add(
            sys.stderr,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}",
            level="DEBUG",
        )
        print("Logging to console")
    except Exception as e:
        print(f"Error setting up console logger: {e}")

    # Step 3: Email error handler for critical errors
    if log_file_path:
        try:
            config = AppConfig()
            recipient = config.get("smtp_recipient", "")
            if recipient:
                error_email_handler = ErrorEmailLogHandler(log_file_path, recipient)
                logger.add(
                    error_email_handler,
                    format="{time} | {level} | {message}",
                    level="ERROR",
                )
                print("Email error handler setup complete")
            else:
                print("Email error handler skipped: no recipient configured")
        except Exception as e:
            print(f"Error setting up email error handler: {e}")

    _logger_initialized = True  # Set flag to prevent reinitialization
    return logger
