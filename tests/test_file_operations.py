"""Tests for file_operations.is_temporary_file()."""

from file_operations import is_temporary_file


def test_tmp_extension():
    assert is_temporary_file("report.tmp") is True


def test_tilde_dollar_prefix():
    assert is_temporary_file("~$budget.xlsx") is True


def test_normal_file():
    assert is_temporary_file("data.csv") is False


def test_tmp_in_middle_of_name():
    assert is_temporary_file("my.tmp.bak") is False


def test_full_path_with_tmp_extension():
    assert is_temporary_file("C:\\Users\\lab\\report.tmp") is True


def test_full_path_with_tilde_dollar():
    # startswith checks the entire string, so a full path won't match "~$"
    assert is_temporary_file("C:\\Users\\~$budget.xlsx") is False


def test_empty_string():
    assert is_temporary_file("") is False
