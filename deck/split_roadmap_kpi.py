from copy import copy, deepcopy
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as E

BASE=Path(__file__).resolve().parent
NS={'p':'http://schemas.openxmlformats.org/presentationml/2006/main','a':'http://schemas.openxmlformats.org/drawingml/2006/main','r':'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
for k,v in NS.items():E.register_namespace(k,v)
def q(s):
    p,n=s.split(':');return '{'+NS[p]+'}'+n
def sub(e,s,**attrs):return E.SubElement(e,q(s),{k:str(v) for k,v in attrs.items()})
def xml(e):return E.tostring(e,encoding='utf-8',xml_declaration=True)
def shape(root,n):return next(s for s in root.findall('.//p:sp',NS) if s.find('p:nvSpPr/p:cNvPr',NS).get('id')==str(n))
def position(s,x,y,w,h):
    t=s.find('.//a:xfrm',NS)
    t.find('a:off',NS).attrib.update(x=str(round(x*914400)),y=str(round(y*914400)))
    t.find('a:ext',NS).attrib.update(cx=str(round(w*914400)),cy=str(round(h*914400)))
def write_text(s,value,size,color='142D4E',bold=False):
    body=s.find('p:txBody',NS)
    for p in list(body.findall('a:p',NS)):body.remove(p)
    for line in value.split('\n'):
        p=sub(body,'a:p');sub(p,'a:pPr',algn='l')
        r=sub(p,'a:r');rp=sub(r,'a:rPr',sz=size*100,b=int(bold))
        sub(sub(rp,'a:solidFill'),'a:srgbClr',val=color)
        for f in ('latin','ea','cs'):sub(rp,'a:'+f,typeface='Thonburi')
        sub(r,'a:t').text=line
def add_text(root,n,value,x,y,w,h,size,color='142D4E',bold=False):
    s=deepcopy(shape(root,3));s.find('p:nvSpPr/p:cNvPr',NS).attrib.update(id=str(n),name='Text '+str(n))
    position(s,x,y,w,h);write_text(s,value,size,color,bold)
    root.find('p:cSld/p:spTree',NS).append(s)

with zipfile.ZipFile(BASE/'henjai-white-blue-v3.pptx') as src:
    roadmap=E.fromstring(src.read('ppt/slides/slide26.xml'))
    tree=roadmap.find('p:cSld/p:spTree',NS)
    for s in list(tree.findall('p:sp',NS)):
        if int(s.find('p:nvSpPr/p:cNvPr',NS).get('id'))>6:tree.remove(s)
    write_text(shape(roadmap,6),'Roadmap 12 สัปดาห์',36,bold=True)
    frame=sub(tree,'p:graphicFrame')
    nv=sub(frame,'p:nvGraphicFramePr');sub(nv,'p:cNvPr',id=20,name='Roadmap table');sub(nv,'p:cNvGraphicFramePr');sub(nv,'p:nvPr')
    xf=sub(frame,'p:xfrm');sub(xf,'a:off',x=502920,y=2057400);sub(xf,'a:ext',cx=11155680,cy=3840480)
    data=sub(sub(frame,'a:graphic'),'a:graphicData',uri='http://schemas.openxmlformats.org/drawingml/2006/table')
    tbl=sub(data,'a:tbl');sub(tbl,'a:tblPr',firstRow=1,bandRow=0)
    grid=sub(tbl,'a:tblGrid')
    for width in [2194560,4206240,4754880]:sub(grid,'a:gridCol',w=width)
    rows=[['สัปดาห์','งานหลัก','ผลที่ได้'],['1–2','สัมภาษณ์ผู้ใช้ 10 คน','ความต้องการและร่างเกณฑ์'],['3–6','พัฒนาและทบทวนเกณฑ์','ระบบพร้อมใช้ / ขออนุมัติเกณฑ์'],['7–10','ทดลองใช้ 10 คน / 2 สัปดาห์','ผลทดสอบและข้อเสนอแนะ'],['11–12','ประเมินร่วมกับผู้เชี่ยวชาญ','สรุปผลตามเกณฑ์ที่อนุมัติ']]
    for i,row in enumerate(rows):
        tr=sub(tbl,'a:tr',h=768096)
        for j,value in enumerate(row):
            tc=sub(tr,'a:tc');body=sub(tc,'a:txBody');sub(body,'a:bodyPr');sub(body,'a:lstStyle')
            p=sub(body,'a:p');sub(p,'a:pPr',algn='l')
            r=sub(p,'a:r');rp=sub(r,'a:rPr',sz=2100,b=int(i==0 or j==0))
            sub(sub(rp,'a:solidFill'),'a:srgbClr',val='FFFFFF' if i==0 else '142D4E')
            for f in ['latin','ea','cs']:sub(rp,'a:'+f,typeface='Thonburi')
            sub(r,'a:t').text=value
            cp=sub(tc,'a:tcPr',marL=160000,marR=160000,marT=70000,marB=70000,anchor='ctr')
            for side in ['lnL','lnR','lnT','lnB']:
                ln=sub(cp,'a:'+side,w=6350);sub(sub(ln,'a:solidFill'),'a:srgbClr',val='D7E4F5')
            sub(sub(cp,'a:solidFill'),'a:srgbClr',val='1565D8' if i==0 else ('EAF2FF' if i%2 else 'FFFFFF'))

    kpi=deepcopy(roadmap)
    kpi.find('.//p:graphicFrame/p:xfrm/a:off',NS).set('y','2194560')
    write_text(shape(kpi,6),'แนวทางประเมินที่เสนอ (KPI)',34,bold=True)
    table=kpi.find('.//a:tbl',NS)
    template=deepcopy(table.find('a:tr',NS))
    for row in list(table.findall('a:tr',NS)):table.remove(row)
    columns=table.find('a:tblGrid',NS)
    for c,w in zip(columns,[1828800,5029200,4297680]):c.set('w',str(w))
    krows=[['ด้านที่วัด','ตัวชี้วัดจากเอกสาร','วิธีประเมินที่เสนอ'],
        ['การตรวจจับ','Precision, Recall, F1-score, mAP','เทียบกับข้อมูลที่คนกำกับ'],
        ['อารมณ์','Macro F1-score, Balanced Accuracy','เทียบกับป้ายกำกับจากมนุษย์'],
        ['บริบท','Context Accuracy, Critical Error Rate','ผู้เชี่ยวชาญตรวจความถูกต้อง'],
        ['คำบรรยาย','Correctness, Helpfulness,\nConciseness, Hallucination Rate','ให้คะแนนคำบรรยายภาษาไทย'],
        ['ความปลอดภัย','Hazard Recall, Time-to-Alert','วัดการตรวจพบและเวลาเตือน']]
    for i,values in enumerate(krows):
        row=deepcopy(template);row.set('h','640080')
        for j,(cell,value) in enumerate(zip(row.findall('a:tc',NS),values)):
            body=cell.find('a:txBody',NS)
            for p in list(body.findall('a:p',NS)):body.remove(p)
            for line in value.split('\n'):
                p=sub(body,'a:p');sub(p,'a:pPr',algn='l')
                r=sub(p,'a:r');rp=sub(r,'a:rPr',sz=1600,b=int(i==0 or j==0))
                sub(sub(rp,'a:solidFill'),'a:srgbClr',val='FFFFFF' if i==0 else '142D4E')
                for f in ['latin','ea','cs']:sub(rp,'a:'+f,typeface='Thonburi')
                sub(r,'a:t').text=line
            cell.find('a:tcPr/a:solidFill/a:srgbClr',NS).set('val','1565D8' if i==0 else ('EAF2FF' if i%2 else 'FFFFFF'))
        table.append(row)
    add_text(kpi,32,'ยังไม่มีเกณฑ์ผ่านที่ยืนยันแล้ว',.55,1.9,12,.45,20,'1565D8',True)
    add_text(kpi,33,'ให้ผู้เชี่ยวชาญทบทวนวิธีวัดและอนุมัติเกณฑ์ก่อนประเมินจริง',.55,6.6,12,.5,19,'1565D8',True)
    add_text(kpi,34,'อ้างอิง: CONCEPT IDEA, Plan Test หน้า 8–9',.55,7.1,12,.3,11,'52657D')
    # Reference-style roadmap: phases across columns, workstreams down rows.
    rt=roadmap.find('.//a:tbl',NS)
    template=deepcopy(rt.find('a:tr',NS))
    for row in list(rt.findall('a:tr',NS)):rt.remove(row)
    rg=rt.find('a:tblGrid',NS)
    for c in list(rg):rg.remove(c)
    for width in [1600200,2388870,2388870,2388870,2388870]:sub(rg,'a:gridCol',w=width)
    roadmap.find('.//p:graphicFrame/p:xfrm/a:off',NS).set('y','1828800')
    roadmap.find('.//p:graphicFrame/p:xfrm/a:ext',NS).set('cy','4297680')
    phases=[
        ['แผนงาน','W1–2\nเข้าใจผู้ใช้','W3–6\nพัฒนาและเตรียม','W7–10\nทดลองใช้งาน','W11–12\nสรุปผล'],
        ['ระบบ','กำหนดขอบเขต\nจากปัญหาผู้ใช้','พัฒนา AI\nและการแจ้งเตือน','วัดความถูกต้อง\nและความเสถียร','สรุปข้อผิดพลาด\nและปรับระบบ'],
        ['การประเมิน','ร่างวิธีวัด\nตามเอกสารแนวคิด','ผู้เชี่ยวชาญทบทวน\nและอนุมัติเกณฑ์','บันทึกผลตาม\nเกณฑ์ที่อนุมัติ','ผู้เชี่ยวชาญร่วม\nทบทวนผล'],
        ['ผู้ใช้','สัมภาษณ์\nผู้ใช้ 10 คน','เตรียมกลุ่มทดลอง\nและขอความยินยอม','ทดลองใช้ 10 คน\nนาน 2 สัปดาห์','สรุปข้อเสนอแนะ\nและแผนพัฒนาต่อ'],
    ]
    for i,values in enumerate(phases):
        tr=sub(rt,'a:tr',h=822960 if i==0 else 1158240)
        for j,value in enumerate(values):
            cell=deepcopy(template.find('a:tc',NS));tr.append(cell)
            body=cell.find('a:txBody',NS)
            for p in list(body.findall('a:p',NS)):body.remove(p)
            for line in value.split('\n'):
                p=sub(body,'a:p');sub(p,'a:pPr',algn='ctr')
                r=sub(p,'a:r');rp=sub(r,'a:rPr',sz=1800 if j else 1900,b=int(i==0 or j==0))
                sub(sub(rp,'a:solidFill'),'a:srgbClr',val='FFFFFF' if i==0 else '142D4E')
                for f in ['latin','ea','cs']:sub(rp,'a:'+f,typeface='Thonburi')
                sub(r,'a:t').text=line
            cp=cell.find('a:tcPr',NS)
            cp.find('a:solidFill/a:srgbClr',NS).set('val',(['142D4E','6C9DE0','397DDD','1565D8','10479D'][j] if i==0 else ('EAF2FF' if j==0 else 'FFFFFF')))
    add_text(roadmap,40,'อนุมัติเกณฑ์ก่อนทดลองกับผู้ใช้',.55,7.0,12,.35,15,'1565D8')
    pres=E.fromstring(src.read('ppt/presentation.xml'));lst=pres.find('p:sldIdLst',NS)
    lst.insert(26,E.Element(q('p:sldId'),{'id':'286',q('r:id'):'rId37'}))
    rel=src.read('ppt/_rels/presentation.xml.rels').replace(b'</Relationships>',b'<Relationship Id="rId37" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/slide" Target="slides/slide31.xml"/></Relationships>')
    types=src.read('[Content_Types].xml').replace(b'</Types>',b'<Override PartName="/ppt/slides/slide31.xml" ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/></Types>')
    changes={'ppt/slides/slide26.xml':xml(roadmap),'ppt/presentation.xml':xml(pres),'ppt/_rels/presentation.xml.rels':rel,'[Content_Types].xml':types}
    evaluation=E.fromstring(src.read('ppt/slides/slide22.xml'))
    for t in evaluation.findall('.//a:t',NS):
        if t.text=='ให้ผู้เชี่ยวชาญด้านการมองเห็นร่วมกำหนดเกณฑ์':t.text='ให้ผู้เชี่ยวชาญด้านการมองเห็นทบทวนวิธีวัด'
        elif t.text=='ทบทวนความเหมาะสมและความเสี่ยงของคำบรรยาย':t.text='และอนุมัติเกณฑ์ก่อนเริ่มประเมินจริง'
        elif t.text=='ทดลองกับผู้ใช้ 10 คน และบันทึกผลตาม KPI':t.text='จากนั้นทดลองกับผู้ใช้ 10 คนตามเกณฑ์ที่อนุมัติ'
    changes['ppt/slides/slide22.xml']=xml(evaluation)
    if 'docProps/app.xml' in src.namelist():changes['docProps/app.xml']=re.sub(rb'<Slides>\d+</Slides>',b'<Slides>31</Slides>',src.read('docProps/app.xml'))
    for n in range(1,31):
        name=f'ppt/slides/slide{n}.xml'
        root=E.fromstring(changes.get(name,src.read(name)))
        tree=root.find('p:cSld/p:spTree',NS)
        removed=False
        for s in list(tree.findall('p:sp',NS)):
            if any('TRUE INNOVATION' in (t.text or '') for t in s.findall('.//a:t',NS)):
                tree.remove(s);removed=True
        if removed:changes[name]=xml(root)
    kt=kpi.find('p:cSld/p:spTree',NS)
    for s in list(kt.findall('p:sp',NS)):
        if any('TRUE INNOVATION' in (t.text or '') for t in s.findall('.//a:t',NS)):kt.remove(s)
    out=BASE/'henjai-white-blue-v7.pptx'
    with zipfile.ZipFile(out,'w') as dst:
        for item in src.infolist():dst.writestr(copy(item),changes.get(item.filename,src.read(item.filename)))
        dst.writestr('ppt/slides/slide31.xml',xml(kpi))
        dst.writestr('ppt/slides/_rels/slide31.xml.rels',src.read('ppt/slides/_rels/slide26.xml.rels'))
with zipfile.ZipFile(out) as src:
    assert src.testzip() is None
    assert all(b'TRUE INNOVATION' not in src.read(n) for n in src.namelist() if re.fullmatch(r'ppt/slides/slide\d+\.xml',n))
    assert len(E.fromstring(src.read('ppt/presentation.xml')).find('p:sldIdLst',NS))==31
    preview=Path('/private/tmp/henjai-v4-preview');preview.mkdir(exist_ok=True)
    for n in [22,26,27]:
        p=E.fromstring(src.read('ppt/presentation.xml'));lst=p.find('p:sldIdLst',NS);selected=deepcopy(lst[n-1]);lst.clear();lst.append(selected)
        with zipfile.ZipFile(preview/f'slide-{n}.pptx','w') as dst:
            for item in src.infolist():dst.writestr(copy(item),xml(p) if item.filename=='ppt/presentation.xml' else src.read(item.filename))
print(out)
