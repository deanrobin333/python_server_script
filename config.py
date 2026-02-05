#!/usr/bin/python3
# config.py

# src/python_server_script/config.py
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


def load_config(config_path: str | Path) -> AppConfig:
    """
    Load configuration from a file.

    The config may contain many irrelevant lines.
    The relevant line starts with:
        linuxpath=/some/path/file.txt

    Rules:
    - Only lines starting with 'linuxpath=' count.
    - First valid linuxpath wins.
    - Blank lines and comments are ignored.
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

    for line in raw.splitlines():
        stripped = line.strip()

        if not stripped or stripped.startswith("#"):
            continue

        if stripped.startswith("linuxpath="):
            value = stripped[len("linuxpath="):].strip()
            if not value:
                raise ConfigError("linuxpath is present but empty")

            linuxpath = Path(value)
            break

    if linuxpath is None:
        raise ConfigError("Missing required config entry: linuxpath=")

    return AppConfig(linuxpath=linuxpath)
