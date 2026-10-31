from pathlib import Path
from lxml import etree as E
import zipfile
p=Path(__file__).resolve().parent.parent / 'گزارش پروژه کارشناسی - تکمیل‌شده.docx'
with zipfile.ZipFile(p) as z:fs={n:z.read(n) for n in z.namelist()}
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}';ns={'w':W[1:-1]};r=E.fromstring(fs['word/document.xml'])
for old in r.findall('.//w:tbl',ns):
 rows=[[ ''.join(c.xpath('.//w:t/text()',namespaces=ns)) for c in row.findall('w:tc',ns)] for row in old.findall('w:tr',ns)]
 n=len(rows[0]);widths=[8600//n]*n
 tbl=E.Element(W+'tbl');pr=E.SubElement(tbl,W+'tblPr');E.SubElement(pr,W+'bidiVisual',attrib={W+'val':'1'});E.SubElement(pr,W+'tblW',attrib={W+'w':'8600',W+'type':'dxa'})
 E.SubElement(pr,W+'tblLayout',attrib={W+'type':'fixed'})
 grid=E.SubElement(tbl,W+'tblGrid')
 for w in widths:E.SubElement(grid,W+'gridCol',attrib={W+'w':str(w)})
 for i,row in enumerate(rows):
  tr=E.SubElement(tbl,W+'tr');trpr=E.SubElement(tr,W+'trPr');E.SubElement(trpr,W+'cantSplit')
  if i==0:E.SubElement(trpr,W+'tblHeader')
  for j,text in enumerate(row):
   tc=E.SubElement(tr,W+'tc');cp=E.SubElement(tc,W+'tcPr');E.SubElement(cp,W+'tcW',attrib={W+'w':str(widths[j]),W+'type':'dxa'});E.SubElement(cp,W+'shd',attrib={W+'fill':'DDDDDD' if i==0 else ('F3F3F3' if i%2 else 'FFFFFF')})
   para=E.SubElement(tc,W+'p');pp=E.SubElement(para,W+'pPr');E.SubElement(pp,W+'bidi',attrib={W+'val':'1'});E.SubElement(pp,W+'spacing',attrib={W+'line':'280',W+'lineRule':'auto',W+'before':'60',W+'after':'60'})
   run=E.SubElement(para,W+'r');rp=E.SubElement(run,W+'rPr');E.SubElement(rp,W+'rFonts',attrib={W+'ascii':'FreeSerif',W+'hAnsi':'FreeSerif',W+'cs':'B Nazanin'});E.SubElement(rp,W+'sz',attrib={W+'val':'22'});E.SubElement(rp,W+'szCs',attrib={W+'val':'22'})
   if i==0:E.SubElement(rp,W+'b');E.SubElement(rp,W+'bCs')
   E.SubElement(run,W+'t').text=text
 old.getparent().replace(old,tbl)
fs['word/document.xml']=E.tostring(r,xml_declaration=True,encoding='UTF-8',standalone=True)
with zipfile.ZipFile(p,'w',zipfile.ZIP_DEFLATED) as z:
 for n,b in fs.items():z.writestr(n,b)
