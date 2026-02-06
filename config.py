#!/usr/bin/python3
# config.py

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    """Raised when the configuration file is missing required values
    or is invalid."""


@dataclass(frozen=True)
class AppConfig:
    """
    Parsed configuration used by the server.

    Required configuration is path_to_file:
    - linuxpath=<path to file>
    """
    linuxpath: Path
    reread_on_query: bool = True
    search_algo: str = "linear_scan"


def _parse_bool(value: str) -> bool:
    """Parse True/False from config values."""
    v = value.strip().lower()
    if v in {"true", "1", "yes", "y", "on"}:
        return True
    if v in {"false", "0", "no", "n", "off"}:
        return False
    raise ConfigError(f"Invalid boolean value: {value!r}")


def load_config(config_path: str | Path) -> AppConfig:
    """
    Load configuration from a file.

    The config may contain many irrelevant lines.
    The relevant line starts with:
        linuxpath=/some/path/file.txt
        reread_on_query=True|False
        search_algo=linear_scan

    Rules:
    - Unknown keys are ignored.
    - Blank lines and comments (#...) are ignored.
    - linuxpath is required.
    """

    path = Path(config_path)

    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except FileNotFoundError as exc:
        raise ConfigError(f"Config file not found: {path}") from exc
    except OSError as exc:
        raise ConfigError(
            f"Failed to read config file: {path} ({exc})"
        ) from exc

    linuxpath: Path | None = None
    reread_on_query: bool = True
    search_algo: str = "linear_scan"

    for line in raw.splitlines():
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("linuxpath="):
            value = stripped[len("linuxpath="):].strip()
            if not value:
                raise ConfigError("linuxpath is present but empty")
            linuxpath = Path(value)
            continue

        if stripped.startswith("reread_on_query="):
            value = stripped[len("reread_on_query="):].strip()
            reread_on_query = _parse_bool(value)
            continue

        if stripped.startswith("search_algo="):
            value = stripped[len("search_algo="):].strip()
            if not value:
                raise ConfigError("search_algo is present but empty")
            search_algo = value
            continue

        # Ignore other keys/lines.

    if linuxpath is None:
        raise ConfigError("Missing required config entry: linuxpath=")

    allowed = {
        "linear_scan",
        "mmap_scan",
        "grep_fx",
        "set_cache",
        "sorted_bisect",
    }

    if search_algo not in allowed:
        raise ConfigError(
            f"Unsupported search_algo={search_algo!r}. "
            f"Allowed: {sorted(allowed)}"
        )

    return AppConfig(
        linuxpath=linuxpath,
        reread_on_query=reread_on_query,
        search_algo=search_algo,
    )
