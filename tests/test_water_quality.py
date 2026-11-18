"""Water Quality's content and reference constraints, without generated output."""
import json, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
EVENT=ROOT/'events/water-quality-b/2027'
class WaterQuality(unittest.TestCase):
 def test_canonical_photo_provenance(self):
  import hashlib
  from shared.provenance import atlas, supplemental, records, notices
  from shared.raster_assets import external_masters
  external=external_masters(ROOT)
  rasters={row['path']:row for row in json.loads((ROOT/'manifests/raster-masters.json').read_text())['assets']}
  index={r.get('id'):r for r in records() if r.get('id')}
  rows=atlas(EVENT)['organisms']+supplemental(EVENT)
  self.assertEqual(len(rows),50)
  for row in rows:
   with self.subTest(source_id=row['source_id']):
    record=index[row['source_id']]
    self.assertIn(record['path'],external)
    self.assertEqual(record['sha256'],rasters[record['path']]['sha256'])
    master=ROOT/record['path']
    if master.is_file():
     self.assertEqual(record['sha256'],hashlib.sha256(master.read_bytes()).hexdigest())
    for key in ('creator','license','license_url','source_url'):
     self.assertTrue(record[key])
    self.assertIn(record['creator'],row.get('credit',row['caption']))
    self.assertIn(record['source_url'],notices())
  self.assertEqual((ROOT/'THIRD_PARTY_NOTICES.txt').read_text(),notices())
 def test_provenance_fails_on_wrong_asset(self):
  from shared.provenance import hydrate_photo
  row=json.loads((EVENT/'source/organisms.json').read_text())['organisms'][0]
  row['image']='assets/nonexistent.jxl'
  with self.assertRaises(ValueError):hydrate_photo(row,EVENT,True)
 def test_citation_locator_and_quotation(self):
  from shared.provenance import citation_detail, validate_citation
  self.assertEqual(citation_detail({'author':'NOAA','locator':'Figure 3'}),'NOAA; Figure 3')
  with self.assertRaises(ValueError):validate_citation({'id':'quote','quotation':'Words'})
  record={'quotation':'Words','locator':'p. 2','rights_basis':'Public domain'}
  self.assertEqual(validate_citation(record),record)
 def test_reference_allowance(self):
  from soso.site.event_registry import load,reference_page_limit
  e=next(e for e in load(ROOT) if e['slug']=='water-quality-b')
  self.assertEqual(reference_page_limit(e),2)
  self.assertEqual(e['reference_constraints']['allocation'],'team')
 def test_lessons_have_feedback_and_resolved_sources(self):
  sources=json.loads((EVENT/'source/source-registry.json').read_text())
  rows=sources.get('sources',sources) if isinstance(sources,dict) else sources
  ids=set(rows) if isinstance(rows,dict) else {r['id'] for r in rows}
  seen=set()
  for kind in ('study','build'):
   lessons=json.loads((EVENT/f'source/water-quality-{kind}.json').read_text())
   if isinstance(lessons,dict):lessons=lessons['lessons']
   for lesson in lessons:
    self.assertNotIn(lesson['id'],seen);seen.add(lesson['id'])
    self.assertTrue(lesson.get('question'));self.assertTrue(lesson.get('answer'))
    self.assertTrue(set(lesson['sources']).issubset(ids),lesson['id'])
 def test_atlas_complete_with_attribution(self):
  organisms=json.loads((EVENT/'source/organisms.json').read_text())['organisms']
  self.assertEqual(len(organisms),23)
  self.assertEqual(len({o['id'] for o in organisms}),23)
  from shared.raster_assets import external_masters
  external=external_masters(ROOT)
  for o in organisms:
   self.assertTrue(o['diagnostic']);self.assertTrue(o['answer']);self.assertTrue(o['caption'])
   self.assertIn((EVENT/o['image']).relative_to(ROOT).as_posix(),external,o['name'])
  lobsters=[o for o in organisms if 'lobster' in o['name'].lower()]
  self.assertTrue(lobsters)
  self.assertTrue(any('Palinuridae' in o['scientific_name'] for o in lobsters))
if __name__=='__main__':unittest.main()
