import json
from pathlib import Path
p=Path('science-olympiad-study-guides/events/thermodynamics-b/2027/source')
rows=[('R01','Science Olympiad 2027 Division B Rules, Thermodynamics B56–B58 (user-supplied official PDF)',''),('R02','Official Thermodynamics B event page','https://www.soinc.org/thermodynamics-b'),('R03','Official rules corrections','https://www.soinc.org/events/rules-corrections'),('R04','Official rules clarifications','https://www.soinc.org/events/submit-question-and-rule-clarifications'),('R05','Official scoresheets','https://www.soinc.org/scoresheets'),('R06','2019 example Thermodynamics graphs: historical cooling, not current heating rules','https://www.soinc.org/sites/default/files/uploaded_files/Example.Thermodynamics.Graphs.2019.pdf'),('P01','OpenStax College Physics 2e: Heat and Heat Transfer Methods','https://openstax.org/books/college-physics-2e/pages/14-introduction-to-heat-and-heat-transfer-methods'),('P02','OpenStax College Physics 2e: Temperature, Kinetic Theory, and Gas Laws','https://openstax.org/books/college-physics-2e/pages/13-introduction-to-temperature-kinetic-theory-and-the-gas-laws'),('P03','OpenStax College Physics 2e: Thermodynamics','https://openstax.org/books/college-physics-2e/pages/15-introduction-to-thermodynamics'),('H01','Saslow: A History of Thermodynamics: The Missing Manual','https://pmc.ncbi.nlm.nih.gov/articles/PMC7516509/'),('H02','Max Planck Society: What did Max Planck discover?','https://www.mpg.de/19252749/what-did-max-planck-discover'),('D01','US Department of Energy: Solar Water Heating','https://www.energy.gov/sites/prod/files/2013/11/f5/41085.pdf'),('D02','NASA JPL: Solar Oven activity (sunlight activity, not competition heat-lamp instructions)','https://www.jpl.nasa.gov/edu/resources/lesson-plan/solar-oven/'),('V01','NASA: Solar Oven video (research link; not redistributed)','https://svs.gsfc.nasa.gov/14643/')]
r=[dict(id=i,title=t,url=u,accessed_date='2026-10-30') for i,t,u in rows]
(p/'source-registry.json').write_text(json.dumps(r,indent=2)+'\n')
for fn in ['thermodynamics-study.json','thermodynamics-build.json']:
 a=json.loads((p/fn).read_text())
 for x in a:
  if x['id'] in ['thermo-system','thermo-temperature','thermo-scales','thermo-phase-diagram','thermo-gas-law']: x['sources']=['R01','P02']
  if x['id'] in ['thermo-first-law','thermo-processes','thermo-engines','thermo-third-law']:x['sources']=['R01','P03']
  if x['id']=='thermo-history':x['sources']=['R01','H01','H02']
  x['source_urls']=[y['url'] for y in r if y['id'] in x['sources'] and y['url']]
 (p/fn).write_text(json.dumps(a,ensure_ascii=False,indent=2)+'\n')
