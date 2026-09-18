"""Tests for file_converter.is_writable()."""

import stat
import sys

from file_converter import is_writable


def test_writable_directory(tmp_path):
    assert is_writable(str(tmp_path)) is True


def test_writable_file(tmp_path):
    f = tmp_path / "writable.txt"
    f.write_text("hello")
    assert is_writable(str(f)) is True


def test_nonexistent_path(tmp_path):
    assert is_writable(str(tmp_path / "no_such_file.txt")) is False


def test_read_only_file(tmp_path):
    if sys.platform == "win32":
        # On Windows, os.access + os.W_OK is unreliable for read-only files
        return
    f = tmp_path / "readonly.txt"
    f.write_text("locked")
    f.chmod(stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
    try:
        assert is_writable(str(f)) is False
    finally:
        # Restore write permission so tmp_path cleanup succeeds
        f.chmod(stat.S_IRUSR | stat.S_IWUSR)
