#!/usr/bin/python3
# tests/test_protocol.py

from __future__ import annotations

from pathlib import Path
import pytest

import socket
import subprocess
import sys
import time

"""
This test verifies the basic “wire protocol” between client and server:
1. Server can start and bind a port
2. A client can connect
3. Client can send a query string
4. Server responds with:
- at least one DEBUG: line
- and a final result line ending in either:
  - STRING NOT FOUND or
  - STRING EXISTS
"""


def _get_free_port() -> int:
    """get an unused port for the operating system"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _recv_all(conn: socket.socket, bufsize: int = 4096) -> bytes:
    """Read until the server closes the connection (EOF)."""
    chunks: list[bytes] = []
    while True:
        part = conn.recv(bufsize)
        if not part:
            break
        chunks.append(part)
    return b"".join(chunks)


def test_server_responds_with_debug_and_result_line(tmp_path: Path) -> None:
    """the actuall test to be done using pytest"""
    port = _get_free_port()

    # create a dummy data file and config file
    data_file = tmp_path / "data.txt"
    data_file.write_text("hello\n", encoding="utf-8")

    cfg_file = tmp_path / "app.conf"
    cfg_file.write_text(f"linuxpath={data_file}\n", encoding="utf-8")

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
        # Give the server a moment to bind.
        time.sleep(0.3)

        # If the process already died, show why.
        rc = proc.poll()
        if rc is not None:
            out, err = proc.communicate(timeout=1)
            raise RuntimeError(
                "Server exited early.\n"
                f"exit_code={rc}\n"
                f"--- stdout ---\n{out}\n"
                f"--- stderr ---\n{err}\n"
            )

        """connect as a client and send query"""
        with socket.create_connection(("127.0.0.1", port), timeout=3) as s:
            s.sendall(b"hello\n")
            raw = _recv_all(s)

        data = raw.decode("utf-8", errors="replace")

        assert "DEBUG:" in data, f"Missing DEBUG line. Got: {data!r}"
        assert data.endswith("STRING NOT FOUND\n") or data.endswith(
            "STRING EXISTS\n"
        ), f"Missing/invalid result line at end. Got: {data!r}"

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
