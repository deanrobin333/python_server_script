#!/usr/bin/python3
# search.py

from __future__ import annotations

from bisect import bisect_left
from pathlib import Path

import mmap
import subprocess


class SearchError(RuntimeError):
    """Raised when the search subsystem cannot read the data file."""


def search_linear_scan(file_path: Path, query: str) -> bool:
    """
    Exact full-line match: returns True only if a line equals `query`.
    Reads file sequentially each call.
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
    """Load all lines into a set for fast membership testing."""
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
    """Search using a pre-built set cache."""
    return query in cache


def build_sorted_list(file_path: Path) -> list[str]:
    """Load all lines, strip newlines, sort for binary-search membership."""
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
    """Binary search membership in a sorted list."""
    idx = bisect_left(sorted_lines, query)
    return idx < len(sorted_lines) and sorted_lines[idx] == query


# ----------------------------
# Algorithms best for reread_on_query=True
# ----------------------------

def search_mmap_scan(file_path: Path, query: str) -> bool:
    """
    Exact full-line match using memory-mapped file.

    - Does NOT read the entire file into Python (no mm.read(), no split()).
    - Finds query bytes and validates line boundaries to avoid partial matches.
    - Handles both \\n and \\r\\n files.
    """
    try:
        q = query.encode("utf-8")
        if not q:
            return False

        with file_path.open("rb") as f:
            # If file is empty, mmap of size 0 fails; handle explicitly.
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

                    before_ok = (pos == 0) or (mm[pos - 1:pos] == b"\n")

                    after_pos = pos + len(q)
                    if after_pos == n:
                        after_ok = True  # EOF boundary
                    else:
                        nxt = mm[after_pos:after_pos + 1]
                        if nxt == b"\n":
                            after_ok = True
                        elif nxt == b"\r":
                            # accept CRLF: must be followed by '\n' OR be EOF
                            if after_pos + 1 == n:
                                after_ok = True
                            else:
                                after_ok = (
                                    mm[after_pos + 1:after_pos + 2] == b"\n"
                                )
                        else:
                            after_ok = False

                    if before_ok and after_ok:
                        return True

                    # Continue searching after this occurrence
                    start = pos + 1

    except FileNotFoundError as exc:
        raise SearchError(f"Data file not found: {file_path}") from exc
    except OSError as exc:
        raise SearchError(
            f"Failed mmap reading data file: {file_path} ({exc})"
            ) from exc


def search_grep_fx(file_path: Path, query: str) -> bool:
    """
    Exact full-line match using GNU grep (-F -x).

    Spawns a subprocess per query (safe for reread_on_query=True).
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
