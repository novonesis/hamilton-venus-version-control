"""Tests for folder_structure_creator.create_folder_structure return values."""

from __future__ import annotations

from folder_structure_creator import FolderCreationResult, create_folder_structure


def test_nonexistent_destination_returns_error(tmp_path):
    fake_dest = str(tmp_path / "does_not_exist")
    result = create_folder_structure(fake_dest, "MyMethod")
    assert isinstance(result, FolderCreationResult)
    assert result.status == "error"
    assert "does not exist" in result.message


def test_existing_folder_without_force_returns_confirm_needed(tmp_path):
    method_dir = tmp_path / "MyMethod"
    method_dir.mkdir()
    result = create_folder_structure(str(tmp_path), "MyMethod")
    assert result.status == "confirm_needed"


def test_existing_folder_with_force_returns_success(tmp_path):
    method_dir = tmp_path / "MyMethod"
    method_dir.mkdir()
    result = create_folder_structure(str(tmp_path), "MyMethod", force=True)
    assert result.status == "success"


def test_new_folder_returns_success(tmp_path):
    result = create_folder_structure(str(tmp_path), "BrandNewMethod")
    assert result.status == "success"
    # Verify the folder structure was actually created
    root = tmp_path / "BrandNewMethod"
    assert root.is_dir()
    for subfolder in ("Libraries", "Labware", "Documentation", "Data", "Other"):
        assert (root / subfolder).is_dir()
    assert (root / "README.md").is_file()
    assert (root / ".gitignore").is_file()
