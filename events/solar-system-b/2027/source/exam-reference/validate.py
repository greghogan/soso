#!/usr/bin/env python3
"""Structural and source-preservation checks; visual review is still required."""
import json, re, sys
from pathlib import Path
from pypdf import PdfReader
from export_tex import D, rich
R=Path(__file__).resolve().parent
PROJECT=R.parents[4]
sys.path.insert(0,str(PROJECT/'shared'))
from build_paths import event_output
OUTPUT=event_output(R.parents[1])/'build/exam-reference'
sys.path.insert(0,str(PROJECT))
from soso.site.event_registry import load, reference_page_limit, validate_reference_page_size
event=next(e for e in load(PROJECT) if e['path']==R.parents[1].relative_to(PROJECT).as_posix())
page_limit=reference_page_limit(event)
import argparse
ap=argparse.ArgumentParser()
ap.add_argument('--tex',type=Path,default=OUTPUT/'exam-reference.tex')
ap.add_argument('--pdf',type=Path,default=OUTPUT/'exam-reference.pdf')
ap.add_argument('--report',type=Path,default=OUTPUT/'layout-check.json')
args=ap.parse_args()
tex=args.tex.read_text()
assert len(D['page1']['worlds'])==9 and len(D['page1']['systems'])==3
assert sum(map(len,D['page3']['missions']))==16
# Check all source strings, except titles formatted as plain text and formula
# strings represented by the explicitly reviewed native math equivalents.
count=0
def check(s):
    global count
    assert rich(s) in tex,s
    count+=1
for p in range(1,5):
    d=D[f'page{p}'];check(d['subtitle'])
    if p==1:
        for row in d['worlds']+d['systems']:
            for s in row:check(s)
        check(d['end'])
    if p==3:
        for col in d['missions']:
            for m in col:
                for key in ['name','status','text']:check(m[key])
    if p in [2,3,4]:
        for col in d['columns']:
            for block in col:
                for s in block['items']:check(s)
r=PdfReader(args.pdf)
assert page_limit is not None, 'Solar reference requires a finite verified allowance'
assert len(r.pages)==page_limit, f'Expected {page_limit} PDF pages for the full team allowance; got {len(r.pages)}'
for i,p in enumerate(r.pages,1):
    validate_reference_page_size(event,p.mediabox.width,p.mediabox.height)
    assert len(p.extract_text())>1500
links=[a.get_object()['/A']['/URI'] for a in r.pages[2]['/Annots'] if '/A' in a.get_object() and '/URI' in a.get_object()['/A']]
credit_links={'https://github.com/greghogan/soso', 'https://creativecommons.org/licenses/by/4.0/', 'https://github.com/greghogan/soso/blob/main/LICENSE.md'}
assert credit_links.issubset(set(links))
links=[link for link in links if link not in credit_links]
assert len(links)==3
result={'pages':len(r.pages),'reference_page_limit':page_limit,'page_size':event['reference_constraints']['paper_size'],'canonical_source_strings_checked':count,'worlds':9,'systems':3,'missions':16,'status_links':links,'pdf_bytes':args.pdf.stat().st_size}
args.report.parent.mkdir(parents=True,exist_ok=True)
args.report.write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
