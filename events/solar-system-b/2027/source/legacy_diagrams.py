"""Regenerate wide Solar System B figures and print-only equation variants."""
import importlib.util
import json
from pathlib import Path
import sys

from reportlab.pdfgen import canvas

SRC = Path(__file__).resolve().parent
EVENT = SRC.parent
sys.path.insert(0, str(EVENT.parents[2] / 'shared'))
from build_paths import event_output

DIAGRAMS = event_output(EVENT) / 'build/diagrams'
LEGACY_IDS = {
    'foundation-4', 'foundation-5', 'foundation-6', 'foundation-8',
    'foundation-10', 'foundation-12', 'foundation-13', 'foundation-14',
    'detection-microlensing', 'detection-imaging', 'trappist_system',
    'math01', 'math04', 'math05', 'math06', 'math07', 'math08', 'math09',
    'math10', 'math11', 'math12', 'math13', 'math14',
}
PRINT_IDS = {'math01', 'math07', 'math08', 'math10', 'math12'}


def _load_diagram_source():
    # An isolated module lets the print variant adjust drawing behavior without
    # mutating the standard renderer or sharing its QA warnings.
    spec = importlib.util.spec_from_file_location('diagrams_light', SRC / 'diagrams_light.py')
    diagrams = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(diagrams)
    return diagrams


def _render(diagrams, target, selected):
    target.mkdir(parents=True, exist_ok=True)
    for lesson in json.loads((SRC / 'lessons.json').read_text()):
        if lesson['id'] not in selected:
            continue
        height = diagrams.design_height(lesson)
        file = target / (lesson['id'] + '.pdf')
        page = canvas.Canvas(str(file), pagesize=(516, height))
        diagrams.draw_diagram(page, lesson, 0, 0, 516, height)
        page.save()


def export_legacy():
    diagrams = _load_diagram_source()
    _render(diagrams, DIAGRAMS / 'vector-original', LEGACY_IDS)
    warnings = DIAGRAMS / 'diagram-layout-warnings.json'
    if diagrams.LAYOUT_WARNINGS:
        warnings.write_text(json.dumps(diagrams.LAYOUT_WARNINGS, indent=2))
    else:
        warnings.unlink(missing_ok=True)
    return LEGACY_IDS


def export_print_equations():
    """Create the unboxed equation figures without changing their scientific labels."""
    diagrams = _load_diagram_source()
    original_rect = diagrams.Figure.rect

    def editorial_rect(self, x, y, w, h, fill=diagrams.PANEL, stroke=diagrams.LINE, r=5, width=.6):
        if fill not in (diagrams.PANEL, diagrams.PANEL2):
            # Omit decorative card backgrounds, not parts of a scientific shape.
            return original_rect(self, x, y, w, h, fill, stroke, r, width)

    diagrams.Figure.rect = editorial_rect
    _render(diagrams, DIAGRAMS / 'print-layout-v1', PRINT_IDS)


if __name__ == '__main__':
    export_legacy()
    export_print_equations()
