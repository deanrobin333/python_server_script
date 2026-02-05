#!/usr/bin/python3
# tests/test_server_search_integration.py

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


def test_server_returns_exists_for_exact_line(tmp_path: Path) -> None:
    port = _get_free_port()

    data_file = tmp_path / "data.txt"
    data_file.write_text("one\ntwo\nthree\n", encoding="utf-8")

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
        time.sleep(0.3)

        with socket.create_connection(("127.0.0.1", port), timeout=3) as s:
            s.sendall(b"two\n")
            raw = _recv_all(s)

        data = raw.decode("utf-8", errors="replace")
        assert "DEBUG:" in data
        assert data.endswith("STRING EXISTS\n")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_server_returns_not_found_for_partial(tmp_path: Path) -> None:
    port = _get_free_port()

    data_file = tmp_path / "data.txt"
    data_file.write_text("one\ntwo\nthree\n", encoding="utf-8")

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
        time.sleep(0.3)

        with socket.create_connection(("127.0.0.1", port), timeout=3) as s:
            s.sendall(b"tw\n")
            raw = _recv_all(s)

        data = raw.decode("utf-8", errors="replace")
        assert "DEBUG:" in data
        assert data.endswith("STRING NOT FOUND\n")

    finally:
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
