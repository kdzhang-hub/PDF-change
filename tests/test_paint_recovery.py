import numpy as np
import pytest
import zipfile
from lxml import etree as E
from backend.paint_recovery import vertical_gradient,linear_gradient


def reconstructed(fit,height):
    colors=np.array([[int(color[i:i+2],16) for i in (1,3,5)] for color in fit.colors])
    return np.array([np.interp(np.linspace(0,1,height),fit.positions,colors[:,c]) for c in range(3)]).T


def test_visible_core_recovers_gradient_despite_coloured_antialias_and_missing_tips():
    height=180;y=np.linspace(0,1,height)
    expected=np.array([255+0*y,190+55*y,5+220*y**1.3]).T
    image=np.zeros((height,60,3),np.uint8);image[:]=[5,45,100]
    ink=np.zeros((height,60),bool);ink[5:-5,18:42]=True
    for row in range(5,height-5):
        image[row,18:42]=expected[row]
        image[row,[18,41]]=[60,90,115]
    fit=vertical_gradient(image,ink)
    assert np.abs(reconstructed(fit,height)-expected).mean()<2
    assert fit.method=='supported-smooth-fit'


def test_hidden_rgb_never_changes_a_transparent_gradient():
    image=np.zeros((90,50,4),np.uint8);image[:,:,:3]=[255,0,240]
    for row in range(90):image[row,20:30]=[255,150+row,10+row*2,255]
    first=vertical_gradient(image);image[:,:20,:3]=[0,255,0]
    assert vertical_gradient(image)==first
    assert np.max(np.abs(reconstructed(first,90)-np.array([[255,150+y,10+y*2] for y in range(90)])))<=1


def test_directional_fit_ignores_invisible_rgb_even_when_mask_includes_it():
    height,width=100,220;yy,xx=np.indices((height,width));p=(xx+yy)/318
    image=np.zeros((height,width,4),np.uint8);image[:,:,:3]=[30,80,90]
    image[10:90,20:200,:3]=np.stack([220+25*p,100+120*p,15+200*p],axis=2)[10:90,20:200]
    image[10:90,20:200,3]=255
    first=linear_gradient(image,np.ones((height,width),bool))
    image[image[:,:,3]==0,:3]=[255,40,80]
    assert linear_gradient(image,np.ones((height,width),bool))==first
    assert abs(first.angle-45)<=.5


def test_thin_text_and_single_row_remain_supported():
    image=np.zeros((40,20,4),np.uint8)
    for row in range(40):image[row,10]=[255,150+row,30,255]
    fit=vertical_gradient(image,image[:,:,3]>0)
    assert fit.core_pixels==40 and fit.supported_rows==40
    single=vertical_gradient(image[20:21])
    assert len(set(single.colors))==1 and single.colors[0]=='#ffaa1e'


def test_sharp_gradient_keeps_observed_profile_instead_of_smoothing():
    image=np.full((100,40,4),255,np.uint8);image[:50,:,:3]=[255,0,0];image[50:,:,:3]=[0,0,255]
    fit=vertical_gradient(image)
    assert fit.method=='observed-rows' and fit.colors[0]=='#ff0000' and fit.colors[-1]=='#0000ff'
    # The export model's eight stops cannot represent the abrupt transition
    # exactly. Surface this uncertainty rather than reporting a perfect fit.
    assert fit.mean_error>2


@pytest.mark.parametrize('image,mask',[(np.zeros((4,4)),None),(np.zeros((4,4,4)),None),(np.zeros((4,4,3)),np.ones((3,4)))])
def test_invalid_or_invisible_samples_are_rejected(image,mask):
    with pytest.raises(ValueError):vertical_gradient(image,mask)


@pytest.mark.parametrize('angle',[0,35,97,145])
def test_direction_is_recovered_from_one_word_mask_with_a_local_light_effect(angle):
    height,width=100,220;yy,xx=np.indices((height,width));dx,dy=np.cos(np.radians(angle)),np.sin(np.radians(angle))
    p=(xx*dx+yy*dy-min(0,(width-1)*dx)-min(0,(height-1)*dy))/(abs((width-1)*dx)+abs((height-1)*dy))
    rgb=np.stack([220+25*p,100+120*p,15+200*p],axis=2)
    mask=np.zeros((height,width),bool);mask[5:95,20:55]=True;mask[25:95,100:135]=True;mask[25:45,100:205]=True
    image=np.zeros((height,width,3),np.uint8);image[mask]=rgb[mask]
    # A compact glare patch must not determine the complete word's direction.
    image[30:35,105:115]=255
    fit=linear_gradient(image,mask)
    assert min(abs(fit.angle-angle),abs(fit.angle-angle-180),abs(fit.angle-angle+180))<=1
    colors=np.array([[int(c[i:i+2],16) for i in (1,3,5)] for c in fit.colors])
    fx,fy=np.cos(np.radians(fit.angle)),np.sin(np.radians(fit.angle))
    actual=(xx*fx+yy*fy-min(0,(width-1)*fx)-min(0,(height-1)*fy))/(abs((width-1)*fx)+abs((height-1)*fy))
    recovered=np.stack([np.interp(actual,fit.positions,colors[:,c]) for c in range(3)],axis=2)
    assert np.abs(recovered[mask]-rgb[mask]).mean()<2


@pytest.mark.parametrize('angle',[0,35,95.5,180,270,360])
def test_same_scene_angle_drives_both_native_exports(tmp_path,monkeypatch,angle):
    from backend import store
    from backend.models import LayerElement,PageScene
    from backend.export import export_pptx
    from backend.export_docx import export_docx
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init();project=store.create('angled-fill')
    layer=LayerElement(kind='text',name='whole word',text='ART',x=20,y=20,width=220,height=80,font_size=60,
        text_fit='shape',text_gradient=['#ffcc00','#fff8dc'],text_gradient_positions=[.1,.9],text_gradient_angle=angle)
    page=PageScene(index=0,width=300,height=160,original='unused.png',status='needs_review',layers=[layer]);before=page.model_dump()
    for suffix,exporter,part in [('pptx',export_pptx,'ppt/slides/slide1.xml'),('docx',export_docx,'word/document.xml')]:
        path=tmp_path/('converted.'+suffix);exporter(project,[page],path)
        with zipfile.ZipFile(path) as archive:
            xml=E.fromstring(archive.read(part));lines=xml.xpath('//*[local-name()="lin"]')
            assert len(lines)==1
            attributes={E.QName(k).localname:v for k,v in lines[0].attrib.items()}
            assert attributes=={'ang':str(round((angle%360)*60000)),'scaled':'0'}
            assert xml.xpath('//*[local-name()="t"]/text()')==['ART']
    assert page.model_dump()==before


def test_old_scene_defaults_to_vertical_and_invalid_angles_are_rejected():
    from backend.models import LayerElement
    values=dict(kind='text',name='word',x=0,y=0,width=20,height=20)
    assert LayerElement(**values).text_gradient_angle==90
    for angle in (-.1,360.1,float('nan'),float('inf')):
        with pytest.raises(ValueError):LayerElement(**values,text_gradient_angle=angle)


@pytest.mark.parametrize('complex_fill',[False,True])
def test_local_text_recovery_uses_supported_direction_and_keeps_uncertain_fill(tmp_path,monkeypatch,complex_fill):
    from types import SimpleNamespace
    import hashlib
    from PIL import Image
    from backend import store,text_recovery,local_models
    from backend.models import LayerElement,PageScene
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init();project=store.create('gradient-input')
    height,width=100,220;yy,xx=np.indices((height,width));angle=35
    dx,dy=np.cos(np.radians(angle)),np.sin(np.radians(angle));p=(xx*dx+yy*dy)/((width-1)*dx+(height-1)*dy)
    rgb=np.stack([220+25*p,100+120*p,15+200*p],axis=2).astype(np.uint8)
    mask=np.zeros((height,width),bool);mask[5:95,20:55]=True;mask[25:95,100:135]=True;mask[25:45,100:205]=True
    if complex_fill:rgb=np.where(((xx//8+yy//8)%2)[:,:,None],[255,0,0],[0,0,255]).astype(np.uint8)
    image=np.zeros((height,width,4),np.uint8);image[:,:,:3]=rgb;image[:,:,3]=mask*255
    path=store.asset_path(project,'original.png');Image.fromarray(image).save(path);digest=hashlib.sha256(path.read_bytes()).hexdigest()
    layer=LayerElement(kind='image',name='one full word',x=0,y=0,width=220,height=100,asset='original.png',original_type='shading')
    page=PageScene(index=0,width=300,height=160,original='original.png',status='needs_review',layers=[layer])
    monkeypatch.setattr(local_models,'ocr',lambda image:[('AB',.999,np.array([[20,12],[230,12],[230,110],[20,110]]))])
    fit={'score':.99,'font':'Arial','pixel_size':75,'baseline':80,'file':'unused.ttf'}
    monkeypatch.setattr(text_recovery,'fit_font',lambda *a,**kw:fit)
    monkeypatch.setattr(text_recovery,'fit_with_punctuation',lambda text,alpha,result:(text,result))
    monkeypatch.setattr(text_recovery.fitz,'Font',lambda **kwargs:SimpleNamespace(ascender=1))
    restored,diagnostics=text_recovery.recover_simple_text(project,page)
    assert len(restored.layers)==1 and restored.layers[0].kind=='text' and restored.layers[0].text=='AB'
    word=restored.layers[0]
    if complex_fill:
        assert word.text_gradient_angle==90 and len(word.text_gradient)==4
        assert any('颜色分布较复杂' in note for note in word.notes)
    else:
        assert abs(word.text_gradient_angle-angle)<=1 and len(word.text_gradient)==8
    assert word.needs_review and hashlib.sha256(path.read_bytes()).hexdigest()==digest
