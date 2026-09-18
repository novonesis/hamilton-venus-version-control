"""CLI workflow engine for Hamilton Method Versionator.

Provides an argparse-based interface that reuses existing backend modules
(LabwareFileProcessor, HamiltonLibrarySync, run_conversion) to run the
full versioning pipeline from the command line without the GUI.
"""

from __future__ import annotations

import argparse
import os

from loguru import logger


def build_parser() -> argparse.ArgumentParser:
    """Build and return the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="Hamilton_versioning",
        description=(
            "Hamilton Versioning CLI — run the labware/library sync pipeline from the command line."
        ),
    )
    parser.add_argument(
        "--method-root",
        required=True,
        help="Path to versioned method root folder (must contain Libraries/)",
    )
    parser.add_argument(
        "--hsl",
        required=True,
        help="Path to the .hsl file inside Libraries/",
    )
    parser.add_argument(
        "--skip-labware",
        action="store_true",
        help="Skip the labware sync step",
    )
    parser.add_argument(
        "--skip-library",
        action="store_true",
        help="Skip the library sync step",
    )
    parser.add_argument(
        "--skip-conversion",
        action="store_true",
        help="Skip file conversion steps (initial and final)",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Log errors and keep going instead of aborting",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable DEBUG-level console output (already the default for file logs)",
    )
    return parser


def _validate_args(args: argparse.Namespace) -> list[str]:
    """Validate CLI arguments and return a list of error messages (empty if valid)."""
    errors = []

    method_root = args.method_root
    if not os.path.isdir(method_root):
        errors.append(f"--method-root directory does not exist: {method_root}")
    else:
        libraries_folder = os.path.join(method_root, "Libraries")
        if not os.path.isdir(libraries_folder):
            errors.append(
                f"--method-root must contain a Libraries/ subfolder: {libraries_folder} not found"
            )

    hsl_path = args.hsl
    if not os.path.isfile(hsl_path):
        errors.append(f"--hsl file does not exist: {hsl_path}")
    elif not hsl_path.lower().endswith(".hsl"):
        errors.append(f"--hsl must be a .hsl file, got: {hsl_path}")

    return errors


def run_cli(args: argparse.Namespace) -> int:
    """Execute the CLI versioning workflow. Returns exit code (0=success, 1=failure)."""
    cli_logger = logger.bind(tab="cli")

    # Validate inputs
    errors = _validate_args(args)
    if errors:
        for err in errors:
            cli_logger.error(err)
        return 1

    method_root = os.path.abspath(args.method_root)
    hsl_path = os.path.abspath(args.hsl)
    libraries_folder = os.path.join(method_root, "Libraries")
    labware_folder = os.path.join(method_root, "Labware")

    cli_logger.info("Hamilton Versioning CLI starting")
    cli_logger.info(f"Method root: {method_root}")
    cli_logger.info(f"HSL file:    {hsl_path}")

    step_errors = []

    # ── Step 1: Initial conversion — Libraries/ to ASCII ──
    if not args.skip_conversion:
        cli_logger.info("Step 1/4: Converting Libraries/ files to ASCII...")
        try:
            from file_converter import run_conversion

            run_conversion(libraries_folder, cli_logger)
            cli_logger.success("Step 1/4: Initial conversion complete.")
        except Exception as exc:
            msg = f"Step 1/4: Initial conversion failed: {exc}"
            cli_logger.error(msg)
            if not args.continue_on_error:
                return 1
            step_errors.append(msg)
    else:
        cli_logger.info("Step 1/4: Skipped (--skip-conversion)")

    # ── Step 2: Labware sync (full sub-pipeline) ──
    if not args.skip_labware:
        cli_logger.info("Step 2/4: Running labware sync...")
        try:
            from file_converter import run_conversion
            from labware_sync import LabwareFileProcessor

            # 2a. Create processor
            processor = LabwareFileProcessor(cli_logger)

            # 2b. Process .lay files
            success = processor.start_processing_lay_files(method_root)

            if success:
                # 2c. Convert labware folder to ASCII
                if os.path.isdir(labware_folder):
                    run_conversion(labware_folder, cli_logger)
                else:
                    cli_logger.warning(
                        f"Labware folder not found after processing: {labware_folder}"
                    )

                # 2d. Update paths in .rck and .tml files
                if os.path.isdir(labware_folder):
                    processor.log_paths_in_rck_and_tml_files(labware_folder)
            else:
                raise RuntimeError("start_processing_lay_files returned False")

            cli_logger.success("Step 2/4: Labware sync complete.")
        except Exception as exc:
            msg = f"Step 2/4: Labware sync failed: {exc}"
            cli_logger.error(msg)
            if not args.continue_on_error:
                return 1
            step_errors.append(msg)
    else:
        cli_logger.info("Step 2/4: Skipped (--skip-labware)")

    # ── Step 3: Library sync ──
    if not args.skip_library:
        cli_logger.info("Step 3/4: Running library sync...")
        try:
            from library_path_updater import HamiltonLibrarySync

            sync = HamiltonLibrarySync(hsl_path, cli_logger)
            sync.initiate_library_files_update_process()
            cli_logger.success("Step 3/4: Library sync complete.")
        except Exception as exc:
            msg = f"Step 3/4: Library sync failed: {exc}"
            cli_logger.error(msg)
            if not args.continue_on_error:
                return 1
            step_errors.append(msg)
    else:
        cli_logger.info("Step 3/4: Skipped (--skip-library)")

    # ── Step 4: Final conversion pass on Libraries/ ──
    if not args.skip_conversion:
        cli_logger.info("Step 4/4: Final conversion pass on Libraries/...")
        try:
            from file_converter import run_conversion

            run_conversion(libraries_folder, cli_logger)
            cli_logger.success("Step 4/4: Final conversion complete.")
        except Exception as exc:
            msg = f"Step 4/4: Final conversion failed: {exc}"
            cli_logger.error(msg)
            if not args.continue_on_error:
                return 1
            step_errors.append(msg)
    else:
        cli_logger.info("Step 4/4: Skipped (--skip-conversion)")

    # ── Summary ──
    if step_errors:
        cli_logger.error(
            f"Completed with {len(step_errors)} error(s):\n"
            + "\n".join(f"  - {e}" for e in step_errors)
        )
        return 1

    cli_logger.success("All steps completed successfully.")
    return 0
