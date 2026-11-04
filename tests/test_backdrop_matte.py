import hashlib,json,time
import cv2,numpy as np,pytest
from backend import store,raster,jobs
from backend.models import LayerElement,PageScene,SplitRequest,SplitApplyRequest,uid
from backend.backdrop_matte import propose
from backend.split_preview import get_preview,apply_preview


def portrait():
    h,w=180,150;y,x=np.mgrid[:h,:w]
    background=np.stack([np.full((h,w),10),90+y*.2,160+y*.15],-1)
    hard=np.zeros((h,w),np.uint8)
    cv2.ellipse(hard,(75,55),(29,43),0,0,360,255,-1)
    cv2.rectangle(hard,(60,75),(90,125),255,-1)
    cv2.ellipse(hard,(75,179),(74,66),0,0,360,255,-1)
    alpha=cv2.GaussianBlur(hard,(5,5),.7).astype(float)/255
    foreground=np.full((h,w,3),[225,210,195]);foreground[y>120]=[235,239,245]
    rgb=np.uint8(np.round(foreground*alpha[:,:,None]+background*(1-alpha[:,:,None])))
    return np.dstack([rgb,np.full((h,w),255,np.uint8)]),np.uint8(np.round(background)),alpha


@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init()


def prepared():
    image,_,_=portrait();project=store.create('matte-test')
    layer=LayerElement(kind='image',name='photo',x=40,y=30,width=75,height=90,rotation=15,z=8,asset=raster.save_image(project,image))
    page=PageScene(index=0,width=200,height=300,original=layer.asset,status='needs_review',layers=[layer]);store.save_page(project,page)
    return project,page,layer,image


def queued(project,layer):
    job=uid();payload={'layer_id':layer.id,'request':SplitRequest(method='backdrop').model_dump()}
    with store.db() as c:c.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)',(job,project,json.dumps({'pages':[0],'operation':'split-preview','payload':payload}),'queued',0,'',0,time.time()))
    return job


def test_soft_alpha_foreground_and_hidden_background_are_separate_without_source_mutation():
    image,known_background,known_alpha=portrait();before=image.copy()
    cut,base,quality=propose(image)
    assert np.array_equal(image,before) and quality['ssim']>=.98
    assert quality['soft_pixels']>0 and cut.shape==base.shape==image.shape
    assert np.max(np.abs(base[:,:,:3].astype(float)-known_background))<3
    interior=cv2.erode(np.uint8(known_alpha==1),np.ones((7,7),np.uint8),borderType=cv2.BORDER_CONSTANT,borderValue=0)>0
    assert np.all(cut[:,:,3][interior]==255) and np.array_equal(cut[:,:,:3][interior],image[:,:,:3][interior])
    assert np.all(base[:,:,3]==255) and np.all(cut[cut[:,:,3]==0,:3]==0)
    assert np.max(np.abs(cut[:,:,3]/255-known_alpha))<.13


@pytest.mark.parametrize('case',['small','large','transparent','plain','white','two-objects','complex'])
def test_ambiguous_or_unsupported_backdrops_fail_without_mutation(case):
    image,_,_=portrait()
    if case=='small':image=image[:50,:50]
    elif case=='large':image=np.full((1500,1500,4),255,np.uint8)
    elif case=='transparent':image[0,0,3]=0
    elif case=='plain':image[:,:,:3]=[10,100,180]
    elif case=='white':image[:20,:,:3]=255
    elif case=='two-objects':
        image[:,:,:3]=[10,100,180];image[30:75,20:50,:3]=255;image[30:75,100:130,:3]=255
    elif case=='complex':
        image[:,:,:3]=np.random.default_rng(1).integers(0,256,image[:,:,:3].shape,dtype=np.uint8)
    before=image.copy()
    with pytest.raises(ValueError):propose(image)
    assert np.array_equal(before,image)


def test_preview_is_read_only_and_apply_keeps_two_whole_planes_and_geometry():
    project,page,layer,image=prepared();before=store.get_page(project,0).model_dump()
    digest=hashlib.sha256(store.asset_path(project,layer.asset).read_bytes()).hexdigest()
    job=queued(project,layer);jobs.run(job)
    assert store.get_job(job)['status']=='done'
    draft=get_preview(project,job)
    assert draft['mode']=='backdrop-matte' and len(draft['candidates'])==1 and len(draft['comparisons'])==3
    assert store.get_page(project,0).model_dump()==before
    result=apply_preview(project,page,layer.id,SplitApplyRequest(preview_job=job,candidate_ids=[0],name='Whole person'))
    assert len(result.layers)==2 and result.layers[1].name=='Whole person'
    assert result.layers[0].id==layer.id and result.layers[1].parent_id==layer.id
    for item in result.layers:
        assert all(getattr(item,key)==getattr(layer,key) for key in ('x','y','width','height','rotation'))
        assert item.inferred and item.edited and item.needs_review and item.asset!=layer.asset
    assert result.layers[0].source=='local-backdrop-background' and result.layers[1].z>layer.z
    assert np.all(raster.read_image(project,result.layers[0].asset)[:,:,3]==255)
    assert hashlib.sha256(store.asset_path(project,layer.asset).read_bytes()).hexdigest()==digest
    assert page.model_dump()==before


@pytest.mark.parametrize('case',['stale','logo','locked','opacity','transparent-fill'])
def test_confirmation_protects_locked_logo_and_changed_content(case):
    project,page,layer,_=prepared();job=queued(project,layer)
    if case=='logo':layer.content_role='logo';store.save_page(project,page)
    elif case=='locked':layer.locked=True;store.save_page(project,page)
    elif case=='opacity':layer.opacity=.5;store.save_page(project,page)
    elif case=='transparent-fill':
        with store.db() as c:
            spec=json.loads(c.execute('SELECT pages FROM jobs WHERE id=?',(job,)).fetchone()[0]);spec['payload']['request']['fill']='transparent'
            c.execute('UPDATE jobs SET pages=? WHERE id=?',(json.dumps(spec),job))
    before=store.get_page(project,0).model_dump();jobs.run(job)
    if case=='stale':
        page.revision+=1
        with pytest.raises(ValueError):apply_preview(project,page,layer.id,SplitApplyRequest(preview_job=job,candidate_ids=[0]))
    else:assert store.get_job(job)['status']=='error'
    assert store.get_page(project,0).model_dump()==before
