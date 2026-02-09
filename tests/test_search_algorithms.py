#!/usr/bin/python3
"""
Tests for search algorithm correctness and consistency.

These tests ensure that all search algorithms:
- Perform exact full-line matching (no partial matches).
- Behave consistently across different implementations.
- Respect reread_on_query semantics when used via SearchEngine.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from search import (
    build_set_cache,
    build_sorted_list,
    search_linear_scan,
    search_set_cache,
    search_sorted_bisect,
)
from config import AppConfig
from search_engine import SearchEngine


@pytest.mark.parametrize(
    "query, expected",
    [("beta", True), ("bet", False), ("beta ", False)],
)
def test_algorithms_exact_match_consistency(
    tmp_path: Path,
    query: str,
    expected: bool,
) -> None:
    """Ensure all algorithms enforce exact full-line matching."""
    data = tmp_path / "data.txt"
    data.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    assert search_linear_scan(data, query) is expected

    cache = build_set_cache(data)
    assert search_set_cache(cache, query) is expected

    sorted_lines = build_sorted_list(data)
    assert search_sorted_bisect(sorted_lines, query) is expected


@pytest.mark.parametrize(
    "algo",
    ["linear_scan", "mmap_scan", "grep_fx"],
)
def test_reread_algorithms_consistency(tmp_path: Path, algo: str) -> None:
    """Ensure reread-based algorithms behave consistently via SearchEngine."""
    data = tmp_path / "data.txt"
    data.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    cfg = AppConfig(
        linuxpath=data,
        reread_on_query=True,
        search_algo=algo,
    )
    engine = SearchEngine.from_config(cfg)

    assert engine.exists("beta") is True
    assert engine.exists("bet") is False
