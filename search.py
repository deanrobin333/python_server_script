#!/usr/bin/python3
"""
Search algorithms for exact full-line string lookup.

This module provides multiple strategies for determining whether a given query
string exists as an exact line in a text file.

Design goals:
- Exact full-line matching only (no substring matches).
- Support both per-query file rereads and cached/in-memory modes.
- Provide algorithms with different trade-offs for performance and memory use.

Errors are surfaced as SearchError with context.
"""

from __future__ import annotations

from bisect import bisect_left
from pathlib import Path

import mmap
import subprocess


class SearchError(RuntimeError):
    """Raised when the search subsystem cannot read the data file."""


def search_linear_scan(file_path: Path, query: str) -> bool:
    """Search by sequentially scanning the file for an exact line match.

    This function reads the file line by line on each call and
    returns True only
    if a line equals the query (after stripping line terminators).

    Args:
        file_path: Path to the data file.
        query: Query string to match against full lines.

    Returns:
        True if an exact full-line match is found, otherwise False.

    Raises:
        SearchError: If the file cannot be read.
    """
    try:
        with file_path.open(
            "r", encoding="utf-8", errors="replace", newline=""
        ) as f:
            for line in f:
                if line.rstrip("\r\n") == query:
                    return True
        return False
    except FileNotFoundError as exc:
        raise SearchError(f"Data file not found: {file_path}") from exc
    except OSError as exc:
        raise SearchError(
            f"Failed reading data file: {file_path} ({exc})"
        ) from exc


def build_set_cache(file_path: Path) -> set[str]:
    """Build a set cache of all lines in the file.

    The resulting set enables fast membership checks with `query in cache`.

    Args:
        file_path: Path to the data file.

    Returns:
        A set containing all lines from the file
        (with line terminators stripped).

    Raises:
        SearchError: If the file cannot be read.
    """
    try:
        lines: set[str] = set()
        with file_path.open(
            "r", encoding="utf-8", errors="replace", newline=""
        ) as f:
            for line in f:
                lines.add(line.rstrip("\r\n"))
        return lines
    except FileNotFoundError as exc:
        raise SearchError(f"Data file not found: {file_path}") from exc
    except OSError as exc:
        raise SearchError(
            f"Failed reading data file: {file_path} ({exc})"
        ) from exc


def search_set_cache(cache: set[str], query: str) -> bool:
    """Search for a query in a pre-built set cache.

    Args:
        cache: Set of lines built from the data file.
        query: Query string to check.

    Returns:
        True if the query exists in the cache, otherwise False.
    """
    return query in cache


def build_sorted_list(file_path: Path) -> list[str]:
    """Build a sorted list of all lines in the file.

    The resulting list supports binary-search membership checks.

    Args:
        file_path: Path to the data file.

    Returns:
        A sorted list containing all lines from the file (with line terminators
        stripped).

    Raises:
        SearchError: If the file cannot be read.
    """
    try:
        lines: list[str] = []
        with file_path.open(
            "r", encoding="utf-8", errors="replace", newline=""
        ) as f:
            for line in f:
                lines.append(line.rstrip("\r\n"))
        lines.sort()
        return lines
    except FileNotFoundError as exc:
        raise SearchError(f"Data file not found: {file_path}") from exc
    except OSError as exc:
        raise SearchError(
            f"Failed reading data file: {file_path} ({exc})"
        ) from exc


def search_sorted_bisect(sorted_lines: list[str], query: str) -> bool:
    """Search for a query using binary search on a sorted list.

    Args:
        sorted_lines: Sorted list of file lines.
        query: Query string to locate.

    Returns:
        True if the query exists as an exact element in the list, otherwise
        False.
    """
    idx = bisect_left(sorted_lines, query)
    return idx < len(sorted_lines) and sorted_lines[idx] == query


def search_mmap_scan(file_path: Path, query: str) -> bool:
    """Search using a memory-mapped file scan with boundary validation.

    This algorithm:
    - Does not read the entire file into Python objects (no full read/split).
    - Finds the query bytes and validates line boundaries to avoid partial
      matches.
    - Handles both LF and CRLF line endings.

    Args:
        file_path: Path to the data file.
        query: Query string to match against full lines.

    Returns:
        True if an exact full-line match is found, otherwise False.

    Raises:
        SearchError: If the file cannot be read or memory-mapped.
    """
    try:
        q = query.encode("utf-8")
        if not q:
            return False

        with file_path.open("rb") as f:
            # If the file is empty, mmap of size 0 fails; handle explicitly.
            try:
                mm = mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ)
            except ValueError:
                return False

            with mm:
                n = mm.size()
                start = 0

                while True:
                    pos = mm.find(q, start)
                    if pos == -1:
                        return False

                    before_ok = (pos == 0) or (mm[pos - 1: pos] == b"\n")

                    after_pos = pos + len(q)
                    if after_pos == n:
                        after_ok = True  # EOF boundary
                    else:
                        nxt = mm[after_pos: after_pos + 1]
                        if nxt == b"\n":
                            after_ok = True
                        elif nxt == b"\r":
                            # Accept CRLF: must be followed by '\n' or be EOF.
                            if after_pos + 1 == n:
                                after_ok = True
                            else:
                                after_ok = (
                                    mm[after_pos + 1: after_pos + 2] == b"\n"
                                )
                        else:
                            after_ok = False

                    if before_ok and after_ok:
                        return True

                    start = pos + 1

    except FileNotFoundError as exc:
        raise SearchError(f"Data file not found: {file_path}") from exc
    except OSError as exc:
        raise SearchError(
            f"Failed mmap reading data file: {file_path} ({exc})"
        ) from exc


def search_grep_fx(file_path: Path, query: str) -> bool:
    """Search using GNU grep for an exact full-line match.

    Uses `grep -F -x` to match the query as a fixed string (-F) and require the
    whole line to match (-x).
    This spawns a subprocess per query, which can be a
    reasonable approach when rereading the file per query is acceptable.

    Args:
        file_path: Path to the data file.
        query: Query string to match against full lines.

    Returns:
        True if grep finds an exact matching line, otherwise False.

    Raises:
        SearchError: If grep is unavailable or cannot be executed.
    """
    try:
        result = subprocess.run(
            ["grep", "-F", "-x", "--", query, str(file_path)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return result.returncode == 0
    except FileNotFoundError as exc:
        raise SearchError("grep not found on system") from exc
    except OSError as exc:
        raise SearchError(f"Failed running grep: {exc}") from exc
