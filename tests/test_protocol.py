#!/usr/bin/python3
# tests/test_protocol.py

from __future__ import annotations

from pathlib import Path

import socket
import subprocess
import sys
import time

RESULT_EXISTS = b"STRING EXISTS\n"
RESULT_NOT_FOUND = b"STRING NOT FOUND\n"


def _get_free_port() -> int:
    """Get an unused port from the operating system."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _recv_until_result(conn: socket.socket, bufsize: int = 4096) -> bytes:
    """
    Read until we see a terminal result line.
    Works with persistent connections (no EOF).
    """
    buf = b""
    while True:
        part = conn.recv(bufsize)
        if not part:
            break
        buf += part

        if RESULT_EXISTS in buf or RESULT_NOT_FOUND in buf:
            break

        # Safety: avoid infinite growth if something is wrong
        if len(buf) > 1024 * 1024:
            break

    return buf


def test_server_responds_with_debug_and_result_line(tmp_path: Path) -> None:
    """
    Verifies the basic wire protocol:
      - server starts
      - client connects
      - query is sent
      - response contains DEBUG line and ends with a result line
    """
    port = _get_free_port()

    data_file = tmp_path / "data.txt"
    data_file.write_text("hello\n", encoding="utf-8")

    cfg_file = tmp_path / "app.conf"
    cfg_file.write_text(
        f"linuxpath={data_file}\n"
        "reread_on_query=True\n"
        "search_algo=linear_scan\n",
        encoding="utf-8",
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
        time.sleep(0.3)

        rc = proc.poll()
        if rc is not None:
            out, err = proc.communicate(timeout=1)
            raise RuntimeError(
                "Server exited early.\n"
                f"exit_code={rc}\n"
                f"--- stdout ---\n{out}\n"
                f"--- stderr ---\n{err}\n"
            )

        with socket.create_connection(("127.0.0.1", port), timeout=3) as s:
            s.settimeout(3)
            s.sendall(b"hello\n")
            raw = _recv_until_result(s)

        data = raw.decode("utf-8", errors="replace")

        assert "DEBUG:" in data, f"Missing DEBUG line. Got: {data!r}"
        assert data.endswith(
            ("STRING NOT FOUND\n", "STRING EXISTS\n")
        ), f"Missing/invalid result line at end. Got: {data!r}"

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
