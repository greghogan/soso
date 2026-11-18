#!/usr/bin/env -S uv run --locked
"""Run the SOSO asset fetch command."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from soso.assets.asset_fetch import main

if __name__ == "__main__":
    main()
