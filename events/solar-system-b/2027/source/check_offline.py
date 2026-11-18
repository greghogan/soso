from pathlib import Path
from html.parser import HTMLParser
import json,re
R=Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0,str(R.parents[2]/'shared'))
from build_paths import event_output
OUT=event_output(R)
R=OUT/'web'
class Page(HTMLParser):
 def __init__(self,p):
  super().__init__();self.ids=[];self.refs=[];self.lessons=0;self.feed(p.read_text())
 def handle_starttag(self,t,a):
  a=dict(a)
  if 'id'in a:self.ids.append(a['id'])
  for key in ['href','src']:
   if key in a:self.refs.append((t,key,a[key]))
  if t=='article' and a.get('class')=='lesson':self.lessons+=1
report={}
for f in ['index.html','sample.html']:
 p=Page(R/f);bad=[];external=[]
 for tag,k,ref in p.refs:
  if ref.startswith(('http:','https:','mailto:')):
   if k=='src' or tag=='link':external.append(ref)
   continue
  file,_,frag=ref.partition('#');target=R/file if file else R/f
  if not target.exists():bad.append(ref);continue
  if frag:
   q=Page(target)
   if frag not in q.ids:bad.append(ref)
 report[f]={'lessons':p.lessons,'duplicate_ids':len(p.ids)-len(set(p.ids)),'broken_references':bad,'remote_runtime_dependencies':external}
assert report['index.html']['lessons']==77
assert all(not v['broken_references'] and not v['duplicate_ids'] and not v['remote_runtime_dependencies'] for v in report.values())
qa=OUT/'research/qa';qa.mkdir(parents=True,exist_ok=True)
(qa/'offline-structural.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))
