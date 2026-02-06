#!/usr/bin/python3
# tests/test_search_algorithms.py

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
    "query, expected", [("beta", True), ("bet", False), ("beta ", False)]
)
def test_algorithms_exact_match_consistency(
    tmp_path: Path, query: str, expected: bool
) -> None:
    data = tmp_path / "data.txt"
    data.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    assert search_linear_scan(data, query) is expected

    s = build_set_cache(data)
    assert search_set_cache(s, query) is expected

    lst = build_sorted_list(data)
    assert search_sorted_bisect(lst, query) is expected


@pytest.mark.parametrize(
    "algo",
    ["linear_scan", "mmap_scan", "grep_fx"],
)
def test_reread_algorithms_consistency(tmp_path: Path, algo: str) -> None:
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
