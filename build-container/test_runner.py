"""Small offline checks; these do not pretend to execute Docker."""
import importlib.util
from pathlib import Path
import subprocess
import tempfile
import unittest
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('runner',HERE/'run_build.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
class ContainerRecipeTests(unittest.TestCase):
 def test_source_copy_excludes_host_environments_and_private_configuration(self):
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as t:
   source=Path(t)/'source';stage=Path(t)/'stage';source.mkdir()
   for name in ['.venv','venv']:
    interpreter=source/name/'bin/python';interpreter.parent.mkdir(parents=True)
    interpreter.symlink_to('/host-only-python-not-mounted-in-docker/python3')
   private=['.env','.env.local','.aws/credentials','.azure/accessTokens.json',
            '.ssh/id_ed25519','.config/gcloud/application_default_credentials.json',
            'assets/setup/storage-config.json','assets/cache/verification.json','assets/local-note','.cache/local-file']
   for name in private:
    path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('private fixture')
   # The verified original-image cache is intentionally a build input.
   original=source/'assets/cache/sha256/aa/original';original.parent.mkdir(parents=True)
   original.write_bytes(b'original image fixture')
   (source/'lesson.json').write_text('authored fixture')
   with patch.object(runner,'registry',return_value=[]):runner.copy_inputs(source,stage)
   self.assertEqual((stage/'lesson.json').read_text(),'authored fixture')
   self.assertEqual((stage/'assets/cache/sha256/aa/original').read_bytes(),original.read_bytes())
   for name in private+['.venv','venv']:
    self.assertFalse((stage/name).exists(),name)
 def test_source_copy_keeps_only_authored_web(self):
  with tempfile.TemporaryDirectory() as t:
   source=Path(t)/'source';stage=Path(t)/'stage'
   for name in ['shared/build_thermo.py','source.json','events/solar-system-b/2027/study-guide.pdf','events/solar-system-b/2027/exam-reference.pdf','events/thermodynamics-b/2027/source/interactives/runtime/geometry.html','events/thermodynamics-b/2027/source/interactives/runtime/heat-flow.html','events/thermodynamics-b/2027/source/interactives/runtime/geometry.js','events/thermodynamics-b/2027/source/interactives/runtime/heat-flow.js','events/thermodynamics-b/2027/source/interactives/runtime/model.js','events/thermodynamics-b/2027/source/interactives/runtime/interactive.css','events/solar-system-b/2027/source/reader-metadata/README.txt','events/solar-system-b/2027/source/reader-metadata/ATTRIBUTION.txt','events/thermodynamics-b/2027/web/study-guide.html','source/build/cache','releases/old.json']:
    p=source/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('retained')
   import shutil
   (source/'manifests').mkdir()
   shutil.copy2(HERE.parent/'manifests/events.json',source/'manifests/events.json')
   import json
   for event in json.loads((source/'manifests/events.json').read_text())['events']:
    for name in event.get('required_inputs',[]):
     p=source/'events'/event['slug']/str(event['year'])/name
     p.parent.mkdir(parents=True,exist_ok=True);p.write_text('authored fixture')
   runner.copy_inputs(source,stage)
   self.assertTrue((stage/'source.json').exists())
   self.assertFalse((stage/'events/solar-system-b/2027/exam-reference.pdf').exists())
   self.assertTrue((stage/'events/thermodynamics-b/2027/source/interactives/runtime/geometry.html').exists())
   self.assertFalse((stage/'events/thermodynamics-b/2027/web/study-guide.html').exists())
   self.assertFalse((stage/'events/solar-system-b/2027/study-guide.pdf').exists())
   self.assertFalse((stage/'source/build').exists())
   self.assertFalse((stage/'releases').exists())
 def test_missing_local_dependency_is_detected(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);web=root/'events/example/2027/web';web.mkdir(parents=True)
   (web/'index.html').write_text('<script src="missing.js"></script>')
   with self.assertRaisesRegex(RuntimeError,'missing.js'):runner.check_web_dependencies(root)
   (web/'missing.js').write_text('')
   self.assertEqual(runner.check_web_dependencies(root)['missing_local_dependencies'],[])
 def test_srcset_dependencies_include_queries_and_data_urls(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);web=root/'events/example/2027/web';web.mkdir(parents=True)
   (web/'index.html').write_text('<img srcset="data:image/png;base64,AAAA 1x, ./missing.webp?v=2#crop 2x">')
   with self.assertRaisesRegex(RuntimeError,'missing.webp'):runner.check_web_dependencies(root)
   (web/'missing.webp').write_bytes(b'fixture')
   self.assertEqual(runner.check_web_dependencies(root)['missing_local_dependencies'],[])
 def test_locked_mode_rejects_missing_pin(self):
  result=subprocess.run(['sh',str(HERE/'build-image.sh'),'locked'],capture_output=True,text=True,env={'PATH':'/usr/bin:/bin'})
  self.assertEqual(result.returncode,2)
  self.assertIn('exact sha256 digest',result.stderr)
 def test_existing_output_rejected_before_docker(self):
  with tempfile.TemporaryDirectory() as t:
   result=subprocess.run(['sh',str(HERE/'run.sh'),str(HERE),t],capture_output=True,text=True)
   self.assertEqual(result.returncode,2)
   self.assertIn('approved files will not be replaced',result.stderr)
class CleanSourceTests(unittest.TestCase):
 def test_exam_requires_new_build_not_old_input(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);event=root/'events/solar-system-b/2027';event.mkdir(parents=True)
   (event/'exam-reference.pdf').write_bytes(b'old')
   with self.assertRaises(FileNotFoundError):runner.promote_candidates(root, {'path':'events/solar-system-b/2027','promote':{'build/exam-reference/exam-reference.pdf':'exam-reference.pdf'}})
   candidate=event/'build/exam-reference/exam-reference.pdf';candidate.parent.mkdir(parents=True);candidate.write_bytes(b'new')
   runner.promote_candidates(root, {'path':'events/solar-system-b/2027','promote':{'build/exam-reference/exam-reference.pdf':'exam-reference.pdf'}})
   self.assertEqual((event/'exam-reference.pdf').read_bytes(),b'new')
 def test_missing_mapping_warning_is_preserved(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'stage';logs=Path(t)/'logs';p=root/'events/example/build/example.log';p.parent.mkdir(parents=True)
   p.write_text('Font mapping tex-text not found.\nMissing character: There is no x in font!\n')
   self.assertEqual(len(runner.retain_tex_logs(root,logs)),2)
   self.assertEqual((logs/'tex/events/example/build/example.log').read_bytes(),p.read_bytes())
 def test_site_export_excludes_build_logs_and_sources(self):
  import json
  spec=importlib.util.spec_from_file_location('exporter',HERE/'export_site.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  m.optimize_pdf=lambda path, photo_hashes=():None  # These boundary fixtures are not real PDFs.
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'candidate';root.mkdir();dest=Path(t)/'site'
   files=['events/solar-system-b/2027/index.html','events/thermodynamics-b/2027/index.html','events/thermodynamics-b/2027/web/assets/diagrams/heat-flow-default.svg','events/thermodynamics-b/2027/web/assets/diagrams/geometry-default.svg','events/thermodynamics-b/2027/web/interactives/geometry.html','events/thermodynamics-b/2027/web/interactives/heat-flow.html','index.html','catalog-data.json','shared/reader-navigation.css','events/solar-system-b/2027/study-guide.pdf','events/solar-system-b/2027/exam-reference.pdf','events/thermodynamics-b/2027/study-guide.pdf','events/thermodynamics-b/2027/build-guide.pdf','events/thermodynamics-b/2027/exam-reference.pdf','events/solar-system-b/2027/web/index.html','build-logs/private.txt','exam-candidate/exam-reference.tex']
   files += list(runner.LICENSE_FILES)
   for name in files:
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture')
   thermo=Path('events/thermodynamics-b/2027')
   for name,diagram in [('geometry','geometry-default'),('heat-flow','heat-flow-default')]:
    authored=HERE.parent/thermo/'source/interactives/runtime'/(name+'.html')
    target=root/thermo/'web/interactives'/(name+'.html')
    fallback=f'../assets/diagrams/{diagram}.svg'
    self.assertIn(f'src="{fallback}"',authored.read_text())
    target.write_text(f'<noscript><img src="{fallback}"></noscript>')
   self.assertEqual(runner.check_web_dependencies(root)['missing_local_dependencies'],[])
   events=[event for event in runner.registry(HERE.parent) if event['slug'] in {'solar-system-b','thermodynamics-b'}]
   (root/'build-report.json').write_text(json.dumps({'status':'built-candidates-not-visually-approved','events':events}))
   output=m.export(root,dest)
   self.assertEqual(len(output),21)
   self.assertFalse((dest/thermo/'assets').exists())
   self.assertEqual((dest/'.nojekyll').read_bytes(),b'')
   for name in runner.LICENSE_FILES:self.assertEqual((root/name).read_bytes(),(dest/name).read_bytes())
   self.assertFalse((dest/'build-logs').exists());self.assertFalse((dest/'exam-candidate').exists())
   with self.assertRaises(FileExistsError):m.export(root,dest)
 def test_registry_export_supports_new_event_year(self):
  import json
  spec=importlib.util.spec_from_file_location('exporter',HERE/'export_site.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
  m.optimize_pdf=lambda path, photo_hashes=():None  # These boundary fixtures are not real PDFs.
  with tempfile.TemporaryDirectory() as t:
   root=Path(t)/'candidate';root.mkdir();event={'path':'events/astronomy-c/2028','pdfs':['study-guide.pdf'],'site_assets':[]}
   names=['index.html','catalog-data.json','shared/reader-navigation.css',event['path']+'/index.html',event['path']+'/study-guide.pdf',event['path']+'/web/index.html']+list(runner.LICENSE_FILES)
   for name in names:
    p=root/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text('fixture')
   (root/'build-report.json').write_text(json.dumps({'status':'built-candidates-not-visually-approved','events':[event]}))
   dest=Path(t)/'site';m.export(root,dest)
   self.assertTrue((dest/event['path']/'study-guide.pdf').is_file())
   self.assertFalse((dest/'events/solar-system-b').exists())
 def test_license_copy_preserves_exceptions_and_requires_all_files(self):
  with tempfile.TemporaryDirectory() as t:
   source=Path(t)/'source';out=Path(t)/'output';source.mkdir()
   with self.assertRaises(FileNotFoundError):runner.copy_licenses(source,out)
   self.assertFalse(out.exists())
   for name in runner.LICENSE_FILES:
    p=source/name;p.parent.mkdir(parents=True,exist_ok=True)
    p.write_bytes(('Scoped license: '+name+'\nThird-party and AI exceptions remain.\n').encode())
   runner.copy_licenses(source,out)
   for name in runner.LICENSE_FILES:self.assertEqual((source/name).read_bytes(),(out/name).read_bytes())
if __name__=='__main__':unittest.main()
