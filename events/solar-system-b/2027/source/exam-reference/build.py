#!/usr/bin/env python3
"""Build a validated candidate without replacing the approved exam reference."""
import argparse
from pathlib import Path
import re
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
EVENT = HERE.parents[1]
ROOT = EVENT.parents[2]
sys.path.insert(0, str(ROOT / 'shared'))
from build_paths import event_output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=event_output(EVENT)/'build/exam-reference')
    args = parser.parse_args()
    output = args.output_dir.resolve()
    if output/'exam-reference.pdf' == (EVENT/'exam-reference.pdf').resolve():
        parser.error('Use a candidate directory; preserve the approved exam-reference.pdf.')
    engine = shutil.which('xelatex')
    if not engine:
        parser.exit(1, 'XeLaTeX is required. See source/exam-reference/README.md for dependencies.\n')
    output.mkdir(parents=True, exist_ok=True)
    tex = output/'exam-reference.tex'
    subprocess.run([sys.executable, str(HERE/'export_tex.py'), '--output', str(tex)], check=True)
    for run in (1, 2):
        result = subprocess.run([engine, '-no-shell-escape', '-interaction=nonstopmode', '-halt-on-error',
                                 '-output-directory='+str(output), str(tex)], cwd=output,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        (output/f'build-{run}.log').write_text(result.stdout)
        if result.returncode:
            parser.exit(1, f'XeLaTeX failed; inspect {output}/build-{run}.log\n')
    if re.search(r'Overfull|Missing character|LaTeX Font Warning', result.stdout):
        parser.exit(1, f'Typesetting warnings require review: {output}/build-2.log\n')
    subprocess.run([sys.executable, str(HERE/'validate.py'), '--tex', str(tex),
                    '--pdf', str(output/'exam-reference.pdf'), '--report', str(output/'layout-check.json')], check=True)
    print('Candidate:', output/'exam-reference.pdf')
    print('Approved exam-reference.pdf was preserved; review the candidate before promotion.')


if __name__ == '__main__':
    main()
