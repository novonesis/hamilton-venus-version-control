"""Tests for logger_config.get_cpu_id()."""

from unittest.mock import patch

from logger_config import get_cpu_id


def test_returns_12_char_hex():
    result = get_cpu_id()
    assert len(result) == 12


def test_consistent_across_calls():
    assert get_cpu_id() == get_cpu_id()


def test_returns_error_string_on_exception():
    with patch("logger_config.uuid.getnode", side_effect=RuntimeError("fail")):
        assert get_cpu_id() == "error_retrieving_id"


def test_valid_hex_number():
    result = get_cpu_id()
    int(result, 16)  # raises ValueError if not valid hex
