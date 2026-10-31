from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED
from lxml import etree as E
from copy import deepcopy
import re,difflib,json
ROOT=Path('/home/seyed/code/BlunderGuard')
SRC=ROOT/'artifacts/before_pdf_comments/گزارش پروژه کارشناسی - تکمیل‌شده.docx'
OUT=ROOT/'docs/گزارش پروژه کارشناسی - نهایی.docx'
with ZipFile(SRC) as z:fs={n:z.read(n) for n in z.namelist()}
W='http://schemas.openxmlformats.org/wordprocessingml/2006/main';R='http://schemas.openxmlformats.org/officeDocument/2006/relationships';NS={'w':W,'r':R};qn=lambda x:'{'+W+'}'+x
root=E.fromstring(fs['word/document.xml']);body=root.find('w:body',NS);styles=E.fromstring(fs['word/styles.xml']);rels=E.fromstring(fs['word/_rels/document.xml.rels']);ct=E.fromstring(fs['[Content_Types].xml'])
ps=root.findall('.//w:p',NS);changes=[]
def text(p):return ''.join(p.xpath('.//w:t/text()',namespaces=NS))
def child(e,n,**attrs):
 x=e.find('w:'+n,NS)
 if x is None:x=E.SubElement(e,qn(n))
 for k,v in attrs.items():x.set(qn(k),str(v))
 return x
def pp(p):
 x=p.find('w:pPr',NS)
 if x is None:x=E.Element(qn('pPr'));p.insert(0,x)
 return x
def rp(r):
 x=r.find('w:rPr',NS)
 if x is None:x=E.Element(qn('rPr'));r.insert(0,x)
 return x
def font(r,bold=False,latin=False,size=24):
 pr=rp(r);child(pr,'rFonts',ascii='FreeSerif',hAnsi='FreeSerif',cs='B Nazanin');child(pr,'sz',val=size);child(pr,'szCs',val=size);child(pr,'rtl',val='0' if latin else '1')
 if bold:child(pr,'b',val=1);child(pr,'bCs',val=1)
def run(t,latin=False,bold=False,size=24):
 r=E.Element(qn('r'));font(r,bold,latin,size);e=E.SubElement(r,qn('t'));e.set('{http://www.w3.org/XML/1998/namespace}space','preserve');e.text=t;return r
def paragraph(t,style=None,align='both',latin=False):
 p=E.Element(qn('p'));pr=pp(p);child(pr,'bidi',val=0 if latin else 1);child(pr,'jc',val=align);child(pr,'spacing',line=300,lineRule='auto',after=100)
 if style:child(pr,'pStyle',val=style)
 p.append(run(t,latin=latin,bold=bool(style)));return p
def update(p,new):
 old=text(p)
 if old==new:return
 # Apply textual edits without replacing runs, hyperlinks, equations or drawings.
 nodes=p.findall('.//w:t',NS);starts=[];pos=0
 for n in nodes:starts.append(pos);pos+=len(n.text or '')
 for op,a,b,c,d in reversed(difflib.SequenceMatcher(None,old,new,autojunk=False).get_opcodes()):
  if op=='equal':continue
  if a==b:
   k=next((i for i in range(len(nodes)-1,-1,-1) if starts[i]<=a),0);n=nodes[k];at=a-starts[k];n.text=(n.text or '')[:at]+new[c:d]+(n.text or '')[at:]
  else:
   k=next(i for i,n in enumerate(nodes) if starts[i]+len(n.text or '')>a)
   for i in range(len(nodes)-1,k-1,-1):
    lo=max(0,a-starts[i]);hi=min(len(nodes[i].text or ''),b-starts[i])
    if hi>lo:
     v=nodes[i].text or '';nodes[i].text=v[:lo]+(new[c:d] if i==k else '')+v[hi:]
 for n in nodes:n.set('{http://www.w3.org/XML/1998/namespace}space','preserve')
 assert text(p)==new,(old,new,text(p))
 changes.append({'before':old,'after':new})
def setfull(p,t):
 for c in list(p):
  if c.tag!=qn('pPr'):p.remove(c)
 p.append(run(t))
# Title order.
body.remove(ps[4]);body.insert(body.index(ps[3]),ps[4])
# Normalize spacing and Persian prose, retaining identifiers and quoted source data.
replacements={'آنالین':'برخط','آنلاین':'برخط','سرور':'کارساز','سرویس':'خدمت','پایپالین':'خط لوله','پایپلاین':'خط لوله','بک اند':'بخش پشتی','بک‌اند':'بخش پشتی','استدالل':'استدلال','عالوه':'علاوه','تالش':'تلاش','الزاماً ً':'الزاماً','مستقیما ً':'مستقیماً','کد های':'کدهای','میتوان':'می‌توان','اسکریپت':'برنامه','دیتاست':'مجموعه‌داده','ماژول':'بخش','فاز':'مرحله','استراتژیک':'راهبردی','APIها':'رابط‌های برنامه‌نویسی کاربردی','Frontend':'رابط کاربری','Backend':'بخش پشتی','API':'رابط برنامه‌نویسی کاربردی'}
fa=r'\u0621-\u063A\u0641-\u064A\u066E-\u06D3'
for i,p in enumerate(ps):
 if p.xpath('ancestor::w:sdt',namespaces=NS):continue
 t=text(p)
 if 349<=i<=371 or i in (453,455):continue
 for old,new in replacements.items():t=t.replace(old,new)
 t=re.sub(r'(?<=[A-Za-z0-9])(?=['+fa+'])|(?<=['+fa+'])(?=[A-Za-z])',' ',t)
 t=re.sub(r'(?<=[۰-۹])(?=['+fa+'])',' ',t)
 t=re.sub(r'(?<=\])(?=['+fa+'])',' ',t)
 t=re.sub(r'([،؛])(?=\S)',r'\1 ',t)
 t=t.replace('  ',' ')
 update(p,t)
# Correct malformed numbered headings and a line break that split one sentence.
update(ps[75],'۱. خط لوله ارزیابی مدل‌ها');update(ps[88],'۲. خط لوله استفاده واقعی')
update(ps[83],text(ps[83])+' '+text(ps[84]));ps[84].getparent().remove(ps[84])
update(ps[80],text(ps[80]).replace('پس از دریافت تحلیل، Stockfish اطلاعات','پس از دریافت تحلیل استاک‌فیش، اطلاعات'))
update(ps[81],text(ps[81]).replace('نتایج تحلیل، Stockfish ویژگی‌های','نتایج تحلیل استاک‌فیش، ویژگی‌های'))
update(ps[94],'معماری کلی نرم‌افزار شامل موتور تحلیل شطرنج، بخش استخراج ویژگی و قواعد اکتشافی، بخش ساخت ورودی، بخش ارتباط با مدل‌های زبانی، پایگاه ذخیره نتایج، بخش پشتی برای مدیریت پردازش‌ها و رابط‌های برنامه‌نویسی کاربردی و رابط کاربری برای تعامل کاربر با سامانه است.')
# Use Persian equivalents in running prose; model identifiers and tables stay exact.
terms_replace={'Stockfish':'استاک‌فیش','React':'ری‌اکت','Python':'پایتون','Flask':'فلسک','llama.cpp':'لاما سی‌پلاس‌پلاس','LoRA':'سازگارسازی کم‌رتبه','FEN':'نمادگذاری فورسایت–ادواردز','Lichess':'لیچس','Jhamtani':'جمتانی','Zang':'زانگ','Lee':'لی','Kim':'کیم','Hebbar':'هبار','Cui':'تسوی','Concept-guided Chess Commentary Generation':'تولید توضیحات شطرنجی هدایت‌شده با مفهوم'}
for i,p in enumerate(ps):
 if p.getparent() is None or p.xpath('ancestor::w:sdt|ancestor::w:tc',namespaces=NS) or 349<=i<=371 or i in (453,455):continue
 t=text(p)
 for old,new in terms_replace.items():t=re.sub(r'(?<![A-Za-z0-9_])'+re.escape(old)+r'(?![A-Za-z0-9_])',new,t)
 update(p,t)
# Move/add established citations to first mention, without changing bibliography IDs.
update(ps[8],text(ps[8]).replace('استاک‌فیش','استاک‌فیش [8]',1))
update(ps[63],text(ps[63]).replace('استاک‌فیش','استاک‌فیش [8]',1))
update(ps[113],text(ps[113]).replace('لی، و همکاران','لی و همکاران [3]'))
# Source of weights: explicit project configuration; no invented paper attribution.
weight_text='وزن‌های جدول ۳-۲ از تنظیمات پیاده‌سازی ارزیابی این پروژه گرفته شده‌اند؛ محل تعریف آن‌ها تابع calculate_overall در برنامه evaluation/judge_responses.py است. این مقادیر به‌عنوان ضرایب ارزیابی پروژه گزارش می‌شوند، نه وزن‌های استاندارد و قابل تعمیم به همه مسائل. در این وزن‌دهی، صحت و وفاداری در مجموع ۶۰ درصد سهم دارند و در نتیجه، محتوای توضیح نسبت به روانی صرف سهم بیشتری در امتیاز نهایی دارد. تحلیل حساسیت نسبت به تغییر وزن‌ها در نتایج حاضر گزارش نشده است.'
body.insert(body.index(ps[244]),paragraph(weight_text))
# References: number and entry in one left-aligned LTR paragraph, preserving hyperlinks.
for i in range(350,372,2):
 num=text(ps[i]);p=ps[i+1];p.insert(1,run(num+' ',latin=True));ps[i].getparent().remove(ps[i]);pr=pp(p);child(pr,'jc',val='left');child(pr,'bidi',val=0);child(pr,'spacing',line=260,lineRule='auto',after=140)
 for r in p.findall('.//w:r',NS):child(rp(r),'rtl',val=0)
# Paragraph alignment and headings.
for i,p in enumerate(ps):
 if p.getparent() is None:continue
 pr=pp(p);t=text(p);st=pr.find('w:pStyle',NS);sid=st.get(qn('val'),'') if st is not None else ''
 if p.xpath('ancestor::w:sdt',namespaces=NS):
  child(pr,'jc',val='right');child(pr,'bidi',val=1)
  if sid=='TOCHeading':child(pr,'pageBreakBefore',val=1)
  continue
 if i<7:continue
 if i==349:
  child(pr,'jc',val='left');child(pr,'bidi',val=1);child(pr,'pageBreakBefore',val=1)
 elif 350<=i<=371:continue
 elif sid.startswith('Heading'):
  child(pr,'jc',val='right');child(pr,'bidi',val=1)
  for r in p.findall('.//w:r',NS):font(r,bold=True)
  if sid=='Heading1':
   child(pr,'pageBreakBefore',val=1)
   for br in p.findall('.//w:br',NS):
    if br.get(qn('type'))=='page':br.getparent().remove(br)
 elif re.match(r'^(شکل|جدول)\s+[0-9۰-۹الف]',t):child(pr,'jc',val='center');child(pr,'bidi',val=1)
 elif p.findall('.//w:drawing',NS):child(pr,'jc',val='center')
 elif i in (453,455):child(pr,'jc',val='left');child(pr,'bidi',val=0)
 elif not p.xpath('ancestor::w:tc',namespaces=NS):child(pr,'jc',val='both');child(pr,'bidi',val=1)
# Styles ensure generated TOC paragraphs and headings keep the requested alignment.
for st in styles.findall('w:style',NS):
 sid=st.get(qn('styleId'),'');pr=child(st,'pPr')
 if sid=='Normal':child(pr,'jc',val='both');child(pr,'bidi',val=1)
 if sid.startswith(('Heading','TOC')):
  child(pr,'jc',val='right');child(pr,'bidi',val=1)
  rpr=child(st,'rPr');rf=child(rpr,'rFonts',ascii='FreeSerif',hAnsi='FreeSerif',cs='B Nazanin')
  for k in list(rf.attrib):
   if 'theme' in k.lower():del rf.attrib[k]
 if sid=='TOCHeading':child(pr,'pageBreakBefore',val=1)
# Add genuine Word footnotes at first use in chapter text (not abstract/headings).
fn=E.Element(qn('footnotes'),nsmap={'w':W})
for fid,typ,tag in [(-1,'separator','separator'),(0,'continuationSeparator','continuationSeparator')]:
 f=E.SubElement(fn,qn('footnote'),{qn('id'):str(fid),qn('type'):typ});p=E.SubElement(f,qn('p'));r=E.SubElement(p,qn('r'));E.SubElement(r,qn(tag))
glossary=[
('هوش مصنوعی','Artificial intelligence'),('موتورهای تخصصی شطرنج','Chess engines'),('مدل‌های زبانی','Language models'),('مجموعه‌داده','Dataset'),('مجموعه آزمون','Test set'),('توضیحات مرجع','Reference explanations'),('استاک‌فیش','Stockfish'),('خطوط اصلی بازی','Principal variations'),('ساختار پیاده‌ای','Pawn structure'),('امنیت شاه','King safety'),('خط لوله','Pipeline'),('برچسب‌گذاری','Annotation'),('بخش پشتی','Backend'),('رابط کاربری','User interface / Frontend'),('رابط‌های برنامه‌نویسی کاربردی','Application programming interfaces (APIs)'),('قواعد اکتشافی','Heuristics'),('تولید زبان طبیعی','Natural language generation'),('استدلال نمادین','Symbolic reasoning'),('روانی','Fluency'),('وفاداری','Faithfulness'),('مفیدبودن','Helpfulness'),('پیروی از دستور','Instruction following'),('ری‌اکت','React'),('پایتون','Python'),('فلسک','Flask'),('لاما سی‌پلاس‌پلاس','llama.cpp'),('نمادگذاری فورسایت–ادواردز','Forsyth–Edwards Notation (FEN)'),('سازگارسازی کم‌رتبه','Low-rank adaptation (LoRA)'),('کمی‌سازی','Quantization'),('آموزش نظارت‌شده','Supervised learning'),('تنظیم دقیق','Fine-tuning'),('متخصص‌های ترکیبی','Mixture of experts (MoE)'),('لیچس','Lichess'),('تولید توضیحات شطرنجی هدایت‌شده با مفهوم','Concept-guided Chess Commentary Generation')]
used=[]
def footnote_at(p,end,fid):
 pos=0
 for node in p.findall('.//w:t',NS):
  v=node.text or ''
  if pos<end<=pos+len(v):
   at=end-pos;r=node.getparent();assert r.tag==qn('r')
   tail=v[at:];node.text=v[:at];ref=E.Element(qn('r'));font(ref,size=20);child(rp(ref),'vertAlign',val='superscript');E.SubElement(ref,qn('footnoteReference'),{qn('id'):str(fid)});r.addnext(ref)
   if tail:
    after=deepcopy(r)
    for e in list(after):
     if e.tag!=qn('rPr'):after.remove(e)
    n=E.SubElement(after,qn('t'));n.set('{http://www.w3.org/XML/1998/namespace}space','preserve');n.text=tail;ref.addnext(after)
   return
  pos+=len(v)
 raise ValueError('Footnote insertion failed')
for term,english in glossary:
 for p in ps[58:349]:
  if p.getparent() is None or p.xpath('ancestor::w:tc',namespaces=NS):continue
  st=pp(p).find('w:pStyle',NS)
  if st is not None and st.get(qn('val'),'').startswith('Heading'):continue
  t=text(p);at=t.find(term)
  if at<0:continue
  fid=len(used)+1;footnote_at(p,at+len(term),fid)
  f=E.SubElement(fn,qn('footnote'),{qn('id'):str(fid)});fp=paragraph('',align='left',latin=True)
  for r in fp.findall('w:r',NS):fp.remove(r)
  child(pp(fp),'spacing',line=240,lineRule='auto',after=30)
  rr=E.SubElement(fp,qn('r'));font(rr,latin=True,size=20);E.SubElement(rr,qn('footnoteRef'));fp.append(run(' '+english,latin=True,size=20));f.append(fp)
  used.append((term,english));break
# Add glossary as an independent final section, not a second appendix.
h=paragraph('واژه‌نامه',style='Heading1',align='right');child(pp(h),'pageBreakBefore',val=1)
sect=body.find('w:sectPr',NS);body.insert(body.index(sect),h)
tbl=E.Element(qn('tbl'));pr=E.SubElement(tbl,qn('tblPr'));child(pr,'tblW',w=8800,type='dxa');child(pr,'bidiVisual',val=1)
child(pr,'tblLayout',type='fixed');borders=child(pr,'tblBorders')
for side in ['top','bottom','insideH']:child(borders,side,val='single',sz=4,color='C8D8DD')
grid=E.SubElement(tbl,qn('tblGrid'))
for _ in range(2):E.SubElement(grid,qn('gridCol'),{qn('w'):'4400'})
for i,(fa,en) in enumerate([('اصطلاح فارسی','English equivalent')]+sorted(used)):
 tr=E.SubElement(tbl,qn('tr'));pr=E.SubElement(tr,qn('trPr'));child(pr,'cantSplit')
 if i==0:child(pr,'tblHeader')
 for j,t in enumerate([fa,en]):
  tc=E.SubElement(tr,qn('tc'));cp=E.SubElement(tc,qn('tcPr'));child(cp,'tcW',w=4400,type='dxa');child(cp,'shd',fill='DDEBED' if i==0 else ('F4F7F8' if i%2 else 'FFFFFF'))
  tc.append(paragraph(t,align='right' if j==0 else 'left',latin=j==1))
body.insert(body.index(sect),tbl)
# Page-number footer. Cover has no visible number; abstract starts at 1.
footer=E.Element(qn('ftr'),nsmap={'w':W});p=paragraph('',align='center');footer.append(p)
for r in p.findall('w:r',NS):p.remove(r)
fld=E.SubElement(p,qn('fldSimple'),{qn('instr'):' PAGE '});fld.append(run('1',latin=True))
empty=E.Element(qn('ftr'),nsmap={'w':W});E.SubElement(empty,qn('p'))
rel_ns='http://schemas.openxmlformats.org/package/2006/relationships'
def relationship(rid,kind,target):E.SubElement(rels,'{'+rel_ns+'}Relationship',Id=rid,Type=R+'/'+kind,Target=target)
relationship('rIdReviewFooter','footer','footer_review.xml');relationship('rIdReviewFirstFooter','footer','footer_review_first.xml');relationship('rIdReviewFootnotes','footnotes','footnotes.xml')
for s in root.findall('.//w:sectPr',NS):
 for e in s.findall('w:footerReference',NS):s.remove(e)
 s.insert(0,E.Element(qn('footerReference'),{qn('type'):'default','{'+R+'}id':'rIdReviewFooter'}));s.insert(1,E.Element(qn('footerReference'),{qn('type'):'first','{'+R+'}id':'rIdReviewFirstFooter'}))
 child(s,'pgNumType',fmt='decimal',start=0);child(s,'titlePg');child(s,'pgMar',footer=720)
for path,kind in [('word/footer_review.xml','footer'),('word/footer_review_first.xml','footer'),('word/footnotes.xml','footnotes')]:
 E.SubElement(ct,'{http://schemas.openxmlformats.org/package/2006/content-types}Override',PartName='/'+path,ContentType='application/vnd.openxmlformats-officedocument.wordprocessingml.'+kind+'+xml')
settings=E.fromstring(fs['word/settings.xml']);child(settings,'updateFields',val=1);fpr=child(settings,'footnotePr');child(fpr,'numFmt',val='decimal');child(fpr,'numRestart',val='continuous')
for path,obj in [('word/document.xml',root),('word/styles.xml',styles),('word/_rels/document.xml.rels',rels),('[Content_Types].xml',ct),('word/footer_review.xml',footer),('word/footer_review_first.xml',empty),('word/footnotes.xml',fn),('word/settings.xml',settings)]:fs[path]=E.tostring(obj,xml_declaration=True,encoding='UTF-8',standalone=True)
with ZipFile(OUT,'w',ZIP_DEFLATED) as z:
 for n,b in fs.items():z.writestr(n,b)
(ROOT/'docs/review/editorial_changes.json').write_text(json.dumps({'text_changes':changes,'footnotes':used,'comments_addressed':20},ensure_ascii=False,indent=2))
print('Saved',OUT,'text edits',len(changes),'footnotes',len(used))
