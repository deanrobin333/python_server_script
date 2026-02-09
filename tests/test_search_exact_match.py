#!/usr/bin/python3
"""
Exact-match behavior tests for search functions.

These tests verify that the search implementation performs strict full-line
matching and does not return true for partial or substring matches. They also
validate correct error handling when the data file is missing.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from search import SearchError, search_linear_scan


def test_exact_match_found(tmp_path: Path) -> None:
    """Ensure an exact full-line match is detected."""
    data = tmp_path / "data.txt"
    data.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    assert search_linear_scan(data, "beta") is True


def test_partial_match_not_found(tmp_path: Path) -> None:
    """Ensure partial and substring matches are not treated as valid hits."""
    data = tmp_path / "data.txt"
    data.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    assert search_linear_scan(data, "bet") is False
    assert search_linear_scan(data, "beta ") is False
    assert search_linear_scan(data, "xbeta") is False
    assert search_linear_scan(data, "betax") is False


def test_missing_file_raises(tmp_path: Path) -> None:
    """Ensure missing data files raise SearchError."""
    missing = tmp_path / "missing.txt"
    with pytest.raises(SearchError, match="not found"):
        search_linear_scan(missing, "anything")
