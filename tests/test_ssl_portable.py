#!/usr/bin/python3
# tests/test_ssl_portable.py

from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path


def _get_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _recv_all(conn: socket.socket, bufsize: int = 4096) -> bytes:
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
    cfg_file.write_text(
        "\n".join(
            [
                f"linuxpath={data_file}",
                "reread_on_query=True",
                "search_algo=linear_scan",
                f"ssl_enabled={'True' if ssl_enabled else 'False'}",
                f"ssl_certfile={certfile}",
                f"ssl_keyfile={keyfile}",
                # client TLS settings (used by client when --config is passed)
                "ssl_verify=False",
                "",
            ]
        ),
        encoding="utf-8",
    )


def test_tls_enabled_requires_tls_client_or_it_resets(tmp_path: Path) -> None:
    """
    Portable test:
    - If cert/key files are present, start server with ssl_enabled=True
      and show that a plain TCP client fails (connection reset or garbage),
      but the provided client.py with --config succeeds.
    - If cert/key are missing, skip (portable, no openssl generation).
    """
    port = _get_free_port()

    # Create tiny data file so server can answer something
    data_file = tmp_path / "data.txt"
    data_file.write_text("hello\n", encoding="utf-8")

    # Expect certs to already exist if user wants this test to run
    certfile = Path("certs/server.crt")
    keyfile = Path("certs/server.key")
    if not (certfile.exists() and keyfile.exists()):
        import pytest

        pytest.skip(
            "TLS cert/key not found in certs/. Generate certs to run test."
        )

    cfg_file = tmp_path / "app.conf"
    _write_cfg(
        cfg_file, data_file,
        ssl_enabled=True, certfile=certfile, keyfile=keyfile
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

        # 1) Plain socket client should NOT work against TLS server
        plain_failed = False
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=2) as s:
                s.settimeout(2)
                s.sendall(b"hello\n")
                _ = _recv_all(s)
        except (ConnectionResetError, socket.timeout, OSError):
            plain_failed = True

        assert plain_failed is True

        # 2) python client with --config should succeed (verify=False here)
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
        assert (
            p2.stdout.endswith("STRING EXISTS\n")
            or p2.stdout.endswith("STRING NOT FOUND\n")
        )

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
