"""Offline converter command/cache tests, not a substitute for rendered comparison."""
import importlib.util,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
ROOT=Path(os.environ.get('SO_PROJECT_ROOT',Path(__file__).resolve().parents[1]))
spec=importlib.util.spec_from_file_location('renderer',ROOT/'shared/build_thermo.py')
renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
class SVGConverterTests(unittest.TestCase):
 def test_both_engines_have_distinct_cache_and_commands(self):
  with tempfile.TemporaryDirectory() as t:
   root=Path(t);svg=root/'diagram.svg';svg.write_text('<svg/>');calls=[]
   def convert(cmd,**kwargs):
    calls.append(cmd);output=next(a.split('=',1)[1] for a in cmd if a.startswith(('--output=','--export-filename=')));Path(output).write_bytes(b'%PDF fixture');return SimpleNamespace(returncode=0,stderr='')
   with patch.object(renderer,'BUILD',root/'build'),patch.object(renderer.subprocess,'run',side_effect=convert):
    for engine in ('rsvg-convert','inkscape'):
     with patch.dict(os.environ,{'SVG_PDF_CONVERTER':engine}):
      result=renderer.pdf_asset({'path':svg});self.assertIn(engine,str(result));renderer.pdf_asset({'path':svg})
   self.assertEqual(len(calls),2)
   self.assertIn('--format=pdf',calls[0]);self.assertIn('--export-text-to-path',calls[1])
 def test_default_is_rsvg(self):
  text=(ROOT/'shared/build_thermo.py').read_text()
  self.assertIn("os.environ.get('SVG_PDF_CONVERTER','rsvg-convert')",text)
 def test_unknown_engine_is_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   svg=Path(t)/'a.svg';svg.write_text('<svg/>')
   with patch.dict(os.environ,{'SVG_PDF_CONVERTER':'unknown'}):
    with self.assertRaises(ValueError):renderer.pdf_asset({'path':svg})
if __name__=='__main__':unittest.main()
