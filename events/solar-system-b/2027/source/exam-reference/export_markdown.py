#!/usr/bin/env python3
"""Export canonical exam-reference JSON as human-readable Markdown."""
from pathlib import Path
import html,json,re,sys
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT.parents[4]/'shared'))
from build_paths import event_output

def plain(value):
    value=re.sub(r'<sub>(.*?)</sub>',r'_{\1}',value)
    value=re.sub(r'<super>(.*?)</super>',r'^{\1}',value)
    return html.unescape(re.sub('<[^>]+>','',value.replace('<br/>','\n')))

def emit(value,depth=3):
    if isinstance(value,str):return plain(value)+'\n\n'
    if isinstance(value,list):return ''.join(emit(x,depth) for x in value)
    if isinstance(value,dict):
        return ''.join((('#'*depth+' '+key.replace('_',' ').title()+'\n\n') if key not in ['title','items','formula'] else '')+emit(item,min(depth+1,6)) for key,item in value.items())
    raise TypeError(type(value))

def main():
    data=json.loads((ROOT/'content.json').read_text())
    text='# Solar System B 2027: four-page exam reference\n\nGenerated human-readable export of canonical `content.json`, revised 15 November 2026. Edit that JSON and run `build.py` to create a separate typeset candidate; do not edit this export independently.\n\n'
    for key,value in data.items():text+='## Page '+key.removeprefix('page')+'\n\n'+emit(value)
    output=event_output(ROOT.parents[1])/'build/exam-reference/content.md'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(text)
    print('Exported canonical text:', output)
if __name__=='__main__':main()
