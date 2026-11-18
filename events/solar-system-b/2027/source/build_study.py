#!/usr/bin/env python3
"""Build an illustrated, reflowable XeLaTeX study guide from editable JSON.
Artwork masters retain their original pixels in lossless JPEG XL storage.
"""
import json,re,html,sys,subprocess,shutil,unicodedata,os,tempfile
from PIL import Image
import fitz
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
SERIES=ROOT.parents[2]
sys.path.insert(0,str(SERIES/'shared'))
from math_notation import protect_notation, restore_notation
from raster_assets import decoded_asset
from build_paths import event_output
from diagrams.draw_diagrams import generate as generate_compact_diagrams
from legacy_diagrams import DIAGRAMS, export_legacy, export_print_equations
OUT=event_output(ROOT)
COMPACT=OUT/'build/diagrams/compact'
SRC=ROOT/'source'; BUILD=(SRC if OUT == ROOT else OUT)/'build'; BUILD.mkdir(parents=True,exist_ok=True)
LESSONS=json.loads((SRC/'lessons.json').read_text())
REG=json.loads((SRC/'source-registry.json').read_text())
# TeX math replaces ambiguous compatibility superscripts in authored source.
MATH={
 'PV = nRT = NkᴮT':r'\(PV=nRT=Nk_B T\)',
 'PV = nRT = N k_B T':r'\(PV=nRT=Nk_B T\)',
 'R = N_A k_B':r'\(R=N_Ak_B\)',
 'R = Nᴬkᴮ':r'\(R=N_Ak_B\)',
 'T = [(1 − A)F/(4εσ)]¹/⁴':r'\(T=\left[\dfrac{(1-A)F}{4\varepsilon\sigma}\right]^{1/4}\)',
 'T ∝ L¹/⁴r⁻¹/²':r'\(T\propto L^{1/4}r^{-1/2}\)',
 '(1 − A)FπR²':r'\((1-A)F\pi R^2\)',
 '4πR²εσT⁴':r'\(4\pi R^2\varepsilon\sigma T^4\)',
 'πR²':r'\(\pi R^2\)',
}
def tx(s):
 s=str(s).replace('Ganymede:Europa:Io','Ganymede : Europa : Io').replace('67P/Churyumov','67P / Churyumov').replace('\u2011','-').replace('\u2013','--').replace('\u2014','; ')
 toks={}
 for old,new in MATH.items():
  if old in s:
   key=f'ZZMATH{len(toks)}ZZ';s=s.replace(old,key);toks[key]=new
 s,notation=protect_notation(s,'latex')
 s=html.unescape(s)
 # Convert author-controlled simple emphasis only.
 s=s.replace('<br/>','\n').replace('<br>','\n')
 s=s.replace('<i>','ZZITALICOPENZZ').replace('</i>','ZZCLOSEZZ').replace('<b>','ZZBOLDOPENZZ').replace('</b>','ZZCLOSEZZ')
 # Do not strip angle-bracket expressions: Q < K and Q > K are scientific content.
 s=s.replace('\\',r'\textbackslash{}')
 for a,b in [('&',r'\&'),('%',r'\%'),('$',r'\$'),('#',r'\#'),('_',r'\_'),('{',r'\{'),('}',r'\}')]:s=s.replace(a,b)
 s=s.replace('ZZITALICOPENZZ',r'\emph{').replace('ZZBOLDOPENZZ',r'\textbf{').replace('ZZCLOSEZZ','}')
 # Math symbols absent from the text face are set as math.
 for a,b in [('∝',r'\(\propto\)'),('≠',r'\(\ne\)'),('≈',r'\(\approx\)'),('≤',r'\(\le\)'),('≥',r'\(\ge\)'),('−','-'),('→',r'\(\to\)'),('↔',r'\(\leftrightarrow\)'),('꜀','c'),('√',r'\(\surd\)')]:s=s.replace(a,b)
 s=re.sub('[₀₁₂₃₄₅₆₇₈₉]+', lambda m: r'\textsubscript{'+m[0].translate(str.maketrans('₀₁₂₃₄₅₆₇₈₉','0123456789'))+'}', s)
 for key,value in toks.items():s=s.replace(key,value)
 s=restore_notation(s,notation)
 return s.replace('\n\n','\n\n').replace('“','``').replace('”',"''")
def para(s):return tx(s)+'\n\n'
def tex_image(path):
 path=decoded_asset(path,ART_CACHE)
 # XeLaTeX needs PNG; decode lossless masters only for this build.
 if path.suffix != '.webp':return path
 target=ART_CACHE/(path.parent.name+'-'+path.stem+'.png')
 if not target.exists():
  with Image.open(path) as artwork:artwork.save(target,'PNG')
 return target

def image(path,width=r'\linewidth',bottom_trim=0,right_trim=0,top_trim=0):
 path=tex_image(path)
 options=f',trim=0 {bottom_trim}bp {right_trim}bp {top_trim}bp,clip' if any((bottom_trim,right_trim,top_trim)) else ''
 if right_trim:options+=',height=260pt,keepaspectratio'
 return r'\includegraphics[width='+width+options+']{'+path.as_posix()+'}\n'

def cover():
 art=tex_image(ROOT/'assets/illustrations/overview.jxl')
 return r'''\begin{titlepage}\thispagestyle{empty}
\begin{tikzpicture}[remember picture,overlay]
\node[anchor=center,inner sep=0] at (current page.center) {\includegraphics[width=\paperwidth,height=\paperheight]{'''+art.as_posix()+r'''}};
\node[anchor=north,inner xsep=18pt,inner ysep=17pt,text width=450pt,align=center] at ([yshift=-29pt]current page.north) {{\color{white}\fontsize{29}{34}\selectfont\bfseries Solar System B}\par\vspace{6pt}{\color{white}\Large Study Guide 2027}\par\vspace{7pt}{\color{white}\normalsize\contour{Navy}{Water, energy, chemistry, and the search for habitable worlds}}};
\node[anchor=south,inner sep=16pt,text width=456pt,align=left,font=\sffamily] at ([yshift=33pt]current page.south) {{\color{white}\large\bfseries Could an ocean beneath ice support life?}\par\vspace{7pt}{\color{white}Water is only one part of the question. Follow the evidence for usable energy, accessible chemistry, and connections between a world's surface and interior.}\par\vspace{9pt}{\color{white}\small How could the ocean exchange material with the ice above and the rock below? Look for evidence of connections, not just water.}};
\end{tikzpicture}\null\end{titlepage}
'''

def heading(d):
 title=d['title'].replace('Comparison: ','').replace('Read motion from shifted light','How shifted light reveals motion')
 return '\\lesson{'+d['id']+'}{'+tx(title)+'}{'+tx(d['deck'])+'}\n'

def panels(d,start=0,stop=None):
 out=''
 for i,(t,b) in enumerate(d['panels'][start:stop],start):
  # Keep a lesson's closing explanation with its application question.
  if i==len(d['panels'])-1:
   keep=min(235,max(105,65+13*(len(b)+len(d.get('question','')))/100))
   out+=r'\Needspace{'+str(round(keep))+'pt}\n'
  content=('\\workedhead{' if t.lower().startswith('worked ') else '\\subhead{')+tx(t)+'}\n'+para(b)
  if t.lower().startswith('worked ') and len(b)<800:
   content=r'\begin{minipage}{\linewidth}'+content+r'\end{minipage}\par'+ '\n'
  out+=content
 return out

def identity(d):
 c=d.get('foundation_context')
 if not c:return ''
 vals=[c['identity']]
 if c.get('diameter_km_rounded') is not None:vals.append(f"diameter about {c['diameter_km_rounded']:,} km")
 if c.get('size_text'):vals.append(c['size_text'])
 vals.append('orbits '+c['direct_orbital_primary'])
 out='\\textbf{At a glance} '+tx('; '.join(vals))+'.\n\n'
 for k in ['solar_distance_note','teaching_value']:
  if c.get(k):out+=para(c[k])
 return out

def comparison(d):
 v=d['visual'];rows=v['rows'];headers=v['headers']
 # Real numerical/object comparison tables stay tables; narrative grids become explanations.
 keep={'foundation-solar-atlas','foundation-moon-atlas','compare_liquids','detection-comparison','data-sketch-practice'}
 if d['id'] in keep:
  n=len(headers);cols=r'>{\RaggedRight\arraybackslash}p{'+('0.18' if n>2 else '.28')+r'\linewidth}'+('Y'*(n-1))
  out=r'\begingroup\small\renewcommand{\arraystretch}{1.22}\begin{tabularx}{\linewidth}{@{}'+cols+r'@{}}\toprule'+'\n'
  out+=' & '.join('\\textbf{'+tx(x)+'}' for x in headers)+r'\\\midrule'+'\n'
  for row in rows:out+=' & '.join(tx(x) for x in row)+r'\\'+'\n'
  out+=r'\bottomrule\end{tabularx}\endgroup\par'+'\n'
 else:
  out=''
  for row in rows:
   out+='\\subhead{'+tx(row[0])+'}\n'
   if len(row)==2:out+=para(row[1])
   else:
    out+=para('; '.join(f'<b>{headers[i]}:</b> {row[i]}' for i in range(1,len(row))).replace('.;', ';'))
 if v.get('caption'):out+='\\captiontext{'+tx(v['caption'])+'}\n'
 return out

def compact_map():
 p=generate_compact_diagrams(COMPACT)
 obj=json.loads(p.read_text());items=obj if isinstance(obj,list) else obj.get('figures',[])
 result={}
 for item in items:
  for id in item.get('lesson_ids',[]):result[id]=item
 first_by_file={}
 for lesson in LESSONS:
  item=result.get(lesson['id'])
  if item:
   first_by_file.setdefault(item['file'],lesson['id'])
   result[lesson['id']]=dict(item,first_lesson=first_by_file[item['file']])
 return result

ARTCROPS=json.loads((SRC/'art-crops.json').read_text())
ARTMAP={'venus':('rocky-worlds.webp','Venus and Mars. Sizes are not to scale.'),'ganymede':('worlds.webp','Clockwise from upper left: Ganymede, Europa, Titan, Enceladus. Sizes are not to scale; Enceladus’s south pole is shown upward.'),'titan_surface':('titan.webp','Conceptual Titan surface and alternative interior models; layer thicknesses are not known.'),'bennu':('small-bodies.webp','Artist’s montage of Makemake, Bennu, and comet 67P; not to scale. Makemake’s terrain and the floating Bennu specks are illustrative, not measured features.')}

def lesson_start_space(d,selected,cm):
 if d['kind']=='practice':
  items=d['visual'].get('items',[])
  return 80+min(330,55+15*len(items)+13*sum(len(x) for x in items)/100)
 return 245 if d['id'] in cm and cm[d['id']]['first_lesson']==d['id'] else (165 if d['id'] in selected else (220 if d['id'] in {'foundation-solar-atlas','foundation-moon-atlas','compare_liquids','detection-comparison','data-sketch-practice'} else 125))

def lesson(d,selected,cm):
 hasart=d['id'] in ARTMAP
 firstspace=lesson_start_space(d,selected,cm)
 out=r'\Needspace{'+str(firstspace)+'pt}'+ '\n'+heading(d)+identity(d)
 if d.get('prerequisite_note'):out+=para(d['prerequisite_note'])
 if d['kind']=='practice':
  items=d['visual'].get('items',[])
  # Establish scenario givens before explaining their consequences.
  keep=min(330,55+15*len(items)+13*sum(len(x) for x in items)/100)
  out+=r'\Needspace{'+str(round(keep))+'pt}\n'
  out+='\\begin{enumerate}\n'+''.join('\\item '+tx(x)+'\n' for x in items)+'\\end{enumerate}\n'
 if d['kind']=='comparison':out+=comparison(d)
 if d['id'] in cm and cm[d['id']]['first_lesson']==d['id']:
  item=cm[d['id']]
  out+=r'\hypertarget{figure:'+d['id']+r'}{}\label{figure:'+d['id']+'}\n'
  path=COMPACT/item['file']
  title,body=d['panels'][0]
  row_start=len(out)
  out+=r'\begin{minipage}[t]{.49\linewidth}\vspace{0pt}'+'\n'+image(path)+r'\captiontext{'+tx(item['caption'])+'}\n'+r'\end{minipage}\hfill\begin{minipage}[t]{.47\linewidth}\RaggedRight\vspace{0pt}'+'\n'
  out+='\\subhead{'+tx(title)+'}\n'+para(body)+r'\end{minipage}'+'\n'
  row=out[row_start:];head=out[:row_start].split('\n',1)[1]
  # Comparison lead-ins can be several paragraphs or a table; never trap them in the row box.
  out=(head+r'\measuredrow{0}{}{'+row+'}\n' if d['kind']=='comparison' else r'\measuredrow{0}{}{'+head+row+'}\n')+panels(d,1,-1 if hasart else None)
 else:
  if d['id'] in cm:
   first=cm[d['id']]['first_lesson']
   out+=r'{\sffamily\small See the comparison diagram on \hyperlink{figure:'+first+r'}{page~\pageref*{figure:'+first+r'}}. Use it alongside this explanation.}\par'+'\n'
  if d['id'] in selected and d.get('panels'):
   # Legacy figures were designed at 516 pt: retain >= 8.9 pt labels.
   # Place the diagram after the explanation it supports, before worked reasoning.
   path=DIAGRAMS/'print-layout-v1'/(d['id']+'.pdf')
   if not path.exists():path=DIAGRAMS/'vector-original'/(d['id']+'.pdf')
   title,body=d['panels'][0]
   out+='\\subhead{'+tx(title)+'}\n'+para(body)
   out+=r'\begin{center}'+image(path,r'.85\linewidth' if d['id']=='math05' else r'.75\linewidth')+r'\end{center}'+'\n'+panels(d,1,-1 if hasart else None)
  else:out+=panels(d,0,-1 if hasart else None)
 if d['kind']=='equation' and d['id'] not in selected and d['id'] not in cm:
  v=d['visual'];out+=para(v.get('eq',''))+para(v.get('meaning',''))
  out+='\\begin{itemize}\n'+''.join('\\item '+tx(x)+'\n' for x in v.get('steps',[]))+'\\end{itemize}\n'
 if hasart:
  fname,cap=ARTMAP[d['id']];ap=ROOT/'assets/illustrations'/Path(fname).with_suffix('.jxl')
  # Artwork is an interpretive companion to the closing argument, not a poster page.
  art_start=len(out)
  out+=r'\par\medskip\begin{minipage}[t]{.34\linewidth}\vspace{0pt}'+image(ap,bottom_trim=ARTCROPS.get(d['id'],{}).get('bottom_px',0),right_trim=ARTCROPS.get(d['id'],{}).get('right_px',0),top_trim=ARTCROPS.get(d['id'],{}).get('top_px',0))+r'\captiontext{'+tx(cap)+r'}\end{minipage}\hfill\begin{minipage}[t]{.62\linewidth}\RaggedRight\vspace{0pt}'+'\n'
  title,body=d['panels'][-1]
  out+='\\subhead{'+tx(title)+'}\n'+para(body)
  out+='\\checkquestion{'+tx(d['question'])+'}\n'
  out+=r'{\sffamily\small\hyperlink{answer:'+d['id']+r'}{See the explanation (page~\pageref*{answer:'+d['id']+r'}).}}\par\end{minipage}\par'+'\n'
  out=out[:art_start]+r'\measuredrow{0}{}{'+out[art_start:]+'}\n'
  return out
 out+=r'\begin{samepage}'+'\n'
 out+='\\checkquestion{'+tx(d['question'])+'}\n'
 out+=r'{\sffamily\small\hyperlink{answer:'+d['id']+r'}{See the explanation (page~\pageref*{answer:'+d['id']+r'}).}}\par\end{samepage}'+'\n'
 return out

def opening():
 return r'''\section*{Explore the evidence}
This guide explains why a world might be habitable and how scientists investigate that possibility. You will compare planets, moons, small bodies, and exoplanets; follow the measurements made by missions; and use physics and chemistry to explain what the measurements mean.

Begin with the foundations, then follow a world or a question that interests you. The diagrams show mechanisms and relationships. The questions ask you to apply them, with explanations collected at the back. The separate exam reference is a compact reminder after you understand the ideas.

\textbf{Read an image with its caption.} A spacecraft photograph records an observation. An artist's interpretation helps you imagine a possibility. A schematic simplifies a mechanism. These are useful in different ways, and this guide identifies which you are looking at.

\textbf{Keep the scales straight.} A diameter is twice a radius. One astronomical unit (AU) is about 150 million kilometers. A moon's distance from its planet is different from that planet's distance from the Sun. Approximate sizes and distances here are for comparison.

\textbf{For competition preparation.} The 2027 Solar System B rules describe what the event may test. Use the official rules and any tournament clarifications alongside this guide. The source and coverage notes are collected at the back rather than mixed into every lesson.

\readerguide
\clearpage
\setcounter{tocdepth}{1}
\begingroup\small\setlength{\parskip}{1pt}
\section*{Contents}\begin{multicols}{2}\makeatletter\@starttoc{toc}\makeatother\end{multicols}
\endgroup
\clearpage
'''

def backmatter(lessons):
 out=r'\clearpage\section{Explanations to the questions}\begingroup\small'+'\n'
 seen=set()
 for d in lessons:
  key=(d['question'],d.get('answer',''))
  # Each lesson keeps an answer anchor, even when a question repeats.
  seen.add(key)
  out+='\\Needspace{80pt}\\subsubsection*{'+tx(d['title'])+'}\\hypertarget{answer:'+d['id']+'}{}\\label{answer:'+d['id']+'}\n'
  out+=tx(d.get('answer',''))+' '+r'\hyperlink{lesson:'+d['id']+r'}{Return to the lesson (page~\pageref*{lesson:'+d['id']+r'}).}'+'\n\n'
 out+=r'\endgroup\Needspace{180pt}\section{Sources and further reading}'+'\n'
 out+='The source list below preserves the connection between each topic and its evidence. Original research notes retain the full rule-to-topic map and revision history. Mission status and new findings can change; check the date of the source when using them.\n\n'
 out+=r'\begin{multicols}{2}\raggedcolumns\raggedright\small'+'\n'
 lookup={x['id']:x for x in REG}
 for d in lessons:
  out+=r'\noindent\begin{minipage}{\linewidth}\RaggedRight\vspace{0pt}{\sffamily\small\bfseries '+tx(d['title'])+r'}\par'+'\n'
  for sid in d['sources']:
   s=lookup[sid];url=s['url'];title=s['title']
   out+=r'{\small\href{'+url+'}{'+tx(title)+r'}}\par'+'\n'
  out+=r'\end{minipage}\par\medskip'+'\n'
 return out+r'\end{multicols}'+'\n'

def main():
 sample='--sample' in sys.argv;selected=export_legacy();export_print_equations();cm=compact_map()
 pre=(SERIES/'shared/publication-notice.tex').read_text()+r'\documentclass[11pt]{article}'+'\n\\input{'+(SERIES/'shared/guide-style.tex').as_posix()+'}\n'+r'\hypersetup{pdftitle={Solar System B 2027 Study Guide}}\begin{document}'+'\n'
 if sample:
  out=pre+cover()
  for id in ['foundation-4','detection-transit','math06']:
   d=next(x for x in LESSONS if x['id']==id)
   out+=lesson(d,selected,cm)+r'\clearpage'+'\n'
  name='design-sample'
 else:
  out=pre+cover()+opening();prev=None
  for d in LESSONS:
   if d['chapter']!=prev:
    out+=r'\Needspace{'+str(lesson_start_space(d,selected,cm)+(60 if d['kind']=='practice' else 100))+'pt}\n'
    out+='\\chapterlabel{'+tx(d['chapter'])+'}\n';prev=d['chapter']
   out+=lesson(d,selected,cm)
  out+=backmatter(LESSONS);name='study-guide'
 out+=r'\end{document}'+'\n'
 tex=BUILD/(name+'.tex');tex.write_text(out)
 env=os.environ.copy();cache=BUILD/'tex-cache';cache.mkdir(exist_ok=True)
 env.update(TEXMF='{/usr/share/texlive/texmf-dist,/usr/share/texmf}',TEXMFVAR=str(cache),TEXMFCACHE=str(cache),XDG_CACHE_HOME=str(cache))
 fmt=cache/'xelatex.fmt'
 if not fmt.exists():
  r=subprocess.run(['xetex','--ini','--etex','--interaction=nonstopmode','--halt-on-error','--jobname=xelatex','--progname=xelatex',r'\input xelatex.ini'],cwd=cache,env=env,capture_output=True,text=True)
  (cache/'init-output.txt').write_text(r.stdout+r.stderr)
  if r.returncode: print(r.stdout[-4000:]);raise SystemExit(r.returncode)
 for _ in range(5):
  r=subprocess.run(['xelatex','--fmt='+str(fmt),'-interaction=nonstopmode','-halt-on-error','-output-directory',str(BUILD),str(tex)],env=env,capture_output=True,text=True)
  (BUILD/(name+'-compile.txt')).write_text(r.stdout+r.stderr)
  if r.returncode: print(r.stdout[-4000:]);raise SystemExit(r.returncode)
  if _>=1 and 'Rerun to get cross-references right' not in r.stdout and 'Rerun to get outlines right' not in r.stdout:break
 else:raise RuntimeError('Cross-references did not stabilize after five passes')
 shutil.copy2(BUILD/(name+'.pdf'),OUT/(name+'.pdf'))
 print(OUT/(name+'.pdf'))
if __name__=='__main__':
 with tempfile.TemporaryDirectory(prefix='soso-art-') as directory:
  ART_CACHE=Path(directory)
  main()
