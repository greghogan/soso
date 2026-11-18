#!/usr/bin/env python3
"""Separate portable reader bundle from editable development source."""
from pathlib import Path
import sys
import re,shutil,json,zipfile,hashlib
from html.parser import HTMLParser
EVENT=Path(__file__).resolve().parent.parent
SERIES=EVENT.parents[2]
sys.path.insert(0,str(SERIES/'shared'))
from build_paths import event_output
R=event_output(EVENT);OUT=SERIES/'build/releases';OUT.mkdir(parents=True,exist_ok=True)
D=OUT/'solar-system-b-2027';D.mkdir(exist_ok=True)
for p in ['index.html','style.css','guide.js']:shutil.copy2(R/'web'/p,D/p)
s=(D/'index.html').read_text().replace('<section class="intro">','<section class="intro"><p class="reading-links"><a href="study-guide.pdf">Open the printable study guide</a></p>');(D/'index.html').write_text(s)
class Refs(HTMLParser):
 def __init__(self,s):super().__init__();self.refs=[];self.ids=[];self.feed(s)
 def handle_starttag(self,t,a):
  a=dict(a)
  if 'id' in a:self.ids.append(a['id'])
  for k in ['src','href']:
   if k in a:self.refs.append(a[k])
p=Refs(s);assets={x.partition('#')[0] for x in p.refs if x.startswith('assets/')}
assets.update(re.findall(r"url\(['\"]?(assets/[^)'\"]+)",(D/'style.css').read_text()))
for file in assets:
 dest=D/file;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(R/'web'/file,dest)
shutil.copy2(R/'study-guide.pdf',D/'study-guide.pdf')
(D/'README.txt').write_text('Solar System B 2027 — portable study guide\n\nExtract this ZIP first. Open index.html in a current browser. Keep the extracted folder together. No installation, server, account or internet connection is required for the guide. Optional bibliography links need internet access. study-guide.pdf is the printable edition.\n\nAll text, images, diagrams, CSS and JavaScript are included locally. This release uses original interactive models rather than streaming video. Native answer disclosures work without JavaScript; interactive sliders require it.\n\nTested through a local HTTP preview. Direct file:// opening could not be exercised in the browser QA tool (HTTP/S-only policy); dependencies and relative links were checked independently.\n\nThis is independent study material, not an official Science Olympiad publication. Use the official rules and tournament clarifications for competition requirements. See ATTRIBUTION.txt for media notes. Editable sources and prompts are supplied separately, not needed by readers.\n')
(D/'ATTRIBUTION.txt').write_text('Media provenance\n\nThe artistic world/interior montages were generated for this guide and revised after scientific review. They are conceptual illustrations, not NASA photographs or observational evidence. Captions state relevant limitations.\n\nThe teaching diagrams and interactive models were authored for this guide from the relationships and evidence cited in the lesson bibliography. SVG/PDF diagrams simplify mechanisms; they are not spacecraft observations.\n\nNo externally streamed video, third-party webfont, CDN library or external image download is required. The full authoring package preserves prompts, original assets, source notes and diagram generators.\n')
# Validate every local reference in the relocated root, then again after ZIP extraction.
for ref in p.refs:
 if ref.startswith(('https:','http:','mailto:')):continue
 file,_,anchor=ref.partition('#')
 assert not file or (D/file).exists(),ref
 if anchor:assert anchor in p.ids,ref
manifest={str(f.relative_to(D)):hashlib.sha256(f.read_bytes()).hexdigest() for f in D.rglob('*') if f.is_file() and f.name!='MANIFEST.json'}
(D/'MANIFEST.json').write_text(json.dumps(manifest,indent=2)+'\n')
zip_path=OUT/'solar-system-b-2027-portable.zip'
with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
 for f in D.rglob('*'):
  if f.is_file():z.write(f,f.relative_to(D))
verify=OUT/'verify-solar';verify.mkdir(exist_ok=True)
with zipfile.ZipFile(zip_path) as z:z.extractall(verify)
for path,digest in manifest.items():assert hashlib.sha256((verify/path).read_bytes()).hexdigest()==digest
print(zip_path,zip_path.stat().st_size)
