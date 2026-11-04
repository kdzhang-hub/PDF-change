import numpy as np
import pytest
from PIL import Image,ImageFont,ImageDraw
from pathlib import Path
from backend import local_models,store,raster
from backend.models import LayerElement


def test_orientation_passes_own_each_region_once(monkeypatch):
    image=np.zeros((100,200,4),np.uint8)
    horizontal=('label',.99,np.array([[10,10],[70,10],[70,25],[10,25]]))
    wrong=('bad',.6,np.array([[150,20],[165,20],[165,80],[150,80]]))
    clockwise=('ROTATE',.99,np.array([[20,150],[80,150],[80,165],[20,165]]))
    counter=('ETATOR',.92,np.array([[20,35],[80,35],[80,50],[20,50]]))
    responses=iter([[horizontal,wrong],[counter],[clockwise]])
    monkeypatch.setattr(local_models,'ocr',lambda _:next(responses))
    passes=local_models.ocr_passes(image)
    assert [(k,[r[0] for r in rows]) for k,rows in passes]==[(0,['label']),(3,['ROTATE'])]
    assert np.array_equal(local_models.quarter_turn_points(clockwise[2],3,200,100),wrong[2][[3,0,1,2]])


def test_rotated_text_geometry_respects_parent_transform():
    parent=LayerElement(kind='image',name='source',x=10,y=20,width=400,height=100,rotation=0)
    text=LayerElement(kind='text',name='vertical',x=20,y=30,width=60,height=15,font_size=10,source_ink_bbox=[20,30,80,45])
    result=raster.map_ocr_layer(text,3,parent,200,100)
    assert (result.x,result.y,result.rotation)==pytest.approx((70,100,-90))
    assert (result.width,result.height,result.font_size)==pytest.approx((60,30,20))
    assert result.source_ink_bbox==pytest.approx([70,40,100,100])


def test_rotated_ocr_removes_old_glyph_and_preserves_other_pixels(tmp_path,monkeypatch):
    fontpath=Path('C:/Windows/Fonts/arial.ttf')
    if not fontpath.exists():pytest.skip('Windows font fixture')
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init()
    upright=Image.new('RGBA',(240,80),'white')
    ImageDraw.Draw(upright).text((30,15),'ROTATE',font=ImageFont.truetype(str(fontpath),30),fill='black')
    original=np.rot90(np.array(upright),1).copy()
    project=store.create('rotation');asset=raster.save_image(project,original)
    layer=LayerElement(kind='image',name='rotated',x=0,y=0,width=80,height=240,asset=asset)
    poly=np.array([[25,17],[155,17],[155,46],[25,46]])
    monkeypatch.setattr(local_models,'status',lambda:{'ocr':True,'sam':False})
    monkeypatch.setattr(local_models,'ocr_passes',lambda _:[(3,[('ROTATE',.99,poly)])])
    output,warnings=raster.auto_image(project,layer,segment=False)
    assert not warnings and len(output)==2
    assert output[1].text=='ROTATE' and output[1].rotation==pytest.approx(-90)
    cleaned=raster.read_image(project,output[0].asset)
    assert np.array_equal(cleaned, np.full_like(original,255))
    assert np.array_equal(raster.read_image(project,output[0].restoration_asset),original)
