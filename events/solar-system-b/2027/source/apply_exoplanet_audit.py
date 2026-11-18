import json
from pathlib import Path
P=Path(__file__).parent/'lessons.json';ls=json.loads(P.read_text());by={d['id']:d for d in ls}
d=by['detection-transit'];d['panels'][0][1]=d['panels'][0][1].replace('For a small dark planet crossing an approximately uniform, unblended star','For a small dark planet making a non-grazing crossing of an approximately uniform, unblended star')
d=by['kepler_452'];d['panels'][0][1]=d['panels'][0][1].replace('Kepler-452 b transits a Sun-like G-type star.','Kepler-452 b was identified from repeated transit-like dips around a Sun-like G-type star. NASA’s archive retains it among confirmed planets but flags its detection reliability as controversial.');d['visual']['labels'][0]='Transit signal; reliability debated';d['visual']['caption']='Its appearance and interior are unknown. The disk is schematic, not a picture of a measured surface.'
d=by['detection-comparison']
for row in d['visual']['rows']:
 if 'imag' in row[0].lower():row[2]='Position; brightness; sometimes spectrum'
d=by['practice-2'];d['visual']['items'][1]='Both planets transit. RV measurements, with their inclinations accounted for, indicate equal masses.';d['visual']['items'][2]='The transmission spectrum has no prominent features.'
d=by['trappist_system'];d.pop('prerequisite_note',None)
d=by['trappist_evidence'];d['visual']['rows'][0][1]='Thermal data disfavor tested thick, heat-redistributing atmospheres.';d['panels'][1][1]='The b/c infrared observations favor little heat transfer from day to night. Airless surfaces fit well, although some thin or weak-greenhouse atmosphere models remain possible. For e, a secondary atmosphere remains unresolved. The 2026 f observations disfavor tested extended hydrogen/helium atmospheres. Heavier atmospheres are harder to constrain, and results depend on how the data and the star’s changing light are modeled.\n\nFlares occurred during all five f observing visits. Not detecting one kind of stellar contamination does not mean the star was quiet. No established atmospheric composition or ocean follows for g or h from the evidence summarized here. A result for one planet is not a system-wide verdict.'
d=by['lhs1140_models'];d['panels'][1][1]=d['panels'][1][1].replace('An exceptionally obscured atmosphere is another possibility, not a confirmed explanation.','Extremely high clouds could hide atmospheric features, but the tested climate models make that explanation less plausible, not impossible.')
d=by['lhs1140_helium'];d['question']='Why don’t observations without helium settle what happened on a different date?';d['visual']['rows'][0][0]='September 2024 ground transit';d['visual']['rows'][1][0]='September 2025 ground transit';d['visual']['rows'][2][0]='JWST: December 2023 (two visits), August 2025, July 2026'
d=by['detection-rv'];d['panels'][0][1]+=' Here the wavelength shift means observed wavelength minus rest wavelength; positive radial velocity means moving away.'
d=by['detection-microlensing'];d['panels'][1][1]+=' A planet on a very wide bound orbit can also resemble an isolated lens.'
d=by['compare_methods'];d['visual']['rows'][0][0]='Induced magnetic response to a changing field';d['visual']['rows'][3][1]='Gas and cloud models, after accounting for the star'
for d in ls:
 if d['id'].startswith('foundation-terms-'):
  d['title']={'foundation-terms-1':'Orbit size and shape','foundation-terms-2':'Rotation and resonance','foundation-terms-3':'Names and scales','foundation-terms-4':'Chemistry and surfaces'}[d['id']]
regp=Path(__file__).parent/'source-registry.json';reg=json.loads(regp.read_text());urls={x['url']:x['id'] for x in reg};patches=json.load(open('so-recovery/audit/exoplanet-audit-patches.json'))['patches']
for patch in patches:
 for url in patch.get('sources',patch.get('sources_to_add',[])):
  if url not in urls:
   sid='S'+str(max(int(x['id'][1:]) for x in reg)+1).zfill(3);urls[url]=sid;reg.append({'id':sid,'url':url,'title':url.split('/')[2]+' — '+url.rstrip('/').split('/')[-1]})
  d=by[patch['id']]
  if urls[url] not in d['sources']:d['sources'].append(urls[url])
  if url not in d['source_urls']:d['source_urls'].append(url)
P.write_text(json.dumps(ls,ensure_ascii=False,indent=2)+'\n');regp.write_text(json.dumps(reg,ensure_ascii=False,indent=2)+'\n')
