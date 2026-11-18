"""Render authored printable worksheet structures; never parse pipes or blanks."""
import html

def worksheet_tex(w, tx):
    out=r'\clearpage\hypertarget{worksheet:'+w['id']+r'}{}\label{worksheet:'+w['id']+r'}\section*{'+tx(w['title'])+r'}\addcontentsline{toc}{section}{'+tx(w['title'])+'}\n'
    if 'paragraph_gap_pt' in w:out+=r'\begingroup\setlength{\parskip}{'+str(w['paragraph_gap_pt'])+r'pt}'+'\n'
    out+=tx(w['purpose'])+'\n\n'
    for section in w['sections']:
        out+=r'\subhead{'+tx(section['title'])+'}\n'
        if section['kind']=='fields':
            for field in section['fields']:
                lines=field.get('lines',1)
                out+=r'{\sffamily\small '+tx(field['label'])+r'}\par\nobreak'+'\n'
                for _ in range(lines):out+=r'\vspace{14pt}\noindent\rule{\linewidth}{.25pt}\par\vspace{5pt}'+'\n'
        elif section['kind']=='table':
            heads=section['columns'];cols=section.get('widths',[1/len(heads)]*len(heads))
            spec='|'.join(r'>{\RaggedRight\arraybackslash}p{\dimexpr '+str(round(x,5))+r'\linewidth-6pt\relax}' for x in cols)
            out+=r'\begingroup\small\setlength{\tabcolsep}{3pt}\begin{tabular}{@{}'+spec+r'@{}}\toprule'+'\n'
            out+=' & '.join(r'\textbf{'+(tx(x).replace(' (',r'\newline (') if cols[i]<.25 else tx(x))+'}' for i,x in enumerate(heads))+r'\\\midrule'+'\n'
            for _ in range(section['rows']):out+=r'\rule{0pt}{'+str(section.get('row_height_pt',28))+r'pt}'+' & '*(len(heads)-1)+r'\\\hline'+'\n'
            out+=r'\end{tabular}\endgroup\par\medskip'+'\n'
    if 'paragraph_gap_pt' in w:out+=r'\par\endgroup'+'\n'
    return out

def worksheet_html(w):
    esc=html.escape
    out='<section class="printable-worksheet" id="worksheet-'+esc(w['id'])+'"><h3>'+esc(w['title'])+'</h3><p>'+esc(w['purpose'])+'</p>'
    for s in w['sections']:
        out+='<h4>'+esc(s['title'])+'</h4>'
        if s['kind']=='fields':
            for f in s['fields']:
                out+='<div style="break-inside:avoid"><p>'+esc(f['label'])+'</p>'+''.join('<div style="height:1.7em;border-bottom:1px solid #b8ccd1"></div>' for _ in range(f.get('lines',1)))+'</div>'
        else:
            out+='<table style="table-layout:fixed;width:100%"><thead><tr>'+''.join('<th scope="col">'+esc(x)+'</th>' for x in s['columns'])+'</tr></thead><tbody>'
            out+=''.join('<tr>'+''.join('<td style="height:2.2em;border:1px solid #b8ccd1"></td>' for x in s['columns'])+'</tr>' for _ in range(s['rows']))+'</tbody></table>'
    return out+'</section>'
