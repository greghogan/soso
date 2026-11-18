"""Audit generated PDFs for one-letter hyphen fragments; requires PyMuPDF."""
from pathlib import Path
import json,re
from .build_catalog import discover, editions
import argparse
ROOT=Path(__file__).resolve().parents[2]
def audit(path):
 import fitz
 doc=fitz.open(path);issues=[]
 for number,page in enumerate(doc,1):
  lines=page.get_text().splitlines()
  for a,b in zip(lines,lines[1:]):
   # A word ending in a hyphen followed by a single-letter terminal fragment.
   # Excludes capital math variables and genuine a-/x- style compound prefixes.
   if re.search(r'[A-Za-z]{3,}[-‐]$',a) and re.match(r'^[a-z](?:[.,;:!?)]|\s)',b):
    issues.append({'page':number,'before':a,'after':b})
 return {'pages':len(doc),'one_letter_terminal_fragments':issues}
def pdf_paths(root):
 return sorted({Path(root)/event['path']/ed['pdf']
  for event in discover(root) for ed in editions(root,event).values() if 'pdf' in ed})
def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--root',type=Path,default=ROOT/'build/candidates',help='Generated candidate or site root (default: build/candidates)')
 root=parser.parse_args().root.resolve()
 result={str(p.relative_to(root)):audit(p) for p in pdf_paths(root)}
 print(json.dumps(result,indent=2))
 raise SystemExit(any(x['one_letter_terminal_fragments'] for x in result.values()))

if __name__ == '__main__':
 main()
