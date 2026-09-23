from copy import copy, deepcopy
from pathlib import Path
import zipfile
import xml.etree.ElementTree as E

BASE = Path(__file__).resolve().parent
NS = {'p': 'http://schemas.openxmlformats.org/presentationml/2006/main', 'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
for k, v in NS.items(): E.register_namespace(k, v)
def tag(s):
    a, b = s.split(':'); return '{'+NS[a]+'}'+b
def xml(e): return E.tostring(e, encoding='utf-8', xml_declaration=True)
def set_body(body, value, size, bold=False, color='142D4E'):
    template = deepcopy(body.find('a:p', NS))
    for p in list(body.findall('a:p', NS)): body.remove(p)
    for line in value.split('\n'):
        p = deepcopy(template)
        for child in list(p):
            if child.tag != tag('a:pPr'): p.remove(child)
        r = E.SubElement(p, tag('a:r'))
        rp = E.SubElement(r, tag('a:rPr'), sz=str(size*100), b=str(int(bold)))
        E.SubElement(E.SubElement(rp, tag('a:solidFill')), tag('a:srgbClr'), val=color)
        for f in ['latin','ea','cs']: E.SubElement(rp, tag('a:'+f), typeface='Thonburi')
        E.SubElement(r, tag('a:t')).text = line
        body.append(p)

source = BASE/'henjai-white-blue-v8.pptx'
out = BASE/'henjai-white-blue-v9.pptx'
with zipfile.ZipFile(source) as src:
    root = E.fromstring(src.read('ppt/slides/slide31.xml'))
    shapes = {s.find('p:nvSpPr/p:cNvPr',NS).get('id'):s for s in root.findall('.//p:sp',NS)}
    for sid, text, size, color in [
        ('6','KPI เป้าหมายต้นแบบ 12 สัปดาห์',34,'142D4E'),
        ('32','ค่าเป้าหมายเสนอ ยังไม่ใช่ผลทดสอบจริง',19,'1565D8'),
        ('33','ให้ผู้เชี่ยวชาญทบทวนวิธีวัดและค่าเป้าหมายก่อนทดสอบ',17,'1565D8'),
        ('34','ตัวชี้วัดอิง CONCEPT IDEA หน้า 8–9 / ค่าเป้าหมายเป็นข้อเสนอ ไม่รับรองการเดินทางโดยลำพัง',11,'52657D')]:
        set_body(shapes[sid].find('p:txBody',NS),text,size,sid!='34',color)
    table = root.find('.//a:tbl',NS)
    template = deepcopy(table.find('a:tr',NS))
    for row in list(table.findall('a:tr',NS)): table.remove(row)
    for col,w in zip(table.find('a:tblGrid',NS), [3108960,5303520,2743200]): col.set('w',str(w))
    rows = [
        ['ด้านที่วัด','ตัวชี้วัด','เป้าหมาย'],
        ['ตรวจจับคนและวัตถุ','F1-score','≥ 85%'],
        ['จำแนกสีหน้า','Macro F1-score','≥ 75%'],
        ['เข้าใจบริบท','Context Accuracy','≥ 80%'],
        ['คำบรรยายถูกต้อง','สัดส่วนคำบรรยายที่ผู้ประเมินให้ผ่าน','≥ 85%'],
        ['ข้อมูลไม่มีหลักฐานในภาพ','Hallucination Rate','≤ 5%'],
        ['ตรวจพบอันตราย','Hazard Recall ในชุดทดสอบ','≥ 95%'],
        ['เวลาแจ้งเตือน','Time-to-Alert หลังเกิดเหตุ','≤ 2 วินาที*'],
    ]
    for i, values in enumerate(rows):
        row = deepcopy(template); row.set('h','457200')
        for j,(cell,value) in enumerate(zip(row.findall('a:tc',NS),values)):
            set_body(cell.find('a:txBody',NS),value,16,i==0 or j==2,'FFFFFF' if i==0 else '142D4E')
            cell.find('a:tcPr/a:solidFill/a:srgbClr',NS).set('val','1565D8' if i==0 else ('EAF2FF' if i%2 else 'FFFFFF'))
        table.append(row)
    root.find('.//p:graphicFrame/p:xfrm/a:ext',NS).set('cy',str(457200*8))
    foot = deepcopy(shapes['34'])
    foot.find('p:nvSpPr/p:cNvPr',NS).attrib.update(id='35',name='Time target definition')
    foot.find('.//a:xfrm/a:off',NS).set('y',str(round(6.42*914400)))
    set_body(foot.find('p:txBody',NS),'*อย่างน้อย 95% ของเหตุที่ระบบตรวจพบ',12,color='52657D')
    root.find('p:cSld/p:spTree',NS).append(foot)
    with zipfile.ZipFile(out,'w') as dst:
        for item in src.infolist(): dst.writestr(copy(item),xml(root) if item.filename=='ppt/slides/slide31.xml' else src.read(item.filename))
with zipfile.ZipFile(source) as src, zipfile.ZipFile(out) as dst:
    assert dst.testzip() is None
    assert [n for n in src.namelist() if src.read(n)!=dst.read(n)] == ['ppt/slides/slide31.xml']
    pres=E.fromstring(dst.read('ppt/presentation.xml')); slides=pres.find('p:sldIdLst',NS)
    assert len(slides)==31
    selected=deepcopy(slides[26]); slides.clear(); slides.append(selected)
    preview=Path('/private/tmp/henjai-kpi-v9'); preview.mkdir(exist_ok=True)
    with zipfile.ZipFile(preview/'kpi.pptx','w') as render:
        for item in dst.infolist(): render.writestr(copy(item),xml(pres) if item.filename=='ppt/presentation.xml' else dst.read(item.filename))
print(out)
