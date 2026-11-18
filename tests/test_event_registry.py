"""Registry routing is independent of event name, division and year."""
import json, tempfile, unittest
from pathlib import Path
from soso.site import event_registry as m, build_catalog as catalog
from soso.site import audit_pdf_typography as typography, build_standalone as standalone
ROOT=Path(__file__).resolve().parents[1]
class RegistryTests(unittest.TestCase):
 def fixture(self, root, slug='astronomy-c', year=2028):
  entry={'slug':slug,'year':year,'name':'Astronomy C','division':'C','build':[['source/build.py']], 'web_build':['source/build.py','--web-only'],'pdfs':['study-guide.pdf'],'site_assets':[]}
  (root/'manifests').mkdir(exist_ok=True)
  (root/'manifests/events.json').write_text(json.dumps({'events':[entry]}));return entry
 def test_third_event_and_year(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);self.fixture(root);e=m.load(root)[0]
   self.assertEqual(e['path'],'events/astronomy-c/2028')
   self.assertEqual(m.command(root,e,e['web_build'],'python'),['python',str(root/'events/astronomy-c/2028/source/build.py'),'--web-only'])
 def test_exam_reference_is_pdf_only(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);entry=self.fixture(root)
   for editions in ({'interactive':'web/reference.html'}, {'pdf':'reference.pdf','interactive':'web/reference.html'}):
    entry['documents']={'exam':editions}
    (root/'manifests').mkdir(exist_ok=True)
    (root/'manifests/events.json').write_text(json.dumps({'events':[entry]}))
    with self.assertRaisesRegex(ValueError,'PDF only'):m.load(root)
   entry['documents']={'exam':{'pdf':'reference.pdf'},'study':{'interactive':'web/learn.html'},'build':{'pdf':'build.pdf','interactive':'web/build.html'}}
   (root/'manifests').mkdir(exist_ok=True)
   (root/'manifests/events.json').write_text(json.dumps({'events':[entry]}))
   self.assertEqual(m.load(root)[0]['pdfs'],['reference.pdf','build.pdf'])
 def test_unsafe_and_duplicate(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);e=self.fixture(root);e['pdfs']=['../private.pdf']
   (root/'manifests').mkdir(exist_ok=True)
   (root/'manifests/events.json').write_text(json.dumps({'events':[e]}))
   with self.assertRaises(ValueError):m.load(root)
   e=self.fixture(root);(root/'manifests/events.json').write_text(json.dumps({'events':[e,e]}))
   with self.assertRaises(ValueError):m.load(root)
if __name__=='__main__':unittest.main()

class CatalogOnboardingTests(unittest.TestCase):
 def test_third_event_custom_editions_and_public_snapshot(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)
   entry={'slug':'astronomy-c','year':2028,'name':'Astronomy C','division':'C','build':[['source/render.py']], 'web_build':['source/render.py'],'documents':{'study':{'pdf':'print/notes.pdf','interactive':'web/learn.html'}},'models':[{'path':'web/models/orbit.html','title':'Orbit model','description':'Compare orbital periods.'}]}
   (root/'manifests').mkdir(exist_ok=True)
   (root/'manifests/events.json').write_text(json.dumps({'events':[entry]}))
   base=root/'events/astronomy-c/2028'
   for name in ['print/notes.pdf','web/learn.html','web/models/orbit.html']:
    p=base/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('<html><head></head><body><h1>Astronomy</h1></body></html>')
   self.assertEqual(m.load(root)[0]['pdfs'],['print/notes.pdf'])
   output=catalog.generated(root)
   direct=root/'build/direct'
   from shutil import copytree
   copytree(base,direct/'events/astronomy-c/2028')
   self.assertEqual(output,catalog.generated(direct,registry_root=root))
   self.assertFalse((base/'index.html').exists())
   landing=output['events/astronomy-c/2028/index.html']
   self.assertIn('Division C',landing)
   self.assertIn('print/notes.pdf',landing)
   self.assertIn('web/learn.html',landing)
   self.assertIn('Orbit model',landing)
   self.assertNotIn('geometry.html',landing)
   self.assertIn('2028',output['index.html'])
   self.assertNotIn('source/render.py',output['catalog-data.json'])
   # Exported site metadata must reproduce the same navigation without source files.
   (root/'catalog-data.json').write_text(output['catalog-data.json'])
   (root/'manifests/events.json').unlink()
   self.assertEqual(output,catalog.generated(root))

class RegistryConsumerTests(unittest.TestCase):
 def test_nested_pdf_audit_and_standalone_toolbar(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);base=root/'events/astronomy-c/2028'
   (base/'web').mkdir(parents=True);(base/'print').mkdir()
   (base/'web/index.html').write_text('<html><body>Test guide</body></html>')
   (base/'print/notes.pdf').write_bytes(b'%PDF-test')
   entry={'slug':'astronomy-c','year':2028,'name':'Astronomy C','division':'C','build':[['source/render.py']], 'web_build':['source/render.py'],'documents':{'study':{'pdf':'print/notes.pdf','interactive':'web/index.html'}}}
   (root/'manifests').mkdir(exist_ok=True)
   (root/'manifests/events.json').write_text(json.dumps({'events':[entry]}))
   self.assertEqual(typography.pdf_paths(root),[base/'print/notes.pdf'])
   # Isolate resource/toolbar selection from the separate catalog renderer.
   with patch.object(standalone,'normalise_page',side_effect=lambda root,event,path,text:text):
    bundle=standalone.Compiler(base,include_pdfs=True).compile()
   self.assertEqual(len(bundle['pdfs']),1)
   self.assertEqual(bundle['pdfs'][0]['name'],'Study guide')
   self.assertEqual(bundle['pdfs'][0]['filename'],'notes.pdf')
   self.assertIn('print/notes.pdf',bundle['sources'])

class ReferenceConstraintsTests(unittest.TestCase):
 def policy(self, **changes):
  p={'status':'allowed','medium':'paper','allocation':'team','sheet_limit':2,'sides_per_sheet':2,'paper_size':'US Letter','rule_source':'test rules'}
  p.update(changes);return {'reference_constraints':p}
 def test_current_allowances_and_allocation(self):
  events={e['slug']:e for e in m.load(ROOT)}
  self.assertEqual(m.reference_page_limit(events['solar-system-b']),4)
  self.assertIsNone(m.reference_page_limit(events['thermodynamics-b']))
  self.assertEqual(m.reference_page_limit(self.policy(allocation='participant',sheet_limit=1)),2)
 def test_unknown_is_not_unlimited_or_permission(self):
  for event in ({},self.policy(status='not_allowed'),{'reference_constraints':{'status':'not_applicable'}},{'reference_constraints':{'status':'unspecified'}}):
   with self.assertRaises(ValueError):m.reference_page_limit(event)
 def test_invalid_sheet_limits_rejected(self):
  for value in (0,-1,True,'2'):
   with self.assertRaises(ValueError):m.reference_page_limit(self.policy(sheet_limit=value))
  p=self.policy();del p['reference_constraints']['sheet_limit']
  with self.assertRaises(ValueError):m.reference_page_limit(p)

 def test_page_size_is_read_from_policy(self):
  letter=self.policy()
  self.assertEqual(m.reference_page_size_points(letter),(612,792))
  m.validate_reference_page_size(letter,612,792)
  m.validate_reference_page_size(letter,792,612)
  with self.assertRaises(ValueError):m.validate_reference_page_size(letter,595,842)
  unrestricted=self.policy(paper_size='any')
  self.assertIsNone(m.reference_page_size_points(unrestricted))
  m.validate_reference_page_size(unrestricted,595,842)
  with self.assertRaisesRegex(ValueError,'paper size'):m.reference_page_size_points(self.policy(paper_size='unknown'))
