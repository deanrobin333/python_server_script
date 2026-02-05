#!/usr/bin/python3
# __main__.py

from __future__ import annotations

from .server import main

"""
- defines how the package behaves when it is executed, not imported.
- In other words, it answers:
	- “What should happen when someone runs
	    python -m python_server_script ?”
"""

if __name__ == "__main__":
    main()
