from pathlib import Path
import unittest
ROOT=Path(__file__).resolve().parents[1]
class ThermodynamicNotation(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  import importlib.util
  spec=importlib.util.spec_from_file_location('manual_thermo',ROOT/'shared/build_thermo.py')
  cls.renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.renderer)
 def test_standalone_subscripts_and_boundaries(self):
  self.assertEqual(self.renderer.tx('Th Tc Qh Qc Theory Qheat'),r'\(T_{\mathrm{h}}\) \(T_{\mathrm{c}}\) \(Q_{\mathrm{h}}\) \(Q_{\mathrm{c}}\) Theory Qheat')
  self.assertEqual(self.renderer.body('Th Tc Qh Qc Theory Qheat'),'<i>T</i><sub>h</sub> <i>T</i><sub>c</sub> <i>Q</i><sub>h</sub> <i>Q</i><sub>c</sub> Theory Qheat')
 def test_full_formula_not_remapped(self):
  self.assertEqual(self.renderer.tx('ηmax=1−Tc/Th'),r'\(\eta_{\max}=1-T_{\mathrm{c}}/T_{\mathrm{h}}\)')
 def test_worked_example_cue(self):
  self.assertIn('\\workedhead{',self.renderer.panel_tex(('Worked example','Th is hot.')))

class PortableTypography(unittest.TestCase):
 def test_minimum_hyphen_fragments(self):
  style=(ROOT/'shared/guide-style.tex').read_text()
  self.assertIn(r'\lefthyphenmin=3\righthyphenmin=3',style)
 def test_text_renderer_does_not_require_pdf_toolchain(self):
  import subprocess,sys
  code="import sys,importlib.util;sys.modules['fitz']=None;s=importlib.util.spec_from_file_location('renderer',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);assert '<sub>h</sub>' in m.body('Qh')"
  subprocess.run([sys.executable,'-c',code,str(ROOT/'shared/build_thermo.py')],check=True)


class VisualRefinement(unittest.TestCase):
 def test_art_crop_bounds_keep_a_visible_image(self):
  import json
  source=ROOT/'events/solar-system-b/2027/source'
  crops=json.loads((source/'art-crops.json').read_text())
  lesson_ids={lesson['id'] for lesson in json.loads((source/'lessons.json').read_text())}
  for lesson,crop in crops.items():
   with self.subTest(lesson=lesson):
    self.assertIn(lesson,lesson_ids)
    for dimension, edges in [('width',('left','right')),('height',('top','bottom'))]:
     trims=[crop.get(edge+'_px',0) for edge in edges]
     self.assertTrue(all(type(value) is int and value >= 0 for value in trims))
     self.assertLess(sum(trims),crop['source_'+dimension+'_px'])
 def test_cues_are_vector_paths(self):
  import xml.etree.ElementTree as ET
  for name in ['think','worked','try','review']:
   svg=ET.parse(ROOT/'shared/learning-icons'/(name+'.svg'))
   tags={element.tag.rsplit('}',1)[-1] for element in svg.iter()}
   self.assertIn('path',tags)
   self.assertNotIn('text',tags)


class StructuredLearningRecords(unittest.TestCase):
 def test_forms_and_practice_have_structures(self):
  import json
  build=json.loads((ROOT/'events/thermodynamics-b/2027/source/thermodynamics-build.json').read_text())
  forms=[d['worksheet'] for d in build if 'worksheet' in d]
  self.assertEqual(len(forms),2)
  self.assertTrue(all(w['sections'] for w in forms))
  trial=next(w for w in forms if w['kind']=='trial')
  table=next(s for s in trial['sections'] if s['kind']=='table')
  self.assertEqual(table['rows'],6)
  self.assertGreaterEqual(table['row_height_pt'],28)
  study=json.loads((ROOT/'events/thermodynamics-b/2027/source/thermodynamics-study.json').read_text())
  practice=next(d for d in study if d['id']=='thermo-practice')
  self.assertEqual([len(p[1]) for p in practice['panels']],[6,6])
 def test_solar_chapters_have_distinct_segment_names(self):
  import json
  ds=json.loads((ROOT/'events/solar-system-b/2027/source/lessons.json').read_text())
  segments=[]
  for d in ds:
   if not segments or segments[-1]!=d['chapter']:segments.append(d['chapter'])
  self.assertEqual(len(segments),len(set(segments)))
 def test_scoring_has_equivalent_display_formats(self):
  import json,xml.etree.ElementTree as ET
  ds=json.loads((ROOT/'events/thermodynamics-b/2027/source/thermodynamics-build.json').read_text())
  score=next(d for d in ds if d['id']=='thermo-build-score')
  self.assertEqual(len(score['display_equations']),5)
  for e in score['display_equations']:ET.fromstring(e['mathml'])
  pe=score['display_equations'][3]['tex']
  self.assertIn(r'\lvert T_{\mathrm{final}}-T_{\mathrm{predicted}}\rvert',pe)
  self.assertIn(r'}{T_{\mathrm{final}}}',pe)


class CorrectnessAudit(unittest.TestCase):
 def test_rule_and_energy_qualifications(self):
  s=(ROOT/'events/thermodynamics-b/2027/source/thermodynamics-study.json').read_text()
  for phrase in ('at least three questions','heat-capacity-weighted','closed system','negligible work'):
   self.assertIn(phrase,s)
  s=(ROOT/'events/thermodynamics-b/2027/source/thermodynamics-build.json').read_text()
  for phrase in ('two Class III calculators','same thermometer for its own','No thermometer is left in a device','not impounded'):
   self.assertIn(phrase,s)
 def test_dated_solar_claims(self):
  s=(ROOT/'events/solar-system-b/2027/source/lessons.json').read_text()
  for phrase in ('published in 2026','observed in 2022–2023','13 November 2026','zero remaining speed'):
   self.assertIn(phrase,s)
 def test_exam_formula_groups_match_baseline(self):
  import ast,json
  current=ROOT/'events/solar-system-b/2027/source/exam-reference/export_tex.py'
  # Self-contained typography regression baseline. Intentional equation changes
  # require scientific review and an explicit fixture update, not local archives.
  expected=json.loads((Path(__file__).parent/'fixtures/solar-exam-formulas.json').read_text())
  groups=next(ast.literal_eval(n.value) for n in ast.parse(current.read_text()).body
   if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MATH' for t in n.targets))
  self.assertEqual(groups,expected)
  self.assertEqual(len(groups),10)



class OfficialClarifications(unittest.TestCase):
 def test_current_source_records_allowed_handling_and_limits(self):
  s=(ROOT/'events/thermodynamics-b/2027/source/thermodynamics-build.json').read_text()
  for phrase in ('opening/closing a lid or door','orientation or position','not permission for unrelated redesign','polystyrene','PS/6','one construction violation','Do not swirl, shake or stir','top-layer measurement is recommended','not to a prescribed depth'):
   self.assertIn(phrase,s)
 def test_uniform_model_has_stratification_caveat(self):
  text=(ROOT/'events/thermodynamics-b/2027/source/interactives/runtime/heat-flow.html').read_text()
  self.assertIn('stratified cup',text)
  self.assertIn('prohibit swirling, shaking or stirring',text)

class ArtworkStorage(unittest.TestCase):
 def test_jxl_master_integrity(self):
  import json,hashlib
  assets=json.loads((ROOT/'manifests/raster-masters.json').read_text())['assets']
  self.assertTrue(assets)
  external={row['legacy_path']:row['sha256'] for row in json.loads((ROOT/'manifests/external-assets.json').read_text())['assets']}
  for item in assets:
   path=ROOT/item['path']
   self.assertFalse((ROOT/item['original_path']).exists())
   if item['path'] in external:
    self.assertTrue(item['reversible_jpeg'])
    self.assertEqual(external[item['path']],item['original_sha256'])
   if item['path'] not in external or path.exists():
    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),item['sha256'])
   self.assertRegex(item['decoded_rgb_sha256'],r'^[0-9a-f]{64}$')

class EventMetadataIsolation(unittest.TestCase):
 def test_external_lesson_figure_resolves_without_git_master(self):
  import importlib.util, tempfile
  from unittest.mock import patch
  spec=importlib.util.spec_from_file_location('external_figure_renderer',ROOT/'shared/build_thermo.py')
  renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
  with tempfile.TemporaryDirectory() as scratch:
   root=Path(scratch).resolve()
   event=root/'events/water-quality-b/2027'
   logical=event/'assets/organisms/grouper.jxl'
   with patch.multiple(renderer,SERIES=root,EVENT=event,EXTERNAL_FIGURES={logical.relative_to(root).as_posix():{}}):
    self.assertFalse(logical.exists())
    self.assertEqual(renderer.resolve_asset('assets/organisms/grouper.jxl'),logical)
 def test_rendered_content_and_source_urls_are_not_rebranded(self):
  import importlib.util, tempfile
  from unittest.mock import patch
  spec=importlib.util.spec_from_file_location('metadata_renderer',ROOT/'shared/build_thermo.py')
  renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
  original='The 2027 survey compared Thermodynamics B.'
  with tempfile.TemporaryDirectory() as directory, patch.multiple(renderer, WEB=Path(directory), EVENT_NAME='Water Quality B', EVENT_YEAR='2028', CONFIG={'introduction':'intro'}), patch.object(renderer,'interactive_links',return_value=''), patch.object(renderer,'lesson_html',return_value='<p>'+original+'</p>'), patch.object(renderer,'sources_html',return_value='<a href="https://example.org/2027/report">Historical report</a>'):
   page=renderer.render_web('study',original,original,[{'id':'lesson','chapter':'2027 chapter','title':original}],{'lesson':[]}).read_text()
   self.assertIn(original,page)
   self.assertIn('https://example.org/2027/report',page)
   self.assertIn('Water Quality B 2028</title>',page)
   self.assertIn('2027 chapter',page)
 def test_pdf_metadata_does_not_rewrite_title_description_or_asset_paths(self):
  import importlib.util,tempfile
  from unittest.mock import patch
  spec=importlib.util.spec_from_file_location('pdf_metadata_renderer',ROOT/'shared/build_thermo.py')
  renderer=importlib.util.module_from_spec(spec);spec.loader.exec_module(renderer)
  text='Thermodynamics B historical 2027 report'
  config={'covers':{'study':'cover.jxl'},'cover_questions':{'study':'Question 2027'},'interactive_descriptions':{'study':text}}
  with tempfile.TemporaryDirectory() as directory, patch.multiple(renderer, BUILD=Path(directory), SRC=Path(directory), EVENT_NAME='Water Quality B', EVENT_YEAR='2028', CONFIG=config), patch.object(renderer,'pdf_asset',return_value=Path('/tmp/2027/cover.png')), patch.object(renderer,'compile_tex',side_effect=lambda path:path), patch.object(renderer,'backmatter_tex',return_value=''):
   tex=renderer.render_pdf('study',text,text,[],{}).read_text()
   self.assertIn(text,tex)
   self.assertIn('/tmp/2027/cover.png',tex)
   self.assertIn('Question 2027',tex)
   self.assertIn('Water Quality B 2028',tex)


if __name__=='__main__':unittest.main()
