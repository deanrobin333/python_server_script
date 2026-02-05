#!/usr/bin/python3
# test_config.py

from __future__ import annotations

from pathlib import Path

import pytest

from config import AppConfig, ConfigError, load_config


def test_load_config_parses_linuxpath_among_noise(tmp_path: Path) -> None:
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
    cfg = tmp_path / "app.conf"
    cfg.write_text("foo=bar\nbaz=qux\n", encoding="utf-8")

    with pytest.raises(ConfigError, match=r"linuxpath="):
        load_config(cfg)


def test_load_config_empty_linuxpath_raises(tmp_path: Path) -> None:
    cfg = tmp_path / "app.conf"
    cfg.write_text("linuxpath=\n", encoding="utf-8")

    with pytest.raises(ConfigError, match="empty"):
        load_config(cfg)


def test_load_config_file_not_found_raises(tmp_path: Path) -> None:
    cfg = tmp_path / "missing.conf"

    with pytest.raises(ConfigError, match="not found"):
        load_config(cfg)
