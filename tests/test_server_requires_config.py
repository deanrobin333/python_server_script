#!/usr/bin/python3
"""
Server startup validation tests.

These tests ensure that the server fails fast with a clear error message when
required configuration files are missing or invalid.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def test_server_exits_with_error_when_config_missing(tmp_path: Path) -> None:
    """Ensure the server exits with an error
    when the config file is missing."""
    missing_cfg = tmp_path / "missing.conf"

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "server",
            "--host",
            "127.0.0.1",
            "--port",
            "0",  # Port value is irrelevant; server fails before binding.
            "--config",
            str(missing_cfg),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    out, err = proc.communicate(timeout=2)
    assert proc.returncode != 0

    combined = (out + "\n" + err).lower()
    assert "config error" in combined
    assert "not found" in combined
