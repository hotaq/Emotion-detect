"""Edit three requested slides, preserving the rest of the existing deck."""
from copy import copy, deepcopy
from pathlib import Path
import re
import zipfile
import xml.etree.ElementTree as E

BASE = Path(__file__).resolve().parent
NS = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main', 'p': 'http://schemas.openxmlformats.org/presentationml/2006/main', 'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'}
for prefix, uri in NS.items(): E.register_namespace(prefix, uri)
def tag(n):
    prefix, name = n.split(':')
    return '{'+NS[prefix]+'}'+name
def pos(shape, x, y, w, h):
    xf = shape.find('.//a:xfrm', NS)
    xf.find('a:off', NS).attrib.update(x=str(round(x*914400)), y=str(round(y*914400)))
    xf.find('a:ext', NS).attrib.update(cx=str(round(w*914400)), cy=str(round(h*914400)))
def text(shape, value, size=22, color='142D4E', bold=False):
    body = shape.find('p:txBody', NS)
    template = deepcopy(body.find('a:p', NS))
    for p in list(body.findall('a:p', NS)): body.remove(p)
    for line in value.split('\n'):
        p = deepcopy(template)
        for child in list(p):
            if child.tag != tag('a:pPr'): p.remove(child)
        r = E.SubElement(p, tag('a:r'))
        rp = E.SubElement(r, tag('a:rPr'), sz=str(size*100), b='1' if bold else '0')
        E.SubElement(E.SubElement(rp, tag('a:solidFill')), tag('a:srgbClr'), val=color)
        for kind in ('latin','ea','cs'): E.SubElement(rp, tag('a:'+kind), typeface='Thonburi')
        E.SubElement(r, tag('a:t')).text=line
        body.append(p)
def edit(root, ident):
    return next(s for s in root.findall('.//p:sp', NS) if s.find('p:nvSpPr/p:cNvPr', NS).get('id')==str(ident))
def add(root, value, x,y,w,h,size=22,color='142D4E',bold=False):
    shape=deepcopy(edit(root,3))
    ident=max(int(n.get('id')) for n in root.findall('.//p:cNvPr',NS))+1
    shape.find('p:nvSpPr/p:cNvPr',NS).attrib.update(id=str(ident),name=f'TextBox {ident}')
    text(shape,value,size,color,bold); pos(shape,x,y,w,h)
    root.find('p:cSld/p:spTree',NS).append(shape)
    return shape

with zipfile.ZipFile(BASE/'henjai-white-blue.pptx') as src:
    changes={}
    root=E.fromstring(src.read('ppt/slides/slide12.xml'))
    text(edit(root,6),'สมมติฐานเพื่อทดสอบกับผู้ใช้ ยังไม่ใช่ผลสัมภาษณ์',18,'1565D8',True)
    text(edit(root,7),'User Insight: ความเงียบที่ตีความไม่ได้',32,bold=True)
    pos(edit(root,7),.55,1.85,12.2,.8)
    text(edit(root,8),'สถานการณ์สมมติ: ผู้มีความบกพร่องทางการเห็นคุยกับเพื่อน\nเมื่ออีกฝ่ายเงียบ จึงไม่แน่ใจว่ากำลังคิดหรือไม่พอใจ\n\nพฤติกรรมที่คาด: หยุดพูดหรือถามย้ำเพื่อเช็กความรู้สึก\nความต้องการที่คาด: คำบอกใบหน้าสั้น ๆ เฉพาะจังหวะสำคัญ',23)
    pos(edit(root,8),.55,2.9,12.0,2.65)
    add(root,'แนวทางออกแบบ: บอกสัญญาณที่เห็น พร้อมความไม่แน่ใจ\nยืนยันสมมติฐานด้วยการสัมภาษณ์และทดลองกับผู้ใช้จริง',.55,5.9,12.0,1.0,22,'1565D8',True)
    changes[12]=E.tostring(root,encoding='utf-8',xml_declaration=True)

    root=E.fromstring(src.read('ppt/slides/slide22.xml'))
    text(edit(root,6),'การวัดผลและแผนประเมินร่วมกับผู้เชี่ยวชาญ',30,bold=True)
    pic=root.find('.//p:pic',NS)
    root.find('p:cSld/p:spTree',NS).remove(pic)
    text(edit(root,8),'แผนเก็บภาพขณะใช้งานในชีวิตประจำวัน',24,'1565D8',True)
    pos(edit(root,8),.55,2.05,7.7,.7)
    add(root,'ระหว่างพูดคุย เดินทาง และใช้พื้นที่สาธารณะ\nครอบคลุมสีหน้า ภาษากาย และสภาพแวดล้อม\nเก็บภาพโดยได้รับความยินยอมจากผู้เกี่ยวข้อง',.55,2.9,7.7,1.5,21)
    add(root,'แผนประเมินระยะถัดไป',.55,4.85,7.7,.45,22,'1565D8',True)
    add(root,'ให้ผู้เชี่ยวชาญด้านการมองเห็นร่วมกำหนดเกณฑ์\nทบทวนความเหมาะสมและความเสี่ยงของคำบรรยาย\nทดลองกับผู้ใช้ 10 คน และบันทึกผลตาม KPI',.55,5.4,7.7,1.35,20)
    # Requested empty photo slot, using a native editable rectangle.
    slot=deepcopy(edit(root,2)); slot.find('p:nvSpPr/p:cNvPr',NS).attrib.update(id='40',name='Expert photo placeholder')
    pos(slot,9.05,2.05,3.7,3.55)
    line=slot.find('p:spPr/a:ln',NS)
    for c in list(line):line.remove(c)
    line.set('w','12700')
    E.SubElement(E.SubElement(line,tag('a:solidFill')),tag('a:srgbClr'),val='1565D8')
    root.find('p:cSld/p:spTree',NS).append(slot)
    add(root,'ผู้เชี่ยวชาญด้านการมองเห็น',9.05,5.85,3.7,.75,19,'1565D8',True)
    add(root,'แผนเชิญร่วมประเมิน',9.05,6.5,3.7,.45,16,'52657D')
    text(edit(root,9),'ชุดทดสอบใหม่ที่วางแผนเก็บในระยะถัดไป ไม่ใช่ชุดที่ใช้รายงานผลเบื้องต้น',11,'52657D')
    pos(edit(root,9),.55,7.05,12.1,.3)
    changes[22]=E.tostring(root,encoding='utf-8',xml_declaration=True)

    root=E.fromstring(src.read('ppt/slides/slide26.xml'))
    text(edit(root,6),'Roadmap 12 สัปดาห์ และ KPI เป้าหมาย',34,bold=True)
    labels=['สัมภาษณ์ผู้ใช้','พัฒนาระบบ','ทดลองใช้งาน','ประเมินและสรุป']
    details=['ผู้ใช้ 10 คน\nเตรียมเกณฑ์กับผู้เชี่ยวชาญ','ปรับคำบรรยาย\nและจังหวะการแจ้งเตือน','ผู้ใช้ 10 คน นาน 2 สัปดาห์\nเก็บผลและข้อเสนอแนะ','ผู้เชี่ยวชาญร่วมทบทวน\nเทียบผลกับ KPI']
    for i,x in enumerate([.55,3.72,6.89,10.06]):
        pos(edit(root,7+i*3),x,2.35,2.9,.45)
        text(edit(root,8+i*3),labels[i],21,bold=True);pos(edit(root,8+i*3),x,2.95,2.9,.5)
        text(edit(root,9+i*3),details[i],17,'52657D');pos(edit(root,9+i*3),x,3.65,2.9,1.15)
    text(edit(root,19),'KPI เป้าหมายในการทดลอง ยังไม่ใช่ผลที่ผ่านแล้ว',20,'1565D8',True)
    pos(edit(root,19),.55,5.05,12.1,.5)
    for x,number,label in [( .55,'≥80%','อ่านอารมณ์ถูก'),(4.78,'≤10%','บรรยายสิ่งที่ไม่มีจริง'),(9.0,'≤3 วินาที','ตั้งแต่รับภาพจนเริ่มพูด')]:
        add(root,number,x,5.65,3.8,.85,36,'1565D8',True)
        add(root,label,x,6.6,3.8,.5,18)
    changes[26]=E.tostring(root,encoding='utf-8',xml_declaration=True)
    output=BASE/'henjai-white-blue-v3.pptx'
    with zipfile.ZipFile(output,'w') as dst:
        for item in src.infolist():
            match=re.fullmatch(r'ppt/slides/slide(\d+)\.xml',item.filename)
            dst.writestr(copy(item),changes.get(int(match[1]),src.read(item.filename)) if match else src.read(item.filename))
    preview=Path('/private/tmp/henjai-v2-preview');preview.mkdir(exist_ok=True)
    with zipfile.ZipFile(output) as deck:
        assert deck.testzip() is None
        presentation=deck.read('ppt/presentation.xml')
        ids=re.findall(rb'<p:sldId\s[^>]*/>',presentation);assert len(ids)==30
        for n in changes:
            one=re.sub(rb'<p:sldIdLst>.*?</p:sldIdLst>',b'<p:sldIdLst>'+ids[n-1]+b'</p:sldIdLst>',presentation)
            with zipfile.ZipFile(preview/f'slide-{n}.pptx','w') as dst:
                for item in deck.infolist():dst.writestr(copy(item),one if item.filename=='ppt/presentation.xml' else deck.read(item.filename))
print(output)
