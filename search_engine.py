#!/usr/bin/python3
# search_engine.py

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from config import AppConfig
from search import SearchError, line_exists_in_file


class EngineError(RuntimeError):
    """Raised when the search engine cannot operate correctly."""


@dataclass
class SearchEngine:
    """
    Orchestrates searching according to config.

    - reread_on_query=True  -> always read from disk per query
    - reread_on_query=False -> build an in-memory cache once, then query cache
    """

    file_path: Path
    reread_on_query: bool
    search_algo: str

    # cache for reread_on_query=False (only used for some algorithms)
    _cached_lines: set[str] | None = None

    @classmethod
    def from_config(cls, cfg: AppConfig) -> "SearchEngine":
        return cls(
            file_path=cfg.linuxpath,
            reread_on_query=cfg.reread_on_query,
            search_algo=cfg.search_algo,
        )

    def warmup(self) -> None:
        """
        Prepare any caches needed for fast mode (reread_on_query=False).
        Safe to call multiple times.
        """
        if self.reread_on_query:
            # No caching in this mode.
            self._cached_lines = None
            return

        # For now, in fast mode we cache all lines into a set for O(1) lookups.
        # simplest way to meet the 0.5ms target when the file is stable.
        try:
            self._cached_lines = self._load_lines_as_set(self.file_path)
        except SearchError as exc:
            raise EngineError(str(exc)) from exc

    def exists(self, query: str) -> bool:
        """
        Return True if query exists as an exact full line in the file.

        Behavior depends on reread_on_query:
        - True  -> scan file each time (reflects on-disk changes)
        - False -> query the cached set (fast)
        """
        if self.search_algo != "linear":
            raise EngineError(
                f"search_algo={self.search_algo!r} is not implemented yet"
            )

        if self.reread_on_query:
            # Always read from disk (matches current behavior)
            return line_exists_in_file(self.file_path, query)

        # Fast mode: use cache
        if self._cached_lines is None:
            # Lazy warmup so the server can start before immediate loading
            self.warmup()

        # After warmup, cache must exist
        if self._cached_lines is None:
            raise EngineError("Cache not initialized in fast mode")

        return query in self._cached_lines

    @staticmethod
    def _load_lines_as_set(file_path: Path) -> set[str]:
        """
        Load all lines from file into a set, stripping trailing newlines.
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
