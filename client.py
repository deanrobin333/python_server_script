#!/usr/bin/python3
# client.py

from __future__ import annotations

import argparse
import socket
import ssl
import sys
from typing import List

from config import ConfigError, load_config


RECV_BUFSIZE = 4096  # how many bytes we ask for per recv() call.
RECV_TIMEOUT_SECONDS = 5.0  # stops client hanging forever if server stalls

RESULT_EXISTS = b"STRING EXISTS\n"
RESULT_NOT_FOUND = b"STRING NOT FOUND\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TCP String Lookup Client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=44445)

    # Optional config: lets client use SSL settings from the same app.conf
    parser.add_argument(
        "--config",
        required=False,
        help="Optional config file path (used for SSL settings)",
    )

    parser.add_argument(
        "query",
        help="Query string to send (exact full-line match)",
    )
    return parser.parse_args()


def recv_until_result(sock: socket.socket) -> bytes:
    """
    Receive data until we see one of the result terminators:
      - STRING EXISTS\\n
      - STRING NOT FOUND\\n

    This supports a persistent server connection, where EOF never arrives.
    """
    chunks: List[bytes] = []
    buf = b""

    while True:
        data = sock.recv(RECV_BUFSIZE)
        if not data:
            # Server closed (EOF)
            chunks.append(buf)
            break

        buf += data

        # Stop as soon as we have a full result line.
        if RESULT_EXISTS in buf or RESULT_NOT_FOUND in buf:
            chunks.append(buf)
            break

        # Safety: prevent unbounded growth if something goes wrong.
        if len(buf) > 1024 * 1024:  # 1MB
            chunks.append(buf)
            break

    return b"".join(chunks)


def _wrap_client_ssl(
    raw_sock: socket.socket,
    host: str,
    config_path: str | None,
) -> socket.socket:
    """
    Optionally wrap a connected socket with TLS based on config settings.
    If no config or ssl_enabled=False, returns the raw socket unchanged.
    """
    if not config_path:
        return raw_sock

    try:
        cfg = load_config(config_path)
    except ConfigError as exc:
        raise SystemExit(f"Config error: {exc}") from exc

    if not cfg.ssl_enabled:
        return raw_sock

    if cfg.ssl_verify:
        ctx = ssl.create_default_context(purpose=ssl.Purpose.SERVER_AUTH)

        # For self-signed cert verification, a CA file is required.
        if cfg.ssl_cafile is not None:
            ctx.load_verify_locations(cafile=str(cfg.ssl_cafile))

        # NOTE:
        # - If your cert includes SAN for host/IP, hostname checking will work.
        # - If not, verification can fail with "hostname mismatch".
        # We leave default check_hostname=True when ssl_verify=True.
    else:
        # For local encryption only (no server identity verification)
        ctx = ssl._create_unverified_context()

    return ctx.wrap_socket(raw_sock, server_hostname=host)


def _die(msg: str, code: int = 2) -> "None":
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def main() -> None:
    args = parse_args()
    query_line = args.query + "\n"

    try:
        with socket.create_connection(
            (args.host, args.port),
            timeout=RECV_TIMEOUT_SECONDS,
        ) as raw_sock:
            raw_sock.settimeout(RECV_TIMEOUT_SECONDS)

            # Optional: wrap in TLS if config enables it
            sock = _wrap_client_ssl(raw_sock, args.host, args.config)

            sock.sendall(query_line.encode("utf-8"))

            # Read just one response (debug + result), then exit cleanly.
            response = recv_until_result(sock)

        print(response.decode("utf-8", errors="replace"), end="")

    except ConnectionResetError:
        # Common when server expects TLS but client spoke plain TCP.
        if not args.config:
            _die(
                "Connection reset by server.\n"
                "This often means the server has SSL/TLS enabled "
                "but you ran the client without --config.\n\n"
                "Try:\n"
                f"  python3 -m client --host {args.host} --port {args.port} "
                f"--config app.conf {args.query!r}\n"
            )
        _die(
            "Connection reset by server. "
            "Check server status and SSL settings in your config."
        )

    except ssl.SSLError as exc:
        """
        e.g. WRONG_VERSION_NUMBER, CERTIFICATE_VERIFY_FAILED,
            hostname mismatch
        """
        _die(
            "SSL/TLS handshake failed.\n"
            f"Reason: {exc}\n\n"
            "If using a self-signed certificate, ensure config includes:\n"
            "  ssl_enabled=True\n"
            "  ssl_verify=True\n"
            "  ssl_cafile=certs/server.crt\n\n"
            "If you want local-only encryption without verification, set:\n"
            "  ssl_verify=False\n"
        )

    except TimeoutError as exc:
        _die(f"Timeout: {exc}")

    except socket.timeout:
        _die(
            "Timeout: no complete response received.\n"
            "Check server reachability and whether SSL settings match."
        )

    except OSError as exc:
        _die(f"Network error: {exc}")


if __name__ == "__main__":
    main()
