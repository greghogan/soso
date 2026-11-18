#!/usr/bin/env python3
"""Original compact scientific vector diagrams. Used by the study-guide build.
All labels are >= 9 pt at native 240 pt width. No raster artwork is embedded.
Figures are explanatory schematics unless explicitly marked logarithmic.
"""
from pathlib import Path
from font_paths import dejavu_font
import math, json, random, re
from html import escape
from reportlab.pdfgen import canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import HexColor, Color, white

ROOT = Path(__file__).resolve().parents[2]
OUTPUT = None
LESSONS = {x['id']: x for x in json.loads((ROOT/'source/lessons.json').read_text())}
for name, filename in [('Sans','DejaVuSans.ttf'),('Bold','DejaVuSans-Bold.ttf'),('Italic','DejaVuSans-Oblique.ttf')]:
    pdfmetrics.registerFont(TTFont(name, dejavu_font(filename)))
INK=HexColor('#172F3D'); TEAL=HexColor('#087F8C'); GOLD=HexColor('#BD8424'); BLUE=HexColor('#D8EBF0')
PALE=HexColor('#EFF7F8'); SAND=HexColor('#F4E6C8'); ROCK=HexColor('#BCB3A4'); GREY=HexColor('#5A6C76'); GRID=HexColor('#CEDDE1')
manifest=[]
C=None

def txt(x,y,s,size=9,font='Sans',color=INK,anchor='left'):
    assert size>=9
    sw=pdfmetrics.stringWidth(s,font,size)
    left=x if anchor=='left' else (x-sw/2 if anchor=='center' else x-sw)
    if left < 0 or left+sw > 240: print('WARNING text extends beyond diagram:',s)
    C.setFillColor(color); C.setFont(font,size)
    {'left':C.drawString,'center':C.drawCentredString,'right':C.drawRightString}[anchor](x,y,s)
def lines(x,y,strings,size=9,leading=12,**kw):
    for i,s in enumerate(strings): txt(x,y-i*leading,s,size=size,**kw)
def line(x1,y1,x2,y2,color=INK,width=.8,dash=None):
    C.setStrokeColor(color); C.setLineWidth(width); C.setDash(dash or []); C.line(x1,y1,x2,y2); C.setDash([])
def arrow(x1,y1,x2,y2,color=INK,width=1,head=4):
    line(x1,y1,x2,y2,color,width)
    a=math.atan2(y2-y1,x2-x1)
    p=C.beginPath();p.moveTo(x2,y2)
    p.lineTo(x2-head*math.cos(a-.45),y2-head*math.sin(a-.45));p.lineTo(x2-head*math.cos(a+.45),y2-head*math.sin(a+.45));p.close()
    C.setFillColor(color);C.drawPath(p,fill=1,stroke=0)
def circ(x,y,r,fill=white,stroke=INK,width=.8):
    C.setFillColor(fill);C.setStrokeColor(stroke);C.setLineWidth(width);C.circle(x,y,r,fill=1,stroke=1)
def rect(x,y,w,h,fill=PALE,stroke=None,width=.8):
    C.setFillColor(fill);C.setStrokeColor(stroke or fill);C.setLineWidth(width);C.rect(x,y,w,h,fill=1,stroke=bool(stroke))
def path(points,color=TEAL,width=1.3,fill=None):
    p=C.beginPath();p.moveTo(*points[0])
    for pt in points[1:]:p.lineTo(*pt)
    C.setStrokeColor(color);C.setLineWidth(width)
    if fill is not None:p.close();C.setFillColor(fill)
    C.drawPath(p,stroke=1,fill=fill is not None)
def finish(name,h,ids,caption,limitations,extra_sources=None):
    C.showPage();C.save()
    sources=[]
    for lid in ids:
        for url in LESSONS[lid].get('source_urls',[]):
            if url not in sources:sources.append(url)
    for url in extra_sources or []:
        if url not in sources:sources.append(url)
    manifest.append(dict(file=name+'.pdf',svg_file=name+'.svg',width_pt=240,height_pt=h,minimum_label_size_pt=9,minimum_placement_width_pt=240,lesson_ids=ids,caption=caption,limitations=limitations,source_urls=sources))
def start(name,h,title):
    global C
    C=canvas.Canvas(str(OUTPUT/(name+'.pdf')),pagesize=(240,h),pageCompression=1)
    C.setTitle(title);C.setAuthor('Original educational diagram for Solar System B study guide')
    C.setSubject('Compact vector teaching schematic; see manifest.json for sources and limitations')
    rect(0,0,240,h,white)

def orbital_hierarchy():
    name='orbital-hierarchy';h=170;start(name,h,'A moon has two orbital scales')
    txt(120,155,'Two distances answer different questions',9.3,'Bold',anchor='center')
    C.setStrokeColor(GRID);C.setLineWidth(1.3);C.ellipse(14,33,168,131,stroke=1,fill=0)
    circ(91,82,11,SAND,GOLD);txt(91,63,'Sun',anchor='center')
    C.setStrokeColor(TEAL);C.setLineWidth(1);C.circle(168,82,20,stroke=1,fill=0)
    circ(168,82,8,SAND,GOLD);circ(188,82,3.5,BLUE,TEAL)
    txt(168,49,'Jupiter',anchor='center');line(168,57,168,72,GREY,.6)
    txt(207,98,'Europa',anchor='center');line(200,94,189,86,GREY,.6)
    line(91,96,91,115,GRID,.6);line(168,94,168,115,GRID,.6)
    arrow(91,111,168,111,GOLD);arrow(168,111,91,111,GOLD)
    txt(131,123,'Sun distance',9,anchor='center')
    txt(131,135,'sets sunlight',9,color=GOLD,anchor='center')
    line(168,73,168,62,GRID,.6);line(188,77,188,62,GRID,.6)
    arrow(168,65,188,65,TEAL,head=3);arrow(188,65,168,65,TEAL,head=3)
    lines(235,36,['Moon distance','matters for tides'],9,11,color=TEAL,anchor='right')
    txt(120,11,'Schematic; sizes and distances are not to scale.',9,anchor='center')
    finish(name,h,['foundation-moon-atlas','foundation-solar-atlas'],'Europa orbits Jupiter while the Jupiter system orbits the Sun. Use the appropriate center-to-center distance.','Schematic hierarchy; not true orbital shapes, sizes, positions, or distance ratios. Tides also depend on masses and orbital variation.')

def diameter_logscale():
    name='diameter-logscale';h=187;start(name,h,'Sizes of selected worlds on a logarithmic axis')
    txt(120,172,'Diameter in km: each step is ×10',9.5,'Bold',anchor='center')
    x0=81;x1=227;y0=34;yt=159
    def xx(v):return x0+(math.log10(v)+1)/5.2*(x1-x0)
    for value,label in [(.1,'0.1'),(1,'1'),(10,'10'),(100,'100'),(1000,'1k'),(10000,'10k')]:
        x=xx(value);line(x,y0,x,yt,GRID,.5);txt(x,22,label,anchor='center')
    data=[('Venus',12100),('Mars',6780),('Ganymede',5260),('Titan',5150),('Europa',3120),('Makemake',1430),('Enceladus',500),('Bennu',.5)]
    for i,(label,v) in enumerate(data):
        y=151-i*15.5;txt(72,y-3,label,anchor='right');line(x0,y,xx(v),y,GRID,.8);circ(xx(v),y,2.5,TEAL,TEAL)
    txt(120,6,'Rounded diameters; read dot position, not dot size.',9,anchor='center')
    finish(name,h,['foundation-solar-atlas'],'A logarithmic diameter axis makes kilometer-scale and planet-scale objects readable together. One tick interval is a tenfold change.','Dots do not depict body shapes or scaled silhouettes. Values are rounded teaching diameters. 1k means 1,000 km; 10k means 10,000 km.')

def habitability_overlap():
    name='habitability-overlap';h=184;start(name,h,'Habitability requirements must coincide')
    txt(120,168,'The requirements must meet in one habitat',9.5,'Bold',anchor='center')
    for x,y,col in [(98,107,TEAL),(142,107,GOLD),(120,70,GREY)]:
        C.saveState();C.setFillColor(col);C.setFillAlpha(.12);C.circle(x,y,45,fill=1,stroke=0);C.restoreState()
        C.setStrokeColor(col);C.setLineWidth(.9);C.circle(x,y,45,fill=0,stroke=1)
    lines(75,117,['Liquid','water'],9.5,12,anchor='center',color=TEAL)
    lines(165,117,['Usable','energy'],9.5,12,anchor='center',color=GOLD)
    lines(120,49,['Accessible','chemistry'],9.5,12,anchor='center')
    lines(120,99,['Same','place'],9.5,11,font='Bold',anchor='center')
    txt(120,15,'Suitable conditions must also last.',9.5,'Bold',anchor='center')
    finish(name,h,['foundation-3'],'Water, usable energy, and accessible chemistry must coincide under suitable, lasting conditions.','Conceptual overlap, not measured regions or a probability model. Meeting these requirements does not demonstrate that life exists.')

def atmosphere_escape():
    name='atmosphere-escape';h=178;start(name,h,'Particle speeds and atmospheric escape')
    txt(120,161,'Same temperature, different molecular mass',9.3,'Bold',anchor='center')
    x0=31;y0=45;w=191;hh=91
    arrow(x0,y0,226,y0,GREY);arrow(x0,y0,x0,140,GREY)
    txt(126,28,'Particle speed →',9.5,anchor='center');txt(35,140,'Relative number',9)
    def f(v,s):return math.sqrt(2/math.pi)*(v*v)/(s**3)*math.exp(-v*v/(2*s*s))
    scale=80
    for sigma,col in [(.72,TEAL),(1.2,GOLD)]:
        points=[(x0+w*v/4.5,y0+scale*f(v,sigma)) for v in [j*4.5/180 for j in range(181)]]
        if col==GOLD:
            cut=2.75
            tail=[(x0+w*cut/4.5,y0)]+[(x,y) for x,y in points if x>=x0+w*cut/4.5]+[(x0+w,y0)]
            path(tail,color=SAND,width=.1,fill=SAND)
        path(points,color=col,width=1.6)
    xe=x0+w*2.75/4.5;line(xe,y0,xe,133,INK,.9,[3,2])
    lines(174,139,['Escape','speed'],9,11,anchor='center')
    line(20,12,33,12,TEAL,1.7);txt(38,9,'Heavier',9)
    line(110,12,123,12,GOLD,1.7);txt(128,9,'Lighter',9)
    finish(name,h,['foundation-11','math10'],'At the same temperature, lighter molecules have a broader speed distribution. More may reach escape-capable speeds.','Qualitative Maxwell speed distributions, not measured planetary data. Shows thermal escape only; escape requires appropriate upper-atmosphere conditions. The vertical threshold is illustrative, not a universal cutoff for atmospheric retention.')

def habitable_zone():
    name='habitable-zone';h=176;start(name,h,'Habitable zone is not a guarantee of life')
    txt(120,160,'A surface-water zone is not a life detector',9.4,'Bold',anchor='center')
    rect(51,94,52,33,SAND);rect(103,94,65,33,BLUE);rect(168,94,61,33,PALE)
    circ(26,111,15,SAND,GOLD);txt(26,86,'Star',anchor='center')
    txt(135,136,'Habitable zone',9,'Bold',anchor='center')
    circ(134,110,8,ROCK,GREY);line(134,101,134,82,GREY,.6)
    lines(116,72,['In the zone,','but could be dry'],9,12,anchor='center')
    circ(207,110,10,BLUE,TEAL);circ(207,110,6,TEAL,TEAL);circ(207,110,3,SAND,GOLD)
    line(207,99,207,82,TEAL,.6);lines(202,72,['Outside: ocean','under ice?'],9,12,anchor='center')
    arrow(52,39,227,39,GREY,.8);txt(140,23,'Increasing star distance',9,anchor='center')
    txt(120,6,'Schematic; atmosphere and internal heat matter.',9,anchor='center')
    finish(name,h,['foundation-9'],'The conventional habitable zone concerns possible surface liquid water under suitable conditions. Internal heat can support a different setting beneath ice.','Schematic distance bands without numerical boundaries; not a map of the Solar System. An in-zone world is not necessarily wet or inhabited. The exterior ocean is hypothetical.')

def ocean_contact():
    name='ocean-rock-contact';h=186;start(name,h,'Alternative water and rock arrangements in icy moons')
    txt(45,169,'Europa',9.5,'Bold',anchor='center');txt(157,169,'Ganymede models',9.5,'Bold',anchor='center')
    txt(45,155,'Expected',9,anchor='center');txt(120,155,'A',9,anchor='center');txt(195,155,'B',9,anchor='center')
    xvalues=[15,90,165];w=60
    # All columns are depth schematics, not proportional interiors.
    for x in xvalues:rect(x,63,w,80,ROCK,INK)
    rect(15,123,60,20,BLUE);rect(15,90,60,33,HexColor('#7BC2C9'))
    rect(90,123,60,20,BLUE);rect(90,105,60,18,HexColor('#7BC2C9'));rect(90,85,60,20,HexColor('#E5DFEE'))
    rect(165,123,60,20,BLUE);rect(165,110,60,13,HexColor('#7BC2C9'));rect(165,94,60,16,HexColor('#E5DFEE'));rect(165,84,60,10,HexColor('#7BC2C9'))
    for x in xvalues:
        C.setStrokeColor(INK);C.setLineWidth(.8);C.rect(x,63,w,80,stroke=1,fill=0)
    for x,y in [(15,90),(165,84)]:line(x+2,y,x+58,y,GOLD,2.1)
    lines(45,51,['Water touches','rock'],9,11,anchor='center')
    lines(120,51,['Ice separates','main ocean'],9,11,anchor='center')
    lines(195,51,['Basal liquid','may touch rock'],9,11,anchor='center')
    for x,y,color,label in [(12,25,BLUE,'surface ice'),(128,25,HexColor('#7BC2C9'),'liquid'),(12,11,HexColor('#E5DFEE'),'high-pressure ice'),(128,11,ROCK,'rock')]:
        rect(x,y-1,8,8,color,GRID,.4);txt(x+13,y,label,9)
    finish(name,h,['ganymede','europa'],'Water-rock contact is expected for Europa. Ganymede models permit high-pressure ice and different liquid arrangements; contact is not settled.','Idealized vertical layer stacks, not spherical cross-sections or scaled depths. The two Ganymede columns illustrate alternatives, not an exhaustive model set. Basal liquid does not imply free exchange with the upper ocean. Gold marks possible/expected water-rock interfaces, not hydrothermal vents.')

def bennu_shape():
    name='bennu-shape';h=181;start(name,h,'Bennu as a top-shaped rubble-pile asteroid')
    txt(65,164,'Side view',9.5,'Bold',anchor='center');txt(177,164,'Polar view',9.5,'Bold',anchor='center')
    cx=65;cy=104
    p=C.beginPath();p.moveTo(cx-11,cy+40)
    p.curveTo(cx-1,cy+45,cx+11,cy+42,cx+19,cy+34)
    p.curveTo(cx+29,cy+25,cx+34,cy+8,cx+46,cy+1)
    p.curveTo(cx+48,cy-3,cx+34,cy-16,cx+24,cy-28)
    p.curveTo(cx+12,cy-43,cx-4,cy-43,cx-18,cy-34)
    p.curveTo(cx-30,cy-27,cx-35,cy-13,cx-46,cy-3)
    p.curveTo(cx-47,cy+2,cx-32,cy+20,cx-23,cy+28)
    p.curveTo(cx-19,cy+34,cx-16,cy+38,cx-11,cy+40);p.close()
    C.setFillColor(ROCK);C.setStrokeColor(INK);C.setLineWidth(1);C.drawPath(p,fill=1,stroke=1)
    path([(cx-45,cy-1),(cx-24,cy+3),(cx-3,cy),(cx+20,cy+1),(cx+45,cy+1)],GREY,.8)
    line(cx,cy-48,cx,cy+49,GREY,.7,[2,2])
    # Irregular rounded outline; this is not an image trace or a box icon.
    rnd=random.Random(9);pts=[]
    for i in range(32):
        a=2*math.pi*i/32;r=40*(1+.035*math.cos(4*a)+rnd.uniform(-.025,.025));pts.append((177+r*math.cos(a),104+r*math.sin(a)))
    path(pts+[pts[0]],INK,1,ROCK)
    for xc,yc,rx,ry in [(44,114,3,2),(78,125,4,3),(88,97,3,2),(51,83,4,3),(70,111,3,2),(153,111,4,3),(177,128,3,3),(190,102,5,3),(164,88,3,2),(198,119,3,3),(179,83,4,3)]:
        p2=[(xc-rx,yc),(xc-rx*.3,yc+ry),(xc+rx,yc+ry*.4),(xc+rx*.6,yc-ry),(xc-rx,yc)]
        path(p2,GREY,.5,HexColor('#968F83'))
    txt(19,47,'Equatorial ridge',9);line(31,56,21,101,GREY,.6)
    txt(115,145,'Spin axis',9,anchor='center');line(99,142,67,150,GREY,.6)
    txt(120,29,'About 500 m across; a rubble pile',9.5,'Bold',anchor='center')
    txt(120,11,'Shape sketch, not a map; no present ocean implied.',9,anchor='center')
    finish(name,h,['bennu'],'Bennu has a top-like shape with an equatorial ridge and a boulder-rich rubble-pile surface.','Original shape schematic, not a trace of a specific image or orientation. Boulder locations are illustrative. Dimensions are approximate. No present-day liquid ocean or layered planetary interior is depicted.')

def transit_depth():
    name='transit-depth';h=184;start(name,h,'Doubling planet radius quadruples ideal transit depth')
    txt(120,168,'Same star, twice the planet radius',9.5,'Bold',anchor='center')
    for x,r,label,col,dep in [(64,2.3,'r',TEAL,1),(176,4.6,'2r',GOLD,4)]:
        circ(x,130,23,SAND,GOLD);circ(x+2,130,r,INK,INK)
        txt(x+33,128,label,9.5,'Bold',color=col);line(x+29,131,x+7,131,col,.5)
        txt(x,98,'Planet radius '+label,9,anchor='center')
        xx=x-42;y=88;line(xx,y,xx+84,y,GRID,.5)
        path([(xx,y),(xx+21,y),(xx+26,y-9*dep),(xx+58,y-9*dep),(xx+63,y),(xx+84,y)],col,1.6)
        txt(x,37,str(dep)+'% dip',9.5,'Bold',color=col,anchor='center');txt(x,23,'Time →',9,anchor='center')
    txt(120,8,'Ideal depth ≈ (planet radius / star radius)²',9.5,anchor='center')
    finish(name,h,['detection-transit'],'Around the same star, doubling planet radius makes an ideal transit four times deeper: 1% becomes 4%.','Stellar disks have equal radii. Drawn planet radius ratios are 0.1 and 0.2. Light curves share a vertical scale but omit calibrated axes and limb darkening; transit durations are held equal for illustration. Formula assumes an unblended, approximately uniform star and a non-grazing dark planet.')

def rv_inclination():
    name='rv-inclination';h=190;start(name,h,'Radial velocity mass and inclination ambiguity')
    txt(120,174,'The same wobble can hide different masses',9.3,'Bold',anchor='center')
    for x,i,m,b in [(62,90,4,3),(178,30,8,28)]:
        C.setStrokeColor(TEAL);C.setLineWidth(1);C.ellipse(x-33,123-b,x+33,123+b,stroke=1,fill=0)
        circ(x,123,5,SAND,GOLD);circ(x+33,123,3,INK,INK)
        txt(x,85,'i = '+str(i)+'°',9.5,'Bold',anchor='center');txt(x,72,'m = '+str(m)+' Earth masses',9,anchor='center')
    txt(120,155,'Planet orbits as projected on the sky',9,anchor='center')
    txt(120,52,'Both give m sin(i) = 4 Earth masses',9.5,'Bold',anchor='center')
    line(24,36,216,36,GRID,.6)
    pts=[(24+j*192/120,36+8*math.sin(j/120*4*math.pi)) for j in range(121)];path(pts,TEAL,1.3)
    txt(120,16,'Same star and period; small-planet approximation.',9,anchor='center')
    finish(name,h,['detection-rv'],'An edge-on planet of 4 Earth masses and a 30°-inclined planet of 8 Earth masses have the same m sin(i), so can produce the same radial-velocity semi-amplitude.','Illustrative orbital projections, not scaled sizes. The i = 90° orbit is drawn with a small finite thickness for legibility. Assumes equal period, eccentricity, stellar mass, and planet mass much smaller than stellar mass. The wave is schematic and its axes are omitted. RV alone does not determine radius.')

def inverse_square():
    name='inverse-square';h=166;start(name,h,'Light spreads over a spherical area')
    txt(120,150,'Same luminosity, larger spherical area',9.4,'Bold',anchor='center')
    cx=62;cy=84
    for r in [25,50]:
        C.setStrokeColor(TEAL);C.setLineWidth(.8);C.circle(cx,cy,r,stroke=1,fill=0)
        C.setStrokeColor(GRID);C.ellipse(cx-r,cy-r*.25,cx+r,cy+r*.25,stroke=1,fill=0)
    for a in [0,45,90,135,180,225,270,315]:
        rad=math.radians(a);arrow(cx+9*math.cos(rad),cy+9*math.sin(rad),cx+48*math.cos(rad),cy+48*math.sin(rad),GOLD,.65,3)
    circ(cx,cy,7,SAND,GOLD)
    txt(85,65,'r',9.5,'Bold');txt(104,47,'2r',9.5,'Bold')
    lines(130,117,['At r','Area = 4πr²','Flux = F'],9.5,14)
    lines(130,69,['At 2r','4× the area','Flux = F / 4'],9.5,14,color=TEAL)
    txt(120,11,'No absorption: light spreads out, not “used up.”',9,anchor='center')
    finish(name,h,['math02'],'Doubling distance multiplies the area of the surrounding sphere by four, reducing flux to one quarter.','Two-dimensional rendering of concentric spheres. Assumes isotropic emission, fixed luminosity, and no absorption. Equal total luminosity passes through both spheres.')

def albedo_budget():
    name='albedo-budget';h=177;start(name,h,'Albedo partitions incoming power')
    txt(120,160,'Example: Bond albedo A = 0.25',9.5,'Bold',anchor='center')
    for yy in [96,108,120]:arrow(11,yy,73,yy,GOLD,1,4)
    circ(98,108,25,BLUE,TEAL)
    C.setStrokeColor(TEAL);C.setDash([2,2]);C.ellipse(72,83,80,133,stroke=1,fill=0);C.setDash([])
    arrow(107,121,173,141,GOLD,2.5,6);arrow(107,94,174,75,TEAL,7.5,10)
    txt(49,137,'100 in',9.5,'Bold',anchor='center')
    lines(184,123,['25 reflected','75 absorbed'],9.2,39,anchor='center')
    txt(120,45,'Intercepting disk area = πR²',9.5,anchor='center')
    txt(120,25,'Absorbed power = (1 − A) F πR²',9.5,'Bold',anchor='center')
    txt(120,8,'Incoming energy only; emission is a separate step.',9,anchor='center')
    finish(name,h,['math03'],'For a Bond albedo of 0.25, 25 of every 100 units of incoming power are reflected and 75 are absorbed.','Illustrative power units, not a particular planet. Incoming power is flux times projected disk area, not whole-sphere area. Arrows partition the energy budget; the absorbed-power arrow is not outgoing radiation. Does not include thermal emission or greenhouse transfer. The disk is shown edge-on in perspective.')

def instrument_inference():
    name='instrument-inference';h=188;start(name,h,'Radar measurement to interior inference')
    txt(120,172,'Radar: signal → model → inference',9.5,'Bold',anchor='center')
    # Left: a pulse travels down through material and returns from a boundary.
    rect(10,56,70,75,BLUE)
    rect(10,45,70,11,ROCK)
    line(10,131,80,131,TEAL,1);line(10,56,80,56,INK,1)
    rect(29,145,32,12,PALE,INK)
    txt(45,148,'Radar',9,anchor='center')
    arrow(36,141,36,60,GOLD,1.1);arrow(53,60,53,141,TEAL,1.1)
    txt(17,89,'d',10,'Bold');txt(45,31,'Reflector',9,anchor='center')
    for y,label,sublabel in [(130,'MEASURE','Surface-to-base Δt'),(90,'ASSUME','Wave speed v in ice'),(50,'INFER','Depth d = vΔt / 2')]:
        rect(94,y,136,32,PALE,GRID,.5)
        txt(102,y+20,label,9,'Bold',color=TEAL);txt(102,y+7,sublabel,9)
    arrow(162,129,162,123,GREY,.8,3);arrow(162,89,162,83,GREY,.8,3)
    txt(120,10,'A strong echo alone does not identify liquid water.',9,anchor='center')
    finish(name,h,['engineering-instruments','missions-europa'],'Radar measures the delay Δt between surface and subsurface echoes. A model for wave speed turns this into a depth estimate; reflection strength does not uniquely identify liquid water.','Simplified vertical, two-way travel path in a uniform medium. Δt is the subsurface echo delay relative to the surface echo, excluding the spacecraft-to-surface path. Depth equation omits refraction, layering, and calibration offsets. A real instrument measures received waveform and timing, not depth directly.')

def water_phase():
    name='water-phase';h=192;start(name,h,'A schematic water phase diagram')
    txt(120,176,'Low pressure can remove the liquid route',9.4,'Bold',anchor='center')
    x0=33;y0=33;arrow(x0,y0,226,y0,GREY,.8);arrow(x0,y0,x0,160,GREY,.8)
    txt(131,17,'Temperature →',9.5,anchor='center')
    C.saveState();C.translate(13,99);C.rotate(90);C.setFont('Sans',9.5);C.setFillColor(INK);C.drawCentredString(0,0,'Pressure →');C.restoreState()
    p=C.beginPath();p.moveTo(41,39);p.curveTo(64,47,88,62,112,83);p.curveTo(147,97,185,122,224,151)
    C.setStrokeColor(TEAL);C.setLineWidth(1.4);C.drawPath(p,fill=0,stroke=1)
    line(112,83,96,159,TEAL,1.4)
    txt(69,113,'Ice',10,'Bold',anchor='center');txt(142,132,'Liquid',10,'Bold',anchor='center');txt(172,64,'Vapor',10,'Bold',anchor='center')
    circ(112,83,2.6,GOLD,GOLD);line(115,82,147,82,GREY,.6);txt(150,79,'Triple point',9)
    line(45,52,208,52,GOLD,1,[3,2]);arrow(198,52,210,52,GOLD,1,4)
    txt(136,39,'Heat below the triple-point pressure',9,anchor='center')
    txt(120,3,'Simplified boundaries; axes not numbered.',9,anchor='center')
    finish(name,h,['foundation-4'],'Below the triple-point pressure, heating ice crosses the solid-vapor boundary without entering the liquid region.','Qualitative water phase topology with no numerical axis scale. The ice-liquid boundary has the negative slope appropriate to ordinary ice near the triple point. High-pressure ice phases and the critical point are outside the schematic; curve shapes and angles are not quantitative.')

def export_and_audit():
    import fitz
    audit=[]
    for figure in manifest:
        pdf=OUTPUT/figure['file']; doc=fitz.open(pdf); page=doc[0]
        svg=pdf.with_suffix('.svg')
        vector=page.get_svg_image(text_as_path=True)
        title=pdf.stem.replace('-',' ').title()
        desc=figure['caption']+' '+figure['limitations']
        vector=re.sub(r'(<svg\b[^>]*>)',lambda m:m.group(1)+'<title>'+escape(title)+'</title><desc>'+escape(desc)+'</desc>',vector,count=1)
        svg.write_text(vector)
        spans=[s for b in page.get_text('dict')['blocks'] if b['type']==0 for line in b['lines'] for s in line['spans']]
        minsize=min(s['size'] for s in spans)
        assert minsize>=8.99, (pdf,minsize)
        assert not page.get_images(full=True), 'Raster unexpectedly embedded in '+str(pdf)
        outliers=[s['text'] for s in spans if s['bbox'][0]<-.1 or s['bbox'][1]<-.1 or s['bbox'][2]>page.rect.width+.1 or s['bbox'][3]>page.rect.height+.1]
        assert not outliers,(pdf,outliers)
        audit.append({'file':pdf.name,'pages':len(doc),'minimum_extracted_font_size_pt':round(minsize,3),'embedded_raster_images':0,'text_bounding_boxes_within_page':True,'svg_vector_export':True})
    (OUTPUT/'qa-structural.json').write_text(json.dumps({'figures':audit,'note':'Structural validation supplements, not replaces, visual review.'},indent=2)+'\n')

def synchronous_rotation():
    start('synchronous-rotation',240,'One rotation in one orbit')
    txt(120,224,'One rotation in one orbit',11,'Bold',anchor='center')
    cx,cy,orb=120,128,65
    C.setStrokeColor(GRID);C.setDash([3,3]);C.circle(cx,cy,orb,stroke=1,fill=0);C.setDash([])
    circ(cx,cy,16,BLUE,TEAL);txt(cx,cy-31,'Planet',9,anchor='center')
    for idx,a in enumerate([0,math.pi/2,math.pi,3*math.pi/2]):
     x,y=cx+orb*math.cos(a),cy+orb*math.sin(a)
     circ(x,y,13,SAND,GOLD)
     # Mark a point on the near-side surface, always directed toward the planet.
     circ(x-9*math.cos(a),y-9*math.sin(a),2.3,TEAL,TEAL)
     arrow(x-18*math.cos(a),y-18*math.sin(a),x-30*math.cos(a),y-30*math.sin(a),TEAL,head=3)
     txt(x+19*math.cos(a)+(17 if idx==3 else 0),y+20*math.sin(a)-3+(8 if idx==3 else 0),str(idx+1),9,'Bold',anchor='center')
    arrow(173,170,159,182,GOLD,head=4)
    lines(120,33,['The marked face always points inward.','Its direction turns once per orbit.','Sizes and distances are not to scale.'],9,12,anchor='center')
    finish('synchronous-rotation',240,['foundation-terms-2'],'A moon can rotate once per orbit while keeping the same face toward its planet. Follow the marked point through positions 1–4.','Ideal circular, coplanar orbit viewed from above; libration and axial tilt are omitted. Marker denotes the same surface point, not illumination or lunar phase.')


def generate(destination):
    """Build print vectors, web vectors, and structural QA outside the source tree."""
    global OUTPUT
    OUTPUT = Path(destination)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    manifest.clear()
    for draw in (
        orbital_hierarchy, diameter_logscale, habitability_overlap, atmosphere_escape,
        habitable_zone, ocean_contact, bennu_shape, transit_depth, rv_inclination,
        inverse_square, albedo_budget, instrument_inference, water_phase, synchronous_rotation,
    ):
        draw()
    export_and_audit()
    index = OUTPUT / 'manifest.json'
    index.write_text(json.dumps({'figures': manifest}, ensure_ascii=False, indent=2) + '\n')
    return index
