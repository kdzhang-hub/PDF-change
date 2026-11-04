from __future__ import annotations
import io
import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse,quote
import fitz
from fastapi import FastAPI,UploadFile,File,HTTPException,Request
from fastapi.responses import FileResponse,JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from . import store,jobs,local_models,cloud
from .models import PageScene,ConvertRequest,SplitRequest,CloudRequest,TextRepairRequest,ImageRoleRequest,SplitApplyRequest
from .extract import prepare
from .export import export_pptx
from dotenv import load_dotenv
load_dotenv(store.ROOT/'.env',override=False)


@asynccontextmanager
async def lifespan(app):
    store.init(); jobs.start_pool()
    yield
    jobs.stop_pool()


app=FastAPI(title='LayerDeck',lifespan=lifespan)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['localhost','127.0.0.1','testserver'])


@app.middleware('http')
async def local_only(request:Request,call_next):
    origin=request.headers.get('origin')
    if origin and urlparse(origin).netloc!=request.headers.get('host'):
        return JSONResponse({'detail':'只允许本机编辑器同源访问'},status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    return response


@app.exception_handler(ValueError)
async def bad_request(request,exc): return JSONResponse({'detail':str(exc)},status_code=400)


@app.exception_handler(FileNotFoundError)
async def not_found(request,exc): return JSONResponse({'detail':str(exc)},status_code=404)


@app.get('/api/health')
def health():
    from .font_calibration import available
    return {'ok':True,'models':local_models.status(),'cloud':cloud.config_status(),'budget':store.budget(),'office_calibration':available()}


@app.get('/api/fonts')
def fonts():
    from .fonts import installed_map
    return sorted(set(installed_map().values())|{'Microsoft YaHei','Arial','SimSun','SimHei'})


@app.get('/api/projects')
def projects(): return store.list_projects()


@app.post('/api/projects')
async def upload(file:UploadFile=File(...)):
    name=Path(file.filename or 'document.pdf').name
    data=bytearray()
    while chunk:=await file.read(1024*1024):
        data.extend(chunk)
        if len(data)>200*1024*1024: raise HTTPException(413,'文件超过 200 MB')
    from .imports import normalize_input
    normalized,metadata=normalize_input(data,name)
    project=store.create(name)
    (store.project_dir(project)/'source.pdf').write_bytes(normalized)
    (store.project_dir(project)/'import.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),'utf-8')
    if metadata['kind']=='image':(store.project_dir(project)/'original-input.bin').write_bytes(data)
    for page in prepare(project): store.save_page(project,page)
    return store.get_project(project)


@app.get('/api/projects/{project}')
def get_project(project:str): return store.get_project(project)


@app.get('/api/projects/{project}/jobs')
def project_jobs(project:str):
    store.get_project(project)
    with store.db() as c:
        return [dict(r) for r in c.execute('SELECT * FROM jobs WHERE project=? ORDER BY created DESC LIMIT 20',(project,))]


@app.post('/api/projects/{project}/pages/{index}/merge')
def merge(project:str,index:int,ids:list[str]):
    page=store.get_page(project,index)
    if len(set(ids))<2 or len(ids)>100:raise ValueError('请选择 2 至 100 个图片图层')
    if not set(ids)<={l.id for l in page.layers}:raise ValueError('图层不存在')
    return {'id':jobs.submit(project,[index],'merge',{'ids':ids})}


@app.put('/api/projects/{project}/pages/{index}')
def save_page(project:str,index:int,page:PageScene):
    old=store.get_page(project,index)
    if index!=page.index or (old.width,old.height,old.original)!=(page.width,page.height,page.original):
        raise ValueError('不能修改原稿尺寸或页面身份')
    with store.db() as c:
        active=c.execute("SELECT id FROM jobs WHERE project=? AND status IN ('running','queued')",(project,)).fetchone()
    if active: raise HTTPException(409,'正在处理，请等待或取消后编辑')
    return store.save_page(project,page,expected=page.revision)


@app.get('/api/projects/{project}/pages/{index}/history')
def history(project:str,index:int):
    with store.db() as c:
        return [{'id':r['id'],'created':r['created'],'scene':json.loads(r['scene'])} for r in c.execute(
            'SELECT * FROM history WHERE project=? AND idx=? ORDER BY id DESC LIMIT 50',(project,index))]


@app.post('/api/projects/{project}/convert')
def convert(project:str,req:ConvertRequest):
    for index in req.pages: store.get_page(project,index)
    return {'id':jobs.submit(project,list(dict.fromkeys(req.pages)),payload={'overwrite':req.overwrite,'calibrate':req.calibrate})}


@app.post('/api/projects/{project}/calibrate')
def calibrate_project(project:str,req:ConvertRequest):
    for index in req.pages:
        if store.get_page(project,index).status=='pending':raise ValueError('请先还原页面，再校准文字')
    return {'id':jobs.submit(project,list(dict.fromkeys(req.pages)),'calibrate')}


@app.post('/api/projects/{project}/pages/{index}/layers/{layer_id}/split')
def split(project:str,index:int,layer_id:str,req:SplitRequest):
    store.get_page(project,index)
    operation='split' if req.method=='brush' else 'split-preview'
    return {'id':jobs.submit(project,[index],operation,{'layer_id':layer_id,'request':req.model_dump()}),'review_required':operation=='split-preview'}


@app.get('/api/projects/{project}/split-preview/{job}')
def split_preview(project:str,job:str):
    from .split_preview import get_preview
    return get_preview(project,job)


@app.post('/api/projects/{project}/pages/{index}/layers/{layer_id}/split-apply')
def split_apply(project:str,index:int,layer_id:str,req:SplitApplyRequest):
    store.get_page(project,index)
    return {'id':jobs.submit(project,[index],'split-apply',{'layer_id':layer_id,'request':req.model_dump()})}


@app.post('/api/projects/{project}/pages/{index}/layers/{layer_id}/ocr')
def ocr_layer(project:str,index:int,layer_id:str):
    store.get_page(project,index)
    return {'id':jobs.submit(project,[index],'ocr',{'layer_id':layer_id})}


@app.post('/api/projects/{project}/pages/{index}/layers/{layer_id}/text-repair')
def repair_layer_text(project:str,index:int,layer_id:str,req:TextRepairRequest):
    store.get_page(project,index)
    return {'id':jobs.submit(project,[index],'text-repair',{'layer_id':layer_id,'request':req.model_dump()})}


@app.post('/api/projects/{project}/pages/{index}/layers/{layer_id}/image-role')
def image_role(project:str,index:int,layer_id:str,req:ImageRoleRequest):
    store.get_page(project,index)
    return {'id':jobs.submit(project,[index],'image-role',{'layer_id':layer_id,'role':req.role})}


@app.post('/api/projects/{project}/pages/{index}/cloud')
def cloud_job(project:str,index:int,req:CloudRequest):
    store.get_page(project,index)
    return {'id':jobs.submit(project,[index],'cloud',req.model_dump())}


@app.get('/api/jobs/{job}')
def job(job:str): return store.get_job(job)


@app.post('/api/jobs/{job}/cancel')
def cancel(job:str):
    store.get_job(job); store.update_job(job,cancel=1)
    return {'ok':True}


@app.post('/api/jobs/{job}/resume')
def resume(job:str):
    old=store.get_job(job)
    if old['status'] not in ('error','cancelled','interrupted'): raise ValueError('只能恢复中断或失败的任务')
    spec=json.loads(old['pages'])
    # Cloud retries must be deliberate new submissions because the previous request may be billed.
    if spec['operation']=='cloud': raise ValueError('云端费用状态可能不确定，请核对账本后重新选择局部区域')
    pages=spec['pages']
    if spec['operation']=='convert':
        completed=round(old['progress']*len(pages)/100); pages=pages[completed:]
    if not pages: raise ValueError('没有未完成页面')
    return {'id':jobs.submit(old['project'],pages,spec['operation'],spec['payload'])}


@app.get('/api/projects/{project}/assets/{name}')
def asset(project:str,name:str):
    path=store.asset_path(project,name)
    if not path.exists(): raise FileNotFoundError('素材不存在')
    return FileResponse(path)


@app.post('/api/projects/{project}/export')
def export(project:str,req:ConvertRequest):
    pages=[store.get_page(project,i) for i in dict.fromkeys(req.pages)]
    with store.db() as c:
        if c.execute("SELECT 1 FROM jobs WHERE project=? AND status IN ('queued','running')",(project,)).fetchone():
            raise HTTPException(409,'页面正在处理，请完成或取消后导出')
    from .export_service import create_export
    out=create_export(project,pages)
    return FileResponse(out,filename='LayerDeck.pptx',media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation')


@app.get('/api/budget')
def budget(): return store.budget()


@app.post('/api/projects/{project}/export-docx')
def export_word(project:str,req:ConvertRequest):
    pages=[store.get_page(project,i) for i in dict.fromkeys(req.pages)]
    with store.db() as c:
        if c.execute("SELECT 1 FROM jobs WHERE project=? AND status IN ('queued','running')",(project,)).fetchone():
            raise HTTPException(409,'页面正在处理，请完成或取消后导出')
    from .export_service import create_export
    out=create_export(project,pages,format='docx')
    report_path=out.with_suffix('.report.json')
    warnings=json.loads(report_path.read_text('utf-8')).get('warnings',[]) if report_path.is_file() else []
    headers={'X-LayerDeck-Notice':quote('；'.join(warnings),safe='')} if warnings else None
    return FileResponse(out,filename='LayerDeck.docx',media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',headers=headers)


dist=store.ROOT/'frontend'/'dist'
if dist.exists(): app.mount('/',StaticFiles(directory=dist,html=True),name='editor')
