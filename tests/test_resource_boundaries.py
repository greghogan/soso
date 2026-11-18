"""Private reference files must not leak into candidate builds."""
import importlib.util
from pathlib import Path
import sys,unittest,io,zipfile
ROOT=Path(__file__).resolve().parents[1]
from soso.site import package_distributions as packages
spec=importlib.util.spec_from_file_location('container_runner',ROOT/'build-container/run_build.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
class ResourceBoundaries(unittest.TestCase):
 def test_container_excludes_private_directories_and_rule_filename(self):
  blocked=['rules-manuals','downloaded-resources','private-resources','Science_Olympiad_Div_B_Rules_2027.pdf']
  self.assertEqual(runner.ignore('/source',blocked+['lessons.json']),set(blocked))
 def test_zip_preserves_shell_entrypoint_mode(self):
  with zipfile.ZipFile(io.BytesIO(packages.zipped({'build-container/run.sh':b'#!/bin/sh\nexit 0\n','notes.txt':b'notes'}))) as z:
   self.assertEqual((z.getinfo('build-container/run.sh').external_attr>>16)&0o777,0o755)
   self.assertEqual((z.getinfo('notes.txt').external_attr>>16)&0o777,0o644)
 def test_shell_entrypoints_executable(self):
  for name in ['run.sh','build-image.sh']:
   self.assertTrue((ROOT/'build-container'/name).stat().st_mode & 0o111,name)
if __name__=='__main__':unittest.main()
