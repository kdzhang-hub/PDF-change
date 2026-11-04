import json,zipfile
from lxml import etree as E
import numpy as np
import pytest
from backend import store,export_worker
from backend.models import PageScene,LayerElement,PathCommand,uid
from backend.raster import save_image
from backend.export_docx import export_docx,NS

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init()

def test_docx_preserves_editable_text_geometry_assets_and_page_sizes(tmp_path):
    project=store.create('word')
    text=LayerElement(kind='text',name='small label',x=12.5,y=25,width=150,height=24,text='标签 & <test>',font='SimSun',font_size=12,bold=True,char_spacing=.3)
    image=LayerElement(kind='image',name='photo',x=20,y=60,width=60,height=40,z=1,asset=save_image(project,np.full((40,60,4),255,np.uint8)))
    path=LayerElement(kind='path',name='curve',x=30,y=130,width=40,height=20,z=2,fill='#00ff00',path=[PathCommand(op='M',points=[0,0]),PathCommand(op='C',points=[0,20,40,20,40,0]),PathCommand(op='Z')])
    hidden=text.model_copy(update={'id':uid(),'visible':False,'text':'not exported'})
    pages=[PageScene(index=0,width=300,height=400,original='x',status='ready',layers=[text,image,path,hidden]),PageScene(index=1,width=400,height=300,original='x',status='ready',layers=[])]
    out=export_docx(project,pages,tmp_path/'result.docx')
    with zipfile.ZipFile(out) as z:
        document=E.fromstring(z.read('word/document.xml'));rels=E.fromstring(z.read('word/_rels/document.xml.rels'))
        assert document.xpath('//w:txbxContent//w:t/text()',namespaces=NS)==['标签 & <test>']
        shape=document.xpath('//v:shape',namespaces=NS)[0]
        assert 'margin-left:12.5000pt' in shape.get('style') and 'mso-position-horizontal-relative:page' in shape.get('style')
        assert document.xpath('//w:rFonts/@w:eastAsia',namespaces=NS)==['SimSun']
        assert document.xpath('//w:pgSz/@w:w',namespaces=NS)==['6000','8000']
        assert len(document.xpath('//v:imagedata',namespaces=NS))==1
        assert document.xpath('//v:shape/@path',namespaces=NS)==['m 0,0 c 0,20000,40000,20000,40000,0 x  e']
        for item in rels:
            if item.get('Type').endswith('/image'):assert 'word/'+item.get('Target') in z.namelist()

def test_docx_snapshot_worker_and_invalid_format(tmp_path):
    project=store.create('worker');token=uid();snapshot,output=export_worker.paths(project,token,'docx')
    page=PageScene(index=0,width=300,height=400,original='x',status='ready',layers=[LayerElement(kind='text',name='a',text='saved edit',x=10,y=10,width=100,height=30)])
    snapshot.write_text(json.dumps([page.model_dump()]),'utf-8')
    assert export_worker.build(project,token,'docx')==output
    with pytest.raises(ValueError):export_worker.paths(project,token,'../file')
    with pytest.raises(ValueError):export_docx(project,[page.model_copy(update={'status':'pending'})],tmp_path/'pending.docx')


def test_word_rotation_keeps_scene_top_left_origin(tmp_path):
    project=store.create('rotation')
    text=LayerElement(kind='text',name='rotated',text='ROTATE',x=100,y=150,width=80,height=20,rotation=-90)
    page=PageScene(index=0,width=300,height=300,original='x',status='ready',layers=[text])
    out=export_docx(project,[page],tmp_path/'rotated.docx')
    with zipfile.ZipFile(out) as archive:
        document=E.fromstring(archive.read('word/document.xml'))
        assert not document.xpath('//v:shape',namespaces=NS)
        assert document.xpath('//wp:positionH/wp:posOffset/text()',namespaces=NS)==[str(70*12700)]
        assert document.xpath('//wp:positionV/wp:posOffset/text()',namespaces=NS)==[str(100*12700)]
        assert document.xpath('//a:xfrm/@rot',namespaces=NS)==['16200000']
        assert document.xpath('//wps:bodyPr/@upright',namespaces=NS)==['0']
        assert document.xpath('//w:txbxContent//w:t/text()',namespaces=NS)==['ROTATE']


def test_word_rotated_text_sorts_above_its_raster_background(tmp_path):
    from backend.export_docx import word_z_order
    project=store.create('mixed-order')
    base=LayerElement(kind='image',name='background',x=0,y=0,width=200,height=200,
                      asset=save_image(project,np.full((200,200,4),255,np.uint8)))
    text=LayerElement(kind='text',name='rotation',text='ROTATE',x=100,y=150,width=80,height=20,rotation=-90,z=1)
    page=PageScene(index=0,width=200,height=200,original='x',status='ready',layers=[base,text])
    with zipfile.ZipFile(export_docx(project,[page],tmp_path/'mixed.docx')) as archive:
        document=E.fromstring(archive.read('word/document.xml'))
        assert f'z-index:{word_z_order(0)};' in document.xpath('//v:shape/@style',namespaces=NS)[0]
        assert document.xpath('//wp:anchor/@relativeHeight',namespaces=NS)==[str(word_z_order(1))]


def test_word_transparency_stays_native_for_upright_and_rotated_text(tmp_path):
    project=store.create('text-alpha')
    layers=[LayerElement(kind='text',name='partial',text='Partial opacity',x=10,y=20,width=170,height=30,color='#aabbcc',opacity=.6),
            LayerElement(kind='text',name='invisible',text='Still editable',x=100,y=130,width=120,height=30,rotation=-90,opacity=0),
            LayerElement(kind='text',name='opaque',text='Opaque control',x=20,y=170,width=150,height=30,opacity=1)]
    page=PageScene(index=0,width=300,height=240,original='unused',status='ready',layers=layers)
    with zipfile.ZipFile(export_docx(project,[page],tmp_path/'text-alpha.docx')) as archive:
        document=E.fromstring(archive.read('word/document.xml'))
        assert document.get('{'+NS['mc']+'}Ignorable')=='w14'
        assert document.xpath('//w14:textFill/w14:solidFill/w14:srgbClr/@w14:val',namespaces=NS)==['AABBCC','172033']
        assert document.xpath('//w14:alpha/@w14:val',namespaces=NS)==['40000','100000']
        assert document.xpath('//w:txbxContent//w:t/text()',namespaces=NS)==['Partial opacity','Still editable','Opaque control']
        assert not document.xpath('//v:imagedata',namespaces=NS)
