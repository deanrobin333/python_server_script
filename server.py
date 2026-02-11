#!/usr/bin/python3
"""
TCP String Lookup Server.

This module implements a newline-delimited TCP server
that accepts queries over a persistent connection.
For each query line received, it returns:

- A DEBUG line with the client IP, query, and elapsed time in milliseconds.
- A result line: "STRING EXISTS" or "STRING NOT FOUND".

TLS is optional. If configured, accepted connections are wrapped with an SSL
context in the per-client thread to avoid blocking the accept loop.
"""

from __future__ import annotations

import argparse
import socket
import ssl
import threading
import time
from dataclasses import dataclass
from typing import Optional

from config import ConfigError, load_config
from search_engine import EngineError, SearchEngine


MAX_PAYLOAD_BYTES = 1024
RESPONSE_EXISTS = b"STRING EXISTS\n"
RESPONSE_NOT_FOUND = b"STRING NOT FOUND\n"


@dataclass(frozen=True)
class ServerConfig:
    """Runtime server configuration.

    Attributes:
        host: Interface address to bind to.
        port: TCP port to listen on.
    """

    host: str
    port: int


class TCPStringLookupServer:
    """A threaded TCP server that performs newline-delimited string lookups.

    The server listens on the configured host/port and
    spawns a daemon thread per client connection.
    Each client connection is handled as a persistent session
    that reads newline-delimited queries and responds per query.

    TLS support is optional. If an SSL context is provided, client sockets are
    wrapped with TLS after accept and before request handling.
    """

    def __init__(
        self,
        cfg: ServerConfig,
        engine: SearchEngine,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        """Initialize the server.

        Args:
            cfg: Network bind configuration (host/port).
            engine: Search engine used to answer existence queries.
            ssl_context: Optional server-side SSL context for TLS connections.
        """
        self._cfg = cfg
        self._engine = engine
        self._ssl_context = ssl_context
        self._sock: Optional[socket.socket] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start listening and accepting connections (blocking).

        This method binds and listens on the configured address, then accepts
        connections in a loop until `stop()` is called.
        Each accepted connection is handled in its own daemon thread.
        """
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self._cfg.host, self._cfg.port))
        self._sock.listen(128)
        self._sock.settimeout(0.5)  # allows graceful shutdown checks

        while not self._stop_event.is_set():
            try:
                conn, addr = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break

            t = threading.Thread(
                target=self._handle_client_thread,
                args=(conn, addr),
                daemon=True,
            )
            t.start()

    def stop(self) -> None:
        """Signal the server to stop and close the listening socket."""
        self._stop_event.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass

    def _handle_client_thread(
        self, conn: socket.socket, addr: tuple[str, int]
    ) -> None:
        """Handle a single client connection in a dedicated thread.

        If TLS is enabled, the socket is wrapped here (after accept) so TLS
        negotiation does not block the main accept loop.

        Args:
            conn: The accepted client socket.
            addr: The client address tuple (ip, port).
        """
        if self._ssl_context is not None:
            try:
                conn = self._ssl_context.wrap_socket(conn, server_side=True)
            except ssl.SSLError:
                try:
                    conn.close()
                except OSError:
                    pass
                return

        self._handle_client(conn, addr)

    def _handle_client(
        self, conn: socket.socket, addr: tuple[str, int]
    ) -> None:
        """Serve a persistent client session.

        This handler reads newline-delimited queries in a loop and responds to
        each query without closing the connection. Idle clients are not
        disconnected; the server keeps waiting for the next query.

        Per query, the server sends:
        1) a DEBUG line with timing information
        2) a result line indicating whether the string exists

        Args:
            conn: Connected client socket (plain or TLS-wrapped).
            addr: The client address tuple (ip, port).
        """
        client_ip, _client_port = addr

        # Use a small timeout so threads can exit when server.stop() is called.
        # This does NOT disconnect idle clients; we simply continue waiting.
        conn.settimeout(1.0)

        buf = b""

        try:
            while not self._stop_event.is_set():
                try:
                    chunk = conn.recv(4096)
                except socket.timeout:
                    # No data yet; keep waiting forever (like nc example).
                    continue

                if not chunk:
                    # Client closed the connection.
                    break

                buf += chunk

                while b"\n" in buf:
                    raw_line, buf = buf.split(b"\n", 1)

                    # Trim CRLF and NULLs.
                    raw_line = raw_line.rstrip(b"\r").rstrip(b"\x00")

                    if len(raw_line) > MAX_PAYLOAD_BYTES:
                        msg = (
                            "DEBUG: error=ValueError: query too long\n"
                        ).encode("utf-8")
                        try:
                            conn.sendall(msg)
                            conn.sendall(RESPONSE_NOT_FOUND)
                        except OSError:
                            return
                        continue

                    query = raw_line.decode("utf-8", errors="replace")

                    start = time.perf_counter()
                    try:
                        found = self._engine.exists(query)
                    except EngineError:
                        found = False

                    elapsed_ms = (time.perf_counter() - start) * 1000.0
                    debug = (
                        f"DEBUG: ip={client_ip} "
                        f"query={query!r} "
                        f"elapsed_ms={elapsed_ms:.3f}\n"
                    ).encode("utf-8")

                    try:
                        conn.sendall(debug)
                        conn.sendall(
                            RESPONSE_EXISTS if found else RESPONSE_NOT_FOUND
                        )
                    except OSError:
                        return
        finally:
            try:
                conn.close()
            except OSError:
                pass


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed command-line arguments.
    """
    p = argparse.ArgumentParser(description="TCP String Lookup Server")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=44445)
    p.add_argument(
        "--config",
        required=True,
        help="Path to configuration file (must include linuxpath=...)",
    )
    return p.parse_args()


def _build_server_ssl_context(app_cfg) -> ssl.SSLContext | None:
    """Build a server-side SSL context if enabled.

    Args:
        app_cfg: Loaded application configuration.

    Returns:
        An SSLContext configured for server-side TLS if SSL is enabled,
        otherwise None.

    Raises:
        AssertionError: If SSL is enabled but cert/key paths are missing.
    """
    if not app_cfg.ssl_enabled:
        return None

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    assert app_cfg.ssl_certfile is not None
    assert app_cfg.ssl_keyfile is not None

    ctx.load_cert_chain(
        certfile=str(app_cfg.ssl_certfile),
        keyfile=str(app_cfg.ssl_keyfile),
    )

    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


def main() -> None:
    """Run the TCP server entry point."""
    args = parse_args()

    try:
        app_cfg = load_config(args.config)
    except ConfigError as exc:
        raise SystemExit(f"Config error: {exc}") from exc

    engine = SearchEngine.from_config(app_cfg)

    if not app_cfg.reread_on_query:
        try:
            engine.warmup()
        except EngineError as exc:
            raise SystemExit(f"Engine error: {exc}") from exc

    ssl_ctx = _build_server_ssl_context(app_cfg)

    cfg = ServerConfig(host=args.host, port=args.port)
    server = TCPStringLookupServer(cfg, engine=engine, ssl_context=ssl_ctx)

    try:
        server.start()
    except KeyboardInterrupt:
        pass
    except Exception as exc:
        raise SystemExit(f"Fatal error: {exc}") from exc
    finally:
        server.stop()


if __name__ == "__main__":
    main()
