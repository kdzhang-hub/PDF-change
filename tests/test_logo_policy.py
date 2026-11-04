import cv2,numpy as np,pytest
from backend import store,local_models
from backend.models import LayerElement,PageScene
from backend.raster import save_image,read_image,auto_image
from backend.logo_policy import detect_mark,set_image_role


@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init()


def mark(second_ring=True):
    image=np.zeros((144,435,4),np.uint8)
    white=(255,255,255,255)
    cv2.circle(image,(72,72),68,white,3)
    if second_ring:cv2.circle(image,(72,72),58,white,2)
    cv2.putText(image,'U',(40,106),cv2.FONT_HERSHEY_SIMPLEX,2.8,white,7)
    cv2.putText(image,'ACME',(155,64),cv2.FONT_HERSHEY_SIMPLEX,1.6,white,3)
    cv2.putText(image,'LAB',(155,112),cv2.FONT_HERSHEY_SIMPLEX,.8,white,2)
    return image


def fixture():
    project=store.create('brand')
    original=save_image(project,mark())
    cleaned=save_image(project,np.zeros((144,435,4),np.uint8))
    parent=LayerElement(kind='image',name='brand',x=30,y=20,width=145,height=48,
        asset=cleaned,restoration_asset=original,original_type='image',z=3)
    child=LayerElement(kind='text',name='ACME',text='ACME',x=80,y=25,width=80,height=20,
        parent_id=parent.id,source='local-ocr',z=3.5)
    ordinary=LayerElement(kind='text',name='caption',text='A normal label',x=20,y=90,width=160,height=25)
    page=PageScene(index=0,width=300,height=200,original='none',status='needs_review',layers=[parent,child,ordinary])
    return project,page,parent,child,ordinary


def test_seal_wordmark_detects_without_transcribing_or_guessing_names():
    assert detect_mark(mark())['kind']=='seal-wordmark'
    assert detect_mark(mark(False)) is None  # A single circular chart boundary is insufficient.
    labels=np.zeros((144,435,4),np.uint8)
    cv2.putText(labels,'NORMAL LABEL',(20,60),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255,255),2)
    cv2.putText(labels,'42 PERCENT',(20,110),cv2.FONT_HERSHEY_SIMPLEX,1,(255,255,255,255),2)
    assert detect_mark(labels) is None
    opaque=mark();opaque[:,:,3]=255
    assert detect_mark(opaque) is None
    whole=np.zeros((540,960,4),np.uint8);whole[:144,:435]=mark()
    assert detect_mark(whole) is None


def test_mark_stays_original_image_without_ocr_or_segmentation(monkeypatch):
    project=store.create('mark');image=mark()
    layer=LayerElement(kind='image',name='brand',x=0,y=0,width=145,height=48,asset=save_image(project,image))
    original=layer.asset
    monkeypatch.setattr(local_models,'status',lambda:pytest.fail('A preserved mark must not initialize models'))
    result,notes=auto_image(project,layer)
    assert len(result)==1 and result[0].kind=='image' and result[0].content_role=='logo'
    assert result[0].asset==result[0].restoration_asset==original
    assert np.array_equal(read_image(project,original),image) and notes


def test_explicit_ordinary_content_can_override_detection(monkeypatch):
    project=store.create('override');called=[]
    layer=LayerElement(kind='image',name='content',x=0,y=0,width=145,height=48,
        asset=save_image(project,mark()),content_role='content')
    monkeypatch.setattr(local_models,'status',lambda:{'ocr':True,'sam':False})
    monkeypatch.setattr(local_models,'ocr_passes',lambda image:called.append(True) or [(0,[])])
    result,_=auto_image(project,layer,segment=False)
    assert called and result[0].content_role=='content'


def test_restore_brand_removes_only_its_automatic_text_and_keeps_geometry():
    project,page,parent,child,ordinary=fixture();before=page.model_dump()
    result=set_image_role(project,page,parent.id,'logo')
    restored=result.layers[0]
    assert [l.id for l in result.layers]==[parent.id,ordinary.id]
    assert restored.asset==parent.restoration_asset and restored.content_role=='logo'
    assert all(getattr(restored,k)==getattr(parent,k) for k in ('x','y','width','height','rotation','z','opacity'))
    assert result.layers[1].model_dump()==ordinary.model_dump() and page.model_dump()==before


@pytest.mark.parametrize('update',[{'edited':True},{'locked':True},{'source':'manual-text-repair'}])
def test_user_modified_children_are_never_silently_discarded(update):
    project,page,parent,child,_=fixture();page.layers[1]=child.model_copy(update=update)
    before=page.model_dump()
    with pytest.raises(ValueError,match='人工修改'):set_image_role(project,page,parent.id,'logo')
    assert page.model_dump()==before


def test_mismatched_original_crop_is_not_stretched_or_relocated():
    project,page,parent,_,_=fixture()
    page.layers[0].restoration_asset=save_image(project,np.zeros((20,20,4),np.uint8))
    with pytest.raises(ValueError,match='裁切范围不同'):set_image_role(project,page,parent.id,'logo')


def test_brand_not_silently_transcribed_by_later_recovery(monkeypatch):
    from backend.text_recovery import recover_simple_text
    project=store.create('no-recovery')
    layer=LayerElement(kind='image',name='brand',x=0,y=0,width=145,height=48,asset=save_image(project,mark()),
        content_role='logo',original_type='image')
    page=PageScene(index=0,width=300,height=200,original='none',status='ready',layers=[layer])
    monkeypatch.setattr(local_models,'ocr',lambda *_:pytest.fail('Logo must not be OCRed by recovery'))
    result,diagnostics=recover_simple_text(project,page)
    assert not diagnostics and result.model_dump()==page.model_dump()


def test_role_job_saves_history_and_blocks_later_ocr(monkeypatch):
    from backend import jobs
    project,page,parent,_,_=fixture();store.save_page(project,page)
    class Immediate:
        def submit(self,function,*args):function(*args)
    monkeypatch.setattr(jobs,'POOL',Immediate())
    job=jobs.submit(project,[0],'image-role',{'layer_id':parent.id,'role':'logo'})
    assert store.get_job(job)['status']=='done'
    assert store.get_page(project,0).layers[0].content_role=='logo'
    with store.db() as conn:assert conn.execute('SELECT count(*) FROM history WHERE project=?',(project,)).fetchone()[0]>=1
    monkeypatch.setattr(local_models,'status',lambda:{'ocr':True,'sam':False})
    job=jobs.submit(project,[0],'ocr',{'layer_id':parent.id})
    assert store.get_job(job)['status']=='error' and '整体保留' in store.get_job(job)['message']


def test_audit_exempts_only_text_contained_in_an_explicit_intact_mark():
    from backend.logo_policy import preserved_text_region
    project,page,parent,_,_=fixture()
    restored=set_image_role(project,page,parent.id,'logo').model_dump()
    assert preserved_text_region(restored,[80,30,140,50])
    assert not preserved_text_region(restored,[20,90,180,115])
    assert not preserved_text_region(restored,[20,30,140,50])
    restored['layers'][0]['asset']='cleaned.png'
    assert not preserved_text_region(restored,[80,30,140,50])
