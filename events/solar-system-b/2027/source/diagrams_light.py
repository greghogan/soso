"""Editable vector teaching figures for the hybrid Solar System B guide.

All positions are in a 516-unit-wide design space.  No raster art, data-like
random textures, page furniture, or scientific content changes are introduced.
The light curves and interior drawings are explicitly schematic, except the
mathematical plots, which evaluate their stated relations.
"""
import math
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[4]/"shared"))
from math_notation import TOKEN_SPECS
from font_paths import dejavu_font
import re
from reportlab.lib.colors import HexColor, Color
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_CENTER

BG = HexColor('#FFFFFF')
PANEL = HexColor('#EDF5F5')
PANEL2 = HexColor('#E1EDEE')
CYAN = HexColor('#087B85')
GOLD = HexColor('#A86D16')
WHITE = HexColor('#15333F')
ICE = HexColor('#B2DDE8')
MUTED = HexColor('#526874')
COPPER = HexColor('#D99572')
BLUE = HexColor('#307FA6')
ROCK = HexColor('#765C50')
LINE = HexColor('#B8CCD1')

SUPPORTED_KINDS = frozenset(('flow ingredients phase waterforms biomolecules energy zone greenhouse retention tides geology spectrum world transit rv lensing imaging mission equation graph flux blackbody equilibrium orbit practice').split())
LAYOUT_WARNINGS = []


def _fonts():
    for name, filename in [('HybridSans','DejaVuSans.ttf'),('HybridBold','DejaVuSans-Bold.ttf'),('HybridItalic','DejaVuSans-Oblique.ttf')]:
        if name not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont(name, dejavu_font(filename)))
    pdfmetrics.registerFontFamily('HybridSans', normal='HybridSans', bold='HybridBold', italic='HybridItalic', boldItalic='HybridBold')


class Figure:
    def __init__(self, canvas, lesson, height=360):
        self.c = canvas
        self.lesson = lesson
        self.v = lesson.get('visual', {})
        self.id = lesson.get('id', '')
        self.height = height

    def text(self, text, x, top, width, size=14, color=WHITE, bold=False, center=False, leading=None, maxh=None):
        color = MUTED if color == ICE else (GOLD if color == COPPER else color)
        text = str(text).replace('\n','<br/>')
        # Unicode subscript glyph designs differ by font; explicitly position chemistry indices.
        text = re.sub('[₀₁₂₃₄₅₆₇₈₉]+', lambda m: '<sub rise="20%" size="70%">'+m[0].translate(str.maketrans('₀₁₂₃₄₅₆₇₈₉','0123456789'))+'</sub>', text)
        for token,spec in TOKEN_SPECS.items():
            text=re.sub(r'(?<!\w)'+re.escape(token)+r'(?!\w)',lambda m:spec.base+'<sub>'+spec.index+'</sub>',text)
        text=text.replace('<sub>','<sub rise="20%" size="70%">')
        size = max(12.1, size)
        style = ParagraphStyle('diagram', fontName='HybridBold' if bold else 'HybridSans', fontSize=size, leading=leading or size*1.23, textColor=color, alignment=TA_CENTER if center else TA_LEFT)
        p = Paragraph(text,style)
        _, h = p.wrap(width, 1000)
        if x < -.1 or x+width > 516.1 or top > self.height+.1 or top-h < -.1 or (maxh is not None and h > maxh+.1):
            LAYOUT_WARNINGS.append((self.id, str(text)[:90], (x,top,width,h), maxh))
        p.drawOn(self.c,x,top-h)
        return h

    def label(self, text, x, top, width, size=14, color=WHITE, bold=False, **kw):
        return self.text(text,x,top,width,size,color,bold,True,**kw)

    def line(self,x1,y1,x2,y2,color=LINE,width=1,dash=None):
        c=self.c;c.saveState();c.setStrokeColor(color);c.setLineWidth(width)
        if dash:c.setDash(dash)
        c.line(x1,y1,x2,y2);c.restoreState()

    def path(self,pts,color=CYAN,width=1.6,fill=None,close=False,dash=None):
        if not pts:return
        c=self.c;c.saveState();c.setStrokeColor(color);c.setLineWidth(width)
        if dash:c.setDash(dash)
        if fill:c.setFillColor(fill)
        p=c.beginPath();p.moveTo(*pts[0])
        for xy in pts[1:]:p.lineTo(*xy)
        if close:p.close()
        c.drawPath(p,stroke=1,fill=int(fill is not None));c.restoreState()

    def arrow(self,x1,y1,x2,y2,color=CYAN,width=1.6,head=5,dash=None):
        self.line(x1,y1,x2,y2,color,width,dash)
        a=math.atan2(y2-y1,x2-x1)
        self.path([(x2,y2),(x2-head*math.cos(a-.45),y2-head*math.sin(a-.45)),(x2-head*math.cos(a+.45),y2-head*math.sin(a+.45))],color,.3,color,True)

    def rect(self,x,y,w,h,fill=PANEL,stroke=LINE,r=5,width=.6):
        c=self.c;c.saveState();c.setFillColor(fill);c.setStrokeColor(stroke or fill);c.setLineWidth(width)
        c.roundRect(x,y,w,h,r,fill=1,stroke=int(stroke is not None));c.restoreState()

    def circle(self,x,y,r,fill=CYAN,stroke=None,width=1):
        c=self.c;c.saveState();c.setFillColor(fill);c.setStrokeColor(stroke or fill);c.setLineWidth(width);c.circle(x,y,r,fill=1,stroke=int(stroke is not None));c.restoreState()

    def ellipse(self,x,y,w,h,color=CYAN,width=1,fill=None,dash=None):
        c=self.c;c.saveState();c.setStrokeColor(color);c.setLineWidth(width)
        if fill:c.setFillColor(fill)
        if dash:c.setDash(dash)
        c.ellipse(x,y,x+w,y+h,fill=int(fill is not None),stroke=1);c.restoreState()

    def kicker(self,text):
        self.text(text.upper(),14,self.height-13,488,13,CYAN,True,leading=16,maxh=35)
        self.line(14,self.height-52,502,self.height-52,LINE,.65)

    def caption(self,text):
        self.line(14,58,502,58,LINE,.65)
        self.text(text,14,50,488,12.1,MUTED,leading=14.4,maxh=44)

    def axis(self,x,y,w,h,xlabel,ylabel,grid=True):
        if grid:
            for v in (.25,.5,.75,1):self.line(x,y+h*v,x+w,y+h*v,LINE,.45)
        self.arrow(x,y,x+w+3,y,MUTED,.9,4)
        self.arrow(x,y,x,y+h+3,MUTED,.9,4)
        if ylabel:self.text(ylabel,x,y+h+24,w,12.5,ICE,maxh=32)
        if xlabel:self.label(xlabel,x,y-11,w,12.5,ICE,maxh=32)

    def badge(self,n,x,y,color=CYAN):
        self.circle(x,y,9,PANEL2,color,.8)
        self.label(str(n),x-9,y+7.5,18,12.1,color,True)

    def bullets(self,items,x,top,w,size=14,gap=13):
        yy=top
        for i,s in enumerate(items):
            self.circle(x+3,yy-5,1.7,CYAN)
            yy-=self.text(s,x+13,yy,w-13,size,ICE)+gap
        return yy


def flow(f):
    f.kicker('Evidence → explanation → test')
    nodes=f.v.get('nodes',['Observe','Explain','Test']);n=len(nodes);gap=18;bw=(488-(n-1)*gap)/n
    for i,s in enumerate(nodes):
        xx=14+i*(bw+gap);f.rect(xx,100,bw,130,PANEL2)
        f.badge(i+1,xx+19,211);f.text(s,xx+12,190,bw-24,14.5,WHITE,True,maxh=82)
        if i<n-1:f.arrow(xx+bw+3,163,xx+bw+gap-3,163,GOLD,1.4)
    f.caption(f.v.get('caption','Conceptual sequence; each explanation should lead to a test.'))


def ingredients(f):
    f.kicker('A habitat is an interacting system')
    f.rect(14,99,216,193,HexColor('#103A50'),None)
    f.path([(14,140),(56,151),(92,138),(130,155),(172,140),(230,153),(230,99),(14,99)],ROCK,.6,ROCK,True)
    f.rect(115,150,15,26,ROCK,None,0)
    for dx in (-16,0,16):f.arrow(122+dx*.25,176,122+dx,225,COPPER,1.5,4)
    f.text('LIQUID WATER',26,278,191,13.5,ICE,True)
    f.text('Rock–water\nexchange',26,137,189,14,WHITE)
    for i,(a,b) in enumerate([('Solvent','Transports reactants'),('Chemical energy','Donor–acceptor reactions'),('Elements','Accessible building blocks'),('Persistence','Supply and suitable conditions')]):
        yy=292-i*49;f.badge(i+1,254,yy-10)
        f.text(a,272,yy,229,13,CYAN,True);f.text(b,272,yy-18,229,14,ICE,maxh=35)
    f.caption('Hydrothermal habitat schematic. Heat alone is not a redox fuel.')


def phase(f):
    f.kicker('Water near its low-pressure triple point')
    x,y,w,h=62,101,407,136;f.axis(x,y,w,h,'Temperature →','Pressure ↑ (nonlinear scale)')
    tp=(215,160)
    f.path([(64,103),(99,114),(139,130),(178,149),tp],CYAN,2)
    f.path([tp,(269,178),(310,204),(351,235)],CYAN,2)
    f.path([tp,(209,183),(202,208),(195,240)],ICE,2)
    f.circle(*tp,3.5,GOLD)
    f.label('ICE I',96,221,92,14,ICE,True);f.label('LIQUID',234,233,105,14,CYAN,True)
    f.label('VAPOR',356,161,109,14,GOLD,True)
    f.text('Triple point',224,151,136,12.5,GOLD)
    f.caption('Topology, not scale. Ice I has a negative-slope melting boundary; high-pressure phases are outside this view.')


def waterforms(f):
    f.kicker('Structure changes what ice can do')
    for i,(title,sub) in enumerate([('CRYSTALLINE','Ordered water lattice'),('AMORPHOUS','Disordered solid water'),('CLATHRATE','Guest gas in a water cage')]):
        xx=14+i*166;f.rect(xx,78,156,207,PANEL)
        f.label(title,xx+4,270,148,12.5,CYAN,True)
        if i==0:
            pts=[(xx+30+a*31+(b%2)*6,168+b*24) for a in range(4) for b in range(3)]
            for a in range(4):
                for b in range(3):
                    p=pts[a*3+b]
                    if a<3:f.line(*p,*pts[(a+1)*3+b],BLUE,.8)
                    if b<2:f.line(*p,*pts[a*3+b+1],BLUE,.8)
            for p in pts:f.circle(*p,3.5,ICE)
        elif i==1:
            pts=[(xx+28,172),(xx+48,210),(xx+67,188),(xx+94,218),(xx+125,197),(xx+103,164),(xx+37,194),(xx+80,227),(xx+125,168),(xx+73,159),(xx+111,232)]
            for a,b in [(0,6),(6,1),(1,2),(2,3),(3,4),(4,5),(5,9),(2,9),(3,7),(7,10),(10,4),(4,8)]:f.line(*pts[a],*pts[b],BLUE,.8)
            for p in pts:f.circle(*p,3.5,ICE)
        else:
            pts=[(xx+78+39*math.cos(j*math.pi/3),194+35*math.sin(j*math.pi/3)) for j in range(6)]
            inner=[(xx+78+22*math.cos(j*math.pi/3+.45),194+20*math.sin(j*math.pi/3+.45)) for j in range(6)]
            f.path(pts,CYAN,1.2,close=True);f.path(inner,BLUE,.9,close=True)
            for a,b in zip(pts,inner):f.line(*a,*b,BLUE,.7)
            for p in pts:f.circle(*p,3.5,ICE)
            f.circle(xx+78,194,8,GOLD)
        f.label(sub,xx+9,130,138,14,ICE,maxh=52)
    f.caption('Molecular organization cartoons, not atomic structures or crystal unit cells.')


def biomolecules(f):
    f.kicker('Four molecular families, different roles')
    blocks=[(14,185,'PROTEINS','Folded tools',COPPER),(267,185,'NUCLEIC ACIDS','Encoded information',CYAN),(14,75,'LIPIDS / MEMBRANES','Selective boundaries',CYAN),(267,75,'CARBOHYDRATES','Fuel and structure',GOLD)]
    for x,y,title,desc,col in blocks:
        f.rect(x,y,235,100,PANEL);f.text(title,x+10,y+87,215,12.1,col,True)
        f.text(desc,x+114,y+56,111,14,ICE,maxh=52)
    pts=[(34,237),(46,246),(60,233),(78,240),(96,228),(80,220),(61,225),(46,218)]
    f.path(pts,COPPER,1.6)
    for p in pts:f.circle(*p,3.5,COPPER)
    for i in range(6):
        xx=287+i*14;dy=6*math.sin(i)
        f.circle(xx,236+dy,2.4,CYAN);f.circle(xx,218+dy,2.4,CYAN);f.line(xx,234+dy,xx,220+dy,GOLD,1)
        if i:f.line(xx-14,236+6*math.sin(i-1),xx,236+dy,BLUE,1);f.line(xx-14,218+6*math.sin(i-1),xx,218+dy,BLUE,1)
    for i in range(7):
        xx=33+i*11
        for yy,d in [(132,-1),(108,1)]:
            f.circle(xx,yy,2.8,CYAN);f.line(xx-1,yy+d*3,xx-2,yy+d*10,COPPER,.8);f.line(xx+1,yy+d*3,xx+2,yy+d*10,COPPER,.8)
    for xx in (291,322,353):f.path([(xx+10*math.cos(i*math.pi/3),122+10*math.sin(i*math.pi/3)) for i in range(6)],GOLD,1.2,close=True)
    f.line(301,122,312,122,GOLD,1);f.line(332,122,343,122,GOLD,1)
    f.caption('Conceptual shapes. Organic ingredients alone do not demonstrate organisms.')


def energy(f):
    if f.id=='math14':
        f.kicker('Dynamic equilibrium: equal rates, not equal amounts')
        f.rect(14,126,157,107,PANEL2);f.rect(345,126,157,107,PANEL2)
        f.label('REACTANTS',24,219,137,12.5,CYAN,True);f.label('PRODUCTS',355,219,137,12.5,GOLD,True)
        for xx,yy in [(42,153),(68,181),(93,152),(121,181),(145,153)]:f.circle(xx,yy,6,CYAN)
        for xx,yy in [(381,158),(421,181),(464,153)]:f.circle(xx,yy,8,GOLD)
        f.arrow(181,189,335,189,CYAN,2.1);f.arrow(335,151,181,151,GOLD,2.1)
        f.label('forward rate',177,215,162,12.5,CYAN);f.label('reverse rate',177,142,162,12.5,GOLD)
        f.label('rate<sub>forward</sub> = rate<sub>reverse</sub>',34,105,448,19,WHITE,True)
        f.caption('Both directions continue while bulk concentrations stay constant. Particle counts are symbolic.')
    else:
        f.kicker('Disequilibrium can power chemical work')
        f.rect(14,142,156,99,PANEL2);f.rect(346,142,156,99,PANEL2)
        f.label('DONOR',24,224,136,13,CYAN,True);f.label('H₂',24,198,136,29,WHITE)
        f.label('ACCEPTOR',356,224,136,13,GOLD,True);f.label('CO₂',356,198,136,29,WHITE)
        f.arrow(181,190,334,190,COPPER,3);f.label('electron transfer',175,171,166,12.5,COPPER)
        f.label('4 H₂ + CO₂ → CH₄ + 2 H₂O',25,113,466,22,WHITE,True)
        f.caption('Methanogenesis example. Available energy depends on temperature, pressure and chemical activities.')


def zone(f):
    f.kicker('Habitable zone ≠ guaranteed habitat')
    f.circle(49,174,24,GOLD)
    for i,(title,sub,col) in enumerate([('HIGH FLUX','Surface water difficult',COPPER),('MODELED HZ','Surface water possible',CYAN),('LOW FLUX','Surface freezing favored',ICE)]):
        xx=94+i*138;f.rect(xx,104,130,132,PANEL,col,.5)
        f.label(title,xx+5,222,120,12.2,col,True);f.label(sub,xx+10,190,110,14,ICE,maxh=70)
    f.arrow(91,88,491,88,MUTED,1);f.label('Orbital distance increases →',108,81,372,12.5,ICE)
    f.caption('Model-dependent surface-water zone. Subsurface habitats can lie outside it.')


def greenhouse(f):
    f.kicker('An atmosphere changes infrared transfer')
    f.rect(14,96,488,29,ROCK,None,0);f.rect(14,194,488,40,PANEL2,None,0)
    f.text('ATMOSPHERE',362,224,132,12.2,CYAN,True);f.text('SURFACE',25,117,122,12.2,HexColor('#FFFFFF'),True)
    f.arrow(78,281,148,126,GOLD,3);f.text('starlight',27,288,111,12.5,GOLD)
    f.arrow(230,126,230,280,COPPER,2.4);f.text('IR window',172,290,145,12.5,COPPER)
    f.arrow(323,126,323,204,COPPER,2.4);f.circle(323,214,5,COPPER)
    f.arrow(330,222,379,280,COPPER,2);f.arrow(330,206,380,127,COPPER,2)
    f.text('Absorb and emit IR up and down',385,186,113,14,ICE,maxh=70)
    f.caption('Energy pathways, not ray fractions. Emission depends on temperature and opacity.')


def retention(f):
    f.kicker('Compare thermal motion with escape')
    for i,(title,col,sub) in enumerate([('COLDER / STRONGER GRAVITY',BLUE,'Lower thermal speed relative to escape'),('HOTTER / WEAKER GRAVITY',COPPER,'Higher thermal speed relative to escape')]):
        xx=14+i*253;f.rect(xx,89,235,177,PANEL)
        f.label(title,xx+8,253,219,12.2,CYAN if i==0 else GOLD,True,maxh=35)
        f.circle(xx+60,184,25 if i==0 else 20,col)
        for j in range(3):
            yy=169+j*16;length=(24+j*4) if i==0 else (59+j*10)
            f.arrow(xx+100,yy,xx+100+length,yy,CYAN if i==0 else GOLD,1.2)
        f.label(sub,xx+10,145,215,14,ICE,maxh=52)
    f.caption('Thermal escape only. Composition, stellar activity and replenishment also matter.')


def geology(f):
    f.kicker('Geometry suggests a process; context tests it')
    for i,title in enumerate(['VALLEY NETWORK','DELTA','SEDIMENTARY LAYERS']):
        xx=14+i*166;f.rect(xx,95,156,173,PANEL)
        f.label(title,xx+6,254,144,12.2,CYAN,True,maxh=35)
        if i==0:
            for a,b in [((xx+25,207),(xx+73,168)),((xx+65,213),(xx+73,168)),((xx+128,203),(xx+73,168))]:f.path([a,b,(xx+86,131)],CYAN,2)
            f.path([(xx+27,176),(xx+53,185)],CYAN,1.3)
        elif i==1:
            f.line(xx+78,215,xx+78,185,CYAN,3)
            for j in range(5):f.path([(xx+78,185),(xx+52+j*13,162),(xx+25+j*26,134)],CYAN,1.5)
            f.path([(xx+20,127),(xx+137,127)],BLUE,3)
        else:
            for j in range(5):f.path([(xx+13,131+j*17),(xx+60,137+j*16),(xx+103,130+j*17),(xx+142,138+j*15)],COPPER,2)
    f.caption('Similar shapes can have different histories. Compare the processes that could form each landform.')


def spectrum(f):
    f.kicker('Absorption features constrain composition')
    x,y,w,h=62,85,410,96;f.axis(x,y,w,h,'Wavelength →','Relative reflected light')
    pts=[]
    for i in range(401):
        t=i/400;v=.83-.48*math.exp(-((t-.3)/.048)**2)-.32*math.exp(-((t-.7)/.065)**2);pts.append((x+t*w,y+v*h))
    f.path(pts,CYAN,2.2)
    f.arrow(185,185,185,120,GOLD,1.1);f.arrow(349,193,349,139,GOLD,1.1)
    f.label('absorption bands',264,216,208,12.3,GOLD)
    f.caption('Schematic spectrum, not observations. Compare bands with laboratory references and alternative models.')


def _ice_world(f,name):
    f.kicker({'europa':'Connect surface chemistry, hidden water and rock','ganymede':'Layer structure controls ocean–rock contact','enceladus':'Measured plume → inferred source'}[name])
    f.rect(14,238,234,61,HexColor('#A6C6D4'),None,0);f.rect(14,163,234,75,HexColor('#1E6789'),None,0);f.rect(14,103,234,60,ROCK,None,0)
    f.text('ICE SHELL',26,282,210,13,BG,True);f.text('INFERRED\nSALTY WATER',26,218,211,13.5,WHITE,True)
    if name=='ganymede':
        f.rect(14,150,234,23,HexColor('#6D9DB4'),None,0);f.text('High-pressure ice?',26,169,211,12.5,BG,True);f.text('ROCK-RICH INTERIOR',26,133,211,12.3,WHITE,True)
    else:f.text('ROCKY SEAFLOOR',26,137,211,12.5,WHITE,True)
    if name in ('europa','enceladus'):
        f.path([(209,299),(197,281),(211,259),(201,239)],BG,2.2);f.arrow(201,224,201,267,CYAN,1.4,4,dash=[3,2])
        for dx in (-12,12):f.arrow(175+dx,163,175+dx,185,COPPER,1.1,4,dash=[3,2])
    if name=='enceladus':
        for dx in (-15,0,15):f.arrow(203,295,203+dx,307,CYAN,1.3,4)
    f.bullets(f.v.get('labels',[]),272,291,228,14,17)
    cap={'europa':'Interior model, not scale. Transport and seafloor activity remain hypotheses.','ganymede':'Interior model, not a measured section. Liquid layers, high-pressure ice and connectivity remain uncertain.','enceladus':'Layer model, not scale. Plume ingredients were measured; deep reaction pathways are inferred.'}[name]
    f.caption(cap)


def _venus(f):
    f.kicker('Atmospheric layers impose different constraints')
    f.rect(14,98,235,199,HexColor('#593E32'),None,0);f.rect(14,98,235,34,HexColor('#A45D3F'),None,0)
    for j in range(5):f.path([(15,229+j*11),(88,236+j*10),(165,227+j*11),(249,233+j*10)],GOLD,2)
    f.rect(22,263,137,23,HexColor('#593E32'),None,0);f.text('ACID CLOUDS',26,282,211,13,GOLD,True);f.text('DENSE CO₂',26,194,211,14,ICE,True);f.text('HOT SURFACE',26,123,211,13,WHITE,True)
    f.text('Clouds',277,294,221,14,CYAN,True);f.text('Milder temperature does not remove acidity or low water availability.',277,273,221,14,ICE,maxh=86)
    f.text('Surface',277,179,221,14,COPPER,True);f.text('Dense CO₂ drives intense greenhouse warming.',277,158,221,14,ICE,maxh=69)
    f.caption('Atmospheric profile, not scale. Temperature alone does not establish habitability.')


def _mars(f):
    f.kicker('A past habitat leaves a modern geological record')
    for i,title in enumerate(['PAST: LAKE MODEL','TODAY: GEOLOGICAL CLUES']):
        xx=14+i*253;f.rect(xx,102,235,191,PANEL);f.text(title,xx+10,279,215,12.5,CYAN,True,maxh=34)
        f.path([(xx+10,218),(xx+51,224),(xx+91,206),(xx+143,213),(xx+224,207),(xx+224,120),(xx+10,120)],ROCK,.6,ROCK,True)
        if i==0:
            f.path([(xx+103,203),(xx+221,203),(xx+196,162),(xx+141,166)],BLUE,.8,BLUE,True)
            f.path([(xx+24,243),(xx+57,226),(xx+88,223),(xx+131,202)],CYAN,2.2);f.path([(xx+63,246),(xx+57,226)],CYAN,1.6)
            for dy in (0,7,14):f.line(xx+135,177+dy,xx+193,177+dy,CYAN,.6)
        else:
            for j in range(5):f.path([(xx+17,132+j*16),(xx+79,139+j*14),(xx+143,131+j*16),(xx+217,136+j*15)],COPPER,1.6)
            f.text('layers + minerals',xx+27,239,187,12.5,ICE)
    f.caption('The lake is reconstructed, not photographed. Past water does not demonstrate past organisms.')


def _titan_surface(f):
    f.kicker('Hydrocarbon weather over water-ice terrain')
    f.rect(14,103,278,196,HexColor('#3C3A2F'),None,0);f.rect(14,103,278,38,HexColor('#7A705D'),None,0)
    f.ellipse(146,116,128,23,CYAN,.9,BLUE);f.text('CH₄ / C₂H₆ lake',139,97,145,12.1,ICE)
    for xx in (59,79,100):f.circle(xx,256,14,HexColor('#A7976E'))
    f.arrow(72,233,72,151,CYAN,1.8);f.arrow(211,152,211,239,GOLD,1.8)
    f.text('rain',27,209,63,13,CYAN);f.text('vapor',220,214,70,13,GOLD)
    f.text('N₂ + ORGANIC HAZE',25,287,244,12.4,GOLD,True)
    f.text('Surface solvent',310,294,184,14,CYAN,True);f.text('Methane and ethane, not liquid water.',310,271,184,14,ICE,maxh=70)
    f.text('Solid landscape',310,190,184,14,GOLD,True);f.text('Water ice behaves as rock in this cold setting.',310,167,184,14,ICE,maxh=70)
    f.caption('Surface cycle, not an interior measurement. The lakes do not establish deep liquid water.')


def _titan_interior(f):
    f.kicker('Test competing interiors with tidal measurements')
    for i,(title,sub) in enumerate([('EARLIER OCEAN MODEL','Continuous deep liquid layer'),('2025 ALTERNATIVE','Slush and localized melt')]):
        xx=14+i*253;f.label(title,xx+5,283,225,12.5,CYAN,True,maxh=33)
        f.rect(xx,210,235,35,HexColor('#9C9D88'),None,0);f.rect(xx,141,235,69,BLUE if i==0 else HexColor('#4A6979'),None,0);f.rect(xx,115,235,26,ROCK,None,0)
        f.text('Frozen exterior',xx+10,237,215,12.5,BG,True)
        if i:
            for dx,dy in [(25,163),(91,181),(159,159)]:f.ellipse(xx+dx,dy,41,12,CYAN,.7,BLUE)
        else:f.text('Water-rich liquid',xx+10,190,215,14,WHITE)
        f.label(sub,xx+8,100,219,14,ICE,maxh=35)
    f.caption('Competing model cartoons, not measured sections. The December 2025 alternative is a hypothesis.')


def _primitive(f,name):
    iscomet='67p' in name
    f.kicker('Sublimation carries a changing sample' if iscomet else 'A returned sample records an ancient parent body')
    if iscomet:
        f.ellipse(33,176,82,69,ROCK,.8,ROCK);f.ellipse(101,190,57,49,ROCK,.8,ROCK)
        f.path([(91,205),(112,216),(107,230),(87,220)],ROCK,.5,ROCK,True)
        for dx,dy in [(29,35),(47,21),(59,4)]:f.arrow(151,231,151+dx,231+dy,CYAN,1.2)
        f.arrow(28,282,64,250,GOLD,1.4);f.text('solar heating',18,294,175,12.5,GOLD)
        f.text('ICE + DUST',35,160,160,13,ICE,True)
        f.text('NUCLEUS → COMA',246,285,255,14,CYAN,True)
        f.bullets(['Solid ice changes directly to gas.','Gas and dust carry chemical clues.','Activity changes what is sampled.'],246,254,255,14,15)
        f.caption('Nucleus/coma schematic. Sublimation is not melting; a coma is not a dense, stable atmosphere.')
    else:
        pts=[(31,211),(70,255),(122,244),(162,201),(123,158),(65,161)];f.path(pts,HexColor('#9C8F83'),1.2,ROCK,True)
        for a,b in [(0,3),(1,4),(2,5)]:f.line(*pts[a],*pts[b],HexColor('#9C8F83'),.6)
        f.text('BENNU TODAY',24,145,172,12.5,ICE,True)
        f.arrow(173,210,219,210,GOLD,1.8);f.rect(208,116,43,39,PANEL2,CYAN,3);f.line(214,148,245,148,CYAN,1)
        f.text('sample',196,108,79,12.5,ICE,center=True)
        f.text('EARTH LABORATORIES',271,286,230,14,CYAN,True)
        f.bullets(['Curated returned material','Brine minerals and organic building blocks','Ancient water-related processing'],271,253,230,14,15)
        f.caption('Modern Bennu has no depicted ocean. Ancient aqueous processing is reconstructed from its sample.')


def _makemake(f):
    f.kicker('A distant spectrum is not an ocean photograph')
    f.circle(99,192,48,HexColor('#72665F'),ICE,.9);f.label('SURFACE NOT MAPPED',20,130,166,12.3,ICE,True,maxh=33)
    for yy in (180,192,204):f.arrow(155,yy,223,yy,CYAN,1.1)
    f.text('spectrum',155,232,99,12.5,CYAN)
    f.axis(268,112,216,111,'Wavelength →','Relative signal')
    f.path([(268+i*.54,112+84-39*math.exp(-((i/400-.42)/.07)**2)-26*math.exp(-((i/400-.74)/.05)**2)) for i in range(401)],CYAN,1.7)
    f.caption('Conceptual spectrum. Volatile-ice signatures do not reveal an ocean or a habitable interior.')


def _trappist(f):
    f.kicker('One star, seven planets, different flux')
    f.circle(43,193,22,COPPER);f.rect(259,143,152,111,PANEL2,CYAN,5,.7)
    f.label('COMMON HZ MODELS',266,244,138,12.1,CYAN,True,maxh=33)
    for i,letter in enumerate('bcdefgh'):
        xx=104+i*57;f.circle(xx,190,[9,9,7,8,10,11,7][i],CYAN if letter in 'efg' else BLUE);f.label(letter,xx-15,169,30,14,WHITE,True)
    f.arrow(82,119,477,119,MUTED,.9);f.label('Orbital sequence →',92,109,380,13,ICE)
    f.caption('No common scale for star size, planet sizes or orbital spacing. Planetary surfaces are unknown.')


def _exoplanet(f,name):
    if 'lhs' in name:
        f.kicker('Mass and radius permit competing models')
        for i,(title,layers) in enumerate([('WATER-RICH MODEL',[(45,BLUE),(29,ROCK)]),('GAS-ENVELOPE MODEL',[(45,HexColor('#567585')),(31,ROCK)])]):
            xx=136+i*244
            for rr,col in layers:f.circle(xx,212,rr,col,ICE,.5)
            f.label(title,xx-112,289,224,12.5,CYAN,True);f.label('hypothesis',xx-100,153,200,13,ICE)
        f.label('≈1.73 Earth radii  ·  ≈5.6 Earth masses',20,120,476,15,WHITE,True)
        f.label('Atmosphere and detailed layers are not confirmed.',20,95,476,14,ICE)
        f.caption('Alternative interior cartoons, not measured sections. No open ocean or surface map is established.')
    else:
        f.kicker('An Earth-like orbit is not an Earth-like surface')
        f.circle(99,194,48,HexColor('#3D5362'),ICE,.8);f.label('?',61,222,76,38,CYAN,True)
        f.label('APPEARANCE UNKNOWN',16,130,168,12.1,ICE,True,maxh=33)
        f.text('MEASURED CONSTRAINTS',217,265,279,14,CYAN,True);f.bullets(f.v.get('labels',[]),217,233,279,14,17)
        f.caption('Symbolic disk, not an observed surface. Transit radius and orbit do not establish oceans or air.')


def world(f):
    name=f.v.get('name','').lower()
    if name in ('europa','ganymede','enceladus'):_ice_world(f,name)
    elif name=='venus':_venus(f)
    elif name=='mars':_mars(f)
    elif 'titan interior' in name:_titan_interior(f)
    elif name.startswith('titan'):_titan_surface(f)
    elif 'bennu' in name or '67p' in name:_primitive(f,name)
    elif 'makemake' in name:_makemake(f)
    elif 'trappist' in name:_trappist(f)
    elif 'kepler' in name or 'lhs' in name:_exoplanet(f,name)
    else:raise ValueError('Unsupported named-world diagram: '+repr(name))

def transit(f):
    f.kicker('Transit depth measures a missing fraction')
    f.circle(87,214,43,GOLD);f.line(28,214,167,214,WHITE,.7,[3,3]);f.circle(99,214,11,BG,CYAN,.5);f.arrow(118,214,164,214,CYAN,1.5)
    f.label('δ ≈ (Rₚ/R★)²',17,147,182,19,WHITE,True)
    f.axis(245,119,239,126,'Time →','Relative brightness')
    f.path([(246,226),(293,226),(308,180),(405,180),(420,226),(482,226)],CYAN,2.1)
    f.line(444,180,444,226,GOLD,1);f.line(439,180,449,180,GOLD,1);f.line(439,226,449,226,GOLD,1);f.text('δ',454,212,24,15,GOLD)
    f.caption('Schematic. Radius-ratio approximation neglects limb darkening, dilution and grazing geometry.')


def rv(f):
    f.kicker('Stellar line shifts trace a gravitational wobble')
    f.ellipse(28,179,164,78,LINE,1);f.ellipse(85,206,50,24,COPPER,.9);f.circle(85,218,20,GOLD);f.circle(192,218,7,BLUE)
    f.line(110,212,110,224,WHITE,.9);f.line(104,218,116,218,WHITE,.9);f.arrow(83,243,61,254,COPPER,1.5);f.arrow(183,199,160,192,CYAN,1.5)
    f.label('Shared center of mass',18,161,184,14,ICE,maxh=35)
    f.axis(247,119,239,126,'Time →','Stellar radial velocity')
    f.line(247,182,486,182,MUTED,.7,[3,3]);f.path([(247+i*239/300,182+45*math.sin(i/300*4*math.pi)) for i in range(301)],CYAN,2)
    f.text('0',230,190,15,12.5,ICE)
    f.caption('Circular-orbit velocity model; geometry not to scale. RV alone usually gives the minimum mass Mₚ sin i.')


def lensing(f):
    f.kicker('Alignment bends light; a planet perturbs the signal')
    f.circle(53,256,7,GOLD);f.circle(220,256,17,BLUE);f.circle(239,273,3,CYAN);f.circle(440,256,4,ICE)
    f.path([(65,256),(218,286),(437,256)],GOLD,1.2);f.path([(65,256),(218,228),(437,256)],GOLD,1.2)
    f.text('source star',16,220,113,12.5,ICE);f.text('foreground lens',166,220,160,12.5,ICE);f.text('observer',399,220,103,12.5,ICE)
    f.axis(54,100,429,65,'Time →','Source brightness')
    pts=[]
    for i in range(401):
        t=(i/400-.5)*6;u=math.hypot(.35,t);a=(u*u+2)/(u*math.sqrt(u*u+4));bump=.35*math.exp(-((t-.58)/.1)**2);pts.append((54+i*429/400,100+23*(a-1)+15*bump))
    baseline=[]
    for i in range(401):
        t=(i/400-.5)*6;u=math.hypot(.35,t);a=(u*u+2)/(u*math.sqrt(u*u+4));baseline.append((54+i*429/400,100+23*(a-1)))
    f.path(baseline,GOLD,1.2,dash=[3,2])
    f.path(pts,CYAN,1.7)
    f.text('Dashed: star-only lens model',210,183,275,12.1,GOLD,maxh=25)
    f.caption('Usually an unresolved light curve, not a resolved arc. The planet perturbation shown is illustrative.')


def imaging(f):
    f.kicker('Suppress the star; preserve planet light')
    # A simple opaque focal-plane mask, not a universal coronagraph design.
    f.circle(94,224,51,PANEL2,GOLD,.8)
    f.circle(94,224,36,WHITE,WHITE,1)
    f.label('Star image\nblocked',57,240,74,12.1,BG,maxh=34)
    f.line(94,187,94,170,MUTED,.8)
    f.label('Opaque mask',20,163,148,12.5,WHITE,maxh=34)
    f.circle(190,224,6,CYAN);f.text('Planet light',166,261,93,13,CYAN)
    f.arrow(207,224,261,224,CYAN,1.5);f.rect(272,204,34,40,PANEL2,CYAN,3)
    for j,col in enumerate([CYAN,ICE,GOLD,COPPER]):f.line(307,224,360,197+j*18,col,1.2)
    f.text('Spectrum',371,275,129,14,CYAN,True);f.text('Chemistry\nTemperature\nModels',371,245,129,14,ICE,leading=31)
    f.text('The mask suppresses the star’s image while nearby planet light passes.',20,119,476,13,WHITE,maxh=40)
    f.caption('Brightness contrast, residual starlight and angular separation limit detection.')


def _spacecraft(f,x,y):
    f.rect(x-12,y-9,24,18,PANEL2,ICE,1);f.rect(x-38,y-11,22,22,BLUE,CYAN,0,.8);f.rect(x+16,y-11,22,22,BLUE,CYAN,0,.8)
    for dx in (-31,-24,23,30):f.line(x+dx,y-10,x+dx,y+10,ICE,.5)
    f.line(x-37,y,x-16,y,ICE,.5);f.line(x+17,y,x+37,y,ICE,.5);f.line(x,y+9,x+7,y+23,ICE,1);f.path([(x,y+23),(x+7,y+28),(x+14,y+23)],ICE,.9)


def mission(f):
    f.kicker('Instrument signal → model → scientific question')
    f.text(f.v.get('headline','Measure a signal, not a conclusion.'),251,293,247,14,CYAN,True,maxh=52)
    f.bullets(f.v.get('labels',[]),251,233,247,14,13)
    f.c.saveState();f.c.translate(0,85);_mission_scene(f);f.c.restoreState()
    f.caption('Measurement schematic, not hardware scale or trajectory. Instruments constrain, not certify, habitability.')


def _mission_scene(f):
    ident=f.id
    if 'dragonfly' in ident:
        f.rect(14,52,214,36,ROCK,None,0)
        f.ellipse(48,164,45,8,CYAN,.8);f.ellipse(133,164,45,8,CYAN,.8)
        f.line(70,163,90,143,ICE,1);f.line(155,163,135,143,ICE,1)
        f.rect(89,131,47,20,PANEL2,ICE,2)
        f.line(100,132,91,112,ICE,1);f.line(125,132,136,112,ICE,1)
        f.arrow(112,128,112,86,GOLD,1.5)
        f.text('surface sample',49,77,159,10.3,ICE)
        f.label('MOBILE LABORATORY',19,193,204,10.1,GOLD,True)
    elif 'osiris' in ident:
        f.path([(30,104),(61,153),(104,151),(143,109),(109,73),(60,70)],ROCK,1,ROCK,True)
        _spacecraft(f,176,168)
        f.line(164,157,130,124,ICE,1.4)
        f.circle(129,123,4,GOLD)
        f.arrow(165,100,205,78,CYAN,1.3)
        f.text('collect → return',28,60,191,10.5,ICE)
    elif 'roman' in ident:
        _spacecraft(f,106,146)
        for xx,yy in [(29,182),(64,197),(151,196),(198,173),(204,108),(38,106)]:f.circle(xx,yy,1.9,GOLD)
        f.arrow(111,112,111,77,CYAN,1.3)
        f.text('survey light curves',33,66,180,10.5,ICE)
    elif 'rosetta' in ident:
        f.ellipse(32,79,73,64,ROCK,.8,ROCK);f.ellipse(90,100,47,43,ROCK,.8,ROCK)
        _spacecraft(f,174,166)
        for dx in (0,18,36):f.arrow(121,126,151+dx,146,CYAN,1.1)
        f.text('gas + dust sampling',25,65,202,10.5,ICE)
    elif 'mars-surface' in ident:
        f.rect(14,51,214,34,ROCK,None,0)
        _spacecraft(f,109,169)
        f.arrow(109,149,109,100,CYAN,1.1)
        f.rect(83,86,48,14,PANEL2,ICE,1)
        for xx in (88,108,128):f.circle(xx,84,5,ICE)
        f.text('orbit + rover context',25,66,195,10.2,WHITE)
    elif 'venus-atmosphere' in ident or 'cassini' in ident:
        f.circle(100,117,51,HexColor(f.v.get('color','#8AB4C7')))
        _spacecraft(f,170,172)
        f.path([(91,163),(111,163),(105,153),(96,153)],ICE,1,ICE,True)
        f.arrow(101,149,101,110,GOLD,1.5)
        f.label('orbiter + descent',20,58,206,10.5,ICE)
    elif 'mars-escape' in ident:
        f.circle(100,111,46,ROCK)
        f.ellipse(42,53,116,116,BLUE,1,dash=[3,3])
        for dx in (-20,0,20):f.arrow(100+dx,153,100+dx*1.8,195,GOLD,1.2)
        _spacecraft(f,179,154)
        f.label('escaping particles',19,53,211,10.5,ICE)
    elif 'juice' in ident:
        for xx,yy,rr in [(57,133,24),(116,113,19),(182,90,28)]:f.circle(xx,yy,rr,BLUE,ICE,.6)
        f.path([(24,166),(74,170),(127,147),(177,131),(214,151)],CYAN,1.3,dash=[3,3])
        _spacecraft(f,174,166)
        f.text('compare moon environments',20,62,211,9.9,ICE)
    else:
        f.circle(109,112,48,HexColor(f.v.get('color','#8AB4C7')))
        f.ellipse(29,59,160,120,LINE,.8)
        _spacecraft(f,173,169)
        f.arrow(159,152,127,126,CYAN,1.5)
        if 'venus-geology' in ident:
            f.arrow(131,119,169,147,GOLD,1.2)
            f.text('radar echo + IR',25,60,201,10.5,ICE)
        else:f.text('complementary measurements',18,60,212,9.8,ICE)

def practice(f):
    f.kicker('Reason from clues before reaching for numbers')
    for i,s in enumerate(f.v.get('items',[])):
        xx=14+(i%2)*253;yy=194 if i<2 else 74
        f.rect(xx,yy,235,112,PANEL);f.badge(i+1,xx+19,yy+92,GOLD)
        f.text(s,xx+37,yy+100,187,14,ICE,maxh=94)
    f.caption('Use stated evidence and assumptions. A plausible model is not a unique explanation.')


# Heights are typography-driven, not an invitation to stretch the vector canvas.
HEIGHTS={'flow':300,'ingredients':360,'phase':320,'waterforms':350,'biomolecules':350,'energy':300,'zone':300,'greenhouse':350,'retention':330,'geology':330,'spectrum':270,'world':350,'transit':340,'rv':340,'lensing':340,'imaging':340,'mission':350,'practice':360}
WORLD_HEIGHTS={'venus':360,'mars':360,'ganymede':360,'europa':360,'enceladus':360,'titan_surface':360,'titan_interior':350,'bennu':350,'comet_67p':350,'makemake':320,'trappist_system':320,'kepler_452':330,'lhs1140_models':350}


def design_height(lesson):
    kind=lesson.get('kind','flow')
    if kind in ('equation','graph','flux','blackbody','equilibrium','orbit','tides'):
        from readable_math_light import HEIGHTS as math_heights
        return math_heights.get(kind,350)
    return WORLD_HEIGHTS.get(lesson.get('id'),HEIGHTS.get(kind,350))


def diagram_height(lesson,width=528):
    # The surrounding flowable reserves 7 pt on all sides.
    return 14+design_height(lesson)*(width-14)/516


def diagram_parts(lesson):
    return [lesson]


def draw_diagram(canvas,lesson,x,y,w,h):
    _fonts();kind=lesson.get('kind','flow')
    if kind not in SUPPORTED_KINDS:raise ValueError('Unsupported diagram kind: '+repr(kind))
    dh=design_height(lesson);scale=min(w/516,h/dh)
    canvas.saveState();canvas.translate(x+(w-516*scale)/2,y+(h-dh*scale)/2);canvas.scale(scale,scale)
    p=canvas.beginPath();p.rect(0,0,516,dh);canvas.clipPath(p,stroke=0,fill=0)
    canvas.setFillColor(BG);canvas.rect(0,0,516,dh,fill=1,stroke=0)
    f=Figure(canvas,lesson,dh)
    if kind in ('equation','graph','flux','blackbody','equilibrium','orbit','tides'):
        import readable_math_light as readable_math
        getattr(readable_math,kind)(f)
    else:globals()[kind](f)
    canvas.restoreState();return True

# Compatibility alias used by compact/continuous builders.
def recommended_height(lesson,width=528):
    return diagram_height(lesson,width)
