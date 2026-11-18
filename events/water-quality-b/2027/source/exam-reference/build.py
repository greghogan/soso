#!/usr/bin/env python3
"""Build the independently authored Water Quality retrieval reference."""
from pathlib import Path
import json, os, re, shutil, subprocess, sys
from pypdf import PdfReader

HERE = Path(__file__).resolve().parent
EVENT = HERE.parents[1]
ROOT = EVENT.parents[2]
sys.path.insert(0, str(ROOT / 'shared'))
from build_paths import event_output
sys.path.insert(0, str(ROOT))
from soso.site.event_registry import load, reference_page_limit, validate_reference_page_size

def main():
    out = event_output(EVENT) / 'build/exam-reference'
    out.mkdir(parents=True, exist_ok=True)
    text = (HERE / 'reference.tex').read_text().replace('@@NOTICE@@', str(ROOT / 'shared/publication-notice.tex'))
    tex = out / 'exam-reference.tex'
    tex.write_text(text)
    engine = shutil.which('xelatex')
    if not engine:
        raise SystemExit('XeLaTeX is required; use the repository Docker build.')
    env = os.environ.copy()
    # Debian stores generated Type 1 font maps outside the isolated TEXMF trees.
    # Preserve the default search while making installed Latin Modern maps visible.
    maps = Path("/var/lib/texmf/fonts/map")
    if maps.is_dir():
        env["TEXFONTMAPS"] = str(maps) + "//:" + env.get("TEXFONTMAPS", "")
    for i in (1, 2):
        result = subprocess.run([engine, '-no-shell-escape', '-interaction=nonstopmode', '-halt-on-error',
                                 '-output-directory=' + str(out), str(tex)], cwd=out,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
        (out / f'build-{i}.log').write_text(result.stdout)
        if result.returncode:
            raise SystemExit(f'XeLaTeX failed: {out}/build-{i}.log')
    if re.search(r'Overfull|Missing character|LaTeX Font Warning|undefined references', result.stdout):
        raise SystemExit(f'Typesetting warning: inspect {out}/build-2.log')
    pdf = out / 'exam-reference.pdf'
    reader = PdfReader(pdf)
    if len(reader.pages) != 2:
        raise ValueError('Two authored reference pages must produce exactly two PDF pages; inspect overflow.')
    event = next(e for e in load(ROOT) if e['path'] == EVENT.relative_to(ROOT).as_posix())
    limit = reference_page_limit(event)
    if limit is not None and len(reader.pages) > limit:
        raise ValueError('Reference exceeds recorded rules allowance.')
    for page in reader.pages:
        validate_reference_page_size(event, float(page.mediabox.width), float(page.mediabox.height))
        if not page.extract_text().strip():
            raise ValueError('Reference contains an empty page.')
    (out / 'layout-check.json').write_text(json.dumps({'pages': len(reader.pages), 'page_limit': limit,
        'status': 'compiled-and-structurally-checked-not-visual-approval'}, indent=2) + '\n')
    print('Built reference candidate:', pdf)

if __name__ == '__main__':
    main()
