#!/usr/bin/python3
# server.py

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
    host: str
    port: int


class TCPStringLookupServer:
    def __init__(
        self,
        cfg: ServerConfig,
        engine: SearchEngine,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        self._cfg = cfg
        self._engine = engine
        self._ssl_context = ssl_context
        self._sock: Optional[socket.socket] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        """Start listening and accepting connections (blocking)."""
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
        """Signal server to stop and close the listening socket."""
        self._stop_event.set()
        if self._sock is not None:
            try:
                self._sock.close()
            except OSError:
                pass

    def _handle_client_thread(
        self, conn: socket.socket, addr: tuple[str, int]
    ) -> None:
        """
        Per-client thread.
        TLS wrapping is done here to avoid blocking the accept loop.
        """
        if self._ssl_context is not None:
            try:
                conn = self._ssl_context.wrap_socket(
                    conn,
                    server_side=True,
                )
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
        client_ip, _client_port = addr
        start = time.perf_counter()

        try:
            conn.settimeout(5.0)

            payload = conn.recv(MAX_PAYLOAD_BYTES)
            payload = payload.rstrip(b"\x00")
            query = payload.decode("utf-8", errors="replace").rstrip("\r\n")

            try:
                found = self._engine.exists(query)
            except EngineError:
                found = False

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
    """Build SSL context if ssl_enabled=True, otherwise return None."""
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
    server = TCPStringLookupServer(
        cfg,
        engine=engine,
        ssl_context=ssl_ctx,
    )

    try:
        server.start()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()


if __name__ == "__main__":
    main()
