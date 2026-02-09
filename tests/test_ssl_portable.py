#!/usr/bin/python3
"""
Portable TLS integration test.

This test validates that:
- When the server is started with TLS enabled, a plain TCP client cannot
  successfully communicate with it.
- The provided client implementation, when configured with --config, can
  successfully connect and receive a well-formed response.

The test is portable: it skips unless cert/key files already exist in certs/.
"""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest


def _get_free_port() -> int:
    """Return an unused TCP port bound on localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _recv_all(conn: socket.socket, bufsize: int = 4096) -> bytes:
    """Read all data from a socket until EOF.

    Args:
        conn: Connected socket.
        bufsize: Bytes per recv() call.

    Returns:
        All bytes received from the socket.
    """
    chunks: list[bytes] = []
    while True:
        part = conn.recv(bufsize)
        if not part:
            break
        chunks.append(part)
    return b"".join(chunks)


def _write_cfg(
    cfg_file: Path,
    data_file: Path,
    *,
    ssl_enabled: bool,
    certfile: Path,
    keyfile: Path,
) -> None:
    """Write a temporary config file used to start the TLS server.

    Args:
        cfg_file: Output path for the config file.
        data_file: Data file path referenced by linuxpath.
        ssl_enabled: Whether to enable TLS.
        certfile: Server certificate path.
        keyfile: Server private key path.
    """
    cfg_file.write_text(
        "\n".join(
            [
                f"linuxpath={data_file}",
                "reread_on_query=True",
                "search_algo=linear_scan",
                f"ssl_enabled={'True' if ssl_enabled else 'False'}",
                f"ssl_certfile={certfile}",
                f"ssl_keyfile={keyfile}",
                "ssl_verify=False",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_tls_enabled_requires_tls_client_or_it_resets(tmp_path: Path) -> None:
    """Verify TLS server rejects plain TCP and accepts the configured client.

    The test starts a server with ssl_enabled=True
        using existing cert/key files.
    It then verifies:
    1) A plain TCP client cannot successfully complete the request.
    2) The packaged client with --config can connect and
        receive a valid result.

    The test is skipped if certs are not present in certs/.
    """
    port = _get_free_port()

    data_file = tmp_path / "data.txt"
    data_file.write_text("hello\n", encoding="utf-8")

    certfile = Path("certs/server.crt")
    keyfile = Path("certs/server.key")
    if not (certfile.exists() and keyfile.exists()):
        pytest.skip(
            "TLS cert/key not found in certs/. Generate certs to run test."
        )

    cfg_file = tmp_path / "app.conf"
    _write_cfg(
        cfg_file,
        data_file,
        ssl_enabled=True,
        certfile=certfile,
        keyfile=keyfile,
    )

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "server",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--config",
            str(cfg_file),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    try:
        time.sleep(0.35)

        if proc.poll() is not None:
            out, err = proc.communicate(timeout=1)
            raise RuntimeError(
                "Server exited early.\n"
                f"--- stdout ---\n{out}\n"
                f"--- stderr ---\n{err}\n"
            )

        plain_failed = False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2) as s:
                s.settimeout(2)
                s.sendall(b"hello\n")
                _ = _recv_all(s)
        except (ConnectionResetError, socket.timeout, OSError):
            plain_failed = True

        assert plain_failed is True

        p2 = subprocess.run(
            [
                sys.executable,
                "-m",
                "client",
                "--host",
                "127.0.0.1",
                "--port",
                str(port),
                "--config",
                str(cfg_file),
                "hello",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=5,
        )
        assert p2.returncode == 0, p2.stderr
        assert "DEBUG:" in p2.stdout
        assert p2.stdout.endswith(("STRING EXISTS\n", "STRING NOT FOUND\n"))

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
