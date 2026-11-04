import io,hashlib,zipfile
from pathlib import Path
import numpy as np
import pytest
from PIL import Image
from backend import store
from backend.raster import save_image
from backend.models import LayerElement,PageScene
from backend.image_assets import png_bytes,picture_source
from backend.export import export_pptx
from backend.export_docx import export_docx


def samples():
    rgba=np.random.default_rng(37).integers(0,256,(600,1000,4),dtype=np.uint8);rgba[:,:,3]=0
    rgba[180:250,340:500]=[30,180,240,255]
    rgba[180:250,338:340]=[80,140,220,1]
    rgba[180:250,500:502]=[90,140,220,127]
    return rgba


def test_compaction_preserves_faint_edges_and_composites_and_input():
    original=samples();image=Image.fromarray(original);encoded=png_bytes(image)
    compact=np.array(Image.open(io.BytesIO(encoded)))
    assert np.array_equal(np.array(image),original)
    assert np.array_equal(compact[:,:,3],original[:,:,3])
    assert np.array_equal(compact[original[:,:,3]>0],original[original[:,:,3]>0])
    assert np.all(compact[:100,:,:3]==0)
    assert np.array_equal(compact[179,337],original[179,337])
    for background in ((255,255,255,255),(10,20,45,255),(220,50,100,255)):
        base=Image.new('RGBA',image.size,background)
        assert np.array_equal(np.array(Image.alpha_composite(base,image)),
            np.array(Image.alpha_composite(base,Image.fromarray(compact))))
    raw=io.BytesIO();image.save(raw,format='PNG')
    assert len(encoded)<len(raw.getvalue())*.06


def test_picture_source_keeps_opaque_and_already_compact_bytes(tmp_path):
    for name,rgba in [('opaque',np.full((40,60,4),255,np.uint8)),('transparent',np.zeros((40,60,4),np.uint8))]:
        path=tmp_path/(name+'.png');Image.fromarray(rgba).save(path)
        assert picture_source(path)==str(path)


def test_extreme_downscale_keeps_original_samples_instead_of_unbounded_kernel(tmp_path):
    original=samples();image=Image.fromarray(original)
    encoded=png_bytes(image,(.1,.1))
    assert np.array_equal(np.array(Image.open(io.BytesIO(encoded))),original)
    path=tmp_path/'small-placed.png';image.save(path)
    assert picture_source(path,.1,.1)==str(path)


@pytest.mark.parametrize('format',['pptx','docx'])
def test_both_exports_compact_old_assets_without_changing_original_or_objects(tmp_path,monkeypatch,format):
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init();project=store.create('old-project')
    source=samples();asset=save_image(project,source);path=store.asset_path(project,asset)
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    image=LayerElement(kind='image',name='independent',x=25,y=40,width=300,height=180,rotation=12,asset=asset,opacity=.7)
    text=LayerElement(kind='text',name='editable',text='EDIT ME',x=10,y=10,width=90,height=20,font='Arial')
    page=PageScene(index=0,width=500,height=300,original='original.png',status='needs_review',layers=[image,text])
    before=page.model_dump();output=tmp_path/('compact.'+format)
    (export_pptx if format=='pptx' else export_docx)(project,[page],output)
    assert page.model_dump()==before and hashlib.sha256(path.read_bytes()).hexdigest()==digest
    with zipfile.ZipFile(output) as archive:
        files=[name for name in archive.namelist() if '/media/' in name and name.endswith('.png')]
        assert len(files)==1
        pixels=np.array(Image.open(io.BytesIO(archive.read(files[0]))).convert('RGBA'))
        assert pixels.shape==source.shape
        alpha=source[:,:,3] if format=='pptx' else np.round(source[:,:,3]*.7).astype(np.uint8)
        assert np.array_equal(pixels[:,:,3],alpha)
        assert np.array_equal(pixels[alpha>0,:3],source[alpha>0,:3])
        assert len(archive.read(files[0]))<path.stat().st_size*.06
        xml=archive.read('ppt/slides/slide1.xml' if format=='pptx' else 'word/document.xml').decode()
        assert 'EDIT ME' in xml and image.id in xml
