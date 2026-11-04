import io,json,socket,zipfile
from pathlib import Path
import pytest
import fitz
import numpy as np
from PIL import Image
from fastapi.testclient import TestClient
from backend import store,local_models,cloud
from backend.models import LayerElement,PageScene,SplitRequest,PathCommand
from backend.extract import prepare,convert_page
from backend.raster import save_image,read_image,apply_masks,split_mask
from backend.export import export_pptx

@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init()
    monkeypatch.setattr(local_models,'status',lambda:{'sam':False,'ocr':False})

def make_project():
    project=store.create('fixture.pdf');doc=fitz.open();p=doc.new_page(width=600,height=400)
    p.insert_text((35,55),'Revenue 128.50',fontsize=20)
    p.draw_rect((30,100,230,170),color=None,fill=(.2,.4,.8),fill_opacity=.5)
    s=p.new_shape();s.draw_bezier((50,260),(100,180),(150,320),(250,220));s.finish(color=(1,0,0),width=3);s.commit()
    doc.save(store.project_dir(project)/'source.pdf');doc.close()
    for page in prepare(project):store.save_page(project,page)
    return project

def test_native_no_network_no_flat_page(monkeypatch,tmp_path):
    def denied(*a,**k):raise AssertionError('Local conversion attempted network')
    monkeypatch.setattr(socket.socket,'connect',denied)
    p=make_project();page=convert_page(p,0,'original-0.png')
    assert ''.join(l.text for l in page.layers if l.kind=='text')=='Revenue 128.50'
    assert not [l for l in page.layers if l.kind=='image']
    assert any(c.op=='C' for l in page.layers for c in l.path)
    out=export_pptx(p,[page],tmp_path/'native.pptx')
    with zipfile.ZipFile(out) as z:
        xml=z.read('ppt/slides/slide1.xml').decode()
        assert 'cubicBezTo' in xml and 'alpha val="50000"' in xml
        assert 'Revenue 128.50' in xml and '<p:pic>' not in xml
    assert store.budget()['calls']==[]

def test_alpha_split_removes_underlying_ghost():
    p=store.create('raster');image=np.full((100,100,4),255,np.uint8);image[25:65,30:70,:3]=[200,30,70]
    l=LayerElement(kind='image',name='object',x=0,y=0,width=100,height=100,asset=save_image(p,image))
    mask=np.zeros((100,100),bool);mask[25:65,30:70]=True
    pieces=apply_masks(p,l,image,[mask]);base=read_image(p,pieces[0].asset);fg=read_image(p,pieces[1].asset)
    assert np.all(base[25:65,30:70,:3]==255)
    assert fg[30,40,3]==255 and fg[0,0,3]==0
    restored=np.where(fg[:,:,3:]>0,fg,base)
    assert np.array_equal(restored,image)

def test_revision_conflict_preserves_edit():
    p=make_project();a=store.get_page(p,0);b=a.model_copy(deep=True)
    a.warnings=['first'];store.save_page(p,a,expected=0)
    b.warnings=['second']
    with pytest.raises(ValueError,match='页面已更新'):store.save_page(p,b,expected=0)
    assert store.get_page(p,0).warnings==['first']

def test_budget_reservations_atomic_and_conservative():
    from concurrent.futures import ThreadPoolExecutor
    def reserve(_):
        try:return store.reserve('test',.6,{})
        except ValueError:return None
    with ThreadPoolExecutor(max_workers=8) as ex:results=list(ex.map(reserve,range(15)))
    assert sum(x is not None for x in results)==8
    assert store.budget()['committed']==4.8
    with pytest.raises(ValueError):store.reserve('unknown',float('nan'),{})
    store.settle(next(x for x in results if x),'uncertain')
    assert store.budget()['committed']==4.8

def test_path_validation_and_traversal():
    with pytest.raises(ValueError):PathCommand(op='C',points=[1,2])
    with pytest.raises(ValueError):store.asset_path('a'*32,'../secret')
    with pytest.raises(ValueError):store.project_dir('../secret')

def test_cloud_missing_config_never_sends(monkeypatch):
    p=make_project();page=store.get_page(p,0);monkeypatch.delenv('LAYERDECK_CLOUD',raising=False)
    with pytest.raises(ValueError,match='云端未启用'):cloud.process(p,page,{'provider':'sam3','layer_id':'missing','reason':'local failed','box':[0,0,20,20]})
    assert not store.budget()['calls']

def test_api_origin_import_and_validation(monkeypatch):
    from backend.app import app
    with TestClient(app) as client:
        assert client.get('/api/health').status_code==200
        assert client.post('/api/projects',headers={'origin':'https://evil.example'},files={'file':('bad.pdf',b'bad')}).status_code==403
        assert client.post('/api/projects',files={'file':('bad.pdf',b'bad')}).status_code==400
        d=fitz.open();d.new_page();data=d.tobytes();d.close()
        res=client.post('/api/projects',files={'file':('test.pdf',data)})
        assert res.status_code==200;project=res.json();page=project['pages'][0]
        page['width']=1
        assert client.put(f"/api/projects/{project['id']}/pages/0",json=page).status_code==400

def test_manual_mask_bounds():
    image=np.full((100,100,4),255,np.uint8)
    mask=split_mask(image,SplitRequest(method='brush',points=[[20,20],[40,20]],radius=5))[0]
    assert mask[20,30] and not mask[0,0]
    with pytest.raises(ValueError):split_mask(image,SplitRequest(method='box',box=[2,2,2,2]))

def test_complex_paint_contributions_are_independent_and_recompose(monkeypatch):
    from backend.pdfium_extract import convert_paint
    import pypdfium2
    def denied(*a,**k):raise AssertionError('Complex extraction must stay offline')
    monkeypatch.setattr(socket.socket,'connect',denied)
    p=store.create('complex');d=fitz.open();page=d.new_page(width=200,height=120)
    page.draw_rect(page.rect,fill=(.03,.08,.2),color=None)
    page.draw_circle((65,55),28,fill=(.1,.5,1),color=None)
    page.draw_rect((60,30,150,90),fill=(.1,1,.5),fill_opacity=.45,color=None)
    d.save(store.project_dir(p)/'source.pdf');d.close()
    scene=convert_paint(p,0,'original.png',scale=2)
    assert len(scene.layers)>=3
    canvas=Image.new('RGBA',(400,240),'white')
    for layer in sorted(scene.layers,key=lambda l:l.z):
        im=Image.open(store.asset_path(p,layer.asset)).convert('RGBA')
        canvas.alpha_composite(im,(round(layer.x*2),round(layer.y*2)))
    doc=pypdfium2.PdfDocument(str(store.project_dir(p)/'source.pdf'));original=doc[0].render(scale=2).to_pil().convert('RGB')
    error=np.abs(np.array(canvas.convert('RGB')).astype(float)-np.array(original)).mean()
    assert error<1.2
    assert not store.budget()['calls']

def test_ocr_on_transparent_text_removes_alpha_not_black_ghost(monkeypatch):
    from backend.raster import auto_image
    monkeypatch.setattr(local_models,'status',lambda:{'sam':False,'ocr':True})
    monkeypatch.setattr(local_models,'ocr',lambda im:[('TEST',.99,np.array([[5,5],[95,5],[95,35],[5,35]],dtype=np.int32))])
    p=store.create('alpha-text');image=np.zeros((40,100,4),np.uint8);image[12:28,20:80]=255
    layer=LayerElement(kind='image',name='text',x=0,y=0,width=100,height=40,asset=save_image(p,image))
    result,warnings=auto_image(p,layer,segment=False)
    assert any(l.kind=='text' for l in result)
    cleaned=list((store.project_dir(p)/'assets').glob('ocr-clean-*.png'))
    assert cleaned and not read_image(p,cleaned[0].name)[:,:,3].any()
    assert all(l.kind=='text' for l in result)
    assert all(l.parent_id==layer.id and l.restoration_asset==layer.restoration_asset for l in result)
    assert np.array_equal(read_image(p,layer.restoration_asset),image)

def test_tiny_gradient_label_stays_native_editable_text(tmp_path):
    from pptx import Presentation
    p=store.create('tiny-label')
    layer=LayerElement(kind='text',name='tiny',text='小标签 2026',x=10,y=10,width=80,height=12,font='Microsoft YaHei',font_size=6,
        text_gradient=['#fff4c0','#f6ba42'],char_spacing=.15)
    scene=PageScene(index=0,width=200,height=100,original='none',status='ready',layers=[layer])
    out=export_pptx(p,[scene],tmp_path/'label.pptx')
    deck=Presentation(out);shape=deck.slides[0].shapes[0]
    assert shape.has_text_frame and shape.text=='小标签 2026'
    shape.text_frame.paragraphs[0].runs[0].font.name='Arial'
    shape.text_frame.paragraphs[0].runs[0].font.size=__import__('pptx').util.Pt(8)
    assert shape.text_frame.paragraphs[0].runs[0].font.name=='Arial'
    with zipfile.ZipFile(out) as z:
        xml=z.read('ppt/slides/slide1.xml').decode()
        assert 'gradFill' in xml and 'spc="15"' in xml and '<p:pic>' not in xml
        assert xml.index('<a:gradFill')<xml.index('<a:latin')<xml.index('<a:ea')

def test_invalid_gradient_rejected():
    with pytest.raises(ValueError):LayerElement(kind='text',name='x',x=0,y=0,width=10,height=10,text_gradient=['not-a-color','#123456'])


def test_recognized_bold_font_preserves_style(monkeypatch):
    from backend import text_recovery
    from PIL import ImageFont,ImageDraw
    fontfile=Path('C:/Windows/Fonts/arialbd.ttf')
    if not fontfile.exists():pytest.skip('Windows font fixture unavailable')
    font=ImageFont.truetype(str(fontfile),100);bbox=font.getbbox('LABEL')
    glyph=Image.new('L',(bbox[2]+8,bbox[3]+8));ImageDraw.Draw(glyph).text((4,4),'LABEL',fill=255,font=font)
    glyph=glyph.crop(glyph.getbbox())
    monkeypatch.setattr(text_recovery,'candidates',lambda:[(str(fontfile),0,'Arial')])
    fitted=text_recovery.fit_font('LABEL',np.array(glyph))
    assert fitted['score']>.98 and fitted['bold'] and fitted['synthetic_stroke']==0


def test_manual_tiny_text_repair_removes_original_and_exports_editable(tmp_path):
    from backend.raster import repair_text
    from backend.models import TextRepairRequest
    from pptx import Presentation
    p=store.create('tiny-manual');image=np.zeros((40,160,4),np.uint8);image[12:22,15:90]=255
    layer=LayerElement(kind='image',name='tiny label',x=20,y=30,width=80,height=20,z=2,asset=save_image(p,image))
    request=TextRepairRequest(box=[10,6,100,30],text='小标签',font_size=6,color='#ffffff')
    base,text=repair_text(p,layer,request)
    assert not read_image(p,base.asset)[6:30,10:100,3].any()
    assert read_image(p,layer.asset)[12:22,15:90,3].min()==255
    assert text.kind=='text' and text.font_size==6 and (text.x,text.y)==(25,33)
    assert base.restoration_asset==layer.asset and not base.inferred
    scene=PageScene(index=0,width=200,height=100,original='none',layers=[base,text],status='needs_review')
    deck=Presentation(export_pptx(p,[scene],tmp_path/'repaired.pptx'))
    assert deck.slides[0].shapes[1].text=='小标签'
    with pytest.raises(ValueError):repair_text(p,layer,TextRepairRequest(box=[-1,0,100,30],text='x'))
    with pytest.raises(ValueError):TextRepairRequest(box=[0,0,10,10],text='  ')


def test_manual_text_background_fill_is_marked_inferred():
    from backend.raster import repair_text
    from backend.models import TextRepairRequest
    p=store.create('opaque-label');image=np.full((60,160,4),255,np.uint8);image[20:30,30:100,:3]=0
    layer=LayerElement(kind='image',name='label',x=0,y=0,width=160,height=60,asset=save_image(p,image))
    base,text=repair_text(p,layer,TextRepairRequest(box=[20,15,110,35],text='label',font_size=6))
    assert base.inferred and base.needs_review and read_image(p,base.asset)[23:27,40:90,:3].min()>240
    with pytest.raises(ValueError):repair_text(p,layer,TextRepairRequest(box=[0,0,160,60],text='x'))


def test_low_confidence_small_text_keeps_original(monkeypatch):
    from backend.raster import auto_image
    monkeypatch.setattr(local_models,'status',lambda:{'sam':False,'ocr':True})
    monkeypatch.setattr(local_models,'ocr',lambda im:[('wrong',.6,np.array([[5,5],[90,5],[90,30],[5,30]],dtype=np.int32))])
    p=store.create('uncertain-text');image=np.full((40,100,4),255,np.uint8);image[10:20,20:80,:3]=0
    layer=LayerElement(kind='image',name='tiny',x=0,y=0,width=50,height=20,asset=save_image(p,image))
    pieces,warnings=auto_image(p,layer,segment=False)
    assert len(pieces)==1 and np.array_equal(read_image(p,pieces[0].asset),image) and warnings
