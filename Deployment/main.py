"""Entry point for the Hamilton Method Versionator.

Routes to the CLI workflow engine when command-line arguments are present,
or launches the pywebview GUI when invoked without arguments.
"""

from __future__ import annotations

import os
import sys

from logger_config import setup_logger
from loguru import logger


def main() -> None:
    """Initialise logging and dispatch to CLI or GUI mode."""
    # Set up the application logger
    setup_logger()

    # Sanity checks for paths and environment
    working_dir = os.getcwd()
    logger.info(f"New instance of the script started in the following directory : {working_dir}")
    interpreter = sys.executable
    logger.info(f"Script will run using the following Python interpreter: {interpreter}")

    # Route to CLI or GUI based on command-line arguments
    if len(sys.argv) > 1:
        from cli import build_parser, run_cli

        args = build_parser().parse_args()
        sys.exit(run_cli(args))
    else:
        import webgui

        webgui.start_app()


if __name__ == "__main__":
    main()
