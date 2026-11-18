#!/usr/bin/env python3
"""Run the SOSO package distributions command."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from soso.site.package_distributions import main

if __name__ == "__main__":
    main()
