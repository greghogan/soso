#!/usr/bin/env python3
"""Compare actual candidate PDFs with approved sources without promoting either."""
import argparse,hashlib,json
from pathlib import Path
import fitz

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def compare(approved,candidate):
    a=fitz.open(approved);b=fitz.open(candidate)
    text=[];pixels=[]
    for i in range(min(len(a),len(b))):
        if a[i].get_text()!=b[i].get_text():text.append(i+1)
        pa=a[i].get_pixmap(matrix=fitz.Matrix(2,2),alpha=False)
        pb=b[i].get_pixmap(matrix=fitz.Matrix(2,2),alpha=False)
        if (pa.width,pa.height,pa.n,pa.samples)!=(pb.width,pb.height,pb.n,pb.samples):pixels.append(i+1)
    return {'approved_pages':len(a),'candidate_pages':len(b),'approved_sha256':sha(approved),'candidate_sha256':sha(candidate),'byte_identical':sha(approved)==sha(candidate),'text_changed_pages':text,'pixel_changed_pages_144dpi':pixels,'same_page_count':len(a)==len(b),'visual_text_identical':len(a)==len(b) and not text and not pixels,'approved_metadata':a.metadata,'candidate_metadata':b.metadata}
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--approved-source',type=Path,required=True);p.add_argument('--candidates',type=Path,required=True);p.add_argument('--report',type=Path,required=True);args=p.parse_args()
    report=json.loads((args.candidates/'build-report.json').read_text())
    entries=report.get('events')
    paths=([Path(event['path'])/name for event in entries for name in event['pdfs']]
           if entries is not None else sorted(p.relative_to(args.candidates) for p in (args.candidates/'events').glob('*/*/*.pdf')))
    out={str(path):compare(args.approved_source/path,args.candidates/path) for path in paths if (args.approved_source/path).is_file()}
    out_new=[str(path) for path in paths if not (args.approved_source/path).is_file()]
    if out_new:print('New documents without an approved baseline: '+', '.join(out_new))
    args.report.parent.mkdir(parents=True,exist_ok=True);args.report.write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:{'pages':v['candidate_pages'],'visual_text_identical':v['visual_text_identical'],'text_changed_pages':v['text_changed_pages'],'pixel_changed_pages_144dpi':v['pixel_changed_pages_144dpi']} for k,v in out.items()},indent=2))
if __name__=='__main__':main()
