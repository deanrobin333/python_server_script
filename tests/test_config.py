#!/usr/bin/python3
"""
Configuration parsing tests.

These tests validate that load_config():
- Parses required keys from noisy config files.
- Applies defaults correctly.
- Rejects missing/empty required values.
- Validates booleans and supported algorithm names.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from config import AppConfig, ConfigError, load_config


def test_load_config_parses_linuxpath_among_noise(tmp_path: Path) -> None:
    """Ensure linuxpath is parsed even when surrounded by irrelevant keys."""
    cfg = tmp_path / "app.conf"
    cfg.write_text(
        "\n".join(
            [
                "# comment line",
                "something=else",
                "unrelated=123",
                "linuxpath=/tmp/data.txt",
                "another=ignored",
            ]
        ),
        encoding="utf-8",
    )

    parsed = load_config(cfg)
    assert isinstance(parsed, AppConfig)
    assert parsed.linuxpath == Path("/tmp/data.txt")


def test_load_config_missing_linuxpath_raises(tmp_path: Path) -> None:
    """Ensure missing linuxpath triggers a ConfigError."""
    cfg = tmp_path / "app.conf"
    cfg.write_text("foo=bar\nbaz=qux\n", encoding="utf-8")

    with pytest.raises(ConfigError, match=r"linuxpath="):
        load_config(cfg)


def test_load_config_empty_linuxpath_raises(tmp_path: Path) -> None:
    """Ensure an empty linuxpath value triggers a ConfigError."""
    cfg = tmp_path / "app.conf"
    cfg.write_text("linuxpath=\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="empty"):
        load_config(cfg)


def test_load_config_file_not_found_raises(tmp_path: Path) -> None:
    """Ensure missing config files raise ConfigError with a clear message."""
    cfg = tmp_path / "missing.conf"

    with pytest.raises(ConfigError, match="not found"):
        load_config(cfg)


def test_load_config_defaults(tmp_path: Path) -> None:
    """Ensure defaults are applied when optional keys are absent."""
    cfg = tmp_path / "app.conf"
    cfg.write_text("linuxpath=/tmp/data.txt\n", encoding="utf-8")

    parsed = load_config(cfg)
    assert parsed.linuxpath == Path("/tmp/data.txt")
    assert parsed.reread_on_query is True
    assert parsed.search_algo == "linear_scan"


def test_load_config_parses_reread_on_query_and_algo(tmp_path: Path) -> None:
    """Ensure reread_on_query and search_algo are parsed correctly."""
    cfg = tmp_path / "app.conf"
    cfg.write_text(
        "\n".join(
            [
                "linuxpath=/tmp/data.txt",
                "reread_on_query=False",
                "search_algo=linear_scan",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    parsed = load_config(cfg)
    assert parsed.reread_on_query is False
    assert parsed.search_algo == "linear_scan"


def test_load_config_invalid_bool_raises(tmp_path: Path) -> None:
    """Ensure invalid boolean values raise ConfigError."""
    cfg = tmp_path / "app.conf"
    cfg.write_text(
        "\n".join(
            [
                "linuxpath=/tmp/data.txt",
                "reread_on_query=maybe",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="Invalid boolean"):
        load_config(cfg)


def test_load_config_unsupported_search_algo_raises(tmp_path: Path) -> None:
    """Ensure unsupported search_algo values raise ConfigError."""
    cfg = tmp_path / "app.conf"
    cfg.write_text(
        "\n".join(
            [
                "linuxpath=/tmp/data.txt",
                "search_algo=fastest_in_the_world",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="Unsupported search_algo"):
        load_config(cfg)
