#!/usr/bin/python3
# search.py


from __future__ import annotations

from pathlib import Path


class SearchError(RuntimeError):
    """Raised when the search operation cannot be performed."""


def line_exists_in_file(file_path: Path, query: str) -> bool:
    """
    Return True only if the file contains a line that matches `query` exactly.

    Important:
    - No partial matches: the entire line must equal the query.
    - We treat file lines as lines without their trailing newline characters.
    - server already strips incoming \r\n, so `query` should be a "clean" line.
    """
    try:
        with file_path.open(
            "r", encoding="utf-8", errors="replace", newline=""
        ) as f:
            for line in f:
                # Remove newline characters from the file line only
                candidate = line.rstrip("\r\n")
                if candidate == query:
                    return True
        return False
    except FileNotFoundError as exc:
        raise SearchError(f"Data file not found: {file_path}") from exc
    except OSError as exc:
        raise SearchError(
            f"Failed reading data file: {file_path} ({exc})"
        ) from exc
