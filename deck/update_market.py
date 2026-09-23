from copy import copy, deepcopy
from pathlib import Path
import ast
import zipfile
import xml.etree.ElementTree as E

BASE=Path(__file__).resolve().parent
# Reuse only helpers, without running the previous deck-building workflow.
module=ast.parse((BASE/'split_roadmap_kpi.py').read_text())
helpers=ast.Module(body=[n for n in module.body if isinstance(n,(ast.Import,ast.ImportFrom,ast.FunctionDef)) or isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id in ('BASE','NS') for t in n.targets)],type_ignores=[])
exec(compile(helpers,'slide_helpers','exec'))
for k,v in NS.items():E.register_namespace(k,v)

sources=[
    ('Seeing AI','https://www.seeingai.com/'),
    ('Microsoft: facial expressions','https://news.microsoft.com/source/features/ai/15-milestones-that-shaped-microsofts-vision-for-ai/'),
    ('Be My AI','https://support.bemyeyes.com/hc/en-us/articles/18133134809105-How-do-I-use-Be-My-AI'),
    ('Envision Glasses','https://support.letsenvision.com/hc/en-us/articles/7603823400849-Describe-Scene'),
]
with zipfile.ZipFile(BASE/'henjai-white-blue-v7.pptx') as src:
    root=E.fromstring(src.read('ppt/slides/slide13.xml'))
    tree=root.find('p:cSld/p:spTree',NS)
    template=deepcopy(next(s for s in tree.findall('p:sp',NS) if s.find('p:nvSpPr/p:cNvPr',NS).get('id')=='4'))
    # Helper add_text clones id 3, whose old branding was removed in v7.
    template.find('p:nvSpPr/p:cNvPr',NS).set('id','3');tree.append(template)
    for s in list(tree.findall('p:sp',NS)):
        if int(s.find('p:nvSpPr/p:cNvPr',NS).get('id'))>6:tree.remove(s)
    write_text(shape(root,3),'',10)
    write_text(shape(root,6),'ผลิตภัณฑ์ที่มีอยู่ในตลาด',36,bold=True)
    entries=[
        ('Seeing AI','Microsoft / แอปมือถือ','อ่านข้อความและบรรยายภาพ\nระบุสินค้าและบรรยายบุคคล\nMicrosoft ระบุว่าบรรยายสีหน้าได้','ผู้ช่วยงานมองเห็นทั่วไป'),
        ('Be My AI','ฟีเจอร์ในแอป Be My Eyes','บรรยายภาพที่ถ่ายหรืออัปโหลด\nถามต่อเกี่ยวกับภาพได้\nต้องเชื่อมต่ออินเทอร์เน็ต','บรรยายภาพและถามตอบ'),
        ('Envision Glasses','แว่นตาพร้อมกล้องและลำโพง','ถ่ายภาพเพื่อบรรยายฉาก\nถามต่อด้วย Ask Envision\nDescribe Scene ต้องใช้อินเทอร์เน็ต','ใช้งานผ่านอุปกรณ์สวมใส่'),
    ]
    for i,(name,kind,features,summary) in enumerate(entries):
        x=.55+i*4.23
        add_text(root,20+i*4,name,x,2.2,3.85,.6,26,'1565D8',True)
        add_text(root,21+i*4,kind,x,2.95,3.85,.65,17,'52657D')
        add_text(root,22+i*4,features,x,3.8,3.85,1.65,19)
        add_text(root,23+i*4,summary,x,5.55,3.85,.6,17,'1565D8',True)
    add_text(root,40,'HENJAI: มุ่งคำบรรยายสังคมภาษาไทย และเลือกจังหวะพูดตามภาพที่เปลี่ยน',.55,6.35,12.1,.5,20,'1565D8',True)
    add_text(root,41,'จุดเน้นที่ต้องทดสอบเทียบกับผลิตภัณฑ์จริง ยังไม่ได้ยืนยันว่าเหนือกว่า',.55,6.9,12.1,.35,14,'52657D')
    add_text(root,42,'ที่มา: Seeing AI / Microsoft, Be My Eyes Help Center, Envision Support • ตรวจ 12 ก.ย. 2569',.55,7.25,12.1,.2,9,'52657D')
    changes={'ppt/slides/slide13.xml':xml(root)}
    for number,before,after in [(5,'เทคโนโลยีทุกวันนี้บอกได้แค่นี้','ตัวอย่างผลจากระบบตรวจจับวัตถุ'),(6,'สิ่งที่เขาต้องการจริง ๆ','ตัวอย่างคำบรรยายของ HENJAI')]:
        s=E.fromstring(src.read(f'ppt/slides/slide{number}.xml'))
        for t in s.findall('.//a:t',NS):
            if t.text==before:t.text=after
        changes[f'ppt/slides/slide{number}.xml']=xml(s)
    # Attach source URLs as editable speaker notes on the market slide.
    notes=E.Element(q('p:notes'));cs=sub(notes,'p:cSld');nt=sub(cs,'p:spTree')
    nv=sub(nt,'p:nvGrpSpPr');sub(nv,'p:cNvPr',id=1,name='');sub(nv,'p:cNvGrpSpPr');sub(nv,'p:nvPr');sub(nt,'p:grpSpPr')
    sp=sub(nt,'p:sp');nv=sub(sp,'p:nvSpPr');sub(nv,'p:cNvPr',id=2,name='Sources');sub(nv,'p:cNvSpPr');sub(sub(nv,'p:nvPr'),'p:ph',type='body',idx=1);sub(sp,'p:spPr')
    body=sub(sp,'p:txBody');sub(body,'a:bodyPr');sub(body,'a:lstStyle')
    for label,link in sources:
        p=sub(body,'a:p');r=sub(p,'a:r');sub(r,'a:t').text=label+': '+link
    sub(sub(notes,'p:clrMapOvr'),'a:masterClrMapping')
    relns='http://schemas.openxmlformats.org/package/2006/relationships'
    relname='ppt/slides/_rels/slide13.xml.rels'
    rel=E.fromstring(src.read(relname));rid=max(int(r.get('Id')[3:]) for r in rel)+1
    E.SubElement(rel,'{'+relns+'}Relationship',Id=f'rId{rid}',Type=NS['r']+'/notesSlide',Target='../notesSlides/notesSlide31.xml')
    # Native source hyperlinks retain compatibility with the source deck's
    # lack of a notes master. Source titles remain visible on the slide.
    links=[]
    for offset,(ident,source_index) in enumerate([(20,0),(24,2),(28,3),(42,1)]):
        link_id=f'rId{rid+offset}'
        rp=shape(root,ident).find('.//a:rPr',NS)
        sub(rp,'a:hlinkClick',**{q('r:id'):link_id})
        links.append(f'<Relationship Id="{link_id}" Type="{NS["r"]}/hyperlink" Target="{sources[source_index][1]}" TargetMode="External"/>')
    changes['ppt/slides/slide13.xml']=xml(root)
    changes[relname]=src.read(relname).replace(b'</Relationships>',(''.join(links)+'</Relationships>').encode())
    out=BASE/'henjai-white-blue-v8.pptx'
    with zipfile.ZipFile(out,'w') as dst:
        for item in src.infolist():dst.writestr(copy(item),changes.get(item.filename,src.read(item.filename)))
with zipfile.ZipFile(out) as src:
    assert src.testzip() is None
    pres=E.fromstring(src.read('ppt/presentation.xml'));lst=pres.find('p:sldIdLst',NS);assert len(lst)==31
    selected=deepcopy(lst[12]);lst.clear();lst.append(selected)
    preview=Path('/private/tmp/henjai-market-preview');preview.mkdir(exist_ok=True)
    with zipfile.ZipFile(preview/'market.pptx','w') as dst:
        for item in src.infolist():
            data=xml(pres) if item.filename=='ppt/presentation.xml' else src.read(item.filename)
            if item.filename=='ppt/slides/_rels/slide13.xml.rels':
                data=data.replace(f'<Relationship Id="rId{rid}" Type="{NS["r"]}/notesSlide" Target="../notesSlides/notesSlide31.xml"/>'.encode(),b'')
            dst.writestr(copy(item),data)
print(out)
