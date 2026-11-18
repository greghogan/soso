#!/usr/bin/env python3
"""Export the canonical content.json to portable, editable LaTeX."""
import json,re,html,hashlib
from pathlib import Path
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parent
import sys
sys.path.insert(0,str(ROOT.parents[4]/'shared'))
from build_paths import event_output
D=json.loads((ROOT/'content.json').read_text())
# If canonical equations change, require deliberate review of their TeX renderings.
FORMULA_SOURCE_SHA256="d06d5e9d3ae6f25d3b8905d5f2285b2d9bff11b6381fd6ac877894e9e3c9b7e1"
formulas=[b["formula"] for c in D["page4"]["columns"] for b in c if "formula" in b]
assert hashlib.sha256(json.dumps(formulas,ensure_ascii=False).encode()).hexdigest()==FORMULA_SOURCE_SHA256, "Canonical equations changed: update and review MATH before rebuilding."
SYMS={'≈':r'\ensuremath{\approx}','≠':r'\ensuremath{\ne}','→':r'\ensuremath{\rightarrow}','∝':r'\ensuremath{\propto}','²':r'\textsuperscript{2}','³':r'\textsuperscript{3}','⁴':r'\textsuperscript{4}','⁸':r'\textsuperscript{8}','−':r'\ensuremath{-}','×':r'\ensuremath{\times}','÷':r'\ensuremath{\div}','√':r'\ensuremath{\surd}','½':r'\ensuremath{\tfrac12}','≤':r'\ensuremath{\le}','≪':r'\ensuremath{\ll}','∞':r'\ensuremath{\infty}','★':r'\ensuremath{\star}','⊕':r'\ensuremath{\oplus}','⇌':r'\ensuremath{\rightleftharpoons}','δ':r'\ensuremath{\delta}','ρ':r'\ensuremath{\rho}','θ':r'\ensuremath{\theta}','λ':r'\ensuremath{\lambda}','Δ':r'\ensuremath{\Delta}','π':r'\ensuremath{\pi}','ε':r'\ensuremath{\varepsilon}','σ':r'\ensuremath{\sigma}','·':r'\ensuremath{\cdot}','°':r'\textdegree{}','–':'-','—':'-'}
def esc(s):
    return ''.join(SYMS.get(c,{'&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_','{':r'\{','}':r'\}','\\':r'\textbackslash{}','<':r'\ensuremath{<}','>':r'\ensuremath{>}','~':r'\textasciitilde{}','^':r'\textasciicircum{}'}.get(c,c)) for c in s)
class Rich(HTMLParser):
    def __init__(self): super().__init__();self.out=[]
    def handle_starttag(self,t,a):
        if t=='br': self.out.append(r'\newline ')
        elif t=='link': self.out.append('\\href{'+dict(a)['href']+'}{')
        else:self.out.append({'b':r'\textbf{','i':r'\textit{','sub':r'\textsubscript{','super':r'\textsuperscript{'}.get(t,''))
    def handle_endtag(self,t):
        if t in ['b','i','sub','super','link']:self.out.append('}')
    def handle_data(self,s):self.out.append(esc(s))
def rich(s):
    p=Rich();p.feed(s);return ''.join(p.out)
# Explicit semantic equation rendering. Prose, quantities, assumptions and examples
# remain canonical JSON; these ten entries encode only mathematical typography.
MATH=[
 r'\frac{v_r}{c}\approx\frac{\Delta\lambda}{\lambda_0};\quad\Delta\lambda=\lambda_{\rm obs}-\lambda_0\\ \delta\approx\left(\frac{R_p}{R_\star}\right)^2;\quad R_p\approx R_\star\sqrt{\delta}',
 r'F=\frac{L}{4\pi d^2};\quad\frac{F_2}{F_1}=\frac{L_2}{L_1}\left(\frac{d_1}{d_2}\right)^2\\ P_{\rm abs}=(1-A)F\pi R_p^2',
 r'F_{\rm emit}=\varepsilon\sigma T^4;\quad P_{\rm emit}=4\pi R^2\varepsilon\sigma T^4\\ L_\star=4\pi R_\star^2\sigma T_\star^4\quad\text{(blackbody)};\quad\lambda_{\max}T=b',
 r'(1-A)F\pi R_p^2=4\pi R_p^2\varepsilon\sigma T_{\rm eq}^4\\ T_{\rm eq}=\left[\frac{(1-A)L}{16\pi\varepsilon\sigma d^2}\right]^{1/4}',
 r'PV=nR_gT=Nk_BT;\quad v_{\rm rms}=\sqrt{\frac{3k_BT}{m_{\rm particle}}}',
 r'aA+bB\rightleftharpoons cC+dD;\quad K_{\rm eq}=\frac{a_C^c a_D^d}{a_A^a a_B^b}\\ k=A_{\rm pre}\exp\left[-\frac{E_a}{R_gT}\right]\\ \ln k=\ln A_{\rm pre}-\frac{E_a}{R_g}\frac1T',
 r'F_g=\frac{GMm}{r^2};\quad g=\frac{GM}{r^2}\\ E_K=\tfrac12mv^2;\quad U=-\frac{GMm}{r}\quad(U_\infty=0)\\ v_{\rm esc}=\sqrt{\frac{2GM}{R}};\quad v_{\rm circ}=\sqrt{\frac{GM}{r}}',
 r'r_{\rm peri}=a(1-e);\quad r_{\rm apo}=a(1+e)\\ a=\frac{r_{\rm peri}+r_{\rm apo}}2;\quad e=\frac{r_{\rm apo}-r_{\rm peri}}{r_{\rm apo}+r_{\rm peri}}\\ P^2=\frac{4\pi^2a^3}{G(M+m)}',
 r'\Delta g\approx\frac{2GM_{\rm host}R_{\rm body}}{d^3}\quad(R_{\rm body}\ll d)',
 r'\rho=\frac{3M}{4\pi R^3};\quad\frac\rho{\rho_\oplus}=\frac{M/M_\oplus}{(R/R_\oplus)^3}\\ \theta[\text{arcsec}]\approx\frac{s_{\rm projected}[\text{AU}]}{D[\text{pc}]}\\ M_p\approx\frac{M_p\sin i}{\sin i}'
]
PRE=r'''\documentclass[letterpaper]{article}
\usepackage[margin=25bp,bottom=34bp,headheight=0pt,headsep=0pt,footskip=16bp]{geometry}
\usepackage{fix-cm}\usepackage{fontspec,amsmath,amssymb,array,tabularx,fancyhdr,hyperref}
\setmainfont{Latin Modern Sans}
\hypersetup{hidelinks,pdftitle={Solar System B 2027 - Four-page exam reference},pdfauthor={Greg Hogan and the soso contributors}}
\pagestyle{fancy}\fancyhf{}\renewcommand{\headrulewidth}{0pt}
\fancyfoot[L]{\fontsize{6.1}{7}\selectfont Two sheets, both sides. No calculator. Print at 100\% / actual size. Check current event clarifications.\\{\fontsize{6}{7}\selectfont\sosocredit}}
\fancyfoot[R]{\fontsize{6.1}{7}\selectfont\thepage\ / 4\quad revised 15 Nov 2026}
\renewcommand{\footrulewidth}{0.3pt}
\setlength{\jot}{0pt}\setlength{\parindent}{0pt}\setlength{\parskip}{2.8bp}
\setlength{\tabcolsep}{4bp}\setlength{\emergencystretch}{8pt}
\newcommand{\bodyfont}{\fontsize{7.6}{9.1}\selectfont}
\newcommand{\sect}[1]{\par\vspace{3bp}{\fontsize{8.4}{10}\selectfont\bfseries #1\par}\vspace{1bp}\hrule height .35pt\vspace{3bp}}
\newcommand{\startpage}[2]{{\fontsize{13}{15}\selectfont\bfseries SOLAR SYSTEM B}\hfill{\fontsize{8.5}{10}\selectfont 2027\quad|\quad EXAM REFERENCE}\par\vspace{-1bp}\hrule height .6pt\vspace{6bp}{\fontsize{10.3}{12}\selectfont\bfseries #1\par}\vspace{1bp}{\fontsize{7.4}{9}\selectfont #2\par}\vspace{5bp}}
\newcommand{\formula}[1]{\par\vspace{1bp}{\fontsize{8.1}{10.5}\selectfont\(\begin{gathered}#1\end{gathered}\)}\par\vspace{1bp}}
\newsavebox{\pagebox}
\newenvironment{checkedpage}{\begin{lrbox}{\pagebox}\begin{minipage}[t]{\textwidth}\bodyfont}{\end{minipage}\end{lrbox}\typeout{CONTENT HEIGHT: \the\dimexpr\ht\pagebox+\dp\pagebox\relax}\ifdim\dimexpr\ht\pagebox+\dp\pagebox\relax>\textheight\PackageError{reference}{Page content exceeds printable height}{Do not shrink or omit content. Adjust layout.}\fi\noindent\usebox{\pagebox}\newpage}
\begin{document}\bodyfont
'''
PRE=(ROOT.parents[4]/'shared/publication-notice.tex').read_text()+PRE
T=[PRE]
titles=['WORLDS: ENVIRONMENT → EVIDENCE → LIMITS','HABITABILITY: MECHANISMS, CHEMISTRY & EVIDENCE','MISSIONS, INSTRUMENTS & PLANET DETECTION','MATH: RELATIONSHIPS, ASSUMPTIONS & RATIO TRAPS']
def sect(s):T.append('\\sect{'+esc(s)+'}')
def para(s):T.append(rich(s)+'\\par')
def table(rows):
    T.append(r'\begingroup\fontsize{8}{9.7}\selectfont\renewcommand{\arraystretch}{1.08}\begin{tabularx}{\textwidth}{@{}>{\raggedright\arraybackslash}p{62bp}>{\raggedright\arraybackslash}p{237bp}>{\raggedright\arraybackslash}X@{}}')
    T.append(' & '.join('\\textbf{'+esc(s)+'}' for s in D['page1']['headers'])+r'\\[2bp]\hline')
    for row in rows:T.append(' & '.join(rich(s) for s in row)+r'\\[3.3bp]\hline')
    T.append(r'\end{tabularx}\endgroup\par')
for p in range(1,5):
    data=D[f'page{p}'];T += [r'\begin{checkedpage}',r'\startpage{'+esc(titles[p-1])+'}{'+rich(data['subtitle'])+'}']
    if p==1:
        table(data['worlds']);sect('Three extrasolar systems: an orbit in the habitable zone is not a habitat');table(data['systems']);para(data['end'])
    else:
        for c in range(2):
            if c:T.append(r'\hfill')
            T.append(r'\begin{minipage}[t]{\dimexpr(\textwidth-14bp)/2\relax}\vspace{0pt}')
            T.append(r'\setlength{\parskip}{0.7bp}' if p==4 else r'\fontsize{8}{9.6}\selectfont\setlength{\parskip}{3bp}')
            if p==3:
                sect('Mission → question / measurement / tradeoff')
                for m in data['missions'][c]:para('<b>'+m['name']+'</b> <i>'+m['status']+'</i><br/>'+m['text'])
            for b in data['columns'][c]:
                sect(b['title'])
                if 'formula' in b:
                    index=int(b['title'].split('.')[0])-1
                    T.append('\\formula{'+MATH[index]+'}')
                for s in b['items']:para(s)
            T.append(r'\end{minipage}%')
        if p==3:
            line=(ROOT/'status-sources.html').read_text().strip()
            T.append(r'\par\vspace{6bp}')
            para(line)
    T.append(r'\end{checkedpage}')
T.append(r'\end{document}')
if __name__ == '__main__':
    import argparse
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=Path,default=event_output(ROOT.parents[1])/'build/exam-reference/exam-reference.tex')
    output=ap.parse_args().output.resolve()
    if output == (ROOT/'exam-reference.tex').resolve():
        raise ValueError('Do not export generated TeX into the source directory; use build/')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text('\n'.join(T)+'\n')
    print('Exported all canonical text and ten equation groups:',output)
