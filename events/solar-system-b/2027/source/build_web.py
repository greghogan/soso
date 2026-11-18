#!/usr/bin/env python3
"""Build a server-free offline guide: static HTML, local CSS/JS/SVG/WebP only."""
import json,re,html,shutil,sys
from pathlib import Path
import fitz
ROOT=Path(__file__).resolve().parent.parent;SRC=ROOT/'source'
sys.path.insert(0,str(ROOT.parents[2]/'shared'))
from build_paths import event_output
from diagrams.draw_diagrams import generate as generate_compact_diagrams
OUT=event_output(ROOT);WEB=OUT/'web';WEB.mkdir(parents=True,exist_ok=True)
from legacy_diagrams import DIAGRAMS, export_legacy
VECTOR=DIAGRAMS/'vector-original'
export_legacy()
from learning_cues import icon
from math_notation import protect_notation, restore_notation
ARTCROPS=json.loads((SRC/'art-crops.json').read_text())
LESSONS=json.loads((SRC/'lessons.json').read_text());REG=json.loads((SRC/'source-registry.json').read_text());LOOKUP={s['id']:s for s in REG};BY={d['id']:d for d in LESSONS}
for p in ['assets/art','assets/diagrams']:(WEB/p).mkdir(parents=True,exist_ok=True)
COMPACT=OUT/'build/diagrams/compact'
CM={}
for f in json.loads(generate_compact_diagrams(COMPACT).read_text())['figures']:
 svg=COMPACT/f['svg_file']
 shutil.copy2(svg,WEB/'assets/diagrams'/svg.name)
 for id in f['lesson_ids']:CM[id]={'file':'assets/diagrams/'+svg.name,'caption':f['caption'],'alt':f['caption']}
# Original vector diagrams retain mathematical information at useful wide size.
for p in VECTOR.glob('*.pdf'):
 dest=WEB/'assets/diagrams'/(p.stem+'.svg')
 doc=fitz.open(p);dest.write_text(doc[0].get_svg_image(text_as_path=True));doc.close()
LEGACY={p.stem for p in VECTOR.glob('*.pdf')}
def e(s):return html.escape(str(s),quote=True)
def body(s):
 # Source corpus has only trusted simple emphasis, subscripts and line breaks.
 source,notation=protect_notation(str(s),'html')
 s=e(source).replace('&lt;i&gt;','<em>').replace('&lt;/i&gt;','</em>').replace('&lt;b&gt;','<strong>').replace('&lt;/b&gt;','</strong>').replace('&lt;br/&gt;','<br>')
 for a,b in [('Nkᴮ','Nk<sub>B</sub>'),('Nᴬkᴮ','N<sub>A</sub>k<sub>B</sub>'),('N k_B T','Nk<sub>B</sub>T'),('N_A k_B','N<sub>A</sub>k<sub>B</sub>')]:s=s.replace(a,b)
 s=re.sub('[₀₁₂₃₄₅₆₇₈₉]+',lambda m:'<sub>'+m[0].translate(str.maketrans('₀₁₂₃₄₅₆₇₈₉','0123456789'))+'</sub>',s)
 return restore_notation('</p><p>'.join(s.split('\n\n')),notation)
def paras(s):return '<p>'+body(s)+'</p>'
def panel(p):return '<h4>'+(icon('worked') if str(p[0]).lower().startswith('worked') else '')+e(p[0])+'</h4>'+paras(p[1])
def figure(fig,cls=''):
 crop=fig.get('crop')
 viewport='';imgstyle=''
 if crop:
  visible_w=crop['source_width_px']-crop.get('right_px',0)
  visible_h=crop['source_height_px']-crop.get('bottom_px',0)-crop.get('top_px',0)
  viewport=f' style="display:block;overflow:hidden;aspect-ratio:{visible_w}/{visible_h}"'
  imgstyle=f' style="display:block;width:{100*crop["source_width_px"]/visible_w:.5f}%;max-width:none;height:auto;max-height:none;transform:translateY(-{100*crop.get("top_px",0)/crop["source_height_px"]:.5f}%)"'
 accessible='<span class="sr-only">4 H₂ + CO₂ → CH₄ + 2 H₂O</span>' if fig['file'].endswith('/foundation-8.svg') else ''
 return '<figure class="'+cls+'">'+accessible+'<a class="figure-enlarge" href="'+e(fig['file'])+'" title="Open full-size diagram"'+viewport+'><img src="'+e(fig['file'])+'" alt="'+e(fig['alt'])+'" loading="lazy"'+imgstyle+'></a><figcaption>'+body(fig['caption'])+'</figcaption></figure>'

def comparison(d):
 v=d['visual'];headers=v['headers'];rows=v['rows']
 keep={'foundation-solar-atlas','foundation-moon-atlas','compare_liquids','detection-comparison','data-sketch-practice'}
 if d['id'] in keep:
  out='<div class="table-wrap"><table><thead><tr>'+''.join('<th scope="col">'+body(x)+'</th>' for x in headers)+'</tr></thead><tbody>'
  out+=''.join('<tr>'+''.join(('<th scope="row">' if i==0 else '<td>')+body(x)+('</th>' if i==0 else '</td>') for i,x in enumerate(row))+'</tr>' for row in rows)+'</tbody></table></div>'
 else:
  out='<div class="term-list">'
  for row in rows:
   out+='<div class="term"><h4>'+body(row[0])+'</h4>'
   if len(row)==2:out+=paras(row[1])
   else:
    for i in range(1,len(row)):out+='<p><strong>'+body(headers[i])+':</strong> '+body(row[i])+'</p>'
   out+='</div>'
  out+='</div>'
 return out+('<p class="caption">'+body(v['caption'])+'</p>' if v.get('caption') else '')
def source_title(s):
 title=s['title'].replace('www.','').replace('assets.science.nasa.gov','NASA').replace('science.nasa.gov','NASA').replace('astrobiology.nasa.gov','NASA Astrobiology').replace('exoplanetarchive.ipac.caltech.edu','NASA Exoplanet Archive')
 return title.replace('_',' ').replace('.pdf','')
def reference_links(d):
 lis=[]
 for sid in d['sources']:
  if sid in LOOKUP:lis.append('<li><a href="#source-'+e(sid)+'">'+e(source_title(LOOKUP[sid]))+'</a></li>')
 return '<details class="sources"><summary>Sources for this lesson</summary><ul>'+''.join(lis)+'</ul></details>'
def related(d):
 candidates=[]
 for other in LESSONS:
  if other['id']==d['id']:continue
  score=len(set(other.get('concept_ids',[]))&set(d.get('concept_ids',[])))
  if score:candidates.append((score,other))
 candidates.sort(key=lambda x:-x[0]);seen=set();links=[]
 for _,o in candidates:
  if o['title'] in seen:continue
  seen.add(o['title']);links.append('<a href="'+('index.html' if '--sample' in sys.argv else '')+'#'+e(o['id'])+'">'+e(o['title'])+'</a>')
  if len(links)==3:break
 return '<nav class="related" aria-label="Related lessons">Explore next: '+''.join(links)+'</nav>' if links else ''

def interactive(id):
 if id=='detection-transit':return '''<section class="lab" aria-label="Transit depth explorer"><h4>Change the planet's size</h4><p>Keep the star the same. A larger planet blocks a larger <em>area</em>, so the depth changes with the square of the radius ratio.</p><label for="radius-ratio">Planet radius ÷ star radius: <output id="ratio-value">0.10</output></label><input id="radius-ratio" type="range" min="0.02" max="0.20" step="0.01" value="0.10"><p>Transit depth: <output id="depth-value">1.00%</output></p><svg viewBox="0 0 500 300" role="img" aria-label="Model star, transiting planet, and resulting light curve"><circle cx="65" cy="65" r="60" fill="#efbf55"/><circle id="transit-planet" cx="65" cy="65" r="6" fill="#15333f"/><text x="150" y="45" font-size="16" fill="#15333f">Uniform star; dark planet</text><text x="150" y="70" font-size="14" fill="#526874">Non-grazing transit, no blended light</text><path d="M 15 160 H 485 M 15 150 V 275 H 485" stroke="#8ca5ad" fill="none"/><path id="transit-curve" d="M 15 160 H 155 L 175 185 H 325 L 345 160 H 485" fill="none" stroke="#087b85" stroke-width="4"/><text x="20" y="153" font-size="13">1.0000</text><text id="transit-bottom" x="200" y="263" font-size="16">0.9900</text><text x="390" y="295" font-size="14">Time →</text></svg><p id="radius-explain">A radius ratio of 0.10 blocks about 1% of the light.</p><p class="caption">Illustrative model, not telescope data. Real curves are affected by limb darkening, orbital geometry, and noise. The vertical scale is expanded to make the dip visible.</p></section>'''
 if id=='math02':return '''<section class="lab" aria-label="Distance and flux explorer"><h4>Move a planet farther from its star</h4><label for="distance-ratio">Distance relative to the starting orbit: <output id="distance-value">1.0 ×</output></label><input id="distance-ratio" type="range" min="1" max="4" step="0.1" value="1"><svg viewBox="0 0 410 110" role="img" aria-label="Star and planet separation"><circle cx="42" cy="53" r="27" fill="#efbf55"/><path d="M 78 53 H 370" stroke="#b1c6cc" stroke-dasharray="4 4"/><circle id="flux-planet" cx="140" cy="53" r="13" fill="#087b85"/><text x="10" y="100" font-size="14">Same star, same albedo and emissivity</text></svg><p>Flux: <output id="flux-value">1.000 ×</output> · Equilibrium temperature: <output id="temperature-value">1.000 ×</output></p><p id="flux-explain"></p><p class="caption">An equilibrium benchmark in kelvin, not a predicted surface temperature. No internal heat; uniform reradiation. Objects and distances are not to scale.</p></section>'''
 if id=='math05':return '''<section class="lab" aria-label="Thermal radiation explorer"><h4>Heat a radiating surface</h4><label for="temperature-ratio">Absolute temperature: <output id="thermal-value">300 K</output></label><input id="temperature-ratio" type="range" min="150" max="900" step="25" value="300"><p>Emitted power per area compared with 300 K: <output id="power-value">1.00 ×</output></p><p>Wavelength of the blackbody peak: <output id="peak-value">9.66 μm</output></p><p class="caption">Power uses T⁴ at constant emissivity; peak wavelength uses 2898/T in micrometers. The peak refers to intensity per unit wavelength, not per unit frequency.</p></section>'''
 return ''

def art_for(d):
 # Viewport crops preserve source PNG bytes and explicitly trim empty background.
 if d['id']=='venus':return {'file':'assets/art/rocky-worlds.webp','alt':'Conceptual montage comparing Venus and Mars','caption':'An artist’s comparison of Venus and Mars. Surface details are illustrative, not an observed map; the worlds are not shown to scale.'}
 if d['id']=='ganymede':return {'file':'assets/art/worlds.webp','alt':'Illustrated portraits of Ganymede, Europa, Enceladus, and Titan','caption':'Clockwise from upper left: Ganymede, Europa, Titan, and Enceladus. Sizes are normalized rather than shown to scale. Enceladus is oriented with its south pole upward.'}
 if d['id']=='titan_surface':return {'file':'assets/art/titan.webp','alt':'Conceptual Titan surface and alternative interior views','caption':'Titan’s surface and alternative interior models. Surface lakes are hydrocarbons; the alternative interior layers and their thicknesses are uncertain.'}
 if d['id']=='bennu':return {'file':'assets/art/small-bodies.webp','alt':'Illustrated small bodies with a top-shaped Bennu','caption':'An artist’s montage of Makemake, Bennu, and comet 67P. Shapes and chemical histories are discussed in the lessons; sizes, distances, and lighting are not to scale. Makemake’s terrain and the floating Bennu specks are illustrative, not measured features.'}
 return None

LEGACY_CAPTIONS={'foundation-5': 'Water can be vapor, liquid, several kinds of ice, or bound in minerals. These forms imply different conditions.', 'foundation-6': 'Life uses linked molecules and reactions; finding an ingredient alone does not establish life.', 'foundation-8': 'Useful energy comes from a maintained difference, not merely a large energy total.', 'foundation-10': 'A surface receives light, exchanges infrared radiation, and transfers energy through its atmosphere.', 'foundation-12': 'Changing tidal forces deform a body. Dissipation can turn part of that mechanical energy into heat.', 'foundation-13': 'Geological processes can move material between a surface and an interior; each pathway needs evidence.', 'foundation-14': 'A spectrum separates light by wavelength. Features constrain composition only through an interpretation model.', 'detection-microlensing': 'A foreground mass temporarily magnifies a background star. A planet can add a deviation to the brightness curve.', 'detection-imaging': 'Suppressing starlight can reveal a nearby faint point of light; this is not a resolved planetary surface.', 'math01': 'A wavelength shift measures motion along our line of sight, not the full three-dimensional velocity.', 'math04': 'At constant emissivity, doubling absolute temperature multiplies emitted power per area by sixteen.', 'math05': 'A hotter blackbody peaks at a shorter wavelength; wavelength-peak and frequency-peak conventions differ.', 'math06': 'Balance absorbed and emitted power to obtain an equilibrium benchmark, not a measured surface temperature.', 'math07': 'For a bound Kepler orbit, total mechanical energy is negative when potential energy is zero at infinity.', 'math08': 'Gravity weakens with the square of distance from the center; force also depends on the test mass.', 'math09': 'A circular orbit requires gravity to supply the inward acceleration that continually turns the velocity.', 'math10': 'Escape speed is the minimum launch speed for reaching infinity with no leftover speed, ignoring drag and further thrust.', 'math11': 'For the same central mass, a larger orbit has a longer period; compare the powers before calculating.', 'math12': 'The ideal-gas model connects pressure, volume, particle number and absolute temperature.', 'math13': 'For a simple Arrhenius model, a plot of ln k against 1/T has slope −Eₐ/R.', 'math14': 'Forward and reverse reactions continue at equal rates. The amounts on the two sides need not be equal.', 'trappist_system': 'A compact family of seven planets shares one ultracool star; orbit size and planet size use different scales.'}

MATHML={'math01': '<mfrac><mrow><mi>Δλ</mi></mrow><msub><mi>λ</mi><mn>0</mn></msub></mfrac><mo>≈</mo><mfrac><msub><mi>v</mi><mi>r</mi></msub><mi>c</mi></mfrac>', 'math03': '<msub><mi>P</mi><mtext>abs</mtext></msub><mo>=</mo><mo>(</mo><mn>1</mn><mo>−</mo><mi>A</mi><mo>)</mo><mi>F</mi><mi>π</mi><msup><mi>R</mi><mn>2</mn></msup>', 'math07': '<mi>K</mi><mo>=</mo><mfrac><mn>1</mn><mn>2</mn></mfrac><mi>m</mi><msup><mi>v</mi><mn>2</mn></msup><mspace width="2em"/><mi>U</mi><mo>=</mo><mo>−</mo><mfrac><mrow><mi>G</mi><mi>M</mi><mi>m</mi></mrow><mi>r</mi></mfrac>', 'math08': '<msub><mi>F</mi><mtext>grav</mtext></msub><mo>=</mo><mfrac><mrow><mi>G</mi><mi>M</mi><mi>m</mi></mrow><msup><mi>r</mi><mn>2</mn></msup></mfrac><mspace width="2em"/><mi>g</mi><mo>=</mo><mfrac><mrow><mi>G</mi><mi>M</mi></mrow><msup><mi>r</mi><mn>2</mn></msup></mfrac>', 'math10': '<msub><mi>v</mi><mtext>esc</mtext></msub><mo>=</mo><msqrt><mfrac><mrow><mn>2</mn><mi>G</mi><mi>M</mi></mrow><mi>r</mi></mfrac></msqrt>', 'math12': '<mi>P</mi><mi>V</mi><mo>=</mo><mi>n</mi><mi>R</mi><mi>T</mi><mo>=</mo><mi>N</mi><msub><mi>k</mi><mi>B</mi></msub><mi>T</mi>'}

def equation(d):
 markup=MATHML.get(d['id'])
 if not markup:return body(d['visual'].get('eq',''))
 return '<math xmlns="http://www.w3.org/1998/Math/MathML" display="block" aria-label="'+e(d['visual'].get('eq',''))+'"><mrow>'+markup+'</mrow></math>'

def lesson(d):
 out='<article class="lesson" id="'+e(d['id'])+'"><h3>'+e(d['title'].replace('Comparison: ',''))+'</h3><p class="deck">'+body(d['deck'])+'</p>'
 if d.get('foundation_context'):
  c=d['foundation_context'];parts=[c['identity']]
  if c.get('diameter_km_rounded') is not None:parts.append('diameter about '+format(c['diameter_km_rounded'],',')+' km')
  if c.get('size_text'):parts.append(c['size_text'])
  parts.append('orbits '+c['direct_orbital_primary']);out+='<p class="factline">'+e('; '.join(parts))+'.</p>'
  for k in ['solar_distance_note','teaching_value']:
   if c.get(k):out+=paras(c[k])
 if d.get('prerequisite_note'):out+=paras(d['prerequisite_note'])
 if d['kind']=='practice':out+='<ol>'+''.join('<li>'+body(s)+'</li>' for s in d['visual'].get('items',[]))+'</ol>'
 if d['kind']=='comparison':out+=comparison(d)
 fig=CM.get(d['id']);art=art_for(d)
 if art and d['id'] in ARTCROPS:art['crop']=ARTCROPS[d['id']]
 if fig:
  out+='<div class="split">'+figure(fig)+'<div>'+panel(d['panels'][0])+'</div></div>'
  out+=''.join(panel(p) for p in d['panels'][1:])
  if art:out+=figure(art,'art-figure supplemental-art')
 elif art:
  out+='<div class="split">'+figure(art,'art-figure')+'<div>'+panel(d['panels'][0])+'</div></div>'
  out+=''.join(panel(p) for p in d['panels'][1:])
 else:out+=''.join(panel(p) for p in d['panels'])
 if d['id'] in LEGACY and not fig:
  out+=figure({'file':'assets/diagrams/'+d['id']+'.svg','alt':'Schematic for '+d['title'],'caption':LEGACY_CAPTIONS.get(d['id'],d['deck'])},'legacy-figure')
 if d['kind']=='equation':
  if d['id'] in LEGACY or d['id'] in CM:out+='<div class="sr-only">'
  out+='<p class="equation">'+equation(d)+'</p>'+paras(d['visual'].get('meaning',''))+'<ul>'+''.join('<li>'+body(s)+'</li>' for s in d['visual'].get('steps',[]))+'</ul>'
  if d['id'] in LEGACY or d['id'] in CM:out+='</div>'
 out+=interactive(d['id']).replace('</section>', '<button type="button" class="reset-model">Reset model</button></section>')
 out+='<div class="self-check"><div class="label">'+icon('think')+'Think it through</div>'+paras(d['question'])+'<details><summary>Show the reasoning</summary><div class="answer">'+paras(d.get('answer',''))+'</div></details></div>'
 out+=related(d)+reference_links(d)+'</article>'
 return out

def main():
 sample='--sample' in sys.argv
 lessons=[BY[x] for x in ['foundation-4','bennu','detection-transit','math02','math14']] if sample else LESSONS
 chapters=[]
 for d in lessons:
  if not chapters or chapters[-1][0]!=d['chapter']:chapters.append((d['chapter'],[]))
  chapters[-1][1].append(d)
 nav='<a href="#introduction">About this guide</a>'
 for title,ds in chapters:nav+='<details open><summary>'+e(title)+'</summary>'+''.join('<a class="lesson-link" href="#'+e(d['id'])+'">'+e(d['title'].replace('Comparison: ',''))+'</a>' for d in ds)+'</details>'
 nav+='<a href="#sources">Sources and further reading</a>'
 out='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="description" content="An offline illustrated Solar System B 2027 study guide with interactive models, linked lessons and hidden reasoning answers."><title>Solar System B 2027 Study Guide</title><link rel="stylesheet" href="style.css"></head><body><a class="skip" href="#main">Skip to the guide</a><header class="topbar"><button class="navtoggle" id="navtoggle" aria-expanded="false" aria-controls="contents">Contents</button><a class="brand" href="#introduction">Solar System B</a><span class="edition">2027 · Illustrated study guide</span></header><div class="layout"><aside class="sidebar" id="contents"><label for="lesson-search">Find a lesson</label><input type="search" id="lesson-search" placeholder="Try ocean, transit, or energy"><p class="status" id="search-status" aria-live="polite">All lessons</p><nav aria-label="Guide contents">'''+nav+'''</nav></aside><main id="main"><section class="hero" id="introduction"><div><p class="eyebrow">Science Olympiad · Division B · 2027</p><h1>How could a world support life?</h1><p class="lead">Follow the evidence for water, energy, chemistry, and the connections that make them useful.</p></div><p class="caption">Conceptual icy-moon cutaway. An illustration can help us ask questions; measurements are needed to answer them.</p></section><section class="intro"><h2>A guide to habitable worlds</h2><p>Compare planets, moons, small bodies, and exoplanets. Learn what missions can measure, then use physics and chemistry to work out what those clues mean.</p><p>Every lesson includes a question with its reasoning hidden until you choose to reveal it. Follow the related-topic links whenever an idea needs a refresher. The interactive models let you change one variable while keeping the assumptions visible.</p><p><strong>Images have different jobs.</strong> The artistic montages are conceptual, not observations. The diagrams simplify mechanisms. Captions tell you which is which, and sources are linked at the end of each lesson.</p><p><strong>For competition preparation.</strong> Use the official 2027 rules and tournament clarifications alongside this guide. Supporting explanations help you understand the required topics; they do not add official requirements.</p><p class="photo-note">This edition works offline. <button type="button" id="hide-answers">Hide all answers</button> Source links are optional further reading and need an internet connection. The illustrations, diagrams, text, scripts and interactive models are included locally.</p></section>'''
 for i,(title,ds) in enumerate(chapters):out+='<section class="chapter" id="chapter-'+str(i)+'"><h2>'+e(title)+'</h2>'+''.join(lesson(d) for d in ds)+'</section>'
 wanted={sid for d in lessons for sid in d['sources']};out+='<section class="source-directory" id="sources"><h2>Sources and further reading</h2><p>These links identify the supporting sources. They are not needed to open or use this guide offline. Research notes in the source package preserve the detailed rule-to-topic map and dated checks.</p>'
 for s in REG:
  if s['id'] not in wanted:continue
  out+='<div class="source-entry" id="source-'+e(s['id'])+'"><div class="source-title">'+e(source_title(s))+'</div><a href="'+e(s['url'])+'">'+e(s['url'])+'</a></div>'
 out+='</section><footer class="footer">Solar System B · 2027. Independent study material. Original artwork and scientific diagrams are identified in the accompanying asset manifest. See the official rules for competition requirements.</footer></main></div><script src="guide.js"></script></body></html>'
 (WEB/('sample.html' if sample else 'index.html')).write_text(out)
 for name in ('README.txt','ATTRIBUTION.txt'):shutil.copy2(SRC/'reader-metadata'/name,WEB/name)
 shutil.copy2(SRC/'web-style.css',WEB/'style.css');shutil.copy2(SRC/'web-interactions.js',WEB/'guide.js')
 # Ship only artwork actually referenced by the reader, not every source master.
 used=set(re.findall(r'assets/art/([A-Za-z0-9_-]+\.webp)',''.join(p.read_text() for p in WEB.rglob('*') if p.suffix in {'.html','.css','.js'})))
 for name in used:
  source=ROOT/'assets/illustrations'/Path(name).with_suffix('.jxl')
  from raster_assets import decoded_asset
  shutil.copy2(decoded_asset(source,OUT/'build/decoded-assets',web=True),WEB/'assets/art'/name)
 for path in (WEB/'assets/art').glob('*.webp'):
  if path.name not in used:path.unlink()

 print(WEB/('sample.html' if sample else 'index.html'))
if __name__=='__main__':main()
