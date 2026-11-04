import io,json
import fitz,pytest
from PIL import Image
from fastapi.testclient import TestClient
from backend import store,local_models
from backend.imports import normalize_input
import numpy as np


def encoded(image,format,**kwargs):
    buffer=io.BytesIO();image.save(buffer,format=format,**kwargs);return buffer.getvalue()


def test_image_upload_retains_original_and_uses_shared_pdf_pipeline(tmp_path,monkeypatch):
    from backend.app import app
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init()
    monkeypatch.setattr(local_models,'status',lambda:{'ocr':False,'sam':False})
    data=encoded(Image.new('RGB',(1600,900),'navy'),'PNG')
    client=TestClient(app)
    response=client.post('/api/projects',files={'file':('photo.png',data,'image/png')})
    assert response.status_code==200
    project=response.json()['id'];root=store.project_dir(project)
    assert (root/'original-input.bin').read_bytes()==data
    assert json.loads((root/'import.json').read_text('utf-8'))['kind']=='image'
    with fitz.open(root/'source.pdf') as pdf:
        assert tuple(pdf[0].rect)==(0,0,960,540)
    from backend.extract import convert_page
    scene=convert_page(project,0,'original-0.png')
    assert any(l.kind=='image' for l in scene.layers) and scene.status=='needs_review'
    assert not store.budget()['calls']


def test_image_orientation_and_tiff_page_order():
    image=Image.new('RGB',(80,40),'red');exif=Image.Exif();exif[274]=6
    data=encoded(image,'JPEG',exif=exif)
    pdf,metadata=normalize_input(data,'oriented.jpg')
    with fitz.open(stream=pdf,filetype='pdf') as document:assert tuple(document[0].rect)==(0,0,40,80)
    second=Image.new('RGB',(40,80),'blue')
    data=encoded(image,'TIFF',save_all=True,append_images=[second])
    pdf,metadata=normalize_input(data,'pages.tif')
    with fitz.open(stream=pdf,filetype='pdf') as document:
        assert len(document)==2 and document[0].rect.width==80 and document[1].rect.width==40
        assert document[0].get_pixmap().pixel(10,10)[0]>200
        assert document[1].get_pixmap().pixel(10,10)[2]>200


def test_invalid_image_and_encrypted_pdf_are_rejected():
    with pytest.raises(ValueError,match='无法读取'):normalize_input(b'not an image','broken.jpg')
    document=fitz.open();document.new_page()
    data=document.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256,user_pw='test',owner_pw='owner');document.close()
    with pytest.raises(ValueError,match='密码'):normalize_input(data,'private.pdf')


def test_binary_white_paint_survives_a_completely_white_pdf_preview(tmp_path,monkeypatch):
    from backend.app import app
    from backend.extract import convert_page
    from backend.raster import read_image
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init()
    monkeypatch.setattr(local_models,'status',lambda:{'ocr':False,'sam':False})
    rgba=np.zeros((60,100,4),np.uint8);rgba[:,:,:3]=[255,0,180]
    rgba[15:35,20:60]=[255,255,255,255]
    data=encoded(Image.fromarray(rgba),'PNG')
    client=TestClient(app);response=client.post('/api/projects',files={'file':('white.png',data,'image/png')})
    assert response.status_code==200
    project=response.json()['id'];folder=store.project_dir(project)
    with fitz.open(folder/'source.pdf') as pdf:assert min(pdf[0].get_pixmap(alpha=False).samples)==255
    preview=Image.open(store.asset_path(project,'original-0.png')).convert('RGBA')
    assert preview.getchannel('A').getextrema()==(0,255)
    scene=convert_page(project,0,'original-0.png')
    assert scene.layers and scene.status=='needs_review'
    composed=Image.new('RGBA',(100,60))
    for layer in sorted(scene.layers,key=lambda l:l.z):
        assert layer.kind=='image' and (layer.width,layer.height)==(100,60)
        composed=Image.alpha_composite(composed,Image.fromarray(read_image(project,layer.asset)))
    result=np.array(composed)
    assert np.array_equal(result[:,:,3],rgba[:,:,3])
    assert np.array_equal(result[:,:,:3][rgba[:,:,3]>0],rgba[:,:,:3][rgba[:,:,3]>0])
    assert (folder/'original-input.bin').read_bytes()==data


def test_original_image_frames_preserve_tiff_order_and_exif_orientation(tmp_path,monkeypatch):
    from backend.app import app
    from backend.imports import imported_image_frame
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init()
    client=TestClient(app)
    a=Image.new('RGB',(80,40),'red');b=Image.new('RGB',(40,80),'blue')
    data=encoded(a,'TIFF',save_all=True,append_images=[b])
    project=client.post('/api/projects',files={'file':('frames.tif',data,'image/tiff')}).json()['id']
    first=imported_image_frame(project,0);second=imported_image_frame(project,1)
    assert first.size==(80,40) and second.size==(40,80)
    assert first.getpixel((10,10))==(255,0,0,255) and second.getpixel((10,10))==(0,0,255,255)
    exif=Image.Exif();exif[274]=6;data=encoded(a,'JPEG',exif=exif)
    project=client.post('/api/projects',files={'file':('rotated.jpg',data,'image/jpeg')}).json()['id']
    assert imported_image_frame(project,0).size==(40,80)


def test_missing_original_image_fails_instead_of_silent_pdf_fallback(tmp_path,monkeypatch):
    from backend.app import app
    from backend.extract import convert_page
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init()
    data=encoded(Image.new('RGBA',(60,40),'white'),'PNG')
    project=TestClient(app).post('/api/projects',files={'file':('image.png',data,'image/png')}).json()['id']
    (store.project_dir(project)/'original-input.bin').unlink()
    with pytest.raises(ValueError,match='原始图片文件缺失'):convert_page(project,0,'original-0.png')


def test_transparent_segmentation_ignores_hidden_rgb_and_clears_the_old_copy(tmp_path,monkeypatch):
    from backend.raster import components,apply_masks,save_image,read_image
    from backend.models import LayerElement
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init();project=store.create('transparent')
    rgba=np.zeros((80,100,4),np.uint8);rgba[:,:,:3]=[255,0,180]
    rgba[18:52,28:62]=[255,255,255,3]  # A faint antialiased edge must move too.
    rgba[20:50,30:60]=[255,255,255,255]
    alternate=rgba.copy();alternate[:,:,:3][alternate[:,:,3]==0]=[0,255,30]
    masks=components(rgba);other=components(alternate)
    assert len(masks)==len(other)==1 and np.array_equal(masks[0],other[0])
    layer=LayerElement(kind='image',name='white',x=0,y=0,width=100,height=80,asset=save_image(project,rgba))
    base,child=apply_masks(project,layer,rgba,masks,fill='local')
    assert not read_image(project,base.asset)[:,:,3].any()
    assert np.array_equal(read_image(project,child.asset)[:,:,3],rgba[:,:,3])
    assert not base.inferred
