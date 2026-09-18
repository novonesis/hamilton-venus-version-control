"""Tests for config.AppConfig.get()."""

from unittest.mock import patch

from config import AppConfig


def _make_config(data: dict) -> AppConfig:
    """Create an AppConfig with load() bypassed and _config set directly."""
    with patch.object(AppConfig, "load"):
        cfg = AppConfig()
    cfg._config = dict(data)
    return cfg


def test_existing_key():
    cfg = _make_config({"smtp_port": 587})
    assert cfg.get("smtp_port") == 587


def test_missing_key_default_none():
    cfg = _make_config({})
    assert cfg.get("nonexistent") is None


def test_missing_key_custom_default():
    cfg = _make_config({})
    assert cfg.get("nonexistent", "fallback") == "fallback"


def test_integer_value_preserved():
    cfg = _make_config({"count": 42})
    assert cfg.get("count") == 42
    assert isinstance(cfg.get("count"), int)
