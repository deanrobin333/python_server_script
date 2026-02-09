#!/usr/bin/python3
"""
Tests for reread_on_query behavior.

These tests verify that the SearchEngine correctly reflects file changes
depending on the reread_on_query configuration:
- When True, file changes are visible immediately.
- When False, cached results remain unchanged until restart/warmup.
"""

from __future__ import annotations

from pathlib import Path

from config import AppConfig
from search_engine import SearchEngine


def test_reread_true_sees_file_changes(tmp_path: Path) -> None:
    """Ensure reread_on_query=True reflects file changes immediately."""
    data = tmp_path / "data.txt"
    data.write_text("alpha\n", encoding="utf-8")

    cfg = AppConfig(
        linuxpath=data,
        reread_on_query=True,
        search_algo="linear_scan",
    )
    engine = SearchEngine.from_config(cfg)

    assert engine.exists("beta") is False

    # Modify file after engine creation.
    data.write_text("alpha\nbeta\n", encoding="utf-8")

    # reread_on_query=True must see the new content.
    assert engine.exists("beta") is True


def test_reread_false_does_not_see_changes_without_restart(
    tmp_path: Path,
) -> None:
    """Ensure reread_on_query=False
    does not reflect file changes without restart."""
    data = tmp_path / "data.txt"
    data.write_text("alpha\n", encoding="utf-8")

    cfg = AppConfig(
        linuxpath=data,
        reread_on_query=False,
        search_algo="set_cache",
    )
    engine = SearchEngine.from_config(cfg)
    engine.warmup()

    assert engine.exists("beta") is False

    # Modify file after warmup.
    data.write_text("alpha\nbeta\n", encoding="utf-8")

    # reread_on_query=False should still return cached results.
    assert engine.exists("beta") is False
