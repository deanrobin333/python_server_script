#!/usr/bin/python3
# tests/test_search_exact_match.py

from __future__ import annotations

from pathlib import Path

import pytest

from search import SearchError, search_linear_scan


def test_exact_match_found(tmp_path: Path) -> None:
    data = tmp_path / "data.txt"
    data.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    assert search_linear_scan(data, "beta") is True


def test_partial_match_not_found(tmp_path: Path) -> None:
    data = tmp_path / "data.txt"
    data.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    assert search_linear_scan(data, "bet") is False
    assert search_linear_scan(data, "beta ") is False
    assert search_linear_scan(data, "xbeta") is False
    assert search_linear_scan(data, "betax") is False


def test_missing_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"
    with pytest.raises(SearchError, match="not found"):
        search_linear_scan(missing, "anything")
