#!/usr/bin/python3
"""
Package entry point.

This module defines the behavior when the package is executed as a script
using:

    python3 -m python_server_script

It delegates execution to the server's main() function.
"""

from __future__ import annotations

from .server import main


if __name__ == "__main__":
    main()
