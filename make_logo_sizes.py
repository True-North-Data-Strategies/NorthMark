#!/usr/bin/env python3
"""Generate logo sizes and brand kits. See README.md for setup and examples."""

import sys

try:
    from northmark.cli import main
except ImportError as exc:
    sys.exit(f'Cannot start: {exc}. Install the dependencies with: pip install -r requirements.txt')

if __name__ == "__main__":
    raise SystemExit(main())
