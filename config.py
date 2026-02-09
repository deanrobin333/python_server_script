#!/usr/bin/python3
"""
Application configuration parsing.

This module defines the configuration schema used by the server/client and
provides a simple parser for key=value configuration files.

Parsing rules:
- Unknown keys are ignored.
- Blank lines and comment lines starting with '#' are ignored.
- The 'linuxpath' key is required.
- Some values are validated (booleans, search algorithm, SSL constraints).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


class ConfigError(ValueError):
    """Raised when the configuration file is missing
    required values or invalid."""


@dataclass(frozen=True)
class AppConfig:
    """Parsed application configuration.

    Attributes:
        linuxpath: Path to the input file containing rows to search.
        reread_on_query: If True, re-read the file on each query.
        search_algo: Search strategy identifier.

        ssl_enabled: If True, enable TLS for server/client connections.
        ssl_certfile: Server certificate path (required if ssl_enabled=True).
        ssl_keyfile: Server private key path (required if ssl_enabled=True).

        ssl_verify: If True, the client verifies the server certificate.
        ssl_cafile: Trust anchor path for self-signed certificates. Required
            when ssl_enabled=True and ssl_verify=True.
    """

    linuxpath: Path
    reread_on_query: bool = True
    search_algo: str = "linear_scan"

    ssl_enabled: bool = False
    ssl_certfile: Path | None = None
    ssl_keyfile: Path | None = None

    ssl_verify: bool = True
    ssl_cafile: Path | None = None


def _parse_bool(value: str) -> bool:
    """Parse a boolean config value.

    Accepted truthy values: true, 1, yes, y, on.
    Accepted falsy values: false, 0, no, n, off.

    Args:
        value: Raw string value from the config file.

    Returns:
        Parsed boolean value.

    Raises:
        ConfigError: If the value cannot be interpreted as a boolean.
    """
    v = value.strip().lower()
    if v in {"true", "1", "yes", "y", "on"}:
        return True
    if v in {"false", "0", "no", "n", "off"}:
        return False
    raise ConfigError(f"Invalid boolean value: {value!r}")


def load_config(config_path: str | Path) -> AppConfig:
    """Load and validate application configuration from a file.

    Supported keys:
        linuxpath=/path/to/file.txt               (required)
        reread_on_query=True|False                (optional)
        search_algo=linear_scan|mmap_scan|...     (optional)

        ssl_enabled=True|False                    (optional)
        ssl_certfile=/path/to/server.crt          (optional)
        ssl_keyfile=/path/to/server.key           (optional)

        ssl_verify=True|False                     (optional)
        ssl_cafile=/path/to/ca_bundle.crt         (optional)

    Validation rules:
    - linuxpath is required and must be non-empty.
    - search_algo must be one of the supported algorithms.
    - If ssl_enabled=True, ssl_certfile and ssl_keyfile must be provided.
    - If ssl_enabled=True and ssl_verify=True, ssl_cafile must be provided.

    Args:
        config_path: Path to the configuration file.

    Returns:
        A validated AppConfig instance.

    Raises:
        ConfigError: If the file cannot be read, required keys are missing, or
            values fail validation.
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

    ssl_enabled: bool = False
    ssl_certfile: Path | None = None
    ssl_keyfile: Path | None = None
    ssl_verify: bool = True
    ssl_cafile: Path | None = None

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

        if stripped.startswith("ssl_enabled="):
            value = stripped[len("ssl_enabled="):].strip()
            ssl_enabled = _parse_bool(value)
            continue

        if stripped.startswith("ssl_certfile="):
            value = stripped[len("ssl_certfile="):].strip()
            ssl_certfile = Path(value) if value else None
            continue

        if stripped.startswith("ssl_keyfile="):
            value = stripped[len("ssl_keyfile="):].strip()
            ssl_keyfile = Path(value) if value else None
            continue

        if stripped.startswith("ssl_verify="):
            value = stripped[len("ssl_verify="):].strip()
            ssl_verify = _parse_bool(value)
            continue

        if stripped.startswith("ssl_cafile="):
            value = stripped[len("ssl_cafile="):].strip()
            ssl_cafile = Path(value) if value else None
            continue

        # Unknown keys are ignored.

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

    if ssl_enabled:
        if ssl_certfile is None or ssl_keyfile is None:
            raise ConfigError(
                "ssl_enabled=True requires ssl_certfile=... and "
                "ssl_keyfile=..."
            )

    if ssl_enabled and ssl_verify and ssl_cafile is None:
        raise ConfigError(
            "ssl_verify=True requires ssl_cafile=... "
            "(for self-signed cert verification)."
        )

    return AppConfig(
        linuxpath=linuxpath,
        reread_on_query=reread_on_query,
        search_algo=search_algo,
        ssl_enabled=ssl_enabled,
        ssl_certfile=ssl_certfile,
        ssl_keyfile=ssl_keyfile,
        ssl_verify=ssl_verify,
        ssl_cafile=ssl_cafile,
    )
