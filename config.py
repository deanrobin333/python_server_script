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

    # Optional SSL/TLS settings
    ssl_enabled: bool = False
    ssl_certfile: Path | None = None
    ssl_keyfile: Path | None = None

    # Client-side SSL verification options (optional)
    ssl_verify: bool = True
    ssl_cafile: Path | None = None


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

    Optional SSL:
        ssl_enabled=True|False
        ssl_certfile=/path/to/server.crt
        ssl_keyfile=/path/to/server.key
        ssl_verify=True|False
        ssl_cafile=/path/to/ca_bundle.crt

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

        # SSL parsing (optional)
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

    # If SSL is enabled, server must have cert + key
    if ssl_enabled:
        if ssl_certfile is None or ssl_keyfile is None:
            raise ConfigError(
                "ssl_enabled=True requires ssl_certfile=... "
                "and ssl_keyfile=..."
            )
    # Client verification sanity: only meaningful when TLS is enabled
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
