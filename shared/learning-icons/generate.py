from pathlib import Path
import json
root=Path(__file__).resolve().parents[2]
p=root/'shared/learning-icons';p.mkdir(exist_ok=True)
# All geometry uses the same 24-unit grid, rounded 1.7-unit strokes, no text.
icons={
 'think':('Think it through',[
'M 8 16 C 8 13 5 12 5 8 C 5 4 8 2 12 2 C 16 2 19 4 19 8 C 19 12 16 13 16 16 Z',
'M 9 19 L 15 19 M 10 22 L 14 22 M 10 12 L 12 14 L 14 12 M 12 14 L 12 16']),
 'worked':('Worked example',[
'M 3 3 L 10 3 L 10 8 L 3 8 Z M 14 10 L 21 10 L 21 15 L 14 15 Z M 3 17 L 10 17 L 10 22 L 3 22 Z',
'M 10 5 L 17 5 L 17 10 M 16 15 L 16 19 L 10 19']),
 'try':('Try it',[
'M 4 15 L 15 4 L 20 9 L 9 20 L 3 21 Z M 13 6 L 18 11 M 4 15 L 9 20',
'M 15 4 L 17 2 C 18 1 19 1 20 2 L 22 4 C 23 5 23 6 22 7 L 20 9']),
 'review':('Review',[
'M 12 12 C 8 10 5 10 2 11 L 2 21 C 5 20 8 20 12 22 C 16 20 19 20 22 21 L 22 11 C 19 10 16 10 12 12 L 12 22',
'M 5 7 C 6 3 10 1 14 2 C 17 2 19 4 20 7 M 16 6 L 20 7 L 21 3'])}
(p/'geometry.json').write_text(json.dumps(icons,indent=2)+'\n')
# A deliberately small path vocabulary ensures SVG and print are identical.
import re
def tikz(path):
 t=path.split();out=[];i=0
 while i<len(t):
  c=t[i];i+=1
  if c in ('M','L'):
   x,y=t[i:i+2];i+=2;out.append(('' if c=='M' else '-- ')+f'({x},{y})')
  elif c=='C':
   a,b,c,d,e,f=t[i:i+6];i+=6;out.append(f'.. controls ({a},{b}) and ({c},{d}) .. ({e},{f})')
  elif c=='Z':out.append('-- cycle')
  else:raise ValueError(c)
 return ' '.join(out)
macros=['% BEGIN GENERATED LEARNING ICONS: shared/learning-icons/generate.py',r'\newcommand{\cuecanvas}[1]{\tikz[baseline=-1.15em,x=.06em,y=-.06em]{\path[use as bounding box] (0,0) rectangle (24,24);\begin{scope}[line width=.65pt,line cap=round,line join=round]#1\end{scope}}}']
for name,(title,paths) in icons.items():
 (p/(name+'.svg')).write_text('<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" viewBox="0 0 24 24" role="img"><title>'+title+'</title><g fill="none" stroke="#17313c" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">'+''.join('<path d="'+v+'"/>' for v in paths)+'</g></svg>\n')
 macros.append('\\expandafter\\def\\csname cue@'+name+'\\endcsname{\\cuecanvas{'+''.join('\\draw '+tikz(v)+';' for v in paths)+'}}')
for alias,name in [('?','think'),('=','worked'),('>','try'),('R','review')]:macros.append('\\expandafter\\def\\csname cue@'+alias+'\\endcsname{\\csname cue@'+name+'\\endcsname}')
macros += [r'\newcommand{\cueicon}[1]{\csname cue@#1\endcsname}', '% END GENERATED LEARNING ICONS']
style=root/'shared/guide-style.tex';s=style.read_text()
if '% BEGIN GENERATED LEARNING ICONS' in s:s=re.sub(r'% BEGIN GENERATED LEARNING ICONS.*?% END GENERATED LEARNING ICONS',lambda m:'\n'.join(macros),s,flags=re.S)
else:s=re.sub(r'\\newcommand\{\\cueicon\}[^\n]*',lambda m:'\n'.join(macros),s)
style.write_text(s)
