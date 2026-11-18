"""Keep direct event outputs separate from authored sources."""
import os
from pathlib import Path


def event_output(event):
    """An isolated Docker stage may retain its historical internal layout."""
    if override := os.environ.get('SOSO_EVENT_OUTPUT_DIR'):
        return Path(override).resolve()
    if os.environ.get('SOSO_STAGE_OUTPUTS') == '1':
        return event
    series = event.parents[2]
    return series / 'build/direct' / event.relative_to(series)
