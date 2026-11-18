"""Readable, exact vector mathematics for the Solar System study guide.

Coordinates use the Figure helpers' bottom-origin drawing / top-origin text.
The figures are designed at their final 516-point width, never stretched.
"""
import math
import re
from reportlab.lib.colors import HexColor

BG = HexColor('#FFFFFF')
PANEL = HexColor('#EDF5F5')
PANEL2 = HexColor('#E1EDEE')
CYAN = HexColor('#087B85')
GOLD = HexColor('#A86D16')
WHITE = HexColor('#15333F')
ICE = HexColor('#526874')
MUTED = HexColor('#526874')
COPPER = HexColor('#A86D16')
BLUE = HexColor('#307FA6')
LINE = HexColor('#B8CCD1')

HEIGHTS = {
    'equation': 350, 'graph': 350, 'flux': 350, 'blackbody': 350,
    'equilibrium': 400, 'orbit': 350, 'tides': 350,
}


def normalize_math(text):
    """Use real subscript markup, including within equation explanations."""
    replacements = {
        'v꜀ᵢᵣ꜀': 'v<sub>circ</sub>', 'vₑₛc': 'v<sub>esc</sub>',
        'v_esc': 'v<sub>esc</sub>', 'v_circ': 'v<sub>circ</sub>',
        'kᴮ': 'k<sub>B</sub>', 'k_B': 'k<sub>B</sub>',
        'Nᴬ': 'N<sub>A</sub>', 'N_A': 'N<sub>A</sub>',
        'Pabs': 'P<sub>abs</sub>', 'Fgrav': 'F<sub>grav</sub>',
    }
    text = str(text)
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _fraction(f, x, bar_y, width, numerator, denominator, size=24,
              color=WHITE, bold=True):
    """A real horizontal fraction bar; no scale transform or tiny glyphs."""
    f.label(normalize_math(numerator), x, bar_y + size * 1.48,
            width, size, color, bold)
    f.line(x + 3, bar_y, x + width - 3, bar_y, color, 1.35)
    f.label(normalize_math(denominator), x, bar_y - 7,
            width, size, color, bold)


def _radical(f, x, bottom, width, top, color=WHITE, index=None):
    """Draw a radical with a full vinculum above its contained expression."""
    f.path([(x - 16, bottom + 21), (x - 10, bottom + 26),
            (x - 3, bottom + 5), (x + 7, top), (x + width, top)],
           color, 1.65)
    if index is not None:
        f.label(str(index), x - 25, bottom + 51, 22, 14, color, True)


def equation(f):
    f.kicker('Read the relationship; test a limiting case')
    eq = normalize_math(f.v.get('eq', ''))
    meaning = normalize_math(f.v.get('meaning', ''))
    f.rect(14, 148, 488, 142, PANEL2)
    # Each main formula is deliberately typeset, rather than squeezed to fit.
    if f.id == 'math01':
        _fraction(f, 92, 241, 100, 'Δλ', 'λ₀', 28)
        f.label('≈', 222, 258, 64, 31, WHITE, True)
        _fraction(f, 324, 241, 100, 'vᵣ', 'c', 28)
    elif f.id == 'math07':
        f.label('K =', 29, 256, 68, 27, WHITE, True)
        _fraction(f, 101, 241, 121, 'mv²', '2', 27)
        f.line(233, 211, 233, 276, LINE, 1)
        f.label('U = −', 241, 256, 95, 26, WHITE, True)
        _fraction(f, 365, 241, 112, 'GMm', 'r', 27)
    elif f.id == 'math08':
        f.label('F<sub>grav</sub>', 25, 256, 98, 26, WHITE, True)
        f.label('=', 121, 256, 28, 26, WHITE, True)
        _fraction(f, 150, 241, 89, 'GMm', 'r²', 27)
        f.line(255, 211, 255, 276, LINE, 1)
        f.label('g =', 272, 256, 70, 27, WHITE, True)
        _fraction(f, 350, 241, 121, 'GM', 'r²', 27)
    elif f.id == 'math10':
        f.label('v<sub>esc</sub> =', 76, 256, 123, 28, WHITE, True)
        _radical(f, 228, 201, 174, 285)
        _fraction(f, 244, 241, 147, '2GM', 'r', 27)
    else:
        plain = re.sub('<[^>]+>', '', eq)
        size = 30 if len(plain) < 27 else 27
        f.label(eq, 28, 263, 460, size, WHITE, True, maxh=73)
    f.label(meaning, 29, 187, 458, 14.5, ICE, leading=18, maxh=38)
    steps = [normalize_math(s) for s in f.v.get('steps', [])]
    if steps:
        gap = 10
        bw = (488 - gap * (len(steps) - 1)) / len(steps)
        for i, step in enumerate(steps):
            xx = 14 + i * (bw + gap)
            f.rect(xx, 73, bw, 65, PANEL)
            f.label(step, xx + 8, 128, bw - 16, 14, GOLD,
                    leading=18, maxh=54)
    f.caption('Idealized relationship: apply the stated assumptions and use consistent units.')


def graph(f):
    typ = f.v.get('type', 'inverse')
    f.kicker('Plot the mathematical model, not invented data')
    if typ == 'arrhenius':
        # The fraction and plot occupy separate vertical bands.
        f.rect(14, 220, 488, 70, PANEL2)
        f.text('ln k = ln A −', 70, 273, 210, 23, GOLD, True)
        _fraction(f, 285, 257, 111, 'Eₐ', 'RT', 21, GOLD)
        x, y, w, h = 64, 111, 414, 80
        # Unscaled qualitative plot: omit non-quantitative gridlines behind annotations.
        f.axis(x, y, w, h, 'Inverse absolute temperature 1/T →', 'ln k', grid=False)
        f.path([(x, y + h * .87), (x + w, y + h * .13)], CYAN, 2.5)
        f.text('slope = −Eₐ/R', 284, 185, 194, 15, ICE)
        f.text('Right means colder.', 82, 161, 200, 13.5, GOLD)
        f.caption('Exact Arrhenius line for constant A and Eₐ; axes are unscaled. Higher T moves left and raises k.')
        return
    x, y, w, h = 64, 111, 414, 147
    ylabel = 'Emitted flux F / F₀' if typ == 'power' else f.v.get('y', 'y')
    f.axis(x, y, w, h, '' if typ == 'power' else f.v.get('x', 'x'), ylabel)
    if typ == 'power':
        f.path([(x + i / 400 * w, y + (i / 400) ** 4 * h)
                for i in range(401)], CYAN, 2.5)
        _fraction(f, 93, 225, 57, 'F', 'F₀', 22, GOLD)
        f.label('=', 161, 239, 35, 24, GOLD, True)
        f.label('(', 199, 251, 21, 43, GOLD)
        _fraction(f, 223, 225, 59, 'T', 'T₀', 22, GOLD)
        f.label(')', 285, 251, 21, 43, GOLD)
        f.label('4', 304, 262, 23, 16, GOLD, True)
        f.text('2× T → 16× F', 91, 174, 240, 17, ICE, True)
        for frac, lab in [(0, '0'), (.5, '½'), (1, '1')]:
            xx = x + w * frac
            f.line(xx, y - 3, xx, y + 3, ICE, .8)
            f.label(lab, xx - 12, y - 7, 24, 12.5, ICE)
        f.label('Absolute temperature T / T₀ →', x, 84, w, 12.5, ICE)
        f.caption('Exact normalized T⁴ curve at fixed emissivity. Temperature ratios must use kelvin.')
    else:
        models = {'inverse': lambda t: 1 / (1 + 3 * t) ** 2,
                  'linear': lambda t: t, 'sqrt': lambda t: math.sqrt(t)}
        if typ not in models:
            raise ValueError('Unsupported graph relation: ' + typ)
        f.path([(x + i / 400 * w, y + models[typ](i / 400) * h)
                for i in range(401)], CYAN, 2.5)
        f.caption(f.v.get('caption', 'Idealized mathematical relation, not measured data.'))


def flux(f):
    f.kicker('The same power spreads over a growing area')
    sx, sy, r = 42, 205, 168
    f.circle(sx, sy, 20, GOLD)
    f.label('L', 18, 256, 48, 19, GOLD, True)
    # Patch centers are exactly r and 2r away; their sides are 50 and 100.
    # The same ray bundle intersects their corresponding upper/lower edges.
    slope = 25 / r
    for sign in (-1, 1):
        f.line(64, sy + sign * slope * (64 - sx),
               454, sy + sign * slope * (454 - sx), GOLD, 1.2)
    for center, side in [(sx + r, 50), (sx + 2 * r, 100)]:
        px, py = center - side / 2, sy - side / 2
        f.rect(px, py, side, side, PANEL, CYAN, 0, 1.5)
        f.line(center, py, center, py + side, CYAN, .8)
        f.line(px, sy, px + side, sy, CYAN, .8)
    f.label('r: area S', 130, 283, 158, 15, CYAN, True)
    f.label('2r: area 4S', 295, 283, 170, 15, CYAN, True)
    f.label('F =', 35, 124, 75, 25, WHITE, True)
    _fraction(f, 117, 108, 130, 'L', '4πr²', 22)
    f.text('2× distance<br/>→ ¼ flux', 293, 134, 205, 17, GOLD, True, leading=23)
    f.caption('Same ray bundle, four times the patch area: both linear dimensions double. Geometric schematic.')


def blackbody(f):
    f.kicker('Hotter blackbodies are brighter and peak bluer')
    x, y, w, h = 59, 111, 429, 147
    f.axis(x, y, w, h, '', 'Spectral radiance B<sub>λ</sub> (common scale)')
    hP, c, k = 6.62607015e-34, 299792458., 1.380649e-23

    def planck(lam, temperature):
        return 2 * hP * c * c / (lam ** 5 * math.expm1(hP * c / (lam * k * temperature)))

    lmin, lmax = .15, 3.0
    norm = planck(2.897771955e-3 / 6000, 6000)
    for temperature, color in [(4000, CYAN), (6000, GOLD)]:
        pts = []
        for i in range(601):
            lm = lmin + (lmax - lmin) * i / 600
            pts.append((x + w * i / 600,
                        y + h * planck(lm * 1e-6, temperature) / norm))
        f.path(pts, color, 2.5)
        peak = 2.897771955e3 / temperature
        xp = x + (peak - lmin) / (lmax - lmin) * w
        yp = y + h * planck(peak * 1e-6, temperature) / norm
        f.line(xp, y, xp, yp, color, .9, [3, 3])
    for lm in (.5, 1, 2, 3):
        xx = x + (lm - lmin) / (lmax - lmin) * w
        f.line(xx, y - 3, xx, y + 3, ICE, .8)
        f.label(str(lm), xx - 16, y - 7, 32, 12.5, ICE)
    f.label('Wavelength λ (μm) →', x, 84, w, 12.5, ICE)
    f.line(324, 239, 349, 239, GOLD, 2.5)
    f.text('6000 K', 359, 249, 123, 15, GOLD, True)
    f.line(324, 209, 349, 209, CYAN, 2.5)
    f.text('4000 K', 359, 219, 123, 15, CYAN, True)
    f.text('λ<sub>max</sub> T ≈ 2898 μm K', 276, 174, 210, 15.5, ICE)
    f.caption('Calculated Planck curves, not observations. Both temperatures share one radiance scale.')


def equilibrium(f):
    f.kicker('Balance absorbed and emitted thermal power')
    f.circle(39, 285, 20, GOLD)
    for yy in (253, 285, 317):
        f.arrow(70, yy, 172, yy, GOLD, 1.9)
    f.circle(219, 285, 46, BLUE, ICE, .9)
    f.ellipse(205, 239, 28, 92, CYAN, 1.3)
    for angle in (-.78, 0, .78):
        f.arrow(219 + 52 * math.cos(angle), 285 + 52 * math.sin(angle),
                219 + 79 * math.cos(angle), 285 + 79 * math.sin(angle),
                COPPER, 1.8)
    f.text('Emit over 4πR²', 330, 339, 172, 16, COPPER, True)
    f.text('Cross-section in.<br/>Whole surface out.', 330, 293, 172, 15, ICE, leading=21)
    f.label('Absorb over πR²', 102, 229, 204, 15, CYAN, True)
    f.label('(1 − A)FπR² = 4πR²εσT⁴', 20, 207, 476, 24, WHITE, True)
    f.label('T =', 83, 132, 83, 28, WHITE, True)
    _radical(f, 197, 76, 194, 165, WHITE, index=4)
    _fraction(f, 215, 121, 164, '(1 − A)F', '4εσ', 24)
    f.text('Cancel πR².', 404, 137, 97, 14, GOLD, leading=18)
    f.caption('Uniform-temperature gray body; no internal heating. This need not be the actual surface temperature.')


def orbit(f):
    f.kicker('The central star is at a focus, not the center')
    # Uniformly enlarged copy of the source ellipse: identical eccentricity.
    cx, cy, a = 185., 213., 155.
    b = a * 65 / 137
    eccentricity = math.sqrt(1 - (b / a) ** 2)
    fx = cx - a * eccentricity
    f.ellipse(cx - a, cy - b, 2 * a, 2 * b, CYAN, 1.6)
    f.circle(cx, cy, 2, MUTED)
    f.line(cx, cy, cx + a, cy, LINE, .9, [3, 3])
    f.label('a', 247, 206, 32, 14, ICE)
    f.circle(cx - a, cy, 4.5, COPPER)
    f.circle(cx + a, cy, 4.5, COPPER)

    def solve(mean_anomaly):
        eccentric_anomaly = mean_anomaly
        for _ in range(40):
            delta = ((eccentric_anomaly - eccentricity * math.sin(eccentric_anomaly) - mean_anomaly)
                     / (1 - eccentricity * math.cos(eccentric_anomaly)))
            eccentric_anomaly -= delta
            if abs(delta) < 1e-12:
                break
        return eccentric_anomaly

    # Equal mean-anomaly widths give exact equal swept areas and equal times.
    # Star at LEFT focus; E=0 at left periapsis: x=cx-a cos E.
    dM = .12
    for m0, fill in [(0, HexColor('#3A5347')), (math.pi, HexColor('#233F50'))]:
        e1, e2 = solve(m0 - dM), solve(m0 + dM)
        pts = [(fx, cy)] + [
            (cx - a * math.cos(e1 + (e2 - e1) * i / 70),
             cy + b * math.sin(e1 + (e2 - e1) * i / 70))
            for i in range(71)
        ]
        f.path(pts, GOLD if m0 == 0 else CYAN, .9, fill, True)
    f.line(cx, cy, cx + a, cy, MUTED, .9, [3, 3])
    f.circle(cx, cy, 2.2, ICE)
    f.circle(fx, cy, 8.5, GOLD)
    f.text('Sun', 53, 196, 60, 13.5, GOLD, True)
    f.text('periapsis', 16, 128, 113, 13.5, ICE)
    f.text('apoapsis', 250, 128, 102, 13.5, ICE)
    f.text('Equal areas<br/>in equal times', 359, 289, 142, 16, CYAN, True, leading=21)
    f.text('Faster near<br/>periapsis.', 359, 232, 142, 14.5, ICE, leading=20)
    f.text('Slower near<br/>apoapsis.', 359, 185, 142, 14.5, ICE, leading=20)
    f.text('P² ∝ a³', 359, 130, 142, 25, GOLD, True)
    f.text('Same central mass', 359, 96, 142, 12.5, ICE)
    f.caption('Exact ellipse and equal-area sectors, at arbitrary scale. The period rule holds for the same central mass.')


def tides(f):
    f.kicker('Tides are differences from the center’s fall')
    f.circle(45, 223, 25, COPPER)
    f.label('PERTURBER', 14, 187, 93, 12, COPPER, True)
    f.circle(300, 223, 48, BLUE)
    f.ellipse(234, 189, 132, 68, CYAN, 1.4, dash=[4, 3])
    # These are differential accelerations in the freely falling frame.
    # The near-side vector points toward the perturber; far-side away.
    f.arrow(252, 223, 201, 223, GOLD, 2.8)
    f.arrow(348, 223, 399, 223, GOLD, 2.8)
    f.circle(300, 223, 2.5, WHITE)
    f.text('near side', 178, 286, 113, 14, ICE, True)
    f.text('far side', 348, 286, 118, 14, ICE, True)
    f.text('toward<br/>perturber', 124, 200, 127, 14, GOLD, leading=19)
    f.text('away from<br/>center', 370, 200, 132, 14, GOLD, leading=19)
    if f.id == 'math11':
        f.label('Δg ∝', 109, 127, 110, 27, WHITE, True)
        _fraction(f, 234, 112, 94, 'M R', 'd³', 24)
        f.text('2× d<br/>→ ⅛ Δg', 373, 133, 127, 15, GOLD, True, leading=21)
    else:
        f.label('Changing deformation + dissipation<br/>can heat the interior',
                27, 130, 462, 17, WHITE, True, leading=23)
    f.caption('Arrows subtract the center’s acceleration: these are tidal differences, not total gravitational forces.')
