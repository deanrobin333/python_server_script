#!/usr/bin/python3
# client.py

from __future__ import annotations

import argparse
import socket
from typing import List


RECV_BUFSIZE = 4096
RECV_TIMEOUT_SECONDS = 5.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="TCP String Lookup Client"
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=44445)
    parser.add_argument(
        "query",
        help="Query string to send (exact full-line match)",
    )
    return parser.parse_args()


def recv_all_with_timeout(sock: socket.socket) -> bytes:
    """
    Receive all data from the socket until EOF or timeout.

    Timeout behavior:
    - If no data is ever received -> raise TimeoutError
    - If some data is received, then a timeout occurs -> return what we have
    """
    chunks: List[bytes] = []

    while True:
        try:
            data = sock.recv(RECV_BUFSIZE)
            if not data:
                # Server closed connection (EOF)
                break
            chunks.append(data)
        except socket.timeout:
            if not chunks:
                raise TimeoutError(
                    "Timed out waiting for server response"
                )
            break

    return b"".join(chunks)


def main() -> None:
    args = parse_args()
    query_line = args.query + "\n"

    with socket.create_connection(
        (args.host, args.port),
        timeout=RECV_TIMEOUT_SECONDS,
    ) as sock:
        # Apply timeout to recv/send operations
        sock.settimeout(RECV_TIMEOUT_SECONDS)

        # Send query
        sock.sendall(query_line.encode("utf-8"))

        # Receive full response
        response = recv_all_with_timeout(sock)

    print(response.decode("utf-8", errors="replace"), end="")


if __name__ == "__main__":
    main()
