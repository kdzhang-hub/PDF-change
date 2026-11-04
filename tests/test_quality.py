import subprocess
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest
from PIL import Image,ImageDraw,ImageFont
from backend import store,font_calibration,jobs,text_recovery,local_models
from backend.models import PageScene,LayerElement


@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init()
    monkeypatch.setattr(local_models,'status',lambda:{'ocr':False,'sam':False})


def sample_text(**kwargs):
    values=dict(kind='text',name='auto',text='TEST',x=10,y=20,width=90,height=30,font_size=20,source_ink_bbox=[100,200,160,220])
    values.update(kwargs);return LayerElement(**values)


def test_clipped_image_page_runs_local_restoration(monkeypatch):
    import io,fitz
    from backend import extract,pdfium_extract
    from backend.raster import save_image
    project=store.create('clipped-scan')
    buffer=io.BytesIO();Image.new('RGB',(160,100),'navy').save(buffer,format='PNG')
    source=fitz.open();p=source.new_page(width=160,height=100);p.insert_image(p.rect,stream=buffer.getvalue())
    pdf=fitz.open();page=pdf.new_page(width=200,height=140);page.show_pdf_page(fitz.Rect(20,20,180,120),source,0)
    pdf.save(store.project_dir(project)/'source.pdf');pdf.close();source.close()
    image=LayerElement(kind='image',name='clipped',x=20,y=20,width=160,height=100,
        asset=save_image(project,np.full((100,160,4),255,np.uint8)),original_type='form')
    monkeypatch.setattr(pdfium_extract,'convert_paint',lambda *a:PageScene(index=0,width=200,height=140,original='x',layers=[image]))
    calls=[]
    def restore(project_id,layer):
        calls.append((project_id,layer.x,layer.y,layer.width,layer.height))
        return [layer,sample_text(text='SCAN')],['local restoration needs review']
    monkeypatch.setattr(extract,'auto_image',restore)
    result=extract.convert_page(project,0,'x')
    assert calls==[(project,20,20,160,100)]
    assert any(l.kind=='text' and l.text=='SCAN' for l in result.layers)
    assert result.status=='needs_review' and not store.budget()['calls']


def test_zero_contribution_text_does_not_create_black_duplicate():
    import fitz
    from backend.pdfium_extract import convert_paint
    project=store.create('invisible-text');doc=fitz.open();page=doc.new_page(width=200,height=100)
    page.insert_text((20,40),'Hidden white',color=(1,1,1),fontsize=20)
    doc.save(store.project_dir(project)/'source.pdf');doc.close()
    result=convert_paint(project,0,'x')
    assert not result.layers


def test_mixed_complex_pdf_runs_ocr_inside_native_images(monkeypatch):
    import io,fitz
    from backend import extract,pdfium_extract,text_groups,text_shadows
    from backend.raster import save_image
    project=store.create('mixed-pdf');buffer=io.BytesIO();Image.new('RGB',(160,100),'navy').save(buffer,format='PNG')
    inner=fitz.open();p=inner.new_page(width=160,height=100);p.insert_image(p.rect,stream=buffer.getvalue());p.insert_text((10,30),'Native')
    pdf=fitz.open();page=pdf.new_page(width=200,height=140);page.show_pdf_page(fitz.Rect(20,20,180,120),inner,0)
    pdf.save(store.project_dir(project)/'source.pdf');pdf.close();inner.close()
    image=LayerElement(kind='image',name='embedded logo',x=20,y=20,width=160,height=100,
        asset=save_image(project,np.full((100,160,4),255,np.uint8)),source='pdf-paint',original_type='image')
    monkeypatch.setattr(pdfium_extract,'convert_paint',lambda *a:PageScene(index=0,width=200,height=140,original='x',layers=[sample_text(),image]))
    monkeypatch.setattr(text_groups,'recover_pdf_text_groups',lambda p,s:(s,[]))
    monkeypatch.setattr(local_models,'status',lambda:{'ocr':True,'sam':False})
    calls=[]
    order=[]
    def shadows(project_id,scene):order.append('shadows');return scene,[]
    monkeypatch.setattr(text_shadows,'restore_text_shadows',shadows)
    def restore(project_id,layer,segment=True):
        order.append('ocr');calls.append((layer.id,segment));return [layer,sample_text(text='LOGO')],[]
    monkeypatch.setattr(extract,'auto_image',restore)
    result=extract.convert_page(project,0,'x')
    assert calls==[(image.id,False)] and any(l.kind=='text' and l.text=='LOGO' for l in result.layers)
    assert order.index('shadows')<order.index('ocr')
    assert not store.budget()['calls']


def test_textured_split_does_not_change_uncovered_edges():
    from backend.raster import save_image,read_image,apply_masks
    project=store.create('segmentation-edge');rng=np.random.default_rng(3)
    image=np.concatenate((rng.integers(0,255,(60,90,3),dtype=np.uint8),np.full((60,90,1),255,np.uint8)),axis=2)
    mask=np.zeros((60,90),bool);mask[20:40,30:55]=True
    layer=LayerElement(kind='image',name='scan',x=0,y=0,width=90,height=60,asset=save_image(project,image))
    base,cut=apply_masks(project,layer,image,[mask])
    background=read_image(project,base.asset);foreground=read_image(project,cut.asset)
    assert np.array_equal(background[~mask],image[~mask])
    assert np.array_equal(np.where(foreground[:,:,3:]>0,foreground,background),image)


def test_sam_uses_fresh_process_and_validates_geometry(monkeypatch):
    import os
    if os.name!='nt':pytest.skip('Windows DLL isolation')
    calls=[]
    def run(command,**kwargs):
        calls.append(command)
        folder=Path(command[-1]);image=np.load(folder/'image.npy',allow_pickle=False)
        np.savez_compressed(folder/'masks.npz',mask_0=np.ones(image.shape[:2],bool))
        return SimpleNamespace(returncode=0,stderr='')
    monkeypatch.setattr(local_models.subprocess,'run',run)
    masks=local_models.sam_mask(np.full((20,30,4),255,np.uint8),automatic=True)
    assert calls[0][1:3]==['-m','backend.sam_worker'] and masks[0].shape==(20,30)


def test_models_ignore_invisible_rgb_and_preserve_cutout_alpha(monkeypatch):
    import os
    image=np.zeros((20,30,4),np.uint8);image[4:12,8:19,:3]=[30,60,90];image[4:12,8:19,3]=255
    before=image.copy();seen=[]
    def run(command,**kwargs):
        folder=Path(command[-1]);seen.append(np.load(folder/'image.npy',allow_pickle=False))
        np.savez_compressed(folder/'masks.npz',mask_0=np.ones(image.shape[:2],bool))
        return SimpleNamespace(returncode=0,stderr='')
    monkeypatch.setattr(local_models.subprocess,'run',run)
    def infer(rgb,*args):seen.append(rgb);return [np.ones(image.shape[:2],bool)]
    monkeypatch.setattr(local_models,'_sam_mask_inprocess',infer)
    masks=local_models.sam_mask(image,automatic=True)
    assert np.array_equal(masks[0],image[:,:,3]>0) and np.array_equal(image,before)
    assert np.all(seen[0][image[:,:,3]==0]==255)
    assert np.array_equal(seen[0][4,8],[30,60,90])
    assert local_models.sam_mask(np.zeros_like(image))==[]
    assert local_models.ocr(np.zeros_like(image))==[]


def test_ocr_preserves_contrast_for_white_transparent_logo(monkeypatch):
    seen=[]
    engine=SimpleNamespace(predict=lambda rgb:seen.append(rgb.copy()) or [])
    monkeypatch.setattr(local_models,'_OCR_ENGINE',engine)
    monkeypatch.setattr(local_models,'status',lambda:{'ocr':True,'sam':False})
    image=np.zeros((40,100,4),np.uint8);image[10:30,20:80]=255
    assert local_models.ocr(image)==[]
    assert np.all(seen[0][15,30]==255) and seen[0][0,0].max()<60
    # The OCR adapter reverses RGB to BGR, but hidden colours remain excluded.
    hidden=image.copy();hidden[:,:,:3][hidden[:,:,3]==0]=[255,0,0]
    local_models.ocr(hidden);assert np.array_equal(seen[0],seen[1])


def test_ocr_white_cores_are_not_hidden_by_saturated_outline_average(monkeypatch):
    seen=[]
    monkeypatch.setattr(local_models,'_OCR_ENGINE',SimpleNamespace(predict=lambda rgb:seen.append(rgb.copy()) or []))
    monkeypatch.setattr(local_models,'status',lambda:{'ocr':True,'sam':False})
    image=np.zeros((60,120,4),np.uint8)
    image[10:50,20:100]=[10,65,125,255]
    image[20:40,35:85]=255
    assert image[:,:,:3][image[:,:,3]>160].mean()<160
    local_models.ocr(image)
    assert seen[0][0,0].max()<60 and np.all(seen[0][25,40]==255)
    dark=image.copy();dark[dark[:,:,3]>0,:3]=[10,20,30]
    local_models.ocr(dark)
    assert np.all(seen[1][0,0]==255)


def test_transparent_text_removal_clears_connected_glow_but_keeps_nearby_icon():
    from backend.raster import transparent_text_removal
    import cv2
    ink=np.zeros((50,100),np.uint8);ink[15:35,30:34]=1;ink[15:19,30:50]=1
    glow=cv2.dilate(ink,np.ones((5,5),np.uint8))>0
    alpha=np.where(glow,255,0).astype(np.uint8)
    # This tiny independent decoration is close to the text's dilation radius.
    alpha[22:24,25:27]=255
    removal=transparent_text_removal(alpha,ink>0)
    assert np.all(removal[glow])
    assert not removal[22:24,25:27].any()
    assert not removal[alpha==0].any()


def test_full_text_effect_cleanup_requires_accepted_region_coverage():
    from backend.raster import complete_transparent_text_removal
    alpha=np.zeros((60,100),np.uint8);alpha[15:40,30:55]=255
    alpha[10:50,5:20]=255
    ink=np.zeros(alpha.shape,bool);ink[20:30,35:45]=True
    allowed=np.zeros(alpha.shape,bool);allowed[12:43,28:58]=True
    removal=complete_transparent_text_removal(alpha,ink,allowed)
    assert removal[15:40,30:55].all() and not removal[:,5:20].any()
    # A connected decoration extending outside accepted text cannot be erased.
    alpha[25,20:31]=255
    assert not complete_transparent_text_removal(alpha,ink,allowed).any()


def test_transparent_text_extraction_preserves_fill_opacity_and_ignores_hidden_rgb():
    from backend.raster import restore_ocr_text
    image=np.zeros((60,140,4),np.uint8)
    image[18:40,25:32]=[255,255,255,128]
    image[18:40,55:62]=[255,255,255,128]
    image[18:25,25:62]=[255,255,255,128]
    changed=image.copy();changed[changed[:,:,3]==0,:3]=[255,0,100]
    parent=LayerElement(kind='image',name='source',x=0,y=0,width=140,height=60,opacity=.8)
    record=[('HI',.99,np.array([[20,14],[70,14],[70,44],[20,44]],np.int32))]
    first,texts,_,_=restore_ocr_text(parent.model_copy(deep=True),image,record)
    second,others,_,_=restore_ocr_text(parent.model_copy(deep=True),changed,record)
    assert len(texts)==len(others)==1
    assert texts[0].color==others[0].color=='#ffffff'
    assert texts[0].opacity==pytest.approx(.8*128/255)
    assert np.array_equal(first[:,:,3],second[:,:,3]) and not first[:,:,3].any()


def test_mixed_black_and_white_transparent_text_uses_both_contrast_views(monkeypatch):
    image=np.zeros((60,180,4),np.uint8);image[15:45,20:70]=255;image[15:45,110:160]=[0,0,0,255]
    seen=[]
    def predict(rgb):
        seen.append(rgb.copy());dark=rgb[0,0].max()<60
        poly=[[20,15],[70,15],[70,45],[20,45]] if dark else [[110,15],[160,15],[160,45],[110,45]]
        return [SimpleNamespace(json={'rec_texts':['white' if dark else 'black'],'rec_scores':[.99],'rec_polys':[poly]})]
    monkeypatch.setattr(local_models,'_OCR_ENGINE',SimpleNamespace(predict=predict))
    monkeypatch.setattr(local_models,'status',lambda:{'ocr':True,'sam':False})
    assert {text for text,_,_ in local_models.ocr(image)}=={'black','white'}
    assert len(seen)==2


def test_per_region_text_analysis_preserves_both_black_and_white_glyphs():
    from backend.raster import restore_ocr_text
    image=np.zeros((70,190,4),np.uint8)
    for x,color in [(20,255),(110,0)]:
        image[20:45,x:x+6]=[color,color,color,255]
        image[20:45,x+25:x+31]=[color,color,color,255]
        image[20:26,x:x+31]=[color,color,color,255]
    records=[('HI',.99,np.array([[x-4,16],[x+35,16],[x+35,49],[x-4,49]],np.int32)) for x in (20,110)]
    layer=LayerElement(kind='image',name='mixed',x=0,y=0,width=190,height=70)
    cleaned,texts,_,_=restore_ocr_text(layer,image,records)
    assert [l.color for l in texts]==['#ffffff','#000000'] and not cleaned[:,:,3].any()


def test_text_foreground_excludes_gradient_background():
    from backend.raster import text_foreground
    image=np.zeros((50,140,3),np.uint8);image[:,:,1]=np.linspace(35,110,140).astype(np.uint8);image[:,:,2]=100
    glyph=np.zeros((50,140),bool);glyph[12:38,35:43]=True;glyph[12:38,65:73]=True;glyph[12:20,35:73]=True
    image[glyph]=255
    ink,color=text_foreground(image,np.array([0,35,100]))
    assert np.array_equal(ink,glyph) and np.array_equal(color,[255,255,255])


def test_ocr_colour_search_rejects_thin_decoration_as_glyph():
    from backend.raster import text_foreground
    background=np.array([5,35,75]);image=np.full((50,140,3),background,dtype=np.uint8)
    image[:4]=[255,40,30]
    glyph=np.zeros((50,140),bool)
    for x in (25,55,85):glyph[12:39,x:x+3]=True
    image[glyph]=255
    ink,color=text_foreground(image,background,min_extent=(.35,.4))
    assert np.array_equal(ink,glyph) and np.array_equal(color,[255,255,255])


def test_subpoint_text_exports_editably_with_explicit_size_note(tmp_path):
    from pptx import Presentation
    from backend.export import export_pptx
    project=store.create('subpoint');text=sample_text(text='TINY',font_size=.5)
    scene=PageScene(index=0,width=300,height=200,original='x',status='ready',layers=[text])
    output=export_pptx(project,[scene],tmp_path/'tiny.pptx');deck=Presentation(output)
    assert deck.slides[0].shapes[0].text=='TINY'
    assert deck.slides[0].shapes[0].text_frame.paragraphs[0].runs[0].font.size.pt==1
    assert '1磅' in deck.slides[0].notes_slide.notes_text_frame.text
    assert text.font_size==.5


def test_raster_text_removal_clears_nearby_dark_shadow_only():
    from backend.raster import text_removal_mask
    background=np.array([15,75,145]);image=np.full((60,160,3),background,dtype=np.uint8)
    ink=np.zeros((60,160),bool);ink[18:40,30:38]=True;ink[18:25,30:95]=True
    shadow=np.zeros_like(ink);shadow[22:44,34:42]=True;shadow[22:29,34:99]=True
    image[shadow]=background//3;image[ink]=255
    image[15:45,135:145]=0
    mask=text_removal_mask(image,ink,background)
    assert mask[shadow].all() and mask[ink].all()
    assert not mask[:,135:].any() and not mask[:8].any()


def test_real_profile_fonts_survive_redirected_local_appdata(tmp_path,monkeypatch):
    from backend import fonts
    profile=tmp_path/'profile';real=profile/'AppData'/'Local'/'Microsoft'/'Windows'/'Fonts';real.mkdir(parents=True)
    redirected=tmp_path/'sandbox';redirected.mkdir()
    monkeypatch.setenv('LOCALAPPDATA',str(redirected))
    monkeypatch.setattr(Path,'home',classmethod(lambda cls:profile))
    assert real in fonts.user_font_dirs()


def test_shadow_fit_requires_same_glyph_and_exports_live_effect(tmp_path):
    import cv2,zipfile
    from backend.text_shadows import fit_shadow
    from backend.export import export_pptx
    glyph=np.zeros((70,150),np.uint8);glyph[20:45,20:28]=255;glyph[20:28,20:90]=255;glyph[38:45,20:90]=255
    shifted=cv2.warpAffine(glyph,np.array([[1,0,3],[0,1,4]],np.float32),(150,70));target=np.round(cv2.GaussianBlur(shifted,(0,0),1.2)*.6).astype(np.uint8)
    fit=fit_shadow(glyph,target,3,18)
    assert fit and fit[1]>.9
    wrong=np.zeros_like(glyph);wrong[10:60,110:125]=255
    assert fit_shadow(glyph,wrong,3,18) is None
    project=store.create('live-shadow');text=sample_text(text_shadow=fit[0]);scene=PageScene(index=0,width=300,height=200,original='x',status='ready',layers=[text])
    out=export_pptx(project,[scene],tmp_path/'shadow.pptx')
    with zipfile.ZipFile(out) as archive:
        xml=archive.read('ppt/slides/slide1.xml').decode()
        assert 'outerShdw' in xml and '<p:pic>' not in xml and 'TEST' in xml


def test_pdf_metadata_can_restore_raster_glyph_without_ocr(monkeypatch):
    import fitz
    from backend.raster import save_image
    project=store.create('metadata-text');doc=fitz.open();p=doc.new_page(width=220,height=140)
    p.insert_text((25,75),'TEST',fontname='helv',fontsize=30,color=(1,1,1))
    doc.save(store.project_dir(project)/'source.pdf')
    pix=p.get_pixmap(matrix=fitz.Matrix(3,3),alpha=True);image=Image.frombytes('RGBA',(pix.width,pix.height),pix.samples);box=image.getbbox();crop=image.crop(box)
    layer=LayerElement(kind='image',name='glyph',x=box[0]/3,y=box[1]/3,width=crop.width/3,height=crop.height/3,asset=save_image(project,np.array(crop)),original_type='path')
    scene=PageScene(index=0,width=220,height=140,original='x',layers=[layer]);doc.close()
    def no_ocr(*a):raise AssertionError('PDF metadata should not need an OCR model')
    monkeypatch.setattr(local_models,'ocr',no_ocr)
    restored,rows=text_recovery.recover_simple_text(project,scene,min_score=.78,allow_ocr=False,allow_pdf_hints=True)
    assert rows and any(l.kind=='text' and l.text=='TEST' and l.source=='pdf-metadata-font-fit' for l in restored.layers)


def test_text_group_removes_effect_copies_but_preserves_plate_and_manual_edits(monkeypatch):
    from backend import text_groups
    from backend.raster import save_image
    import cv2
    path=Path('C:/Windows/Fonts/arial.ttf')
    if not path.exists():pytest.skip('Windows font fixture')
    project=store.create('text-group');font=ImageFont.truetype(str(path),100)
    glyph=Image.new('L',(360,150));ImageDraw.Draw(glyph).text((15,5),'TEST',font=font,fill=255)
    alpha=np.array(glyph);core=np.full((150,360,4),255,np.uint8);core[:,:,3]=alpha
    outline=core.copy();outline[:,:,:3]=[30,210,240]
    outline[:,:,3]=cv2.dilate(alpha,np.ones((3,3),np.uint8))-alpha
    shadow=core.copy();shadow[:,:,:3]=0
    shadow[:,:,3]=cv2.GaussianBlur(cv2.warpAffine(alpha,np.array([[1,0,3],[0,1,3]],np.float32),(360,150)),(0,0),1)
    def layer(image,name):return LayerElement(kind='image',name=name,x=20,y=20,width=120,height=50,asset=save_image(project,image),original_type='path')
    fill=layer(core,'fill');edge=layer(outline,'outline');dark=layer(shadow,'shadow');plate=layer(np.full_like(core,255),'plate')
    old=sample_text(text='TEST',x=20,y=20,width=180,height=60,source_ink_bbox=[25,25,130,65])
    hint={'text':'TEST','box':[15,15,145,75],'faces':[(str(path),0,'Arial')]}
    monkeypatch.setattr(text_groups,'source_text_hints',lambda *a:[hint])
    scene=PageScene(index=0,width=200,height=100,original='x',layers=[fill,edge,dark,plate,old])
    recovered,rows=text_groups.recover_pdf_text_groups(project,scene)
    assert len(rows)==1 and len([l for l in recovered.layers if l.kind=='text'])==1
    assert plate.id in {l.id for l in recovered.layers}
    assert {fill.id,edge.id,dark.id,old.id}.issubset(set(rows[0]['removed_ids']))
    old.edited=True;before=scene.model_dump();untouched,rows=text_groups.recover_pdf_text_groups(project,scene)
    assert not rows and untouched.model_dump()==before


def test_text_outline_gradient_positions_and_shadow_export_in_schema_order(tmp_path):
    import zipfile
    from lxml import etree
    from backend.export import export_pptx
    from backend.models import TextShadow
    text=sample_text(stroke='#20ddff',stroke_width=.5,text_gradient=['#ffffff','#4466ff'],text_gradient_positions=[.2,.7],text_shadow=TextShadow())
    project=store.create('live-effects');page=PageScene(index=0,width=300,height=200,original='x',status='ready',layers=[text])
    out=export_pptx(project,[page],tmp_path/'effects.pptx')
    with zipfile.ZipFile(out) as archive:
        xml=etree.fromstring(archive.read('ppt/slides/slide1.xml'));ns={'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}
        props=xml.find('.//a:rPr',ns);tags=[etree.QName(c).localname for c in props]
        assert tags.index('ln')<tags.index('gradFill')<tags.index('effectLst')<tags.index('latin')
        assert props.xpath('./a:gradFill/a:gsLst/a:gs/@pos',namespaces=ns)==['20000','70000']
    with pytest.raises(ValueError):sample_text(text_gradient=['#ffffff','#4466ff'],text_gradient_positions=[.7,.2])


def test_office_calibration_preserves_user_edits_and_locks(monkeypatch):
    project=store.create('calibration');automatic=sample_text()
    manual=sample_text(id='manual',edited=True);locked=sample_text(id='locked',locked=True)
    multiline=sample_text(id='multiline',text='a\nb');rotated=sample_text(id='rotated',rotation=20)
    scene=PageScene(index=0,width=400,height=300,original='none',layers=[automatic,manual,locked,multiline,rotated])
    monkeypatch.setattr(font_calibration,'attach_source_bounds',lambda *a:None)
    monkeypatch.setattr(font_calibration,'available',lambda:True)
    def render(*a,**k):
        image=Image.new('RGB',(3200,1800),'white');ImageDraw.Draw(image).rectangle((40,50,120,80),fill='black')
        image.save(store.project_dir(project)/'font-calibration'/'probe-1.png')
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(font_calibration.subprocess,'run',render)
    result,measurements=font_calibration.calibrate_page(project,scene)
    assert len(measurements)==1 and (result.layers[0].x,result.layers[0].y)==(95,190)
    assert scene.layers[0].x==10 and not result.layers[0].edited
    for before,after in zip(scene.layers[1:],result.layers[1:]):assert before.model_dump()==after.model_dump()


def test_office_timeout_does_not_partially_move_page(monkeypatch):
    project=store.create('timeout');scene=PageScene(index=0,width=200,height=100,original='none',layers=[sample_text()])
    monkeypatch.setattr(font_calibration,'attach_source_bounds',lambda *a:None)
    monkeypatch.setattr(font_calibration,'available',lambda:True)
    def fail(*a,**k):raise subprocess.TimeoutExpired('test',60)
    monkeypatch.setattr(font_calibration.subprocess,'run',fail)
    before=scene.model_dump()
    with pytest.raises(RuntimeError,match='超时'):font_calibration.calibrate_page(project,scene)
    assert scene.model_dump()==before


def test_web_convert_job_runs_local_calibration(monkeypatch):
    project=store.create('convert');scene=PageScene(index=0,width=200,height=100,original='none')
    store.save_page(project,scene)
    monkeypatch.setattr(jobs,'POOL',SimpleNamespace(submit=lambda f,arg:f(arg)))
    from backend import extract
    monkeypatch.setattr(extract,'convert_page',lambda *a:PageScene(index=0,width=200,height=100,original='none',status='ready',layers=[sample_text()]))
    def calibrate(*args):
        page=args[1].model_copy(deep=True);page.layers[0].x=99
        return page,[{'id':page.layers[0].id}]
    monkeypatch.setattr(font_calibration,'calibrate_page',calibrate)
    job=jobs.submit(project,[0],payload={'calibrate':True})
    assert store.get_job(job)['status']=='done' and store.get_page(project,0).layers[0].x==99


def test_missing_office_keeps_conversion_result(monkeypatch):
    project=store.create('no-office');store.save_page(project,PageScene(index=0,width=200,height=100,original='none'))
    monkeypatch.setattr(jobs,'POOL',SimpleNamespace(submit=lambda f,arg:f(arg)))
    from backend import extract
    monkeypatch.setattr(extract,'convert_page',lambda *a:PageScene(index=0,width=200,height=100,original='none',status='ready',layers=[sample_text()]))
    def unavailable(*a):raise RuntimeError('not installed')
    monkeypatch.setattr(font_calibration,'calibrate_page',unavailable)
    job=jobs.submit(project,[0],payload={'calibrate':True})
    page=store.get_page(project,0)
    assert store.get_job(job)['status']=='done' and page.layers[0].x==10 and page.status=='needs_review'
    assert page.warnings and not store.budget()['calls']


def test_punctuation_requires_matching_source_glyph(monkeypatch):
    path=Path('C:/Windows/Fonts/msyhbd.ttc')
    if not path.exists():pytest.skip('Windows font fixture unavailable')
    monkeypatch.setattr(text_recovery,'candidates',lambda:[(str(path),0,'Microsoft YaHei')])
    text='）的成长之路';font=ImageFont.truetype(str(path),100);box=font.getbbox(text)
    image=Image.new('L',(box[2]+10,box[3]+10));ImageDraw.Draw(image).text((5,5),text,font=font,fill=255)
    alpha=np.array(image.crop(image.getbbox()));raw='的成长之路'
    actual,fit=text_recovery.fit_with_punctuation(raw,alpha,text_recovery.fit_font(raw,alpha))
    assert actual==text and fit['score']>.98
    same,same_fit=text_recovery.fit_with_punctuation(text,alpha,fit)
    assert same==text and same_fit==fit


def test_isolated_export_uses_immutable_snapshot_and_unique_file(monkeypatch):
    from backend import export_service,export_worker
    from pptx import Presentation
    project=store.create('immutable-export')
    page=PageScene(index=0,width=200,height=100,original='none',layers=[sample_text(text='before')],status='ready')
    def run(command,**kwargs):
        assert command[1:3]==['-m','backend.export_worker'] and kwargs['env']['LAYERDECK_DATA']==str(store.DATA)
        page.layers[0].text='changed while exporting'
        export_worker.build(command[3],command[4])
        return SimpleNamespace(returncode=0,stdout='',stderr='')
    monkeypatch.setattr(export_service.subprocess,'run',run)
    first=export_service.create_export(project,[page]);second=export_service.create_export(project,[page])
    assert first!=second and first.is_file() and second.is_file()
    assert Presentation(first).slides[0].shapes[0].text=='before'
    assert Presentation(second).slides[0].shapes[0].text=='changed while exporting'


def test_failed_export_releases_slot_and_keeps_scene(monkeypatch):
    from backend import export_service
    project=store.create('export-failure');page=PageScene(index=0,width=200,height=100,original='none',layers=[sample_text()],status='ready')
    def fail(*a,**k):raise subprocess.TimeoutExpired('test',240)
    monkeypatch.setattr(export_service.subprocess,'run',fail)
    with pytest.raises(ValueError,match='超时'):export_service.create_export(project,[page])
    assert export_service._SLOT.acquire(blocking=False);export_service._SLOT.release()
    assert list(store.project_dir(project).glob('export-*.scene.json'))
    assert not list(store.project_dir(project).glob('export-*.pptx'))


def test_sample_seed_import_has_no_side_effects():
    import importlib.util
    before=store.list_projects()
    spec=importlib.util.spec_from_file_location('seed_import_check',Path(__file__).resolve().parents[1]/'scripts'/'seed_manual_text_test.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    assert store.list_projects()==before and callable(module.main)


def test_default_calibration_keeps_nominal_font_size(monkeypatch):
    project=store.create('height-guard');text=sample_text(source_ink_bbox=[100,200,160,217])
    page=PageScene(index=0,width=200,height=100,original='none',layers=[text])
    monkeypatch.setattr(font_calibration,'attach_source_bounds',lambda *a:None)
    monkeypatch.setattr(font_calibration,'available',lambda:True)
    def render(*a,**k):
        image=Image.new('RGB',(3200,1800),'white');ImageDraw.Draw(image).rectangle((40,50,120,80),fill='black')
        image.save(store.project_dir(project)/'font-calibration'/'probe-1.png');return SimpleNamespace(returncode=0)
    monkeypatch.setattr(font_calibration.subprocess,'run',render)
    result,_=font_calibration.calibrate_page(project,page)
    assert result.layers[0].font_size==20 and text.font_size==20
