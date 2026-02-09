#!/usr/bin/python3
"""
TCP String Lookup Client.

This client connects to the TCP String Lookup Server, sends a single newline-
terminated query, then reads and prints the server response
(debug line + result line).

TLS is optional. When a config file is provided via --config, the client will
use SSL settings from that file to determine whether to wrap the connection in
TLS and whether to verify the server certificate.
"""

from __future__ import annotations

import argparse
import socket
import ssl
import sys
from typing import List

from config import ConfigError, load_config


RECV_BUFSIZE = 4096  # bytes to request per recv() call
RECV_TIMEOUT_SECONDS = 5.0  # prevent hanging forever if server stalls

RESULT_EXISTS = b"STRING EXISTS\n"
RESULT_NOT_FOUND = b"STRING NOT FOUND\n"


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed command-line arguments.
    """
    parser = argparse.ArgumentParser(description="TCP String Lookup Client")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=44445)
    parser.add_argument(
        "--config",
        required=False,
        help="Optional config file path (used for SSL settings).",
    )
    parser.add_argument(
        "query",
        help="Query string to send (exact full-line match).",
    )
    return parser.parse_args()


def recv_until_result(sock: socket.socket) -> bytes:
    """Receive server output until a result line is observed.

    The server uses a persistent connection and may not close the socket (EOF)
    after responding. This function therefore reads until it detects one of the
    protocol terminators:

    - STRING EXISTS\\n
    - STRING NOT FOUND\\n

    Args:
        sock: Connected socket from which to read.

    Returns:
        Bytes received up to and including the first result terminator, or
        whatever was received before the connection closed or
        a safety limit was reached.
    """
    chunks: List[bytes] = []
    buf = b""

    while True:
        data = sock.recv(RECV_BUFSIZE)
        if not data:
            chunks.append(buf)
            break

        buf += data

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
    """Optionally wrap a connected socket with TLS based on config settings.

    If no config is provided, or if ssl_enabled=False in the config, this
    function returns the connected socket unchanged.

    When ssl_enabled=True:
    - If ssl_verify=True, the client uses a default verification context and
      optionally loads a CA file to trust a self-signed server certificate.
    - If ssl_verify=False, the client uses an unverified context for local-only
      encryption without server identity verification.

    Args:
        raw_sock: Connected TCP socket.
        host: Hostname/IP used for SNI and (when verifying) hostname checks.
        config_path: Path to the config file providing SSL settings.

    Returns:
        A TLS-wrapped socket if SSL is enabled, otherwise the original socket.

    Raises:
        SystemExit: If the config cannot be loaded.
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

        # For self-signed certificate verification, a CA file is required.
        if cfg.ssl_cafile is not None:
            ctx.load_verify_locations(cafile=str(cfg.ssl_cafile))

        # When ssl_verify=True, we keep the default check_hostname=True.
        # Verification may fail if the server cert SAN does not match `host`.
    else:
        # Local-only encryption without server identity verification.
        ctx = ssl._create_unverified_context()

    return ctx.wrap_socket(raw_sock, server_hostname=host)


def _die(msg: str, code: int = 2) -> "None":
    """Print an error message and exit.

    Args:
        msg: Message to print to stderr.
        code: Exit code.

    Raises:
        SystemExit: Always, with the given exit code.
    """
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def main() -> None:
    """Run the client entry point."""
    args = parse_args()
    query_line = args.query + "\n"

    try:
        with socket.create_connection(
            (args.host, args.port),
            timeout=RECV_TIMEOUT_SECONDS,
        ) as raw_sock:
            raw_sock.settimeout(RECV_TIMEOUT_SECONDS)

            sock = _wrap_client_ssl(raw_sock, args.host, args.config)

            sock.sendall(query_line.encode("utf-8"))

            # Read one response (debug + result), then exit cleanly.
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
        """Handle common TLS handshake errors."""
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
