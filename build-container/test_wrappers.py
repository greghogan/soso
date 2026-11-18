#!/usr/bin/env python3
"""Exercise wrapper arguments with a Docker stub; never contact a daemon."""
import json,os,shutil,subprocess,tempfile,unittest
from pathlib import Path
HERE=Path(__file__).resolve().parent
class Wrappers(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name);self.log=self.root/'calls.jsonl'
  stub=self.root/'docker'
  stub.write_text('#!'+shutil.which('python3')+'\n'+"""
import os,sys,json
from pathlib import Path
args=sys.argv[1:]
with open(os.environ["DOCKER_TEST_LOG"],"a") as f:
 f.write(json.dumps({"args":args,"platform":os.environ.get("DOCKER_DEFAULT_PLATFORM")})+"\\n")
if args[0] == 'run':
 mounts=[x for x in args if x.startswith('type=bind,') and 'dst=/output' in x]
 output=Path(mounts[0].split('src=',1)[1].split(',dst=',1)[0])
 export='/scripts/export_site.py' in args
 if not export:
  (output/'build-logs').mkdir()
  (output/'build-logs'/'compile.log').write_text('test compile log')
 if os.environ.get('DOCKER_FAIL') == ('export' if export else 'compile'):
  sys.exit(7)
 if export:
  (output/'site').mkdir()
  (output/'site'/'index.html').write_text(os.environ.get('BUILD_TEXT','built'))
  (output/'site-export.json').write_text(json.dumps({'files': ['index.html'], 'build': os.environ.get('BUILD_TEXT','built')}))
""")
  stub.chmod(0o755);self.env=dict(os.environ,PATH=str(self.root)+os.pathsep+os.environ['PATH'],DOCKER_TEST_LOG=str(self.log));self.env.pop('IMAGE_TAG',None);self.env.pop('DOCKER_DEFAULT_PLATFORM',None)
 def tearDown(self):self.tmp.cleanup()
 def calls(self):return [json.loads(x) for x in self.log.read_text().splitlines()]
 def run_script(self,name,*args):return subprocess.run([str(HERE/name),*map(str,args)],env=self.env,capture_output=True,text=True)
 def test_build_native_and_matching_tag(self):
  self.env['PLATFORM']='invalid-ignored';self.assertEqual(self.run_script('build-image.sh').returncode,0);c=self.calls()[0];self.assertNotIn('--platform',c['args']);self.assertIn('soso-builder:development',c['args']);self.assertIsNone(c['platform'])
 def test_run_native_and_matching_tag(self):
  self.assertEqual(self.run_script('run.sh',HERE.parent,self.root/'output').returncode,0);a=self.calls()[0]['args'];self.assertNotIn('--platform',a);self.assertEqual(a[-1],'soso-builder:development');self.assertIn('--read-only',a);self.assertIn('none',a)
 def test_standard_docker_override_passes_through(self):
  self.env['DOCKER_DEFAULT_PLATFORM']='linux/amd64';self.assertEqual(self.run_script('build-image.sh').returncode,0);self.assertEqual(self.run_script('run.sh',HERE.parent,self.root/'output').returncode,0)
  self.assertTrue(all(c['platform']=='linux/amd64' and '--platform' not in c['args'] for c in self.calls()))
 def test_explicit_image_and_tag(self):
  self.env['IMAGE_TAG']='custom:test';self.assertEqual(self.run_script('build-image.sh').returncode,0);self.assertIn('custom:test',self.calls()[0]['args']);self.assertEqual(self.run_script('run.sh',HERE.parent,self.root/'output','sha256:chosen').returncode,0);self.assertEqual(self.calls()[-1]['args'][-1],'sha256:chosen')
 def test_refuses_existing_output(self):
  self.assertEqual(self.run_script('run.sh',HERE.parent,self.root).returncode,2);self.assertFalse(self.log.exists())
 def test_site_build_uses_same_image_and_exports_public_site(self):
  self.env['IMAGE_TAG']='custom:pages'
  result=self.run_script('../build.sh',self.root/'build')
  self.assertEqual(result.returncode,0,result.stderr)
  calls=self.calls()
  self.assertIn('custom:pages',calls[0]['args'])
  self.assertEqual(calls[2]['args'][-1],'custom:pages')
  self.assertEqual(calls[3]['args'][-4:],['custom:pages','/scripts/export_site.py','/output/candidates','/output/site'])
  self.assertIn('--read-only',calls[3]['args'])
  self.assertIn('none',calls[3]['args'])
 def test_site_build_refuses_existing_directory_before_docker(self):
  self.assertEqual(self.run_script('../build.sh',self.root).returncode,2)
  self.assertFalse(self.log.exists())
 def test_repeat_build_removes_previous_output_after_success(self):
  output=self.root/'build'
  self.assertEqual(self.run_script('../build.sh',output).returncode,0)
  self.env['BUILD_TEXT']='rebuilt'
  result=self.run_script('../build.sh',output)
  self.assertEqual(result.returncode,0,result.stderr)
  self.assertEqual((output/'site/index.html').read_text(),'rebuilt')
  self.assertEqual(json.loads((output/'site-export.json').read_text())['build'],'rebuilt')
  self.assertFalse((output/'.previous').exists())
  self.assertFalse((output/'.next').exists())
 def test_failed_build_preserves_last_good_and_diagnostics(self):
  output=self.root/'build'
  self.assertEqual(self.run_script('../build.sh',output).returncode,0)
  for failure in ['compile','export']:
   self.env['DOCKER_FAIL']=failure
   result=self.run_script('../build.sh',output)
   self.assertNotEqual(result.returncode,0)
   self.assertEqual((output/'site/index.html').read_text(),'built')
   self.assertEqual(json.loads((output/'site-export.json').read_text())['build'],'built')
   self.assertTrue((output/'.next/candidates/build-logs/compile.log').is_file())
   self.assertFalse((output/'.lock').exists())
  del self.env['DOCKER_FAIL']
  self.assertEqual(self.run_script('../build.sh',output).returncode,0)
 def test_failed_promotion_retains_backup_and_blocks_next_build(self):
  output=self.root/'build'
  self.assertEqual(self.run_script('../build.sh',output).returncode,0)
  stub=self.root/'mv'
  stub.write_text('#!/bin/sh\ncase "$2" in */.next/site) exit 9;; esac\nexec /bin/mv "$@"\n')
  stub.chmod(0o755)
  self.assertEqual(self.run_script('../build.sh',output).returncode,9)
  self.assertEqual((output/'.previous/site/index.html').read_text(),'built')
  stub.unlink()
  self.assertEqual(self.run_script('../build.sh',output).returncode,2)
  self.assertEqual((output/'.previous/site/index.html').read_text(),'built')
 def test_symlink_and_live_lock_refused(self):
  output=self.root/'build'
  self.assertEqual(self.run_script('../build.sh',output).returncode,0)
  link=self.root/'link'; link.symlink_to(output)
  self.assertEqual(self.run_script('../build.sh',link).returncode,2)
  (output/'.lock').mkdir()
  self.assertEqual(self.run_script('../build.sh',output).returncode,2)
  (output/'.lock').rmdir()
  outside=self.root/'protected'; outside.mkdir()
  (outside/'source').write_text('preserve')
  (output/'.next').symlink_to(outside)
  self.assertEqual(self.run_script('../build.sh',output).returncode,2)
  self.assertEqual((outside/'source').read_text(),'preserve')
 def test_invalid_mode_never_calls_docker(self):
  self.assertEqual(self.run_script('build-image.sh','wrong').returncode,2);self.assertFalse(self.log.exists())
if __name__=='__main__':unittest.main()
