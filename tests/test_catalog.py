#!/usr/bin/env python3
"""Static catalog, scoped web finish and package checks."""
from pathlib import Path
from html.parser import HTMLParser
import os,re,sys,tempfile,unittest
from soso.site import build_catalog as catalog, package_distributions as packages
from soso.site.event_registry import load as load_registry
REPO = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get('SO_PROJECT_ROOT', REPO))
class Links(HTMLParser):
 def __init__(self,text):
  super().__init__();self.links=[];self.heads=[];self.h1=[];self.table=False;self.current=None;self.feed(text)
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='a':self.links.append(a.get('href',''))
  if tag=='table':self.table=True
  if tag=='h1' or (tag=='th' and a.get('scope')=='col'):self.current=tag
 def handle_endtag(self,tag):
  if tag==self.current:self.current=None
 def handle_data(self,text):
  if self.current=='th':self.heads.append(text)
  if self.current=='h1':self.h1.append(text)
class YearGroups(HTMLParser):
 def __init__(self,text):
  super().__init__();self.groups=[];self.group=None;self.row=None;self.link=None;self.capture=None;self.buffer=[];self.in_body=False;self.feed(text)
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='details':
   self.group={'open':'open' in a,'years':[],'headers':[],'rows':[],'heading_ids':[],'table_labels':[]};self.groups.append(self.group)
  if self.group is None:return
  if tag=='h2':self.capture='year';self.buffer=[];self.group['heading_ids'].append(a.get('id'))
  if tag=='table':self.group['table_labels'].append(a.get('aria-labelledby'))
  if tag=='tbody':self.in_body=True
  if tag=='tr' and self.in_body:self.row={'event':'','links':[]}
  if tag=='th':self.capture='event' if a.get('scope')=='row' else 'header';self.buffer=[]
  if tag=='a' and self.row is not None and self.capture!='event':
   self.link={'href':a.get('href'),'label':'','aria':a.get('aria-label')};self.capture='link';self.buffer=[]
 def handle_data(self,text):
  if self.capture:self.buffer.append(text)
 def handle_endtag(self,tag):
  if self.group is None:return
  if tag in ['h2','th','a'] and self.capture and not (tag=='a' and self.capture=='event'):
   text=''.join(self.buffer).strip()
   if self.capture=='year':self.group['years'].append(text)
   elif self.capture=='header':self.group['headers'].append(text)
   elif self.capture=='event':self.row['event']=text
   elif self.capture=='link':self.link['label']=text;self.row['links'].append(self.link)
   self.capture=None;self.buffer=[]
  if tag=='tr' and self.row is not None:self.group['rows'].append(self.row);self.row=None
  if tag=='tbody':self.in_body=False
  if tag=='details':self.group=None

class DisplayText(HTMLParser):
 VOID={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
 def __init__(self,text):super().__init__();self.stack=[];self.nodes=[];self.elements=[];self.feed(text)
 def handle_starttag(self,tag,attrs):
  attrs=dict(attrs)
  self.elements.append((tag,attrs))
  if tag not in self.VOID:self.stack.append((tag,attrs))
 def text_of(self,attrs):
  return ' '.join(''.join(text for stack,text in self.nodes if any(a is attrs for _,a in stack)).split())
 def handle_endtag(self,tag):
  for i in range(len(self.stack)-1,-1,-1):
   if self.stack[i][0]==tag:self.stack=self.stack[:i];break
 def handle_data(self,text):
  if self.stack and not any(tag in ['head','script','style'] for tag,_ in self.stack):self.nodes.append((self.stack.copy(),text))

class CatalogTests(unittest.TestCase):
 def test_edition_order_and_format_links(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   event={'slug':'sample-b','year':'2027','name':'Sample B','path':'events/sample-b/2027','documents':{'study':{'interactive':'web/index.html','pdf':'study.pdf'},'build':{'pdf':'build.pdf'},'exam':{'pdf':'exam.pdf'}}}
   for editions in event['documents'].values():
    for filename in editions.values():
     path=root/event['path']/filename;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('')
   page=DisplayText(catalog.catalog(root,[event]))
   labels=[page.text_of(attrs) for _,attrs in page.elements if 'resource-format' in attrs.get('class','').split()]
   self.assertEqual(labels,['Interactive','PDF','Interactive','PDF','PDF'])
   for web in (False,True):
    landing=DisplayText(catalog.event_landing(root,event,web))
    actions=[(landing.text_of(attrs),attrs['href']) for tag,attrs in landing.elements
             if tag=='a' and 'edition-action' in attrs.get('class','').split()]
    source=event['path']+('/web/index.html' if web else '/index.html')
    expected=[(label,catalog.href(source,event['path']+'/'+filename)) for label,filename in
              [('Interactive','web/index.html'),('PDF','study.pdf'),('PDF','build.pdf'),('PDF','exam.pdf')]]
    self.assertEqual(actions,expected)
 def test_catalog_branding_and_portable_license_links(self):
  page=catalog.catalog(ROOT,catalog.discover(ROOT))
  self.assertIn('SOSO · Science Olympiad Study Omnibrary',page)
  self.assertIn('Not affiliated with or endorsed by Science Olympiad.',page)
  self.assertNotIn('Start with understanding.',page)
  self.assertNotIn('Learn. Explore. Compete.',page)
  self.assertNotIn('Build understanding with study guides',page)
  self.assertEqual(Links(page).h1,['Events'])
  self.assertIn('Check the current official rules for your event.',page)
  self.assertIn('LICENSE.md',Links(page).links)
  self.assertFalse(any(link.startswith('/') for link in Links(page).links))
  for event in catalog.discover(ROOT):
   for web,prefix in [(False,'../../../'),(True,'../../../../')]:
    self.assertFalse(any(link.endswith('LICENSE.md') for link in Links(catalog.event_landing(ROOT,event,web)).links))
 @unittest.skipUnless(catalog.discover(ROOT), "Integration check: set SO_PROJECT_ROOT to a generated candidate tree")
 def test_current_catalog_complete_and_year_first(self):
  events=catalog.discover(ROOT)
  registered=load_registry(REPO)
  self.assertEqual({e['path'] for e in events},{e['path'] for e in registered})
  outputs=catalog.generated(ROOT);page=Links(outputs['index.html'])
  years=sorted({str(e['year']) for e in registered},key=int,reverse=True)
  self.assertTrue(page.table)
  self.assertEqual(page.heads,['Event','Study guide','Build guide','Exam reference']*len(years))
  groups=YearGroups(outputs['index.html']).groups
  self.assertEqual([(g['years'],g['open']) for g in groups],[([year],i==0) for i,year in enumerate(years)])
  expected=[]
  for event in registered:
   for editions in event.get('documents',{}).values():
    for name in editions.values():
     target=event['path']+'/'+name
     self.assertTrue((ROOT/target).is_file(),'Missing registered document: '+target)
     expected.append(target)
  self.assertEqual(sorted(x for x in page.links if x.startswith('events/') and x not in [e['path']+'/index.html' for e in events]),sorted(expected))
  for event in events:
   landing=outputs[event['path']+'/index.html'];parsed=Links(landing)
   self.assertEqual(parsed.h1,[event['year']+' '+event['name']])
   self.assertNotRegex(landing,r'(?i)unchanged|revision|[0-9]+ pages|open the offline')
   if any('interactive' in ed for ed in event.get('documents',{}).values()):self.assertIn('>Interactive</a>',landing)
   if 'exam' in event.get('documents',{}):self.assertIn('<h2>Exam reference</h2>',landing)
  for name,text in outputs.items():
   self.assertEqual((ROOT/name).read_text(),text,'Regeneration is not idempotent: '+name)
 def test_discovery_ignores_unbuilt_and_handles_new_year(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);(root/'events/future-b/2028').mkdir(parents=True);(root/'events/future-b/2028/README.md').write_text('Not built')
   self.assertEqual(catalog.discover(root),[])
   (root/'events/future-b/2028/web').mkdir();(root/'events/future-b/2028/web/index.html').write_text('<h1>Built</h1>')
   events=catalog.discover(root);self.assertEqual([(e['year'],e['name']) for e in events],[('2028','Future B')])
   page=Links(catalog.catalog(root,events));self.assertIn('events/future-b/2028/web/index.html',page.links)
 def test_year_sections_direct_resources_and_collapsed_history(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   fixtures={
    'events/beta-b/2028':['study-guide.pdf','build-guide.pdf'],
    'events/alpha-b/2028':['web/index.html'],
    'events/old-b/2026':['exam-reference.pdf','study-guide.pdf','web/index.html'],
    'events/older-b/2025':['build-guide.pdf'],
    'events/not-built-b/2029':['README.md']}
   for base,names in fixtures.items():
    for name in names:
     path=root/base/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('Temporary discovery fixture')
   entries=catalog.discover(root)
   # Reverse input to prove grouping/default expansion does not rely on caller order.
   text=catalog.catalog(root,list(reversed(entries)));groups=YearGroups(text).groups
   self.assertEqual([g['years'] for g in groups],[['2028'],['2026'],['2025']])
   self.assertEqual([g['open'] for g in groups],[True,False,False])
   self.assertNotIn('2029',text)
   self.assertEqual([[r['event'] for r in g['rows']] for g in groups],[['Alpha B','Beta B'],['Old B'],['Older B']])
   for group in groups:
    self.assertEqual(group['headers'],['Event','Study guide','Build guide','Exam reference'])
    self.assertEqual(group['table_labels'],group['heading_ids'])
    for row in group['rows']:
     for link in row['links']:
      self.assertTrue((root/link['href']).is_file(),link)
      self.assertTrue(link['aria'].startswith(group['years'][0]+' '+row['event']+' — '))
      self.assertTrue(link['aria'].endswith(link['label']))
      self.assertTrue(link['href'].endswith(('.pdf','/web/index.html')))
   self.assertEqual([l['label'] for l in groups[0]['rows'][0]['links']],['Study guide Interactive'])
   self.assertEqual([l['label'] for l in groups[0]['rows'][1]['links']],['Study guide PDF','Build guide PDF'])
   self.assertEqual([l['label'] for l in groups[1]['rows'][0]['links']],['Study guide Interactive','Study guide PDF','Exam reference PDF'])
   self.assertEqual([l['label'] for l in groups[2]['rows'][0]['links']],['Build guide PDF'])
 def test_unavailable_guides_preserve_slots_without_links(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);path=root/'events/example-b/2027/study-guide.pdf'
   path.parent.mkdir(parents=True);path.write_text('fixture')
   html=catalog.catalog(root,catalog.discover(root))
   page=DisplayText(html)
   slots=[page.text_of(attrs) for _,attrs in page.elements if 'resource-title' in attrs.get('class','').split()]
   formats=[page.text_of(attrs) for _,attrs in page.elements if 'resource-format' in attrs.get('class','').split()]
   self.assertEqual(list(zip(slots,formats)),[
    ('Study guide','Interactive'),('Study guide','PDF'),
    ('Build guide','Interactive'),('Build guide','PDF'),('Exam reference','PDF')])
   disabled=[(tag,page.text_of(attrs)) for tag,attrs in page.elements if attrs.get('aria-disabled')=='true']
   self.assertEqual(len(disabled),4)
   for tag,label in disabled:
    self.assertNotEqual(tag,'a')
    self.assertIn('not available',label.lower())
   headers=[page.text_of(attrs) for tag,attrs in page.elements if tag=='th' and attrs.get('scope')=='col']
   self.assertEqual(headers,['Event','Study guide','Build guide','Exam reference'])
   self.assertEqual([link for link in Links(html).links if link.startswith('events/') and not link.endswith('/2027/index.html')],
                    ['events/example-b/2027/study-guide.pdf'])
 def test_empty_catalog_does_not_invent_years_or_documents(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);text=catalog.catalog(root,catalog.discover(root))
   self.assertEqual(YearGroups(text).groups,[])
   self.assertFalse(any(link.startswith('events/') for link in Links(text).links))
 @unittest.skipUnless(catalog.discover(ROOT), "Integration check: set SO_PROJECT_ROOT to a generated candidate tree")
 def test_scoped_web_finish_preserves_controls(self):
  for event in catalog.discover(ROOT):
   base=ROOT/event['path']
   for path in (base/'web').rglob('*.html'):
    text=path.read_text();self.assertIn(event['year']+' '+event['name'],text)
    again=catalog.normalise_page(ROOT,event,path.relative_to(base).as_posix(),text)
    self.assertEqual(text,again)
    self.assertEqual(re.findall(r'\bid="([^"]+)"',text),re.findall(r'\bid="([^"]+)"',again))
 @unittest.skipUnless(catalog.discover(ROOT), "Integration check: set SO_PROJECT_ROOT to a generated candidate tree")
 def test_interactive_event_year_is_in_first_header_only(self):
  for event in catalog.discover(ROOT):
   for page in (ROOT/event['path']/'web').rglob('*.html'):
    nodes=DisplayText(page.read_text()).nodes
    brands=[(stack,text) for stack,text in nodes if 'brand' in stack[-1][1].get('class','').split()]
    self.assertEqual(len(brands),1,str(page))
    stack,text=brands[0]
    self.assertTrue(any(tag=='header' for tag,_ in stack))
    self.assertEqual(text,event['year']+' '+event['name'])
    for stack,text in nodes:
     tag,attrs=stack[-1]
     if tag=='h1' or 'eyebrow' in attrs.get('class','').split() or 'edition' in attrs.get('class','').split():
      self.assertNotIn(event['year'],text,(page,tag,text))
     if tag=='footer' and text.startswith(event['name']):self.assertNotIn(event['year'],text)
 @unittest.skipUnless(catalog.discover(ROOT), "Integration check requires generated site")
 def test_reader_navigation_and_model_prominence(self):
  for event in catalog.discover(ROOT):
   base=ROOT/event['path']
   for page in (base/'web').rglob('*.html'):
    text=page.read_text();self.assertIn('data-soso-home',text)
    self.assertNotIn('aria-label="Companion guides"',text)
    self.assertNotIn('id="guide-return-nav"',text)
   if event.get('models'):
    landing=catalog.event_landing(ROOT,event)
    for model in event['models']:
     self.assertIn(catalog.href(event['path']+'/index.html',event['path']+'/'+model['path']),Links(landing).links)
 def test_thermodynamics_guides_keep_models_prominent(self):
  # This is a renderer-specific convention, not a requirement of model metadata.
  event=next(e for e in catalog.discover(ROOT) if e['path']=='events/thermodynamics-b/2027')
  for kind in ('study','build'):
   text=(ROOT/event['path']/event['documents'][kind]['interactive']).read_text()
   page=DisplayText(text)
   links=[page.text_of(attrs) for tag,attrs in page.elements if tag=='a' and attrs.get('href')=='#explorers']
   self.assertIn('Explore the models',links)
   ids=[attrs.get('id') for _,attrs in page.elements]
   first_chapter=next(i for i,value in enumerate(ids) if value and value.startswith('chapter-'))
   self.assertLess(ids.index('explorers'),first_chapter)
 def test_generated_thermodynamics_has_no_old_blanket_lid_ban(self):
  pages=list((ROOT/'events/thermodynamics-b/2027/web').rglob('*.html'))
  self.assertTrue(pages,'Expected generated Thermodynamics pages; run with SO_PROJECT_ROOT pointing to build/candidates')
  banned=('post-setup adjustments are not part of the allowed procedure','a lid opened or a latch reset','without moving or adjusting the device','Do not assume a movable greenhouse lid is legal','only cup insertion and removal are allowed')
  for page in pages:
   text=page.read_text()
   for phrase in banned:self.assertNotIn(phrase,text,str(page))
 def test_display_finish_preserves_scientific_dates_citations_and_metadata(self):
  event={'slug':'solar-system-b','year':'2099','name':'Solar System B','path':'events/solar-system-b/2099'}
  title='<title>Solar System B 2099: sources checked 2099</title>'
  source='<p class="source-title">Science Olympiad 2099 Division B Rules</p>'
  science='<p id="launch-2099">A mission launches in 2099; use the official 2099 rules.</p>'
  link='<a href="science-2099.html#launch-2099" data-label="Solar System B 2099">Flight in 2099</a>'
  raw='<html><head>'+title+'<meta content="2099" name="edition"></head><body><header class="topbar"><a class="brand" href="#introduction">Solar System B</a><span class="edition">2099 · Illustrated study guide</span></header><section class="hero" id="introduction"><h1>2099 Solar System B</h1></section><article class="lesson" id="foundation-1"><p class="deck">2099 • A visual investigation</p></article>'+science+source+link+'<h2>The 2099 flyby</h2><footer class="footer">Solar System B · 2099. Independent material.</footer><footer>Rule basis: 2099 manual.</footer></body></html>'
  result=catalog.normalise_page(ROOT,event,'web/index.html',raw)
  for preserved in [title,source,science,link,'<meta content="2099" name="edition">','<h2>The 2099 flyby</h2>','<footer>Rule basis: 2099 manual.</footer>']:
   self.assertIn(preserved,result)
  self.assertIn('>2099 Solar System B</a>',result)
  self.assertIn('<h1>Solar System B</h1>',result)
  self.assertIn('<p class="deck">A visual investigation</p>',result)
  self.assertIn('<footer class="footer">Solar System B. Independent material. <span class="affiliation-notice">Not affiliated with or endorsed by Science Olympiad.</span></footer>',result)
  self.assertEqual(result.count('Not affiliated with or endorsed by Science Olympiad.'), 1)
  self.assertEqual(result,catalog.normalise_page(ROOT,event,'web/index.html',result))
 @unittest.skipUnless(catalog.discover(ROOT), "Integration check: set SO_PROJECT_ROOT to a generated candidate tree")
 def test_runtime_archives_have_current_pdfs_and_no_broken_local_files(self):
  for event in catalog.discover(ROOT):
   files=packages.runtime(ROOT,event)
   for name,data in packages.license_files(ROOT).items():self.assertEqual(files[name],data)
   self.assertIn('LICENSE.md',Links(files['index.html'].decode()).links)
   self.assertIn('index.html',files)
   for editions in catalog.editions(ROOT,event).values():
    if 'pdf' in editions:
     name=editions['pdf']
     self.assertEqual(files[name],(ROOT/event['path']/name).read_bytes())
   for name,data in files.items():
    if name.endswith('.html'):
     page=Links(data.decode())
     for link in page.links:
      if re.match(r'[a-z]+:|#',link):continue
      local=link.partition('#')[0]
      if local:self.assertIn(os.path.normpath(str(Path(name).parent/local)),files,(name,link))
   self.assertEqual(packages.zipped(files),packages.zipped(files))
   with tempfile.TemporaryDirectory() as directory:
    out=Path(directory)/'event.zip';out.write_bytes(packages.zipped(files));self.assertEqual(packages.verify(out),len(files)-1)
if __name__=='__main__':unittest.main(verbosity=2)

