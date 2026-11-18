#!/usr/bin/env python3
"""Regression checks for lossy HTML/TeX conversion and canonical prose coverage."""
import json,re,html,unicodedata,importlib.util
from pathlib import Path
from html.parser import HTMLParser
import fitz
R=Path(__file__).resolve().parent.parent
import sys
sys.path.insert(0,str(R.parents[2]/'shared'))
from build_paths import event_output
OUT=event_output(R)
spec=importlib.util.spec_from_file_location('print_builder',R/'source/build_study.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
# Regression: a permissive <...> HTML regex used to delete scientific inequalities.
probe='Q < K favors net forward change; Q > K favors reverse change.'
assert 'Q < K favors net forward change; Q > K' in mod.tx(probe)
for glyph,tex in [('≤',r'\le'),('≥',r'\ge'),('−','-'),('∝',r'\propto')]:assert tex in mod.tx(glyph)
for text in ['λ','π','Δ','σ','ε','Q < K','Q > K']:assert text in mod.tx(text)
assert 'k_B' in mod.tx('PV = nRT = N k_B T')
class Text(HTMLParser):
 def __init__(self,s):super().__init__();self.parts=[];self.feed(s)
 def handle_data(self,d):self.parts.append(d)
def unmark(s):return re.sub(r'</?(?:i|b|em|strong|sub|sup)>|<br\s*/?>',' ',s)
def norm(s):
 s=unicodedata.normalize('NFKC',html.unescape(unmark(s))).lower()
 return ''.join(c for c in s if c.isalnum())
lessons=json.loads((R/'source/lessons.json').read_text());web=' '.join(Text((OUT/'web/index.html').read_text()).parts);pdf='\n'.join('\n'.join(b[4] for b in p.get_text('blocks') if b[1]<760) for p in fitz.open(OUT/'study-guide.pdf'))
texts={'web':norm(web),'pdf':norm(pdf)};missing={k:[] for k in texts}
# Each panel is compared phrase-by-phrase because PDF column extraction interleaves text.
for d in lessons:
 for title,body in d['panels']:
  words=unmark(body).split()
  for i in range(0,len(words),8):
   phrase=' '.join(words[i:i+8]);needle=norm(phrase)
   if len(needle)<12:continue
   for kind,haystack in texts.items():
    if needle not in haystack:missing[kind].append({'lesson':d['id'],'phrase':phrase})
report={'lessons':len(lessons),'inequality_converter_regression':'passed','canonical_panel_phrase_mismatches':missing,'pdf_inequality_context':'Q < K favors net forward change' in re.sub(r'\s+',' ',pdf) and 'Q > K favors reverse change' in re.sub(r'\s+',' ',pdf)}
qa=OUT/'research/qa';qa.mkdir(parents=True,exist_ok=True)
(qa/'content-parity.json').write_text(json.dumps(report,ensure_ascii=False,indent=2));print(json.dumps(report,ensure_ascii=False,indent=2))
assert not missing['web'] and not missing['pdf'], 'Canonical panel prose lost during rendering'
assert report['pdf_inequality_context'], 'Chemical equilibrium inequalities missing in extracted PDF text'
