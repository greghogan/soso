"""Locate shared DejaVu faces in the build image or the bundled fallback."""
from pathlib import Path

SYSTEM = Path('/usr/share/fonts/truetype/dejavu')
BUNDLED = Path(__file__).resolve().with_name('fonts')


def dejavu_font(filename):
    installed = SYSTEM / filename
    return str(installed if installed.is_file() else BUNDLED / filename)
