"""Export the complete Persian report to editable Word using the supplied style template."""
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile
from lxml import etree as E
P = Path(__file__).resolve().parent
BUILD = Path(tempfile.gettempdir()) / 'blunderguard-report-build'

def expand(s):
    return re.sub(r'\\input\{([^}]+)\}', lambda m: expand((P / m[1]).read_text()), s)

s=expand((P/'report_updated_fa.tex').read_text())
s=s.split(r'\begin{document}',1)[1].split(r'\end{document}',1)[0]
s=re.sub(r'\\begin\{tabularx\}\{\\linewidth\}\{([^\n]+)\}', lambda m: r'\begin{tabular}{lll}' if 'p{3.5cm}' in m[1] else r'\begin{tabular}{ll}', s)
s=s.replace(r'\end{tabularx}',r'\end{tabular}')
s=re.sub(r'\\rowcolors\{[^}]+\}\{[^}]+\}\{[^}]+\}|\\rowcolor\{[^}]+\}', '', s)

s=re.sub(r'\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}', lambda m: r'\includegraphics[width=14cm]{chapter3_assets/'+('intro_flow' if 'ساخت مجموعه مرجع' in m[0] else 'pipeline')+'.png}', s, flags=re.S)
# Resolve the PDF's semantic reference labels, not its page numbers.
aux=(BUILD/'report_updated_fa.aux').read_text()
labels=dict(re.findall(r'\\newlabel\{([^}]+)\}\{\{([^}]+)\}',aux))
cites=dict(re.findall(r'\\bibcite\{([^}]+)\}\{([^}]+)\}',aux))
s=re.sub(r'\\ref\{([^}]+)\}',lambda m:labels.get(m[1],m[1]),s)
s=re.sub(r'\\cite\{([^}]+)\}',lambda m:'['+', '.join(cites[k] for k in m[1].split(','))+']',s)
s=re.sub(r'\\nocite\{[^}]+\}|\\label\{[^}]+\}|\\addcontentsline\{[^}]+\}\{[^}]+\}\{[^}]+\}', '',s)
s=re.sub(r'\\renewcommand\{\\thechapter\}[^\n]+','',s)
s=s.replace(r'\begin{thebibliography}{99}',r'\chapter*{منابع}').replace(r'\end{thebibliography}','')
s=re.sub(r'\\bibitem\{([^}]+)\}',lambda m:'\n\n['+cites[m[1]]+'] ',s)
s=s.replace(r'\listoffigures','').replace(r'\listoftables','').replace(r'\tableofcontents','')
# Explicit section numbers make the standalone document portable across Word/Docs.
chapter=0;sec=0;sub=0;fig=0;tab=0;appendix=False
lines=[]
for line in s.splitlines():
    if line.strip()==r'\appendix':appendix=True;chapter=0;continue
    if line.startswith(r'\chapter{'):
        chapter+=1;sec=sub=fig=tab=0
        ch = ['الف','ب'][chapter-1] if appendix else str(chapter)
        prefix = 'پیوست '+ch+': ' if appendix else 'فصل '+['اول','دوم','سوم'][chapter-1]+': '
        line=line.replace(r'\chapter{',r'\chapter{'+prefix)
    elif line.startswith(r'\section{'):
        sec+=1;sub=0;line=line.replace(r'\section{',r'\section{'+ch+'-'+str(sec)+' ')
    elif line.startswith(r'\subsection{'):
        sub+=1;line=line.replace(r'\subsection{',r'\subsection{'+ch+'-'+str(sec)+'-'+str(sub)+' ')
    if r'\begin{figure}' in line:kind='figure'
    if r'\begin{table}' in line:kind='table'
    if r'\caption{' in line:
        if kind=='figure':fig+=1;prefix='شکل '+ch+'-'+str(fig)+': '
        else:tab+=1;prefix='جدول '+ch+'-'+str(tab)+': '
        line=line.replace(r'\caption{',r'\caption{'+prefix)
    lines.append(line)
s='\n'.join(lines)
s=re.sub(r'\\includegraphics\[[^]]*\]\{([^}]+)\}',lambda m:r'\includegraphics[width='+('2.8cm' if 'beheshti_logo' in m[1] else '14cm')+']{'+m[1]+'}',s)
s=r'\newcommand{\lr}[1]{#1}'+'\n'+s
source=BUILD/'full_word.tex';source.write_text(s)
out=P.parent/'گزارش پروژه کارشناسی - تکمیل‌شده.docx'
subprocess.run(['pandoc',str(source),'--from=latex','--to=docx','--resource-path='+str(P),'--reference-doc='+str(P.parent/'قالب گزارش پروژه کارشناسی 1400.11.02.docx'),'-M','lang=fa','-M','dir=rtl','--toc','--toc-depth=3','-o',str(out)],check=True,cwd=P)
with zipfile.ZipFile(out) as z:fs={n:z.read(n) for n in z.namelist()}
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}';ns={'w':W[1:-1]}
r=E.fromstring(fs['word/document.xml']);st=E.fromstring(fs['word/styles.xml'])
for root in [r,st]:
    for e in root.findall('.//w:rFonts',ns):
        for a in list(e.attrib):
            if a.endswith('Theme'):del e.attrib[a]
        for a in ['ascii','hAnsi','cs','eastAsia']:e.set(W+a,'B Nazanin' if a=='cs' else 'FreeSerif')
    for e in root.findall('.//w:numPr',ns):e.getparent().remove(e)
for e in st.findall('.//w:color',ns):e.attrib.clear();e.set(W+'val','000000')
for sect in r.findall('.//w:sectPr',ns):
    for e in list(sect):
        if e.tag in [W+'headerReference',W+'footerReference']:sect.remove(e)
for p in r.findall('.//w:p',ns):
    pp=p.find('w:pPr',ns)
    if pp is None:
        pp=E.Element(W+'pPr');p.insert(0,pp)
    style=pp.find('w:pStyle',ns);sid=style.get(W+'val','') if style is not None else ''
    if pp.find('w:bidi',ns) is None:E.SubElement(pp,W+'bidi')
    if sid.startswith('Heading'):
        n=E.SubElement(pp,W+'numPr');E.SubElement(n,W+'numId').set(W+'val','0')
        for t in p.findall('.//w:t',ns):t.text=(t.text or '').translate(str.maketrans('0123456789','۰۱۲۳۴۵۶۷۸۹'))
        if sid=='Heading1':E.SubElement(pp,W+'pageBreakBefore')
    if p.findall('.//w:drawing',ns):
        for e in pp.findall('w:spacing',ns):pp.remove(e)
        E.SubElement(pp,W+'spacing',attrib={W+'line':'240',W+'lineRule':'auto',W+'before':'120',W+'after':'120'})
for run in r.findall('.//w:r',ns):
    t=''.join(run.xpath('.//w:t/text()',namespaces=ns))
    if t and all(ord(c)<128 or c in '۰۱۲۳۴۵۶۷۸۹٫' for c in t):
        rp=run.find('w:rPr',ns)
        if rp is None:rp=E.SubElement(run,W+'rPr')
        rtl=rp.find('w:rtl',ns)
        if rtl is None:rtl=E.SubElement(rp,W+'rtl')
        rtl.set(W+'val','0')
        if '٫' in t:
            fonts=rp.find('w:rFonts',ns)
            if fonts is None:fonts=E.SubElement(rp,W+'rFonts')
            for key in ['ascii','hAnsi','cs']:fonts.set(W+key,'FreeSerif')
# Normalize paragraph spacing and table widths inherited from the template.
for p in r.findall('.//w:p',ns):
    pp=p.find('w:pPr',ns)
    for e in pp.findall('w:spacing',ns):pp.remove(e)
    E.SubElement(pp,W+'spacing',attrib={W+'line':'300',W+'lineRule':'auto',W+'after':'100'})
    for run in p.findall('w:r',ns):
        rp=run.find('w:rPr',ns)
        if rp is None:rp=E.SubElement(run,W+'rPr')
        for tag in ['sz','szCs']:
            e=rp.find('w:'+tag,ns)
            if e is None:e=E.SubElement(rp,W+tag)
            e.set(W+'val','24')
for ti,tbl in enumerate(r.findall('.//w:tbl',ns)):
    rows=tbl.findall('w:tr',ns);n=len(rows[0].findall('w:tc',ns))
    widths=([2200,3200,3200] if ti==0 else [int(8600/n)]*n)
    pr=tbl.find('w:tblPr',ns)
    tw=pr.find('w:tblW',ns);tw.set(W+'type','dxa');tw.set(W+'w','8600')
    E.SubElement(pr,W+'tblLayout').set(W+'type','fixed')
    E.SubElement(pr,W+'bidiVisual')
    grid=tbl.find('w:tblGrid',ns)
    if grid is None:
        grid=E.Element(W+'tblGrid');tbl.insert(1,grid)
    for e in list(grid):grid.remove(e)
    for w in widths:E.SubElement(grid,W+'gridCol').set(W+'w',str(w))
    borders=E.SubElement(pr,W+'tblBorders')
    for tag in ['top','bottom','insideH']:
        E.SubElement(borders,W+tag,attrib={W+'val':'single',W+'sz':'4',W+'color':'C0C0C0'})
    for ri,row in enumerate(rows):
        trp=row.find('w:trPr',ns)
        if trp is None:
            trp=E.Element(W+'trPr');row.insert(0,trp)
        E.SubElement(trp,W+'cantSplit')
        if ri==0:E.SubElement(trp,W+'tblHeader')
        for ci,cell in enumerate(row.findall('w:tc',ns)):
            cp=cell.find('w:tcPr',ns)
            if cp is None:
                cp=E.Element(W+'tcPr');cell.insert(0,cp)
            cw=cp.find('w:tcW',ns)
            if cw is None:cw=E.SubElement(cp,W+'tcW')
            cw.set(W+'type','dxa');cw.set(W+'w',str(widths[ci]))
            E.SubElement(cp,W+'shd',attrib={W+'fill':'DDDDDD' if ri==0 else ('F3F3F3' if ri%2 else 'FFFFFF')})
            for p in cell.findall('w:p',ns):
                pp=p.find('w:pPr',ns)
                for e in pp.findall('w:spacing',ns):pp.remove(e)
                E.SubElement(pp,W+'spacing',attrib={W+'line':'270',W+'lineRule':'auto',W+'after':'70',W+'before':'70'})
                if ti==0 and ri<len(rows)-1:E.SubElement(pp,W+'keepNext')
body=r.find('w:body',ns)
toc=body.find('w:sdt',ns)
if toc is not None:
    body.remove(toc)
    for t in toc.findall('.//w:t',ns):
        if t.text=='Table of Contents':t.text='فهرست مطالب'
    for i,e in enumerate(body):
        if ''.join(e.xpath('.//w:t/text()',namespaces=ns)).startswith('فصل اول'):
            body.insert(i,toc);break
# Give the title page a clear hierarchy.
for e in body:
    text=''.join(e.xpath('.//w:t/text()',namespaces=ns))
    if text=='چکیده':break
    if e.tag!=W+'p':continue
    pp=e.find('w:pPr',ns)
    for old in pp.findall('w:spacing',ns):pp.remove(old)
    E.SubElement(pp,W+'spacing',attrib={W+'line':'360',W+'lineRule':'auto',W+'before':'160',W+'after':'140'})
    jc=pp.find('w:jc',ns)
    if jc is None:jc=E.SubElement(pp,W+'jc')
    jc.set(W+'val','center')
    for sz in e.findall('.//w:sz',ns)+e.findall('.//w:szCs',ns):sz.set(W+'val','32' if 'تحلیل و تفسیر' in text else '28')

rels=E.fromstring(fs['word/_rels/document.xml.rels'])
for e in list(rels):
    if e.get('Type','').endswith(('/header','/footer')):rels.remove(e)
ids=[e.get('Id') for e in rels];assert len(ids)==len(set(ids))
for name,root in [('word/document.xml',r),('word/styles.xml',st),('word/_rels/document.xml.rels',rels)]:fs[name]=E.tostring(root,xml_declaration=True,encoding='UTF-8',standalone=True)
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED) as z:
    for n,b in fs.items():z.writestr(n,b)
print(out)
print('Images:',len(r.findall('.//w:drawing',ns)),'Tables:',len(r.findall('.//w:tbl',ns)))

subprocess.run(["python", str(P / "normalize_word_tables.py")], check=True)
