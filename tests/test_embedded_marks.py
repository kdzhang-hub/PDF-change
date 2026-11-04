from pathlib import Path
import cv2,numpy as np,pytest
from backend import store,local_models
from backend.models import LayerElement
from backend.raster import save_image,read_image,auto_image
from backend.embedded_marks import locate,extract


@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init()


def raster_page(rings=2,texture=False):
    image=np.zeros((640,1000,4),np.uint8);image[:]=[10,45,90,255]
    if texture:
        rng=np.random.default_rng(42);image[:,:,:3]=rng.integers(0,100,(640,1000,3),dtype=np.uint8)
    white=(255,255,255,255)
    cv2.circle(image,(582,122),68,white,3)
    if rings==2:cv2.circle(image,(582,122),58,white,2)
    cv2.putText(image,'U',(550,156),cv2.FONT_HERSHEY_SIMPLEX,2.8,white,7)
    cv2.putText(image,'ACME',(665,114),cv2.FONT_HERSHEY_SIMPLEX,1.6,white,3)
    cv2.putText(image,'LAB',(665,162),cv2.FONT_HERSHEY_SIMPLEX,.8,white,2)
    cv2.putText(image,'NORMAL LABEL',(45,410),cv2.FONT_HERSHEY_SIMPLEX,1.2,white,2)
    return image


def parent(project,image,**updates):
    return LayerElement(kind='image',name='page',x=10,y=20,width=500,height=320,
        asset=save_image(project,image),original_type='image',**updates)


def test_crop_preserves_pixels_and_exact_recomposition_and_removes_old_copy():
    project=store.create('embedded');image=raster_page();layer=parent(project,image);original=layer.asset
    work,marks,diagnostics=extract(project,layer,image)
    assert len(marks)==1 and layer.inferred and layer.restoration_asset==original
    mark=marks[0];assert mark.content_role=='logo' and mark.asset==mark.restoration_asset
    left,top,right,bottom=diagnostics[0]['bounds'];crop=read_image(project,mark.asset)
    assert np.array_equal(crop,image[top:bottom,left:right])
    reconstructed=work.copy();reconstructed[top:bottom,left:right]=crop
    assert np.array_equal(reconstructed,image)
    assert np.max(np.abs(work[top:bottom,left:right,:3].astype(int)-[10,45,90]))<=1
    assert np.array_equal(work[350:450],image[350:450])
    assert mark.x==pytest.approx(10+left*.5) and mark.y==pytest.approx(20+top*.5)
    assert mark.width==pytest.approx((right-left)*.5)


def test_single_circle_chart_and_busy_background_do_not_get_logo_exemptions():
    assert locate(raster_page(rings=1))==[]
    assert locate(raster_page(texture=True))==[]
    blank=np.full((640,1000,4),255,np.uint8)
    cv2.putText(blank,'Just a label',(30,200),cv2.FONT_HERSHEY_SIMPLEX,1,(0,0,0,255),2)
    assert locate(blank)==[]


@pytest.mark.parametrize('scale',[1,2,3])
def test_detection_scale_does_not_change_mark_or_chart_policy(scale):
    def resize(image):return cv2.resize(image,None,fx=scale,fy=scale,interpolation=cv2.INTER_CUBIC)
    assert len(locate(resize(raster_page())))==1
    assert locate(resize(raster_page(rings=1)))==[]


@pytest.mark.parametrize('updates',[{'edited':True},{'locked':True},{'rotation':15},{'opacity':.6},{'content_role':'content'}])
def test_existing_user_choices_and_group_opacity_are_preserved(updates):
    project=store.create('protected');image=raster_page();layer=parent(project,image,**updates)
    before=layer.model_dump();work,marks,diagnostics=extract(project,layer,image)
    assert np.array_equal(work,image) and not marks and not diagnostics and layer.model_dump()==before


def test_ordinary_ocr_sees_cleaned_page_not_logo_letters(monkeypatch):
    project=store.create('ocr-input');image=raster_page();layer=parent(project,image)
    seen=[]
    monkeypatch.setattr(local_models,'status',lambda:{'ocr':True,'sam':False})
    def passes(pixels):
        seen.append(pixels.copy());return [(0,[])]
    monkeypatch.setattr(local_models,'ocr_passes',passes)
    result,notes=auto_image(project,layer,segment=False)
    assert len(seen)==1
    marks=[l for l in result if l.content_role=='logo'];assert len(marks)==1
    assert seen[0][65:180,530:940,:3].max()<145
    assert np.array_equal(seen[0][350:450],image[350:450])
    assert notes and result[0].inferred


def test_ordinary_caption_still_becomes_native_text_after_mark_extraction(monkeypatch):
    from PIL import Image,ImageDraw,ImageFont
    from backend import text_recovery
    font_path=Path('C:/Windows/Fonts/arial.ttf')
    if not font_path.exists():pytest.skip('Installed Windows font fixture unavailable')
    image=raster_page();image[350:450,:,:3]=[10,45,90]
    canvas=Image.fromarray(image);font=ImageFont.truetype(str(font_path),36)
    ImageDraw.Draw(canvas).text((45,355),'EDIT ME',font=font,fill=(255,255,255,255))
    image=np.array(canvas);bbox=font.getbbox('EDIT ME');x0,y0,x1,y1=[bbox[0]+43,bbox[1]+353,bbox[2]+47,bbox[3]+357]
    poly=np.array([[x0,y0],[x1,y0],[x1,y1],[x0,y1]],dtype=np.int32)
    monkeypatch.setattr(local_models,'status',lambda:{'ocr':True,'sam':False})
    monkeypatch.setattr(local_models,'ocr_passes',lambda pixels:[(0,[('EDIT ME',.99,poly)])])
    monkeypatch.setattr(text_recovery,'candidates',lambda:[(str(font_path),0,'Arial')])
    project=store.create('caption');layer=parent(project,image)
    result,_=auto_image(project,layer,segment=False)
    assert any(l.kind=='text' and l.text=='EDIT ME' for l in result)
    assert sum(l.content_role=='logo' for l in result)==1
