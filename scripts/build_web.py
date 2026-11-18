#!/usr/bin/env python3
"""Run the SOSO build web command."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from soso.site.build_web import main

if __name__ == "__main__":
    main()
