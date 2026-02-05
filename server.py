#!/usr/bin/python3
# server.py

from __future__ import annotations

import argparse
import socket
import threading
import time
from dataclasses import dataclass
from typing import Optional

from pathlib import Path
from search import SearchError, line_exists_in_file

MAX_PAYLOAD_BYTES = 1024
RESPONSE_EXISTS = b"STRING EXISTS\n"
RESPONSE_NOT_FOUND = b"STRING NOT FOUND\n"


@dataclass(frozen=True)
class ServerConfig:
    host: str
    port: int


class TCPStringLookupServer:
    def __init__(self, cfg: ServerConfig, data_file: Path) -> None:
        self._cfg = cfg
        self._data_file = data_file
        self._sock: Optional[socket.socket] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start listening and accepting connections (blocking)."""
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self._cfg.host, self._cfg.port))
        self._sock.listen(128)
        self._sock.settimeout(0.5)  # important for graceful shutdown

        """Accept loop"""
        while not self._stop_event.is_set():
            try:
                conn, addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                # Happens if socket is closed while we're waiting in accept()
                break

            """creates multithreading"""
            t = threading.Thread(
                target=self._handle_client,
                args=(conn, addr),
                daemon=True,
            )
            t.start()

    def stop(self) -> None:
        """Signal server to stop and close the listening socket."""
        self._stop_event.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass

    """runs in a separate thread per client"""
    def _handle_client(
        self,
        conn: socket.socket,
        addr: tuple[str, int],
    ) -> None:
        client_ip, _client_port = addr
        start = time.perf_counter()

        """Timeout prevents a client from connecting
        and never sending anything"""
        try:
            conn.settimeout(5.0)

            payload = conn.recv(MAX_PAYLOAD_BYTES)
            payload = payload.rstrip(b"\x00")
            query = payload.decode("utf-8", errors="replace").rstrip("\r\n")

            try:
                found = line_exists_in_file(self._data_file, query)
            except SearchError as exc:
                # Treat search errors as NOT FOUND but emit debug info
                found = False
                # we shall append to debug later, but keeping minimal for now


            elapsed_ms = (time.perf_counter() - start) * 1000.0
            debug = (
                f"DEBUG: ip={client_ip} "
                f"query={query!r} "
                f"elapsed_ms={elapsed_ms:.3f}\n"
            )

            conn.sendall(debug.encode("utf-8"))
            conn.sendall(RESPONSE_EXISTS if found else RESPONSE_NOT_FOUND)

        except Exception as exc:
            msg = f"DEBUG: error={type(exc).__name__}: {exc}\n"
            try:
                conn.sendall(msg.encode("utf-8"))
                conn.sendall(RESPONSE_NOT_FOUND)
            except OSError:
                pass
        finally:
            try:
                conn.close()
            except OSError:
                pass


def parse_args() -> argparse.Namespace:
    """reads data from a configuration file"""
    p = argparse.ArgumentParser(description="TCP String Lookup Server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=44445)

    # NEW: config file path (required for Task 3B)
    p.add_argument(
        "--config",
        required=True,
        help="Path to configuration file (must include linuxpath=...)",
    )
    return p.parse_args()


def main() -> None:
    """This is the 'orchestration' function:
    - parse args
    - build config
    - create server object
    - start server
    """

    """local import to keep startup clean"""
    from config import ConfigError, load_config

    args = parse_args()

    # NEW: load config and validate linuxpath exists in config file
    try:
        app_cfg = load_config(args.config)
    except ConfigError as exc:
        # Fail fast with a clear message
        raise SystemExit(f"Config error: {exc}") from exc

    # For now we only parse it (Task 4 will actually use it)
    # You can keep this as a local variable to avoid unused warnings later.
    data_file = app_cfg.linuxpath

    cfg = ServerConfig(host=args.host, port=args.port)
    server = TCPStringLookupServer(cfg, data_file=data_file)

    try:
        server.start()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


if __name__ == "__main__":
    main()
