#!/usr/bin/env python3
"""Build the Thermodynamics guides from canonical JSON, without network dependencies.

Usage: bundled-python shared/build_thermo.py [--web-only] [--allow-missing]
The default is a strict web + two-PDF build. Source prose is not rewritten.
"""
from __future__ import annotations
import argparse, hashlib, html, json, os, re, shutil, subprocess, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from build_paths import event_output
from learning_cues import icon
from raster_assets import decoded_asset, external_masters
from identification_practice import practice_records
from provenance import atlas as load_atlas, supplemental as load_supplemental, citation_detail, validate_citation
from math_notation import protect_notation, restore_notation
from worksheet_renderer import worksheet_tex, worksheet_html
from urllib.parse import urlsplit

SERIES=Path(__file__).resolve().parent.parent
EXTERNAL_FIGURES=external_masters(SERIES)
EVENT=Path(os.environ.get('SOSO_EVENT_DIR', SERIES/'events/thermodynamics-b/2027')); SRC=EVENT/'source'
OUT=event_output(EVENT); WEB=OUT/'web'; BUILD=(SRC if OUT == EVENT else OUT)/'build'
SHARED=SERIES/'shared'
GENERATED_DIAGRAMS=BUILD/'generated-diagrams'
SPECS=[('study','thermodynamics-study.json','Study guide','Understand energy, temperature, and heat transfer.'),('build','thermodynamics-build.json','Build guide','Connect the apparatus, design choices, and measurements.')]
# Optional event configuration reuses the mature lesson layout without copying it.
CONFIG=json.loads((SRC/'guide-config.json').read_text()) if (SRC/'guide-config.json').exists() else {}
EVENT_NAME=CONFIG.get('name','Thermodynamics B')
EVENT_YEAR=str(CONFIG.get('year',2027))
if CONFIG:SPECS=[tuple(spec) for spec in CONFIG['guides']]
WARNINGS=[]; MISSING=[]; REG={}; RECORDS=[]

def e(s):return html.escape(str(s),quote=True)
def as_list(x):return x if isinstance(x,list) else ([] if x is None else [x])
def body(s):
    source,notation=protect_notation(str(s),"html")
    value=e(source)
    for a,b in [('&lt;i&gt;','<em>'),('&lt;/i&gt;','</em>'),('&lt;em&gt;','<em>'),('&lt;/em&gt;','</em>'),('&lt;b&gt;','<strong>'),('&lt;/b&gt;','</strong>'),('&lt;strong&gt;','<strong>'),('&lt;/strong&gt;','</strong>'),('&lt;br/&gt;','<br>'),('&lt;br&gt;','<br>')]:value=value.replace(a,b)
    value=re.sub(r'(?<=[A-Za-z0-9Α-ω)])\^(-?\d+(?:/\d+)?)', r'<sup>\1</sup>', value)
    value=re.sub(r'\b([TQ])([hc])\b', r'\1<sub>\2</sub>', value)
    return restore_notation(value,notation)

def paras(s):
    if isinstance(s,list):return ''.join(paras(p) for p in s)
    return ''.join('<p>'+body(p)+'</p>' for p in str(s or '').split('\n\n') if p.strip())
def panel_parts(p):
    if isinstance(p,dict):return p.get('title',p.get('heading','')),p.get('body',p.get('text',p.get('content','')))
    if isinstance(p,(list,tuple)):return (p[0] if p else ''),(p[1] if len(p)>1 else '')
    return '',str(p)
def panels(d):return [panel_parts(p) for p in d.get('panels',[])]
def is_answer_panel(p):return bool(re.match(r'^(answers?|solutions?)(?:\b|:)',str(p[0]),re.I))
def numbered_steps(p):
    if str(p[0]).lower() in ['questions','answers'] and isinstance(p[1],list):return p[1]
    # Only the authored construction panels; decimal values are not list markers.
    if str(p[0]).lower() not in ['construction','construction sequence'] or not isinstance(p[1],str):return []
    text=p[1].strip();matches=list(re.finditer(r'(?<!\S)(\d+)\.\s+',text))
    if len(matches)<2 or matches[0].start()!=0 or [int(m.group(1)) for m in matches]!=list(range(1,len(matches)+1)):return []
    return [text[m.end():matches[i+1].start() if i+1<len(matches) else len(text)].strip() for i,m in enumerate(matches)]

def panel_html(p):
    if is_answer_panel(p):
        answer='<ol>'+''.join('<li>'+body(x)+'</li>' for x in p[1])+'</ol>' if isinstance(p[1],list) else paras(p[1])
        return '<details class="answer-disclosure"><summary>Show '+body(str(p[0]).lower())+'</summary><div class="answer">'+answer+'</div></details>'
    steps=numbered_steps(p)
    content='<ol class="construction-steps">'+''.join('<li>'+body(x)+'</li>' for x in steps)+'</ol>' if steps else paras(p[1])
    return ('<h4>'+(icon('worked') if str(p[0]).lower().startswith('worked') else '')+body(p[0])+'</h4>' if p[0] else '')+content
def source_ids(d):
    ids=[]
    for v in as_list(d.get('sources',[])):
        if isinstance(v,dict):
            sid=v.get('id',v.get('url',''));REG.setdefault(sid,validate_citation(v))
        else:sid=str(v)
        if sid:ids.append(sid)
    return ids

def load_sources():
    names=['thermodynamics-source-registry.json','source-registry.json','thermodynamics-sources.json']
    candidates=[SRC/name for name in names]+[EVENT/'research'/name for name in names]
    for p in candidates:
        if not p.exists():continue
        raw=json.loads(p.read_text());rows=raw.get('sources',raw) if isinstance(raw,dict) else raw
        if isinstance(rows,dict):rows=[dict(value,id=key) for key,value in rows.items()]
        for row in rows:
            if isinstance(row,dict) and row.get('id'):REG[row['id']]=validate_citation(row)
        return p
    return None

def load_guide(path):
    raw=json.loads(path.read_text())
    if isinstance(raw,list):rows=raw;meta={}
    else:
        meta={k:v for k,v in raw.items() if k not in ['lessons','sections']}
        rows=raw.get('lessons',raw.get('sections',[]))
    seen=set()
    for n,d in enumerate(rows):
        if not isinstance(d,dict):raise ValueError(f'{path}: lesson {n} must be an object')
        d.setdefault('id',f'lesson-{n+1}');d.setdefault('title',d['id']);d.setdefault('chapter','Learn and apply');d.setdefault('deck','')
        if d['id'] in seen:raise ValueError(f'Duplicate lesson id {d["id"]}')
        seen.add(d['id'])
    return rows,meta

def resolve_asset(name):
    p=Path(str(name))
    choices=[p] if p.is_absolute() else [EVENT/p,EVENT/'assets/diagrams'/p,EVENT/'assets'/p,GENERATED_DIAGRAMS/p.name,SRC/p,WEB/p]
    for candidate in choices:
        resolved=candidate.resolve()
        if resolved.is_file():return resolved
        if resolved.is_relative_to(SERIES) and resolved.relative_to(SERIES).as_posix() in EXTERNAL_FIGURES:
            return resolved
    MISSING.append('figure: '+str(name));return None

def normalize_figures(d):
    out=[]
    values=as_list(d.get('figure'))+as_list(d.get('figures'))
    for value in values:
        f={'file':value} if isinstance(value,str) else dict(value)
        name=f.get('file',f.get('path',f.get('src')))
        if not name:continue
        path=resolve_asset(name)
        if not path:continue
        cap=f.get('caption',f.get('description',''))
        f.update(path=path,caption=cap,alt=f.get('alt',cap or 'Diagram supporting '+d['title']))
        f['wide']=bool(float(f.get('width_pt',240))>280 or f.get('full_width') or f.get('layout') in ['wide','full','full-width'] or any(w in path.stem for w in ['geometry','apparatus','removal','assembly','cut-list']))
        f['web_path']=web_asset(path)
        out.append(f)
    return out

def web_asset(path):
    target=WEB/'assets/diagrams';target.mkdir(parents=True,exist_ok=True)
    if path.suffix.lower()=='.pdf':
        svg=path.with_suffix('.svg')
        if svg.exists():path=svg
        else:
            import fitz
            dest=target/(path.stem+'.svg');doc=fitz.open(path);dest.write_text(doc[0].get_svg_image(text_as_path=True));return dest.relative_to(WEB).as_posix()
    original=path
    path=decoded_asset(path,BUILD/'decoded-assets',web=True)
    dest=target/(original.stem+path.suffix)
    if path.resolve()!=dest.resolve():shutil.copy2(path,dest)
    return dest.relative_to(WEB).as_posix()

def pdf_asset(f):
    p=decoded_asset(f['path'],BUILD/'decoded-assets')
    if p.suffix.lower()=='.webp':
        from PIL import Image
        dest=BUILD/'figure-pdfs'/(p.stem+'.png');dest.parent.mkdir(parents=True,exist_ok=True)
        with Image.open(p) as im:im.save(dest)
        return dest
    if p.suffix.lower()!='.svg':return p
    sibling=p.with_suffix('.pdf')
    if sibling.exists() and sibling.stat().st_mtime>=p.stat().st_mtime:return sibling
    converter=os.environ.get('SVG_PDF_CONVERTER','rsvg-convert')
    if converter not in ('inkscape','rsvg-convert'):raise ValueError('Unsupported SVG_PDF_CONVERTER: '+converter)
    dest=BUILD/'figure-pdfs'/converter/(p.stem+'.pdf');dest.parent.mkdir(parents=True,exist_ok=True)
    if dest.exists() and dest.stat().st_mtime>=p.stat().st_mtime:return dest
    env=os.environ.copy();cache=BUILD/(converter+'-cache');cache.mkdir(parents=True,exist_ok=True)
    env.update(HOME=str(cache),XDG_CACHE_HOME=str(cache),XDG_CONFIG_HOME=str(cache))
    command=([converter,'--format=pdf','--output='+str(dest),str(p)] if converter=='rsvg-convert'
             else [converter,str(p),'--export-type=pdf','--export-text-to-path','--export-filename='+str(dest)])
    r=subprocess.run(command,env=env,capture_output=True,text=True)
    if r.returncode or not dest.exists():raise RuntimeError('SVG-to-PDF failed for '+str(p)+'\n'+r.stderr)
    return dest

def figure_html(f,extra=''):
    cls=('wide-figure' if f['wide'] else 'compact-figure')+' '+extra
    style=' style="max-width:'+str(float(f['width_pt'])*4/3)+'px"' if f.get('width_pt') else ''
    return '<figure class="'+cls+'"'+style+'><a class="figure-enlarge" href="'+e(f['web_path'])+'" title="Open the diagram at full size"><img src="'+e(f['web_path'])+'" alt="'+e(f['alt'])+'" loading="lazy"></a>'+('<figcaption>'+body(f['caption'])+'</figcaption>' if f['caption'] else '')+'<a class="diagram-link" href="'+e(f['web_path'])+'">Enlarge diagram</a></figure>'

def source_title(s):return s.get('title',s.get('name',s.get('url',s.get('id','Source'))))
def reference_html(d):
    items=[]
    for sid in source_ids(d):
        s=REG.get(sid)
        if s:items.append('<li><a href="#source-'+e(sid)+'">'+e(source_title(s))+'</a></li>')
        else:MISSING.append('source: '+sid)
    return '<details class="sources"><summary>Sources for this lesson</summary><ul>'+''.join(items)+'</ul></details>' if items else ''

def table_html(table):
    heads=table.get('headers',[]);rows=table.get('rows',[])
    out='<div class="table-wrap"><table>'
    if heads:out+='<thead><tr>'+''.join('<th scope="col">'+body(x)+'</th>' for x in heads)+'</tr></thead>'
    out+='<tbody>'
    for row in rows:out+='<tr>'+''.join(('<th scope="row">' if i==0 else '<td>')+body(cell)+('</th>' if i==0 else '</td>') for i,cell in enumerate(row))+'</tr>'
    return out+'</tbody></table></div>'

def extras_html(d):
    out=''
    if d.get('body'):out+=paras(d['body'])
    for key in ['items','bullets','steps']:
        if d.get(key):
            tag='ol' if key=='steps' else 'ul';out+='<'+tag+'>'+''.join('<li>'+body(x)+'</li>' for x in d[key])+'</'+tag+'>'
    for key in ['table','tables']:
        for t in as_list(d.get(key)):
            if isinstance(t,dict):out+=table_html(t)
    if d.get('equation'):out+='<p class="equation">'+body(d['equation'])+'</p>'
    if d.get('note'):out+='<aside class="note">'+paras(d['note'])+'</aside>'
    return out

def interactive_links(kind):
    if CONFIG:
        cards=''.join('<article><h3>'+e(m['title'])+'</h3><p>'+e(m['description'])+'</p><a class="action-link" href="'+e(m['path'])+'">Open '+e(m['title'])+'</a></article>' for m in CONFIG.get('models',[]))
        return '<section class="explorers" id="explorers"><h2>Explore and practice</h2><div class="explorer-grid">'+cards+'</div></section>'
    return '''<section class="explorers" id="explorers"><h2>Explore the models</h2><p>Each explorer is a separate local page with its own reset controls, assumptions, and a printable diagram. The conceptual models help you ask questions; they do not certify a build.</p><div class="explorer-grid"><article><h3>Fit the apparatus and keep access clear</h3><p>Change the lamp height, base, opening, and reflector geometry. See a side view, a plan view, and the cup-removal constraint.</p><a class="action-link" href="interactives/geometry.html">Open the lamp and collector geometry explorer</a><figure><img src="assets/diagrams/geometry-default.svg" alt="Static default apparatus side and plan views; use the linked geometry page to vary the controls."><figcaption>Static default example. The explorer explains which dimensions come from the rules and which are prototype choices.</figcaption></figure></article><article><h3>Follow energy into and out of the water</h3><p>Change one model input at a time and compare the temperature response. Read the assumptions before using a curve to reason about a real test.</p><a class="action-link" href="interactives/heat-flow.html">Open the heat-flow explorer</a><figure><img src="assets/diagrams/heat-flow-default.svg" alt="Static illustrative heat-flow model; the linked page contains adjustable model controls."><figcaption>Illustrative model, not measured performance of a tested device. The static graphic remains readable without JavaScript.</figcaption></figure></article></div></section>'''

def prepare_interactive_assets():
    if CONFIG:
        runtime=SRC/'interactives/runtime'
        if runtime.exists():shutil.copytree(runtime,WEB/'interactives',dirs_exist_ok=True)
        if CONFIG.get('atlas'):
            rows=load_atlas(EVENT,CONFIG['atlas'])['organisms']
            photos=load_supplemental(EVENT,CONFIG['supplemental_images']) if CONFIG.get('supplemental_images') else []
            records=practice_records(rows,photos)
            for record in records:
                record['image']='../'+web_asset(EVENT/record['image'])
            page=WEB/'interactives/practice.html'
            if page.exists():page.write_text(page.read_text().replace('@@ORGANISMS@@',json.dumps(records).replace('</','<\\/')))
        return
    runtime=EVENT/'source/interactives/runtime'
    for name in ('geometry.html','heat-flow.html','geometry.js','heat-flow.js','model.js','interactive.css'):
        src=runtime/name
        if not src.is_file():raise FileNotFoundError('Missing authored interactive: '+str(src))
        dest=WEB/'interactives'/name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,dest)
    for stem in ['geometry-default','geometry-removal','heat-flow-default']:
        p=EVENT/'assets/diagrams'/(stem+'.svg')
        if p.exists():web_asset(p)
        else:MISSING.append('interactive fallback: '+str(p))
    for stem in ['geometry','heat-flow']:
        page=WEB/'interactives'/(stem+'.html')
        if not page.exists():MISSING.append('interactive page: '+stem);continue
        markup=page.read_text()
        nav='<nav id="guide-return-nav" aria-label="Return to guides" style="padding:12px 20px;background:#edf5f5;display:flex;flex-wrap:wrap;gap:18px"><a href="../index.html">Guide home</a><a href="../study-guide.html">Study guide</a><a href="../build-guide.html">Build guide</a><a href="../../study-guide.pdf">Study PDF</a><a href="../../build-guide.pdf">Build PDF</a></nav>'
        markup=re.sub(r'<nav id="guide-return-nav".*?</nav>', '', markup, flags=re.S)
        markup=re.sub(r'(<body[^>]*>)', lambda m:m.group(1)+nav, markup, count=1)
        page.write_text(markup)

def placed_after(f,index,heading):
    value=f.get('after_panel')
    return value==index or (isinstance(value,str) and value==heading)

def equations_html(d,index):
    return ''.join('<div class="display-equation"><math xmlns="http://www.w3.org/1998/Math/MathML" display="block">'+x['mathml']+'</math></div>' for x in d.get('display_equations',[]) if x['after_panel']==index)

def equations_tex(d,index):
    return ''.join(r'\['+x['tex']+r'\]'+'\n' for x in d.get('display_equations',[]) if x['after_panel']==index)

def lesson_html(d,figs):
    out='<article class="lesson" id="'+e(d['id'])+'"><h3>'+body(d['title'])+'</h3>'
    if d.get('deck'):out+='<p class="deck">'+body(d['deck'])+'</p>'
    pp=panels(d);remaining=list(figs);start=0
    if remaining and not remaining[0]['wide'] and pp and remaining[0].get('after_panel') is None:
        start=min(len(pp),d.get('paired_panels',1))
        out+='<div class="split">'+figure_html(remaining.pop(0))+'<div>'+''.join(panel_html(p) for p in pp[:start])+'</div></div>'
        for f in list(remaining):
            if placed_after(f,0,pp[0][0]):out+=figure_html(f);remaining.remove(f)
    elif remaining and remaining[0]['wide'] and remaining[0].get('after_panel') is None:out+=figure_html(remaining.pop(0))
    for index in range(start,len(pp)):
        out+=panel_html(pp[index])+equations_html(d,index)
        for f in list(remaining):
            if placed_after(f,index,pp[index][0]):out+=figure_html(f);remaining.remove(f)
    out+=extras_html(d)+''.join(figure_html(f) for f in remaining)
    if d.get('question'):
        out+='<div class="self-check"><div class="label">'+icon('think')+'Think it through</div>'+paras(d['question'])
        if d.get('answer') is not None:out+='<details><summary>Show the reasoning</summary><div class="answer">'+paras(d['answer'])+'</div></details>'
        out+='</div>'
    if d['id'] in ['thermo-build-geometry','thermo-build-cup','thermo-build-reflector']:
        out+='<p class="model-link"><a href="interactives/geometry.html">Try the geometry explorer: change the apparatus dimensions and inspect cup access.</a></p>'
    if d['id'] in ['thermo-build-energy','thermo-capacity','thermo-transfer']:
        out+='<p class="model-link"><a href="interactives/heat-flow.html">Try the heat-flow explorer: change one assumption and compare the temperature response.</a></p>'
    if d.get('worksheet'):out+=worksheet_html(d['worksheet'])
    return out+reference_html(d)+'</article>'

def chapters(lessons):
    result=[]
    for d in lessons:
        if not result or result[-1][0]!=d['chapter']:result.append((d['chapter'],[]))
        result[-1][1].append(d)
    return result

def page_start(title,kind=None,description=''):
    return '<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="'+e(description)+'"><title>'+e(title)+' | '+e(EVENT_NAME)+' '+e(EVENT_YEAR)+'</title><link rel="stylesheet" href="style.css"></head><body><a class="skip" href="#main">Skip to the guide</a><header class="topbar">'+('<button class="navtoggle" id="navtoggle" aria-expanded="false" aria-controls="contents">Contents</button>' if kind else '')+'<a class="brand" href="index.html">'+e(EVENT_NAME)+'</a><nav class="toplinks" aria-label="Companion guides"><a href="study-guide.html"'+(' aria-current="page"' if kind=='study' else '')+'>Study</a><a href="build-guide.html"'+(' aria-current="page"' if kind=='build' else '')+'>Build</a></nav><span class="edition">'+e(EVENT_YEAR)+' · Division B</span></header>'

def sources_html(lessons):
    wanted=set(sid for d in lessons for sid in source_ids(d));out='<section class="source-directory" id="sources"><h2>Sources and further reading</h2><p>Source links identify the evidence behind the lessons. Internet access is only needed if you choose to open these external references.</p>'
    if any(REG.get(sid,{}).get('license_url') for sid in wanted):out+=paras('Published photographs may be resized and re-encoded as high-quality WebP or JPEG; individual credits and changes below remain applicable.')
    for sid,s in REG.items():
        if sid not in wanted:continue
        out+='<div class="source-entry" id="source-'+e(sid)+'"><div class="source-title">'+e(source_title(s))+'</div>'
        if s.get('url'):out+='<a href="'+e(s['url'])+'">'+e(s['url'])+'</a>'
        if citation_detail(s):out+=paras(citation_detail(s))
        if s.get('quotation'):out+='<blockquote>'+body(s['quotation'])+'</blockquote>'
        if s.get('note'):out+=paras(s['note'])
        if s.get('license_url'):out+='<p><a href="'+e(s['license_url'])+'">Image license terms</a></p>'
        out+='</div>'
    return out+'</section>'

def render_web(kind,title,description,lessons,figmap):
    nav='<a href="#introduction">About this guide</a><a href="#explorers">Interactive models</a>'
    for chapter,ds in chapters(lessons):nav+='<details open><summary>'+e(chapter)+'</summary>'+''.join('<a class="lesson-link" href="#'+e(d['id'])+'">'+e(d['title'])+'</a>' for d in ds)+'</details>'
    nav+='<a href="#sources">Sources and further reading</a>'
    out=page_start(title,kind,description)+'<div class="layout"><aside class="sidebar" id="contents"><label for="lesson-search">Find a lesson</label><input type="search" id="lesson-search" placeholder="Search this guide"><p class="status" id="search-status" aria-live="polite">All lessons</p><nav aria-label="Guide contents">'+nav+'</nav></aside><main id="main">'
    out+='<section class="guide-heading" id="introduction"><p class="eyebrow">Science Olympiad · Division B · '+e(EVENT_YEAR)+'</p><h1>'+e(EVENT_NAME)+'<br><span>'+e(title)+'</span></h1><p class="lead">'+e(description)+'</p><div class="reading-links"><a href="../'+kind+'-guide.pdf">Download the printable '+e(title.lower())+' (PDF)</a><a href="'+('build' if kind=='study' else 'study')+'-guide.html">Open the companion '+('build' if kind=='study' else 'study')+' guide</a></div><p class="guide-use">Read each figure with its caption. Questions have hidden explanations so you can think before revealing the reasoning. <button type="button" id="hide-answers">Hide all answers</button> <button type="button" id="reset-guide">Reset guide controls</button></p><p class="caption">Works offline: text, figures, scripts, and model pages are local. Use the official rules and tournament clarifications alongside this independent guide.</p></section>'
    for i,(chapter,ds) in enumerate(chapters(lessons)):
        out+='<section class="chapter" id="chapter-'+str(i)+'"><h2>'+e(chapter)+'</h2>'+''.join(lesson_html(d,figmap[d['id']]) for d in ds)+'</section>'
    out+=interactive_links(kind)+sources_html(lessons)+'<footer class="footer">'+e(EVENT_NAME)+' · '+e(EVENT_YEAR)+'. Independent learning and construction guidance. A diagram or model is not a safety, performance, or rules-compliance certificate.</footer></main></div><script src="guide.js"></script></body></html>'
    path=WEB/(kind+'-guide.html');path.write_text(out);return path

def render_landing(available):
    out=page_start('Study and build guides',description='Offline '+EVENT_NAME+' '+EVENT_YEAR+' study and build guides with interactive models.')+'<main id="main" class="landing"><section class="guide-heading"><p class="eyebrow">Science Olympiad · Division B · '+e(EVENT_YEAR)+'</p><h1>'+('Read the water.<br>Test the evidence.' if CONFIG else 'Learn the physics.<br>Test the design.')+'</h1><p class="lead">'+e(CONFIG.get('introduction',EVENT_NAME+' brings energy, heat transfer, and measurement into one investigation.'))+'</p></section><section class="guide-cards" aria-label="Choose a guide">'
    for kind,title,description,count in available:
        out+='<article><p class="eyebrow">'+str(count)+' lessons</p><h2>'+e(title)+'</h2><p>'+e(description)+'</p><a class="action-link" href="'+kind+'-guide.html">Open the '+e(title.lower())+'</a><p><a href="../'+kind+'-guide.pdf">Printable PDF</a></p></article>'
    out+='</section>'+interactive_links('landing')+'<footer class="footer">Everything needed to read and explore is included locally. External source links are optional further reading. Use the official '+e(EVENT_YEAR)+' rules and tournament clarifications alongside these independent guides.</footer></main></body></html>'
    (WEB/'index.html').write_text(out)

# XeLaTeX: preserve wording; typeset recurring relationships as real mathematics.
PRINT_MATH={
    'power≈εσA(Tobject^4−Tsurroundings^4)':r'\(\text{power}\approx\varepsilon\sigma A(T_{\mathrm{object}}^4-T_{\mathrm{surroundings}}^4)\)',
    'ηmax=1−Tc/Th':r'\(\eta_{\max}=1-T_{\mathrm{c}}/T_{\mathrm{h}}\)',
    'η=W/Qh':r'\(\eta=W/Q_{\mathrm{h}}\)',
    'W=Qh−Qc':r'\(W=Q_{\mathrm{h}}-Q_{\mathrm{c}}\)',
    'M=εσT^4':r'\(M=\varepsilon\sigma T^4\)',
    'M=σT^4':r'\(M=\sigma T^4\)',
    'ΔU=Q−W':r'\(\Delta U=Q-W\)',
    'W=PΔV':r'\(W=P\Delta V\)',
    'PV=nRT':r'\(PV=nRT\)',
    'Q=mcΔT':r'\(Q=mc\Delta T\)',
    'C=mc':r'\(C=mc\)',
    'Q=mL':r'\(Q=mL\)',
    'Q=Pt':r'\(Q=Pt\)',
}
def tx(s):
    s=html.unescape(str(s));math_tokens={}
    for expression,value in PRINT_MATH.items():
        key=f'ZZPRINTMATH{len(math_tokens)}ZZ'
        s,count=re.subn(re.escape(expression)+r'(?![A-Za-z0-9])',lambda m:key,s)
        if count:math_tokens[key]=value
    s,notation=protect_notation(s,"latex")
    s=s.replace('\u2011','-').replace('\u2013','--').replace('\u2014','; ')
    s=s.replace('<br/>','\n').replace('<br>','\n')
    tags={'<i>':'ZZITALICOPENZZ','<em>':'ZZITALICOPENZZ','<b>':'ZZBOLDOPENZZ','<strong>':'ZZBOLDOPENZZ','</i>':'ZZCLOSEZZ','</em>':'ZZCLOSEZZ','</b>':'ZZCLOSEZZ','</strong>':'ZZCLOSEZZ'}
    for a,b in tags.items():s=s.replace(a,b)
    # Only strip markup tags, never scientific comparisons such as Q < K.
    s=re.sub(r'</?[A-Za-z][A-Za-z0-9]*(?:\s[^>]*)?/?>','',s)
    s=re.sub(r'(?<=[A-Za-z0-9Α-ω)])\^(-?\d+(?:/\d+)?)',r'ZZSUPOPENZZ\1ZZCLOSEZZ',s)
    chars={'\\':r'\textbackslash{}','&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_','{':r'\{','}':r'\}','~':r'\textasciitilde{}','^':r'\textasciicircum{}'}
    s=''.join(chars.get(c,c) for c in s)
    s=s.replace('ZZITALICOPENZZ',r'\emph{').replace('ZZBOLDOPENZZ',r'\textbf{').replace('ZZCLOSEZZ','}').replace('ZZSUPOPENZZ',r'\textsuperscript{')
    for a,b in [('∝',r'\(\propto\)'),('≠',r'\(\ne\)'),('≈',r'\(\approx\)'),('≤',r'\(\le\)'),('≥',r'\(\ge\)'),('−','-'),('→',r'\(\to\)'),('↔',r'\(\leftrightarrow\)')]:s=s.replace(a,b)
    s=s.replace('=',r'\allowbreak{}\,=\,\allowbreak{}').replace('×',r'\allowbreak{}\,×\,\allowbreak{}')
    for key,value in math_tokens.items():s=s.replace(key,value)
    return restore_notation(s,notation)

def para(s):
    return '\n\n'.join(tx(p) for p in as_list(s))+'\n\n'
def panel_tex(p):
    steps=numbered_steps(p)
    content='\\begin{enumerate}\n'+''.join('\\item '+tx(x)+'\n' for x in steps)+'\\end{enumerate}\n' if steps else para(p[1])
    head='\\workedhead{' if str(p[0]).lower().startswith('worked') else '\\subhead{'
    out=(head+tx(p[0])+'}\n' if p[0] else '')+content
    # A construction sequence is a usable instruction unit, not isolated steps.
    return r'\begin{samepage}'+out+r'\end{samepage}'+'\n' if steps and str(p[0]).lower() not in ['questions','answers'] else out

def print_figure_width(f):
    """Print sizing is independent of authored web sizing and source artwork."""
    stem=f['path'].stem
    if stem.startswith('geometry-'):return r'\linewidth'
    if stem.startswith('concept-'):return r'\linewidth'
    if stem=='reflector-pattern':return '360pt'
    return '300pt'

def figure_tex(f,width=None):
    width=width or print_figure_width(f)
    p=pdf_asset(f)
    # One unbreakable image/caption unit; no floating figure can drift away.
    out=r'\begin{minipage}{'+width+r'}\centering'+'\n'
    options=r'width=\linewidth'+(',height='+str(f['height_pt'])+'pt,keepaspectratio' if f.get('height_pt') else '')
    out+='\\includegraphics['+options+']{'+p.as_posix()+'}\\par\n'
    if f['caption']:out+=r'\raggedright'+ '\\captiontext{'+tx(f['caption'])+'}\n'
    return out+r'\end{minipage}'+'\n'

def extras_tex(d):
    out=para(d['body']) if d.get('body') else ''
    for key in ['items','bullets','steps']:
        if d.get(key):
            env='enumerate' if key=='steps' else 'itemize';out+='\\begin{'+env+'}\n'+''.join('\\item '+tx(x)+'\n' for x in d[key])+'\\end{'+env+'}\n'
    for key in ['table','tables']:
        for t in as_list(d.get(key)):
            if not isinstance(t,dict):continue
            heads=t.get('headers',[])
            if t.get('compact') and heads:
                out+=r'\par\smallskip\noindent\begin{tabularx}{\linewidth}{@{}'+('X'*len(heads))+r'@{}}\toprule'+'\n'
                out+=' & '.join(r'\textbf{'+tx(h)+'}' for h in heads)+r'\\\midrule'+'\n'
                out+=''.join(' & '.join(tx(str(cell)) for cell in row)+r'\\'+'\n' for row in t.get('rows',[]))
                out+=r'\bottomrule\end{tabularx}\par\medskip'+'\n'
                continue
            # Narrative table cells reflow safely; all headers remain visible.
            for row in t.get('rows',[]):
                out+='\\subhead{'+tx(row[0])+'}\n'
                for n,cell in enumerate(row[1:],1):out+=para((heads[n]+': ' if n<len(heads) else '')+str(cell))
    for key in ['equation','note']:
        if d.get(key):out+=para(d[key])
    return out

def paired_panel_count(d,figs):
    if not figs or figs[0].get('after_panel') is not None:return 0
    if figs[0]['path'].stem.startswith(('geometry-','concept-')):return 0
    pp=panels(d)
    if not pp or is_answer_panel(pp[0]):return 0
    count=min(len(pp),d.get('paired_panels',1))  # Explicit atlas rows may pair several short panels.
    # Preserve explicit figure placements and keep answer material at the back.
    for index in range(count):
        if is_answer_panel(pp[index]):return index
        if any(placed_after(f,index,pp[index][0]) for f in figs[1:]):return index+1
    return count

def first_block_height(d,figs):
    count=paired_panel_count(d,figs)
    if count:return 275 if not figs[0]['path'].stem.startswith('concept-') else 300
    if not figs:return 135
    if figs[0]['path'].stem.startswith(('geometry-','concept-')):return 220
    p=pdf_asset(figs[0])
    import fitz
    with fitz.open(p) as doc:ratio=doc[0].rect.height/doc[0].rect.width
    width=518 if figs[0]['path'].stem.startswith('geometry-') else 300
    return min(540,max(180,width*ratio+105))

def centered_figure(f):
    return r'\par\smallskip\noindent\makebox[\linewidth][c]{'+figure_tex(f)+r'}\par\smallskip'+'\n'

def lesson_tex(d,figs,chapter_head=''):
    pp=panels(d);out='\\Needspace{'+str(round(first_block_height(d,figs)+(55 if chapter_head else 0)))+'pt}\n'+chapter_head
    out+='\\lesson{'+d['id']+'}{'+tx(d['title'])+'}{'+tx(d.get('deck',''))+'}\n'
    remaining=list(figs);start=paired_panel_count(d,figs)
    if start:
        row_start=len(out)
        f=remaining.pop(0);concept=f['path'].stem.startswith('concept-')
        left,right=('.31','.65') if concept else (('.44','.52') if d.get('paired_panels') else ('.58','.38'))
        out+=r'\noindent\begin{minipage}[t]{'+left+r'\linewidth}\vspace{0pt}\centering'+'\n'+figure_tex(f,r'\linewidth')+r'\end{minipage}\hfill\begin{minipage}[t]{'+right+r'\linewidth}\vspace{0pt}\raggedright'+'\n'
        out+=''.join(panel_tex(p) for p in pp[:start])+r'\end{minipage}\par\medskip'+'\n'
        row=out[row_start:];head=out[:row_start].split('\n',1)[1]
        out=r'\measuredrow{0}{}{'+head+row+'}\n'
        for f in list(remaining):
            if any(placed_after(f,index,pp[index][0]) for index in range(start)):
                out+=centered_figure(f);remaining.remove(f)
    elif remaining and remaining[0].get('after_panel') is None:
        if remaining[0]['path'].stem.startswith(('geometry-','concept-')) and pp:
            start=1 if remaining[0]['path'].stem.startswith('concept-') else min(2,len(pp))
            out+=''.join(panel_tex(p) for p in pp[:start])
        out+=centered_figure(remaining.pop(0))
    nonanswers=[i for i,p in enumerate(pp) if not is_answer_panel(p)]
    for index in range(start,len(pp)):
        inline=next((f for f in remaining if f['path'].stem=='reflector-pattern' and placed_after(f,index,pp[index][0])),None)
        if inline:
            # Keep the cut-pattern explanation beside its drawing, not one page apart.
            out+=r'\Needspace{300pt}\noindent\begin{minipage}[t]{.47\linewidth}\vspace{0pt}\raggedright'+'\n'+panel_tex(pp[index])+r'\end{minipage}\hfill\begin{minipage}[t]{.49\linewidth}\vspace{0pt}'+'\n'+figure_tex(inline,r'\linewidth')+r'\end{minipage}\par\medskip'+'\n'
            remaining.remove(inline)
        elif not is_answer_panel(pp[index]):
            if d.get('question') and index==nonanswers[-1]:
                keep=min(230,max(105,65+13*len(str(pp[index][1]))/95+13*len(str(d['question']))/95))
                out+='\\Needspace{'+str(round(keep))+'pt}\n'
            out+=panel_tex(pp[index])+equations_tex(d,index)
        for f in list(remaining):
            if placed_after(f,index,pp[index][0]):out+=centered_figure(f);remaining.remove(f)
    out+=extras_tex(d)
    for f in remaining:out+=centered_figure(f)
    if d.get('worksheet'):
        w=d['worksheet'];out+=r'\par\smallskip\learningcue{try}{Use the printable worksheet} '+r'\hyperlink{worksheet:'+w['id']+'}{'+tx(w['title'])+r' (page~\pageref*{worksheet:'+w['id']+r'}).}\par'+'\n'
    if d.get('question'):out+='\\begin{samepage}\\checkquestion{'+tx(d['question'])+'}\\nopagebreak\n{\\small\\hyperlink{answer:'+d['id']+'}{See the explanation (page~\\pageref*{answer:'+d['id']+'}).}}\\par\\end{samepage}\n'
    return out

def backmatter_tex(lessons):
    out=r'\clearpage\section{Reasoning for the questions}\begingroup\small'+'\n'
    for d in lessons:
        answer_panels=[p for p in panels(d) if is_answer_panel(p)]
        if d.get('answer') is None and not answer_panels:continue
        out+='\\Needspace{75pt}\\hypertarget{answer:'+d['id']+'}{}\\label{answer:'+d['id']+'}\\subsubsection*{'+tx(d['title'])+'}\n'
        if d.get('answer') is not None:out+=para(d['answer'])
        for p in answer_panels:out+=panel_tex(p)
        out=out.rstrip()+' '
        out+=r'\hyperlink{lesson:'+d['id']+r'}{Return to the lesson (page~\pageref*{lesson:'+d['id']+r'}).}\par'+'\n'
    out+=r'\endgroup\Needspace{160pt}\section{Sources and further reading}\begingroup\small\setlength{\parskip}{4pt}'+'\n'
    wanted=set(sid for d in lessons for sid in source_ids(d))
    if any(REG.get(sid,{}).get('license_url') for sid in wanted):out+=para('Published photographs may be resized and re-encoded as high-quality JPEG; individual credits and changes below remain applicable.')
    for sid,s in REG.items():
        if sid not in wanted:continue
        url=s.get('url')
        title=tx(source_title(s))
        if url:title=r'\href{'+url.replace('%',r'\%')+'}{'+title+'}'
        out+='\\Needspace{100pt}\\textbf{'+title+'}\\label{source:'+tx(sid)+'}\\par\n'
        supported=list(dict.fromkeys(d['chapter'] for d in lessons if sid in source_ids(d)))
        out+=para('Related chapters: '+'; '.join(supported)+'.')
        if citation_detail(s):out+=para(citation_detail(s))
        if s.get('quotation'):out+=r'\begin{quote}'+tx(s['quotation'])+r'\end{quote}'
        if s.get('note'):out+=para(s['note'])
        if s.get('license_url'):out+=r'\href{'+s['license_url']+r'}{Image license terms.}\par'+'\n'
        out+='\\smallskip\n'
    return out+r'\endgroup'+'\n'

def compile_tex(tex):
    cache=BUILD/'tex-cache';cache.mkdir(parents=True,exist_ok=True);env=os.environ.copy()
    env.update(TEXMF='{/usr/share/texlive/texmf-dist,/usr/share/texmf}',TEXMFVAR=str(cache),TEXMFCACHE=str(cache),XDG_CACHE_HOME=str(cache))
    fmt=cache/'xelatex.fmt'
    if not fmt.exists():
        r=subprocess.run(['xetex','--ini','--etex','--interaction=nonstopmode','--halt-on-error','--jobname=xelatex','--progname=xelatex',r'\input xelatex.ini'],cwd=cache,env=env,capture_output=True,text=True)
        (cache/'init-output.txt').write_text(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError(r.stdout[-4000:]+r.stderr[-1000:])
    for _ in range(5):
        r=subprocess.run(['xelatex','--fmt='+str(fmt),'-interaction=nonstopmode','-halt-on-error','-output-directory',str(BUILD),str(tex)],env=env,capture_output=True,text=True)
        (BUILD/(tex.stem+'-compile.txt')).write_text(r.stdout+r.stderr)
        if r.returncode:raise RuntimeError(r.stdout[-5000:]+r.stderr[-1000:])
        if _>=1 and 'Rerun to get cross-references right' not in r.stdout and 'Rerun to get outlines right' not in r.stdout:break
    else:raise RuntimeError('Cross-references did not stabilize after five passes')
    dest=OUT/(tex.stem+'.pdf');shutil.copy2(BUILD/(tex.stem+'.pdf'),dest)
    return dest

def render_pdf(kind,title,description,lessons,figmap):
    pre=(SHARED/'publication-notice.tex').read_text()+r'\documentclass[11pt]{article}'+'\n\\input{'+(SHARED/'guide-style.tex').as_posix()+'}\n'
    hero=pdf_asset({'path':EVENT/CONFIG['covers'][kind]}) if CONFIG else pdf_asset({'path':resolve_asset('engine.svg' if kind=='study' else 'geometry-default.svg')})
    cover_art=SRC/'cover-art.json'
    cover_spec=json.loads(cover_art.read_text()).get(kind) if cover_art.exists() else None
    if cover_spec: hero=pdf_asset({'path':EVENT/cover_spec['path']})
    question=CONFIG.get('cover_questions',{}).get(kind, 'Where does the energy go?' if kind=='study' else 'What makes an improvement repeatable?')
    purpose=('Connect organisms, environmental measurements, and competing explanations.' if CONFIG else 'Follow a system boundary, explain a mechanism, and test your reasoning.') if kind=='study' else 'Connect each design choice to a prediction, a safe test, and a clear record of evidence.'
    cover=r'\manualcover{'+tx(EVENT_NAME)+'}{'+tx(title)+'}{'+tx(description)+'}{'+hero.as_posix()+'}{'+tx(question)+'}{'+tx(purpose)+'}\n'
    if cover_spec or kind in CONFIG.get('image_led_covers', []):
        cover=cover.replace(r'\manualcover', r'\imageledcover')
    pre+=r'''\fancyfoot[L]{\sffamily\fontsize{8}{10}\selectfont\color{Muted}'''+tx(EVENT_NAME)+' · '+tx(EVENT_YEAR)+r'''\\{\fontsize{6.3}{8}\selectfont\sosocredit}}
\setcounter{tocdepth}{1}
\widowpenalty=10000\clubpenalty=10000
\hypersetup{pdftitle={'''+tx(EVENT_NAME)+' '+tx(EVENT_YEAR)+' '+tx(title)+r'''}}
\begin{document}
'''+cover+r'''\section*{Explore, explain, and test}
Read each figure with its caption and the explanation beside it. Try the questions before turning to the reasoning at the back. '''+tx(CONFIG.get('interactive_descriptions',{}).get(kind,'The companion offline web guide contains adjustable geometry and heat-flow models, each with its assumptions visible.'))+r'''

Use the official '''+tx(EVENT_YEAR)+r''' rules and tournament clarifications alongside this independent guide. A drawing or model is not a safety, performance, or rules-compliance certificate.

\readerguide
\begingroup\small\setlength{\parskip}{1pt}
\section*{Contents}\begin{multicols}{2}\makeatletter\@starttoc{toc}\makeatother\end{multicols}
\endgroup
\clearpage
'''
    out=pre
    for chapter,ds in chapters(lessons):
        head='\\chapterlabel{'+tx(chapter)+'}\n'
        out+=''.join(lesson_tex(d,figmap[d['id']],head if i==0 else '') for i,d in enumerate(ds))
    for d in lessons:
        if d.get('worksheet'):out+=worksheet_tex(d['worksheet'],tx)
    out+=backmatter_tex(lessons)+r'\end{document}'+'\n'
    tex=BUILD/(kind+'-guide.tex');tex.write_text(out);return compile_tex(tex)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--web-only',action='store_true');parser.add_argument('--allow-missing',action='store_true');args=parser.parse_args()
    for p in [WEB,BUILD,OUT/'research']:p.mkdir(parents=True,exist_ok=True)
    diagram_generator=SRC/'diagrams/generate.py'
    if diagram_generator.is_file():
        subprocess.run([sys.executable,str(diagram_generator),'--output',str(GENERATED_DIAGRAMS)],check=True)
    registry=load_sources();prepare_interactive_assets();bundles=[]
    for kind,name,title,description in SPECS:
        p=SRC/name
        if not p.exists():MISSING.append('guide source: '+str(p));continue
        lessons,meta=load_guide(p)
        if kind=='study' and CONFIG.get('atlas'):
            atlas=load_atlas(EVENT,CONFIG['atlas'])
            supplemental=load_supplemental(EVENT,CONFIG['supplemental_images']) if CONFIG.get('supplemental_images') else []
            for row in atlas['organisms']:
                lesson={'id':'water-id-'+row['id'],'chapter':'Reef identification atlas','title':row['name'],'deck':row['scientific_name'],'panels':[['Recognize',row['diagnostic']],['Ecology and interpretation',row['ecology']],['Life cycle and event grouping',row['life_cycle']+' '+row['region']+'. Event groupings are not exhaustive geographic ranges.']],'question':row['question'],'answer':row['answer'],'sources':row.get('sources',[])}
                if row.get('image'):
                    lesson['figure']={'file':row['image'],'caption':row['caption'],'alt':row['alt'],'width_pt':245,'height_pt':190}
                    lesson['paired_panels']=3
                    credit='image-'+row['id']
                    REG[credit]={'id':credit,'title':row['source_title'],'url':row['image_source'],'note':row['caption']+' Changes: '+row['source_changes'],'license_url':row['image_license_url']}
                    lesson['sources']=list(lesson['sources'])+[credit]
                for photo in supplemental:
                    if photo['organism_id'] != row['id']:continue
                    caption=photo['caption']+' '+photo['credit']+'.'
                    lesson.setdefault('figures', []).append({'file':photo['path'],'caption':caption,'alt':photo['alt'],'width_pt':300,'height_pt':185,'after_panel':2})
                    credit='image-'+photo['id']
                    REG[credit]={'id':credit,'title':photo['source_title'],'url':photo['description_url'],'note':caption+' Changes: '+photo['source_changes'],'license_url':photo['license_url']}
                    lesson['sources'].append(credit)
                lessons.append(lesson)
        figmap={d['id']:normalize_figures(d) for d in lessons}
        bundles.append((kind,meta.get('title',title),meta.get('description',description),lessons,figmap))
        for d in lessons:
            for sid in source_ids(d):
                if sid not in REG:MISSING.append('source: '+sid)
    if MISSING and not args.allow_missing:raise SystemExit('Missing required inputs:\n'+'\n'.join(sorted(set(MISSING))))
    if MISSING:WARNINGS.extend(sorted(set(MISSING)))
    shutil.copy2(SHARED/'thermo-style.css',WEB/'style.css');shutil.copy2(SHARED/'thermo-interactions.js',WEB/'guide.js')
    outputs=[]
    for kind,title,description,lessons,figmap in bundles:
        outputs.append(str(render_web(kind,title,description,lessons,figmap)))
        if not args.web_only:outputs.append(str(render_pdf(kind,title,description,lessons,figmap)))
        RECORDS.append({'kind':kind,'lesson_count':len(lessons),'panel_count':sum(len(panels(d)) for d in lessons),'questions':sum(bool(d.get('question')) for d in lessons),'answers':sum(d.get('answer') is not None for d in lessons),'figure_placements':sum(len(v) for v in figmap.values()),'ids':[d['id'] for d in lessons]})
    render_landing([(kind,title,description,len(lessons)) for kind,title,description,lessons,figmap in bundles])
    report={'outputs':outputs,'guides':RECORDS,'source_registry':str(registry) if registry else None,'missing_inputs':sorted(set(MISSING)),'warnings':WARNINGS,'offline':True,'publication':False}
    (OUT/'research/render-manifest.json').write_text(json.dumps(report,indent=2)+'\n')
    print('\n'.join(outputs));print('Warnings:',len(WARNINGS))

if __name__=='__main__':main()
