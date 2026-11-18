"""Generate only the Thermodynamics SVGs reproducible from this drawing code."""
import argparse, html
from pathlib import Path
def text(x,y,s,size=18):return f'<text x="{x}" y="{y}" font-size="{size}">{html.escape(s)}</text>'
def line(x,y,X,Y,c='#147d87',arrow=True):return f'<path d="M{x},{y} L{X},{Y}" stroke="{c}" stroke-width="3" fill="none"'+(' marker-end="url(#a)"' if arrow else '')+'/>'
def box(x,y,w,h,s,c='#e6f3f2'):return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="{c}" stroke="#147d87"/>'+text(x+12,y+h/2+6,s)
def save(output,name,body,title):
 (output/name).write_text('<svg xmlns="http://www.w3.org/2000/svg" width="600" height="390" viewBox="0 0 600 390" role="img"><title>'+html.escape(title)+'</title><defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10" fill="#147d87"/></marker></defs><rect width="600" height="390" fill="#fff"/><g font-family="sans-serif" fill="#163c4a">'+body+'</g></svg>')

# Editorial figures use readable vector labels and shallow perspective, not photorealism.
def label(x,y,s,size=18,anchor='start'):
 return f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}">{html.escape(s)}</text>'
def variable(x,y,base,sub='',prefix='',suffix='',size=20,anchor='start'):
 return f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" xml:space="preserve">{html.escape(prefix)}<tspan font-style="italic">{base}</tspan>'+ (f'<tspan dy="5" font-size="{size*.7:g}">{sub}</tspan><tspan dy="-5">' if sub else '<tspan>')+html.escape(suffix)+'</tspan></text>'
def cylinder(x,y,w,h,color,top):
 return f'<path d="M{x},{y} V{y+h} A{w/2},10 0 0 0 {x+w},{y+h} V{y} Z" fill="{color}" stroke="#526874" stroke-width="1.6"/><ellipse cx="{x+w/2}" cy="{y}" rx="{w/2}" ry="10" fill="{top}" stroke="#526874" stroke-width="1.6"/>'
def beaker(x,y,w,h,level,lid=False):
 # Water level is measured upward from the base; both comparison vessels have the same geometry.
 out=f'<path d="M{x},{y} V{y+h} Q{x+w/2},{y+h+18} {x+w},{y+h} V{y}" fill="#f7fafb" stroke="#526874" stroke-width="2"/>'
 wy=y+h-level
 out+=f'<path d="M{x+3},{wy} V{y+h-2} Q{x+w/2},{y+h+13} {x+w-3},{y+h-2} V{wy} Z" fill="#b6dde9"/><ellipse cx="{x+w/2}" cy="{wy}" rx="{w/2-3}" ry="8" fill="#d9edf3" stroke="#528698"/>'
 out+=f'<ellipse cx="{x+w/2}" cy="{y}" rx="{w/2}" ry="9" fill="none" stroke="#526874" stroke-width="2"/>'
 if lid:out+=f'<path d="M{x-3},{y-4} Q{x+w/2},{y-22} {x+w+3},{y-4} L{x+w+3},{y+5} Q{x+w/2},{y-5} {x-3},{y+5} Z" fill="#d2dce0" stroke="#526874" stroke-width="2"/>'
 return out
def engine_figure():
 out=cylinder(185,35,230,40,'#f4c8a7','#fbe8d8')
 out+=label(300,18,'Hot reservoir',18,'middle')+variable(300,65,'T','h',anchor='middle')
 out+=line(300,85,300,135)+variable(320,118,'Q','h',suffix=' in')
 # A piston/flywheel is a concrete engine cue, not a claim about its internal thermodynamic cycle.
 out+=cylinder(235,165,130,65,'#ccd8dc','#edf2f4')
 out+=f'<rect x="246" y="186" width="108" height="10" fill="#8197a1" stroke="#526874"/><path d="M300 191 V214 H390" fill="none" stroke="#526874" stroke-width="7"/><circle cx="390" cy="214" r="26" fill="#f7fafb" stroke="#526874" stroke-width="5"/><path d="M368 214 H412 M390 192 V236" stroke="#8197a1" stroke-width="3"/>'
 out+=label(215,180,'Engine',18,'end')
 out+=line(422,214,550,214)+variable(475,190,'W',suffix=' out',anchor='middle')
 out+=line(300,243,300,290)+variable(320,277,'Q','c',suffix=' out')
 out+=cylinder(185,310,230,40,'#b9dce9','#e3f1f6')
 out+=variable(300,339,'T','c',prefix='Cold reservoir: ',size=18,anchor='middle')
 out+=variable(45,381,'Q','h',prefix='',suffix=' = ',size=19)
 out+=variable(105,381,'W',suffix=' + ',size=19)+variable(163,381,'Q','c',size=19)
 out+=label(345,381,'h = hot; c = cold',16)
 return out
def capacity_figure():
 out=label(300,27,'Equal energy, different amounts of water',21,'middle')
 out+=beaker(85,118,125,150,55)+beaker(390,118,125,150,110)
 for center,mass,rise in [(147.5,'0.10 kg','≈ 1°C'),(452.5,'0.20 kg','≈ 0.5°C')]:
  out+=label(center,60,'418 J added',18,'middle')+line(center,70,center,100)
  out+=label(center,307,mass+' water',19,'middle')+label(center,338,'Temperature rise '+rise,18,'middle')
 out+=label(300,380,'Same material • twice the mass → half the temperature rise',17,'middle')
 return out
def systems_figure():
 out=label(300,25,'Choose the system boundary',22,'middle')
 for x,title in [(20,'Open'),(215,'Closed'),(410,'Isolated: ideal limit')]:
  out+=label(x+85,61,title,18,'middle')
  out+=f'<rect x="{x+5}" y="88" width="160" height="205" rx="18" fill="none" stroke="#7a8e98" stroke-width="1.5" stroke-dasharray="6 5"/>'
 out+=beaker(65,175,80,90,35)
 out+=line(80,173,80,76)+label(94,119,'Matter',16)
 out+=line(8,248,70,248)+label(35,278,'Energy',16)
 out+=beaker(260,175,80,90,35,True)
 out+=line(200,245,265,245)+label(228,278,'Energy',16)
 # Thick surrounding shell shows insulation, while wording makes perfect isolation an idealization.
 out+=f'<rect x="434" y="145" width="122" height="129" rx="18" fill="#e7edef" stroke="#8498a1" stroke-width="9"/>'
 out+=beaker(455,175,80,80,30,True)
 out+=label(105,322,'Matter + energy',17,'middle')+label(300,322,'Energy only',17,'middle')+label(495,322,'Neither crosses',17,'middle')
 out+=label(300,365,'Dashed line = system boundary. Real insulation is imperfect.',17,'middle')
 return out
def account_figure():
 out=label(300,30,'Piston system: heat in, work out',22,'middle')
 # Piston and gas occupy the chosen system; the work arrow describes energy transferred.
 out+=f'<path d="M205 105 H365 V255 H205 Z" fill="#e0edf1" stroke="#526874" stroke-width="2"/><ellipse cx="205" cy="180" rx="18" ry="75" fill="#c9dce3" stroke="#526874" stroke-width="2"/><ellipse cx="365" cy="180" rx="18" ry="75" fill="#eef4f6" stroke="#526874" stroke-width="2"/>'
 out+=f'<path d="M320 110 V250" stroke="#778e99" stroke-width="14"/><path d="M320 180 H412" stroke="#778e99" stroke-width="10"/>'
 for x,y in [(240,140),(275,163),(240,210),(285,226),(290,125),(255,182)]:
  out+=f'<circle cx="{x}" cy="{y}" r="5" fill="#528698"/>'
 out+=f'<rect x="179" y="90" width="215" height="180" rx="17" fill="none" stroke="#526874" stroke-width="1.7" stroke-dasharray="6 5"/>'
 out+=line(35,180,228,180)+variable(72,152,'Q')+label(92,152,'in',20)
 out+=line(380,180,565,180)+variable(465,152,'W')+label(491,152,'out',20)
 out+=label(285,295,'System internal energy: ΔU',18,'middle')
 out+=label(300,337,'ΔU = Q − W',28,'middle')+label(300,375,'W is work done by the system; dashed line marks its boundary.',16,'middle')
 return out


# Layout-review figures: label lanes/leader lines are separate from scientific geometry.
def leader(x,y,X,Y):
 return line(x,y,X,Y,c='#7a8e98',arrow=False)
def heating_figure():
 out=line(65,320,565,320)+line(65,320,65,40)
 out+=label(80,30,'Temperature',19)+label(315,375,'Energy added at constant pressure',18,'middle')
 out+='<path d="M85 295 L170 225 L260 225 L350 135 L440 135 L530 55" stroke="#147d87" stroke-width="4" fill="none"/>'
 for x,y,word,X,Y in [(90,230,'Solid',120,266),(190,270,'Melting',215,225),(235,145,'Liquid',300,185),(355,185,'Boiling',395,135),(460,35,'Gas',495,86)]:
  out+=label(x,y,word,18)+leader(x+22,y-22 if Y<y else y+7,X,Y)
 return out
def gas_figure():
 out=line(65,320,565,320)+line(65,320,65,35)+label(80,28,'Pressure P',19)+label(315,357,'Volume V',19,'middle')
 # Ideal gas, normalized common state V0=1/P0=1. gamma=1.4 is a stated example, not universal.
 def curve(gamma):
  pts=[(65+70*(1+3*i/80),320-240/(1+3*i/80)**gamma) for i in range(81)]
  return '<path d="'+' '.join(('M' if i==0 else 'L')+f'{x:.2f} {y:.2f}' for i,(x,y) in enumerate(pts))+'" stroke="#147d87" stroke-width="3" fill="none"'+(' stroke-dasharray="7 4"' if gamma>1 else '')+'/>'
 out+=line(135,80,345,80,arrow=False)+line(135,80,135,290,arrow=False)+curve(1)+curve(1.4)
 out+='<circle cx="135" cy="80" r="4" fill="#163c4a"/>'
 out+=label(210,60,'Isobaric',18)+label(147,307,'Isochoric',18)
 out+=leader(345,260,385,225)+label(392,228,'Isothermal',18)
 out+=leader(345,320-240/4**1.4,385,295)+label(392,302,'Adiabatic',18)
 out+=label(300,384,'Ideal gas; reversible adiabatic example uses γ = 1.4.',16,'middle')
 return out
def reflector_figure():
 out=label(300,28,'A ray reflects at equal angles to the normal',21,'middle')
 # Incoming d=(0,1), mirror tangent=(1,1)/sqrt(2): reflected d=(1,0), exactly.
 out+='<path d="M150 140 L290 280" stroke="#667f8a" stroke-width="8"/>'
 out+='<path d="M180 250 L260 170" stroke="#7a8e98" stroke-width="1.6" stroke-dasharray="5 4"/>'
 out+=line(220,70,220,210)+line(220,210,350,210)
 out+=beaker(355,155,95,135,60)
 out+=label(245,85,'Incident ray',18)+label(270,195,'Reflected ray',16)
 out+=label(65,305,'Reflective face',18)+leader(190,288,220,215)
 out+=label(70,113,'Normal',18)+leader(135,120,252,178)
 out+=label(397,328,'Cup wall',18,'middle')
 out+=label(300,376,'One 45° mirror example; a real lamp emits rays in many directions.',16,'middle')
 return out
def receiver_figure():
 out=label(300,28,'Dry receiver: absorption → contact → cup',21,'middle')
 out+=beaker(235,110,130,173,100)
 out+='<path d="M225 220 V292 H375 V220" fill="none" stroke="#a96d16" stroke-width="8"/><path d="M225 240 H235 M365 240 H375" stroke="#a96d16" stroke-width="8"/><rect x="180" y="300" width="240" height="12" rx="3" fill="#cbd6db" stroke="#526874"/>'
 out+=line(300,95,300,48)+label(330,67,'Lift out freely',18)
 out+=label(20,145,'Absorbing metal',18)+leader(160,155,225,225)
 out+=label(400,215,'External',18)+label(400,238,'contact tabs',18)+leader(395,244,367,240)
 out+=label(35,335,'Stable base',18)+leader(142,328,180,307)
 out+=label(300,377,'No gripping sleeve; no part enters the water.',18,'middle')
 return out
def reflector_concept():
 out=label(300,28,'Broad panels surround an open center',21,'middle')
 # Cutaway removes the front/back panels to expose the removal path and mounting points.
 out+='<path d="M100 95 L220 295 M500 95 L380 295" stroke="#667f8a" stroke-width="9"/><path d="M200 295 H235 V310 M365 310 V295 H400" fill="none" stroke="#526874" stroke-width="5"/><rect x="160" y="315" width="280" height="12" fill="#cbd6db" stroke="#526874"/>'
 out+=beaker(260,201,80,105,55)+line(300,180,300,60)
 out+=label(320,86,'Clear removal path',18)
 out+=label(20,165,'Reflective',18)+label(20,188,'inner face',18)+leader(112,190,155,185)
 out+=label(420,255,'Fixed',18)+label(420,278,'brackets',18)+leader(420,285,398,297)
 out+=label(300,372,'Cutaway: front and rear panels omitted; no crossbar over cup.',17,'middle')
 return out
def shroud_concept():
 out=label(300,28,'A fixed shroud changes airflow, not cup contact',21,'middle')
 out+=beaker(260,166,80,125,65)
 out+='<path d="M190 175 V300 H410 V175" fill="none" stroke="#667f8a" stroke-width="9"/><rect x="160" y="310" width="280" height="12" fill="#cbd6db" stroke="#526874"/>'
 out+=line(35,245,178,245)+label(35,220,'Draft',18)
 out+=line(300,65,300,130)+label(328,95,'Light in',18)
 out+=label(420,170,'Open top',18)+leader(420,178,360,155)
 out+=label(420,245,'Air gap',18)+leader(417,253,370,260)
 out+=label(300,376,'Wall is fixed to base; keep access clear and test for shadowing.',17,'middle')
 return out


def generate(output):
 output=Path(output)
 output.mkdir(parents=True,exist_ok=True)
 save(output,'energy-flow.svg',box(30,35,150,60,'Lamp')+line(180,65,300,65)+box(310,35,250,60,'Device + cup')+line(435,95,435,160)+box(310,170,250,60,'Water: energy stored')+line(310,65,150,190)+box(25,200,245,60,'Surroundings: losses')+text(35,320,'Some energy also warms the device.'),'Energy paths from a lamp into water and surroundings')
 save(output,'systems.svg',systems_figure(),'System boundaries for open, closed and ideal isolated systems')
 save(output,'temperature-scales.svg',text(35,35,'Same temperatures, different zero points',22)+line(100,290,100,80)+line(290,290,290,80)+line(475,290,475,80)+text(60,330,'Celsius')+text(250,330,'Kelvin')+text(425,330,'Fahrenheit')+text(115,100,'100°C')+text(305,100,'373.15 K')+text(490,100,'212°F')+text(115,275,'0°C')+text(305,275,'273.15 K')+text(490,275,'32°F')+text(40,375,'A change of 1°C = 1 K = 1.8°F',20),'Temperature scale comparison')
 save(output,'capacity.svg',capacity_figure(),'Equal heat added to unequal water masses')
 save(output,'heating-curve.svg',heating_figure(),'Idealized heating curve: sensible and latent heating')
 save(output,'phase-diagram.svg',line(65,320,550,320)+line(65,320,65,40)+text(230,370,'Temperature')+text(80,35,'Pressure')+'<path d="M90 300 Q170 280 250 230 L300 70 M250 230 Q360 190 465 95" fill="none" stroke="#147d87" stroke-width="3"/>'+text(105,135,'Solid')+text(315,120,'Liquid')+text(360,280,'Gas')+'<circle cx="250" cy="230" r="5" fill="#e88536"/><circle cx="465" cy="95" r="5" fill="#e88536"/>'+text(115,215,'Triple point',15)+text(370,65,'Critical point',15)+text(80,345,'Generic substance; not to scale.',15),'Generic phase diagram; melting-line slope is substance dependent')
 save(output,'gas-processes.svg',gas_figure(),'Ideal gas process paths from a common state')
 save(output,'reflector-rays.svg',reflector_figure(),'Specular reflection from one 45-degree face')
 save(output,'energy-account.svg',account_figure(),'Gas and piston: first law energy accounting')
 save(output,'engine.svg',engine_figure(),'Heat engine: heat absorbed, useful work and rejected heat')
 save(output,'build-concepts.svg',text(25,35,'Original starting concepts—not tested winners',22)+box(35,95,140,145,'Cup')+'<path d="M25 140 L25 260 L185 260 L185 140" stroke="#e88536" stroke-width="9" fill="none"/>'+text(25,300,'Dry receiver',18)+box(240,160,110,90,'Cup')+'<path d="M200 80 L230 270 L360 270 L390 80" stroke="#667f8a" stroke-width="8" fill="none"/>'+text(220,300,'Reflector',18)+box(450,150,100,100,'Cup')+'<path d="M425 180 L425 270 L575 270 L575 180" stroke="#147d87" stroke-width="8" fill="none"/>'+text(435,300,'Open shroud',18)+text(35,360,'Keep a permanent, unobstructed cup-removal path.',18),'Receiver, broad reflector and open shroud concept sketches')
 save(output,'concept-receiver.svg',receiver_figure(),'Dry receiver external contact and cup removal')
 save(output,'concept-reflector.svg',reflector_concept(),'Reflector cutaway with clear removal path and fixed brackets')
 save(output,'concept-shroud.svg',shroud_concept(),'Open shroud with air gap and light access')

if __name__ == '__main__':
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--output',type=Path,required=True)
 generate(parser.parse_args().output)
