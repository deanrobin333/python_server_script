#!/usr/bin/python3
# tests/test_search_exact_match.py

from __future__ import annotations

from pathlib import Path

import pytest

from search import SearchError, line_exists_in_file


def test_exact_match_found(tmp_path: Path) -> None:
    data = tmp_path / "data.txt"
    data.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    assert line_exists_in_file(data, "beta") is True


def test_partial_match_not_found(tmp_path: Path) -> None:
    data = tmp_path / "data.txt"
    data.write_text("alpha\nbeta\ngamma\n", encoding="utf-8")

    assert line_exists_in_file(data, "bet") is False
    assert line_exists_in_file(data, "beta ") is False
    assert line_exists_in_file(data, "xbeta") is False
    assert line_exists_in_file(data, "betax") is False


def test_missing_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"
    with pytest.raises(SearchError, match="not found"):
        line_exists_in_file(missing, "anything")
