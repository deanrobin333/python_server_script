#!/usr/bin/python3
# search_engine.py

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union

from config import AppConfig
from search import (
    SearchError,
    build_set_cache,
    build_sorted_list,
    search_grep_fx,
    search_linear_scan,
    search_mmap_scan,
    search_set_cache,
    search_sorted_bisect,
)


class EngineError(RuntimeError):
    """Raised when the search engine cannot operate correctly."""


CACHED_ALGOS = {"set_cache", "sorted_bisect"}
REREAD_ALGOS = {"linear_scan", "mmap_scan", "grep_fx"}
ALL_ALGOS = CACHED_ALGOS | REREAD_ALGOS


CacheType = Union[set[str], list[str]]


@dataclass
class SearchEngine:
    file_path: Path
    reread_on_query: bool
    search_algo: str
    _cache: Optional[CacheType] = None

    @classmethod
    def supported_algorithms(cls) -> set[str]:
        return set(ALL_ALGOS)

    @classmethod
    def from_config(cls, cfg: AppConfig) -> "SearchEngine":
        engine = cls(
            file_path=cfg.linuxpath,
            reread_on_query=cfg.reread_on_query,
            search_algo=cfg.search_algo,
        )
        engine._validate_compatibility()
        return engine

    def _validate_compatibility(self) -> None:
        if self.search_algo not in ALL_ALGOS:
            raise EngineError(f"Unsupported search_algo={self.search_algo!r}")

        if self.reread_on_query and self.search_algo in CACHED_ALGOS:
            raise EngineError(
                f"search_algo={self.search_algo!r} "
                f"is not compatible with reread_on_query=True"
            )

    def warmup(self) -> None:
        """Build cache for cached algorithms
        (only useful when reread_on_query=False)."""
        self._validate_compatibility()

        if self.reread_on_query:
            self._cache = None
            return

        try:
            if self.search_algo == "set_cache":
                self._cache = build_set_cache(self.file_path)
            elif self.search_algo == "sorted_bisect":
                self._cache = build_sorted_list(self.file_path)
            else:
                """linear/mmap/grep in reread=False do not need cache"""
                self._cache = None
        except SearchError as exc:
            raise EngineError(str(exc)) from exc

    def exists(self, query: str) -> bool:
        self._validate_compatibility()

        # reread_on_query=True -> disk-based every call
        if self.reread_on_query:
            try:
                if self.search_algo == "linear_scan":
                    return search_linear_scan(self.file_path, query)
                if self.search_algo == "mmap_scan":
                    return search_mmap_scan(self.file_path, query)
                if self.search_algo == "grep_fx":
                    return search_grep_fx(self.file_path, query)
            except SearchError as exc:
                raise EngineError(str(exc)) from exc

            # Defensive: should never hit due to validation
            raise EngineError(f"Unsupported search_algo={self.search_algo!r}")

        # reread_on_query=False
        if self.search_algo == "linear_scan":
            try:
                return search_linear_scan(self.file_path, query)
            except SearchError as exc:
                raise EngineError(str(exc)) from exc

        if self.search_algo in {"mmap_scan", "grep_fx"}:
            try:
                if self.search_algo == "mmap_scan":
                    return search_mmap_scan(self.file_path, query)
                return search_grep_fx(self.file_path, query)
            except SearchError as exc:
                raise EngineError(str(exc)) from exc

        # Cached algos: allow lazy warmup
        if self._cache is None:
            self.warmup()

        if self.search_algo == "set_cache":
            assert isinstance(self._cache, set)
            return search_set_cache(self._cache, query)

        if self.search_algo == "sorted_bisect":
            assert isinstance(self._cache, list)
            return search_sorted_bisect(self._cache, query)

        raise EngineError(f"Unsupported search_algo={self.search_algo!r}")
