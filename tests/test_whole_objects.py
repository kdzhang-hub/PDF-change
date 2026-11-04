import hashlib,io,json,time
import numpy as np,pytest
from PIL import Image,ImageDraw,ImageFont
from fastapi.testclient import TestClient
from backend import store,local_models,jobs,geometry_recovery,raster
from backend.models import LayerElement,PageScene,SplitRequest,SplitApplyRequest,uid
from backend.split_preview import make_preview,get_preview,apply_preview


@pytest.fixture(autouse=True)
def isolated(tmp_path,monkeypatch):
    monkeypatch.setattr(store,'DATA',tmp_path/'data');store.init()
    monkeypatch.setattr(local_models,'status',lambda:{'ocr':False,'sam':True})
    monkeypatch.setattr(geometry_recovery,'recover_circles',lambda layer,image:(image,[],[]))


def project_image():
    project=store.create('whole-object');image=np.full((100,160,4),255,np.uint8)
    image[20:45,20:45]=[30,110,220,255];image[55:80,20:45]=[30,110,220,255]
    image[20:45,110:135]=[220,50,80,255]
    layer=LayerElement(kind='image',name='source',x=10,y=20,width=160,height=100,asset=raster.save_image(project,image))
    page=PageScene(index=0,width=220,height=160,original=layer.asset,status='needs_review',layers=[layer]);store.save_page(project,page)
    return project,page,layer,image


def preview_job(project,page,layer,monkeypatch):
    masks=[]
    for y,x in ((20,20),(55,20),(20,110)):
        mask=np.zeros((100,160),bool);mask[y:y+25,x:x+25]=True;masks.append(mask)
    monkeypatch.setattr(raster,'split_mask',lambda *a:masks)
    job=uid()
    with store.db() as c:c.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)',(job,project,json.dumps({'pages':[0],'operation':'split-preview','payload':{'layer_id':layer.id,'request':{'method':'auto'}}}),'queued',0,'',0,time.time()))
    return job


def test_default_auto_keeps_unknown_icon_whole_without_applying_sam_fragments(monkeypatch):
    project,page,layer,image=project_image()
    def must_not_run(*a,**k):raise AssertionError('Unreviewed masks must not become layers')
    monkeypatch.setattr(raster,'split_mask',must_not_run)
    before=store.asset_path(project,layer.asset).read_bytes();layers,notes=raster.auto_image(project,layer)
    assert len(layers)==1 and layers[0].id==layer.id and layers[0].needs_review
    assert store.asset_path(project,layer.asset).read_bytes()==before
    assert any('整体' in note for note in layer.notes) and notes


def test_large_artwork_ocr_radicals_stay_in_one_original_asset(monkeypatch):
    project=store.create('artwork');pixels=np.full((400,800,4),255,np.uint8)
    image=Image.fromarray(pixels);font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',120)
    ImageDraw.Draw(image).text((50,80),'AB',font=font,fill=(20,30,80,255));pixels=np.array(image)
    layer=LayerElement(kind='image',name='whole word',x=0,y=0,width=800,height=400,asset=raster.save_image(project,pixels))
    monkeypatch.setattr(local_models,'status',lambda:{'ocr':True,'sam':True})
    records=[('A',.99,np.array([[50,100],[135,100],[135,210],[50,210]],np.int32)),('B',.99,np.array([[140,100],[225,100],[225,210],[140,210]],np.int32))]
    monkeypatch.setattr(local_models,'ocr_passes',lambda *a:[(0,records)])
    layers,notes=raster.auto_image(project,layer)
    assert len(layers)==1 and layers[0].kind=='image'
    assert np.array_equal(raster.read_image(project,layer.asset),pixels)
    assert 'A' in layer.recognized_text and 'B' in layer.recognized_text
    assert any('未拆成单字或偏旁' in n for n in notes)


@pytest.mark.parametrize('symbol',['-','+','→','•'])
def test_symbol_ocr_does_not_cut_a_stroke_out_of_a_complete_icon(symbol):
    project,page,layer,pixels=project_image()
    poly=np.array([[20,20],[44,20],[44,44],[20,44]],np.int32)
    restored,texts,notes,changed=raster.restore_ocr_text(layer,pixels,[(symbol,.999,poly)])
    assert not changed and not texts and np.array_equal(restored,pixels)
    assert any('图标' in note for note in notes)
    assert not layer.recognized_text  # An ambiguous stroke is not a known word.


def test_second_font_matching_pass_cannot_convert_an_icon_stroke(monkeypatch):
    from backend import text_recovery
    project,page,layer,pixels=project_image()
    layer.original_type='image'
    pixels[:]=0;pixels[20:80,20:80]=[30,110,220,255]
    layer.asset=raster.save_image(project,pixels);page.layers=[layer]
    monkeypatch.setattr(local_models,'ocr',lambda _:[('-',.999,np.array([[20,25],[75,25],[75,35],[20,35]],np.int32))])
    def not_a_font_test(*a,**k):raise AssertionError('A matching dash font does not prove icon semantics')
    monkeypatch.setattr(text_recovery,'fit_font',not_a_font_test)
    before=page.model_dump();result,diagnostics=text_recovery.recover_simple_text(project,page)
    assert result.model_dump()==before
    assert len(diagnostics)==1 and not diagnostics[0]['accepted']


@pytest.mark.parametrize('text,role',[('-', 'content'),('9','auto'),('小标签','auto')])
def test_explicit_symbol_text_and_ordinary_labels_still_use_text_recovery(text,role):
    project,page,layer,pixels=project_image();layer.content_role=role
    image=Image.new('RGBA',(180,70),'white')
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',24)
    ImageDraw.Draw(image).text((20,15),text,font=font,fill='black')
    yy,xx=np.where(np.array(image)[:,:,:3].min(axis=2)<100)
    left,right,top,bottom=int(xx.min()),int(xx.max()),int(yy.min()),int(yy.max())
    poly=np.array([[left,top],[right,top],[right,bottom],[left,bottom]],np.int32)
    restored,texts,notes,changed=raster.restore_ocr_text(layer,np.array(image),[(text,.999,poly)])
    assert changed and len(texts)==1 and texts[0].text==text


def test_native_pdf_symbol_is_retained_as_native_text():
    import fitz
    from backend.extract import convert_page
    project=store.create('native-symbol');doc=fitz.open();page=doc.new_page(width=160,height=100)
    page.insert_text((20,40),'-',fontsize=18);doc.save(store.project_dir(project)/'source.pdf');doc.close()
    scene=convert_page(project,0,'source.png')
    assert len(scene.layers)==1 and scene.layers[0].kind=='text' and scene.layers[0].text=='-'


def test_candidate_job_is_readonly_and_apply_combines_parts_into_one_object(monkeypatch):
    project,page,layer,image=project_image();before=store.get_page(project,0).model_dump()
    digest=hashlib.sha256(store.asset_path(project,layer.asset).read_bytes()).hexdigest()
    job=preview_job(project,page,layer,monkeypatch);jobs.run(job)
    assert store.get_job(job)['status']=='done'
    assert store.get_page(project,0).model_dump()==before
    with store.db() as c:assert c.execute('SELECT count(*) FROM history WHERE project=?',(project,)).fetchone()[0]==0
    draft=get_preview(project,job)
    ids=[m['id'] for m in draft['candidates'] if m['box'][0]<100]
    result=apply_preview(project,page,layer.id,SplitApplyRequest(preview_job=job,candidate_ids=ids,name='whole icon'))
    assert len(result.layers)==2 and result.layers[1].name=='whole icon'
    child=raster.read_image(project,result.layers[1].asset);base=raster.read_image(project,result.layers[0].asset)
    assert child[30,30,3]==255 and child[65,30,3]==255 and child[30,120,3]==0
    assert np.all(base[30,30,:3]==255) and np.all(base[65,30,:3]==255)
    assert np.array_equal(base[30,120],image[30,120])
    assert result.layers[1].source=='manual-segmentation'
    assert result.layers[1].restoration_asset==result.layers[1].asset
    assert page.model_dump()==before
    assert hashlib.sha256(store.asset_path(project,layer.asset).read_bytes()).hexdigest()==digest


@pytest.mark.parametrize('case',['stale','other-project','invalid-id','locked'])
def test_preview_does_not_override_changed_or_unrelated_content(monkeypatch,case):
    project,page,layer,_=project_image();job=preview_job(project,page,layer,monkeypatch);jobs.run(job)
    request=SplitApplyRequest(preview_job=job,candidate_ids=[0])
    if case=='stale':page.revision+=1
    if case=='other-project':project=store.create('other')
    if case=='invalid-id':request.candidate_ids=[999]
    if case=='locked':page.layers[0].locked=True
    before=page.model_dump()
    with pytest.raises(ValueError):apply_preview(project,page,layer.id,request)
    assert page.model_dump()==before


def test_split_api_routes_model_masks_to_review_and_keeps_brush_explicit(monkeypatch):
    from backend.app import app
    project,page,layer,_=project_image();calls=[]
    monkeypatch.setattr(jobs,'submit',lambda p,indices,op,payload:(calls.append(op) or '0'*32))
    client=TestClient(app)
    for method in ('auto','box','point'):
        r=client.post(f'/api/projects/{project}/pages/0/layers/{layer.id}/split',json={'method':method})
        assert r.status_code==200 and r.json()['review_required'] and calls[-1]=='split-preview'
    r=client.post(f'/api/projects/{project}/pages/0/layers/{layer.id}/split',json={'method':'brush','points':[[20,30]]})
    assert r.status_code==200 and not r.json()['review_required'] and calls[-1]=='split'


def test_entire_transparent_icon_stays_one_object_without_an_empty_residual(monkeypatch):
    project,page,layer,image=project_image();image[:,:,3]=0
    image[20:45,20:45,3]=255;image[55:80,20:45,3]=255
    layer.asset=raster.save_image(project,image);page.layers=[layer];store.save_page(project,page)
    job=preview_job(project,page,layer,monkeypatch);jobs.run(job);draft=get_preview(project,job)
    result=apply_preview(project,page,layer.id,SplitApplyRequest(preview_job=job,candidate_ids=[c['id'] for c in draft['candidates']]))
    assert len(result.layers)==1 and result.layers[0].kind=='image'
    assert np.array_equal(raster.read_image(project,result.layers[0].asset)[:,:,3],image[:,:,3])


def test_explicit_whole_rectangle_does_not_use_a_model_or_split_letters(monkeypatch):
    monkeypatch.setattr(local_models,'sam_mask',lambda *a,**k:(_ for _ in ()).throw(AssertionError('Rectangle must stay literal')))
    image=np.full((100,160,4),255,np.uint8)
    masks=raster.split_mask(image,SplitRequest(method='rectangle',box=[10,20,120,70]))
    assert len(masks)==1 and np.count_nonzero(masks[0])==110*50
    assert masks[0][20:70,10:120].all()


@pytest.mark.parametrize('outcome',['success','cancel','failure'])
def test_cloud_masks_also_require_whole_object_confirmation(monkeypatch,outcome):
    from backend import cloud
    project,page,layer,image=project_image();layer.needs_review=True;page.layers=[layer];store.save_page(project,page)
    before=store.get_page(project,0).model_dump();digest=hashlib.sha256(store.asset_path(project,layer.asset).read_bytes()).hexdigest()
    with store.db() as c:history_before=c.execute('SELECT count(*) FROM history WHERE project=?',(project,)).fetchone()[0]
    payload={'provider':'sam3','layer_id':layer.id,'reason':'local failed on this crop','box':[10,10,145,90]}
    job=uid()
    with store.db() as c:c.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)',(job,project,json.dumps({'pages':[0],'operation':'cloud','payload':payload}),'queued',0,'',0,time.time()))
    monkeypatch.setenv('LAYERDECK_CLOUD','1');monkeypatch.setenv('FAL_KEY','test-only-not-a-secret')
    masks=[]
    for y in (10,45):
        mask=Image.new('RGB',(135,80));ImageDraw.Draw(mask).rectangle((10,y,34,y+24),fill='white')
        data=io.BytesIO();mask.save(data,format='PNG');masks.append(data.getvalue())
    calls=[]
    class Response:
        def __init__(self,data=None,content=b''):self.data=data;self.content=content
        def raise_for_status(self):pass
        def json(self):return self.data
    class Client:
        def __init__(self,**kwargs):pass
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def post(self,url,**kwargs):
            calls.append(url)
            if outcome=='failure':raise RuntimeError('simulated provider failure')
            return Response({'status_url':'https://queue.fal.run/status','response_url':'https://queue.fal.run/result'})
        def get(self,url,**kwargs):
            calls.append(url)
            if url.endswith('/status'):return Response({'status':'COMPLETED'})
            if url.endswith('/result'):return Response({'masks':[{'url':f'https://test.fal.media/mask{i}'} for i in range(2)]})
            return Response(content=masks[int(url[-1])])
    monkeypatch.setattr(cloud.httpx,'Client',Client)
    settle=store.settle
    def finish(charge,status):
        settle(charge,status)
        if outcome=='cancel':store.update_job(job,cancel=1)
    monkeypatch.setattr(store,'settle',finish)
    jobs.run(job)
    assert store.get_job(job)['status']=={'success':'done','cancel':'cancelled','failure':'error'}[outcome]
    assert store.get_page(project,0).model_dump()==before
    with store.db() as c:assert c.execute('SELECT count(*) FROM history WHERE project=?',(project,)).fetchone()[0]==history_before
    assert hashlib.sha256(store.asset_path(project,layer.asset).read_bytes()).hexdigest()==digest
    assert calls and len(store.budget()['calls'])==1
    assert store.budget()['calls'][0]['status']==('uncertain' if outcome=='failure' else 'spent')
    if outcome!='success':
        with pytest.raises(ValueError):get_preview(project,job)
        return
    draft=get_preview(project,job);assert len(draft['candidates'])==2
    assert draft['candidates'][0]['box']==[20,20,45,45]
    result=apply_preview(project,page,layer.id,SplitApplyRequest(preview_job=job,candidate_ids=[0,1]))
    assert len(result.layers)==2 and result.layers[1].source=='cloud-sam3-reviewed'
    child=raster.read_image(project,result.layers[1].asset)
    assert child[30,30,3]==255 and child[65,30,3]==255 and child[30,120,3]==0


def test_cloud_segmentation_without_confirmation_job_never_sends(monkeypatch):
    from backend import cloud
    project,page,layer,_=project_image();layer.needs_review=True
    monkeypatch.setenv('LAYERDECK_CLOUD','1')
    monkeypatch.setattr(cloud.httpx,'Client',lambda **kwargs:pytest.fail('Missing review job must not send a request'))
    with pytest.raises(ValueError,match='确认任务'):
        cloud.process(project,page,{'provider':'sam3','layer_id':layer.id,'reason':'local failed','box':[0,0,100,80]})
    assert not store.budget()['calls']
