"""Generate the reader catalog, event landing pages, and web-only header finish."""
from pathlib import Path
from html.parser import HTMLParser
import argparse,html,os,re,hashlib,json
from urllib.parse import quote
ROOT=Path(__file__).resolve().parents[2]
PDFS=[("study-guide.pdf","Study PDF"),("build-guide.pdf","Build PDF"),("exam-reference.pdf","Exam reference")]
def esc(text):return html.escape(str(text),quote=True)
def href(source,target):return quote(os.path.relpath(target,str(Path(source).parent)).replace(os.sep,"/"),safe="/.-")
def discover(root, registry_root=None):
 result=[]
 metadata={}
 source=Path(registry_root) if registry_root is not None else Path(root)
 if (source/'manifests/events.json').is_file():
  from .event_registry import load
  metadata={e['path']:e for e in load(source)}
 elif (Path(root)/'catalog-data.json').is_file():
  metadata={e['path']:e for e in json.loads((Path(root)/'catalog-data.json').read_text())['events']}
 for folder in (Path(root)/"events").glob("*/*"):
  if folder.is_dir() and not folder.is_symlink() and re.fullmatch(r"\d{4}",folder.name):
   if folder.relative_to(root).as_posix() in metadata or (folder/"web/index.html").is_file() or any((folder/name).is_file() for name,_ in PDFS):
    record=metadata.get(folder.relative_to(root).as_posix(),{})
    result.append({**record,"division":record.get("division",folder.parent.name.rsplit("-",1)[-1].upper()),"slug":folder.parent.name,"year":folder.name,"name":record.get("name",folder.parent.name.replace("-"," ").title()),"path":folder.relative_to(root).as_posix()})
 return sorted(result,key=lambda e:(-int(e["year"]),e["name"]))
def shell(title,body,css,back=None,brand=None):
 license_link=' <a href="LICENSE.md">Licensing &amp; exceptions</a>' if not back and not brand else ''
 nav='<span class="site-name brand">'+esc(brand)+'</span>' if brand else '<a class="back-link" href="'+esc(back)+'">All events</a>' if back else '<a class="site-identity" href="index.html" aria-label="SOSO home"><span class="wordmark">so<span>so</span></span><span class="site-name">Science Olympiad<br>Study Omnibrary</span></a>'
 return '<!doctype html>\n<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="Independent Science Olympiad study guides, interactive explorations, and exam references. Learn the ideas, test your understanding, and prepare for your event."><title>'+esc(title)+'</title><link rel="stylesheet" href="'+esc(css)+'"></head><body class="reader-catalog"><a class="skip-link" href="#main">Skip to content</a><div class="reader-shell"><header class="site-header">'+nav+'</header><main id="main">'+body+'</main><footer class="reader-footer"><p>Independent learning materials. Not affiliated with or endorsed by Science Olympiad. Check the current official rules for your event.</p><p>Original educational content: CC BY 4.0 · Code: Apache 2.0.'+license_link+'</p></footer></div></body></html>\n'
DOCUMENTS=[('study','Study guide','Concepts, worked examples and practice.'),('build','Build guide','Design choices, measurements and testing.'),('exam','Exam reference','A compact reference for quick lookup.')]
def editions(root,event):
 if 'documents' in event:return event['documents']
 # Compatibility for generated snapshots without source metadata.
 base=Path(root)/event['path']
 return {'study':{'pdf':'study-guide.pdf','interactive':'web/study-guide.html' if (base/'web/study-guide.html').is_file() else 'web/index.html'},'build':{'pdf':'build-guide.pdf','interactive':'web/build-guide.html'},'exam':{'pdf':'exam-reference.pdf'}}
def catalog(root,entries):
 years=sorted({e['year'] for e in entries},key=int,reverse=True)
 sections=[]
 for number,year in enumerate(years):
  rows=[]
  for event in sorted((e for e in entries if e['year']==year),key=lambda e:e['name']):
   base=Path(root)/event['path']
   documents=editions(root,event)
   cells=[]
   for kind,group,_ in DOCUMENTS:
    resources=[(documents.get(kind,{}).get(fmt),label) for fmt,label in [('interactive','Interactive'),('pdf','PDF')] if kind!='exam' or fmt=='pdf']
    links=[]
    for name,label in resources:
     target=event['path']+'/'+name if name else ''
     description=year+' '+event['name']+' — '+group+' '+label
     button='<span class="resource-title">'+esc(group)+'</span> <span class="resource-format">'+label+'</span>'
     if target and (Path(root)/target).is_file():
      links.append('<a href="'+esc(quote(target,safe='/.-'))+'" aria-label="'+esc(description)+'">'+button+'</a>')
     else:
      links.append('<span class="resource-unavailable" aria-disabled="true" title="Not available">'+button+'<span class="visually-hidden"> ('+esc(group)+' not available)</span></span>')
    cells.append('<td><span class="mobile-guide-label" aria-hidden="true">'+group+'</span><div class="resource-links">'+''.join(links)+'</div></td>')
   rows.append('<tr><th scope="row" class="event-name">'+'<a href="'+esc(event['path']+'/index.html')+'">'+esc(event['name'])+'</a></th>'+''.join(cells)+'</tr>')
  heading='year-'+year
  sections.append('<details class="year-group"'+(' open' if number==0 else '')+'><summary><h2 class="year-heading" id="'+heading+'">'+esc(year)+'</h2></summary><table class="event-table" aria-labelledby="'+heading+'"><thead><tr><th scope="col"><span class="visually-hidden">Event</span></th><th scope="col"><span class="visually-hidden">Study guide</span></th><th scope="col"><span class="visually-hidden">Build guide</span></th><th scope="col"><span class="visually-hidden">Exam reference</span></th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></details>')
 body='<div class="page-heading"><h1>Events</h1></div>'+''.join(sections)
 return shell("SOSO · Science Olympiad Study Omnibrary",body,"shared/reader-navigation.css")
def site_nav(home,event_url=None,label=None):
 nav='<a class="soso-home" data-soso-home href="'+esc(home)+'" aria-label="SOSO main page">SOSO</a>'
 if label:nav+='<a class="brand" href="'+esc(event_url)+'">'+esc(label)+'</a>'
 return '<nav class="soso-nav" aria-label="Site navigation">'+nav+'</nav>'
def model_cards(event,source):
 cards=[]
 for model in event.get('models',[]):
  target=href(source,event['path']+'/'+model['path'])
  cards.append('<a href="'+esc(target)+'"><strong>'+esc(model['title'])+'</strong><span>'+esc(model.get('description',''))+'</span></a>')
 return '<section class="model-panel"><h2>Explore the models</h2><div class="model-cards">'+''.join(cards)+'</div><p>Explanatory models, not measured device performance.</p></section>' if cards else ''
def event_landing(root,event,web=False):
 base=Path(root)/event['path'];source=event['path']+('/web/index.html' if web else '/index.html')
 heading=event['year']+' '+event['name'];prefix='' if web else 'web/'
 body='<div class="page-heading"><p class="eyebrow">Division '+esc(event.get('division','B'))+'</p><h1>'+esc(event['name'] if web else heading)+'</h1></div>'
 cards=[]
 for kind,title,description in DOCUMENTS:
  links=[]
  for fmt,label in [('interactive','Interactive'),('pdf','PDF')]:
   filename=editions(root,event).get(kind,{}).get(fmt)
   if filename and (base/filename).is_file():links.append('<a class="edition-action edition-'+fmt+'" href="'+esc(href(source,event['path']+'/'+filename))+'">'+label+'</a>')
  if links:cards.append('<section class="event-guide"><h2>'+title+'</h2><p>'+description+'</p><div class="edition-actions">'+''.join(links)+'</div></section>')
 body+='<div class="event-guides">'+''.join(cards)+'</div>'
 body+=model_cards(event,source)
 page=shell(heading,body,'navigation.css' if web else '../../../shared/reader-navigation.css',None if web else '../../../index.html',heading if web else None)
 nav=site_nav('../../../../index.html' if web else '../../../index.html','../index.html' if web else 'index.html',heading)
 return re.sub(r'(<header class="site-header">).*?(</header>)',lambda m:m[1]+nav+m[2],page,flags=re.S)
def portable_navigation(text):
 """Event-only downloads keep their event home and make the global catalog online."""
 return re.sub(r'(<a\b[^>]*data-soso-home[^>]*href=")[^"]+("[^>]*>)',r'\1https://greghogan.github.io/soso/\2',text).replace('aria-label="SOSO main page"','aria-label="SOSO main page (online)" title="Online catalog; requires internet"')
def reader_labels(event,text):
 """Edit only known display text nodes, preserving science, attributes and metadata."""
 year=event['year'];name=event['name'];heading=year+' '+name
 class Labels(HTMLParser):
  VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
  def __init__(self):
   super().__init__(convert_charrefs=False);self.stack=[];self.changes=[]
   self.lines=[0]
   for match in re.finditer('\n',text):self.lines.append(match.end())
  def handle_starttag(self,tag,attrs):
   if tag not in self.VOID:self.stack.append((tag,dict(attrs)))
  def handle_startendtag(self,tag,attrs):pass
  def handle_endtag(self,tag):
   for i in range(len(self.stack)-1,-1,-1):
    if self.stack[i][0]==tag:self.stack=self.stack[:i];break
  def handle_data(self,data):
   if not self.stack:return
   tag,attrs=self.stack[-1];classes=attrs.get('class','').split();value=data
   if tag=='span' and 'edition' in classes:
    value=re.sub(r'^'+re.escape(year)+r'\s*·\s*','',value)
   if tag=='p' and 'eyebrow' in classes:
    division=event.get('division','')
    labels={'Science Olympiad · Division '+division+' · '+year:'Science Olympiad · Division '+division}
    for kind in ['Build','Model']:
     labels[heading+' · '+kind+' explorer']=kind+' explorer'
     labels[name.upper()+' '+year+' · '+kind.upper()+' EXPLORER']=kind+' explorer'
    value=labels.get(value,value)
   if tag=='h1' and any(set(a.get('class','').split())&{'hero','guide-heading'} for _,a in self.stack):
    if value in [heading,name+' '+year]:value=name
   if tag=='footer' and 'footer' in classes and value.startswith(name+' · '+year+'.'):
    value=value.replace(name+' · '+year+'.',name+'.',1)
   lesson=next((a.get('id') for t,a in reversed(self.stack) if t=='article' and 'lesson' in a.get('class','').split()),None)
   if tag=='p' and 'deck' in classes:
    if lesson=='foundation-1' and value.startswith(year+' • '):value=value[len(year+' • '):]
    if lesson=='thermo-overview' and value=='Study guide '+year:value='Study guide'
    if lesson=='thermo-build-mission' and value=='An engineering guide for the '+year+' hybrid event.':value='An engineering guide for the hybrid event.'
   if tag=='h4' and lesson=='thermo-overview' and value=='The '+year+' written test':value='The written test'
   if value!=data:
    line,column=self.getpos();start=self.lines[line-1]+column
    self.changes.append((start,start+len(data),value))
 parser=Labels();parser.feed(text)
 for start,end,value in reversed(parser.changes):text=text[:start]+value+text[end:]
 return text
def normalise_page(root,event,relative,text):
 heading=event["year"]+' '+event["name"]
 if relative=="web/index.html" and event.get("web_landing",False):return event_landing(root,event,True)
 if relative=='index.html':return event_landing(root,event)
 source=event['path']+'/'+relative
 nested=Path(relative).parent.as_posix()!='web'
 nav=site_nav(href(source,'index.html'),href(source,event['path']+'/index.html'),heading)
 text=re.sub(r'<nav\b[^>]*class="toplinks"[^>]*>.*?</nav>','',text,flags=re.S)
 text=re.sub(r'<nav\b[^>]*id="guide-return-nav"[^>]*>.*?</nav>','',text,flags=re.S)
 text=re.sub(r'<nav class="soso-nav".*?</nav>','',text,flags=re.S)
 text=re.sub(r'<a\b[^>]*class="brand"[^>]*>.*?</a>','',text,count=1,flags=re.S)
 if nested and 'class="model-header"' not in text:text=text.replace('<body>','<body><header class="model-header"></header>',1)
 text=re.sub(r'(<header\b[^>]*>)',lambda m:m[1]+nav,text,count=1)
 document=next(((kind,ed) for kind,ed in editions(root,event).items() if ed.get('interactive')==relative),None)
 if document and 'class="reading-links' in text:
  kind,ed=document
  actions='<div class="reading-links guide-tools">'
  if ed.get('pdf'):actions+='<a href="'+esc(href(source,event['path']+'/'+ed['pdf']))+'">'+kind.title()+' guide · PDF</a>'
  if 'id="explorers"' in text:actions+='<a href="#explorers">Explore the models</a>'
  actions+='</div>'
  text=re.sub(r'<div class="reading-links[^" ]*(?: [^"]*)?">.*?</div>',lambda m:actions,text,count=1,flags=re.S)
  # Bring the existing model section directly after the introduction, preserving IDs and links.
  match=re.search(r'<section class="explorers" id="explorers">.*?</section>',text,re.S)
  if match:
   models=match.group();text=text[:match.start()]+text[match.end():]
   text=re.sub(r'(<section class="guide-heading"[^>]*>.*?</section>)',lambda m:m[1]+models,text,count=1,flags=re.S)
 if event["slug"]=="solar-system-b":
  text=text.replace('<h1>How could a world support life?</h1>','<h1>'+esc(event['name'])+'</h1><p class="hero-question">How could a world support life?</p>')
 if event['slug']=='solar-system-b' and relative=='web/index.html' and 'class="reading-links guide-tools"' not in text:
  text=re.sub(r'(<section class="hero"[^>]*>.*?</h1>(?:<p class="hero-question">.*?</p>)?)',lambda m:m[1]+'<div class="reading-links guide-tools"><a href="../study-guide.pdf">Study guide · PDF</a></div>',text,count=1,flags=re.S)
 # Every standalone guide/model page retains the project affiliation notice.
 # Insert into an existing footer to avoid another rule or footer region.
 disclaimer='Not affiliated with or endorsed by Science Olympiad.'
 if disclaimer not in text:
  if '</footer>' in text:text=text.replace('</footer>',' <span class="affiliation-notice">'+disclaimer+'</span></footer>',1)
  else:text=text.replace('</body>','<footer class="footer"><p>'+disclaimer+'</p></footer></body>',1)
 text=reader_labels(event,text)
 def pdf_label(match):
  label=next((label for name,label in PDFS if match.group(2).partition('#')[0].endswith('/'+name) or match.group(2)==name),None)
  return match.group(1)+label+'</a>' if label else match.group(0)
 text=re.sub(r'(<a\b[^>]*href="([^"]+)"[^>]*>)([^<]*)</a>',pdf_label,text)
 css=href(source,event["path"]+"/web/navigation.css")
 if 'href="'+css+'"' not in text:text=text.replace("</head>",'<link rel="stylesheet" href="'+css+'"></head>',1)
 return text
def generated(root, registry_root=None):
 root=Path(root).resolve();events=discover(root,registry_root)
 css=(Path(__file__).parent/'catalog/navigation.css').read_text()
 public=[{k:v for k,v in event.items() if k in {"slug","year","name","division","path","documents","models","web_landing"}} for event in events]
 result={"shared/reader-navigation.css":css,"index.html":catalog(root,events),"catalog-data.json":json.dumps({"events":public},indent=2)+"\n"}
 for event in events:
  result[event["path"]+'/index.html']=event_landing(root,event)
  base=root/event["path"]
  if (base/'web').is_dir():
   result[event["path"]+'/web/navigation.css']=css
   for page in sorted((base/'web').rglob('*.html')):
    relative=page.relative_to(base).as_posix()
    result[page.relative_to(root).as_posix()]=normalise_page(root,event,relative,page.read_text())
 # Refresh existing web manifests against the regenerated files, excluding themselves.
 for event in events:
  web=root/event["path"]/'web'
  if (web/'MANIFEST.json').is_file():
   names={p.relative_to(web).as_posix() for p in web.rglob('*') if p.is_file() and p.name not in {'MANIFEST.json','.DS_Store'} and not p.name.endswith('-standalone.html')}
   prefix=event['path']+'/web/'
   names.update(name[len(prefix):] for name in result if name.startswith(prefix) and not name.endswith('/MANIFEST.json'))
   values={}
   for name in sorted(names):
    relative=prefix+name
    data=result[relative].encode('utf-8') if relative in result else (web/name).read_bytes()
    values[name]=hashlib.sha256(data).hexdigest()
   result[prefix+'MANIFEST.json']=json.dumps(values,indent=2)+'\n'
 return result
def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true')
 parser.add_argument('--project-root',type=Path,default=None,help='Generated catalog tree (default: build/direct)')
 args=parser.parse_args();root=(args.project_root or ROOT/'build/direct').resolve();changed=[]
 if root.is_relative_to(ROOT) and not root.is_relative_to(ROOT/'build') and os.environ.get('SOSO_STAGE_OUTPUTS')!='1':
  parser.error('Choose a generated tree under build/ or outside the source project')
 files=generated(root, ROOT if args.project_root is None else None)
 if args.project_root is None:
  for name in ('LICENSE.md','NOTICE','LICENSES/Apache-2.0.txt','LICENSES/CC-BY-4.0.txt','THIRD_PARTY_NOTICES.txt'):
   files[name]=(ROOT/name).read_text()
 for relative,text in files.items():
  path=root/relative
  if not path.is_file() or path.read_text()!=text:
   changed.append(relative)
   if not args.check:path.parent.mkdir(parents=True,exist_ok=True);path.write_text(text)
 print(("Out of date: " if args.check and changed else "Updated: " if changed else "Catalog and headers are current: ")+str(len(changed))+" files")
 if args.check and changed:raise SystemExit(1)
if __name__=='__main__':main()

