#!/usr/bin/env python3
"""Check that every explanation link resolves to its own answer, not a stale heading."""
from pathlib import Path
import json,re,unicodedata
import fitz
R=Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0,str(R.parents[2]/'shared'))
from build_paths import event_output
OUT=event_output(R)
D=fitz.open(OUT/'study-guide.pdf');lessons=json.loads((R/'source/lessons.json').read_text());by={d['id']:d for d in lessons}
def norm(s):return ''.join(c for c in unicodedata.normalize('NFKC',s).lower() if c.isalnum())
forward={};back={};issues=[]
for i,p in enumerate(D):
 for l in p.get_links():
  name=l.get('nameddest','')
  if name.startswith('answer:'):forward[name[7:]]=l
  if name.startswith('lesson:'):back[name[7:]]=l
for id,d in by.items():
 if id not in forward:issues.append('Missing forward: '+id);continue
 link=forward[id];page=link.get('page',-1)
 if page<0 or page>=len(D):issues.append('Invalid forward target: '+id);continue
 needle=norm(' '.join(d['answer'].split()[:8]))
 if needle not in norm(D[page].get_text()):issues.append('Wrong answer page: '+id)
 if id not in back:issues.append('Missing return: '+id)
 else:
  page=back[id].get('page',-1);needle=norm(' '.join(d['deck'].split()[:8]))
  if page<0 or needle not in norm(D[page].get_text()):issues.append('Wrong lesson return: '+id)
report={'forward_answer_links':len(forward),'return_lesson_links':len(back),'issues':issues}
qa=OUT/'research/qa';qa.mkdir(parents=True,exist_ok=True)
(qa/'pdf-link-destinations.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2));assert not issues
