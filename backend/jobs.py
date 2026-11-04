from __future__ import annotations
import json
import time
from concurrent.futures import ProcessPoolExecutor
from . import store
from .models import uid, SplitRequest

POOL=None


def start_pool():
    global POOL
    store.recover_jobs()
    POOL=ProcessPoolExecutor(max_workers=1)


def stop_pool():
    global POOL
    if POOL: POOL.shutdown(wait=False,cancel_futures=True)
    POOL=None


def submit(project, pages, operation='convert', payload=None):
    # Serialize project changes; edits are checked again via optimistic revisions.
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        active=c.execute("SELECT id FROM jobs WHERE project=? AND status IN ('queued','running')",(project,)).fetchone()
        if active: raise ValueError('该项目正在处理，请先等待或取消当前任务')
        job=uid()
        c.execute('INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?)',(job,project,json.dumps({'pages':pages,'operation':operation,'payload':payload}), 'queued',0,'排队中',0,time.time()))
    if POOL is None: raise RuntimeError('转换工作进程未启动')
    POOL.submit(run,job)
    return job


def run(job):
    from .extract import convert_page
    from .raster import read_image,split_mask,apply_masks
    data=store.get_job(job); spec=json.loads(data['pages']); pages=spec['pages']
    project=data['project']
    try:
        store.update_job(job,status='running',message='本地处理')
        for pos,index in enumerate(pages):
            if store.get_job(job)['cancel']:
                store.update_job(job,status='cancelled',message='已取消；已完成的页面保留'); return
            old=store.get_page(project,index)
            if spec['operation']=='convert':
                if old.status!='pending' and not (spec['payload'] or {}).get('overwrite'):
                    store.update_job(job,progress=round(100*(pos+1)/len(pages))); continue
                page=convert_page(project,index,old.original)
                if (spec['payload'] or {}).get('calibrate',True):
                    from .font_calibration import calibrate_page
                    store.update_job(job,message=f'本机文字字形校准，第 {pos+1} 页')
                    try:page,measured=calibrate_page(project,page)
                    except (RuntimeError,OSError,TimeoutError) as exc:
                        page.warnings.append('本机文字校准未完成，原位置保留，请手工校正')
                        page.status='needs_review'
            elif spec['operation']=='calibrate':
                from .font_calibration import calibrate_page
                store.update_job(job,message='正在本机测量文字字形，保留已手工修改的对象')
                page,measured=calibrate_page(project,old,True)
                if not measured:page.warnings.append('没有新增的文字校准结果；已有布局、手工修改、锁定、旋转和多行文字保持原样')
            elif spec['operation']=='split':
                payload=spec['payload']; page=old.model_copy(deep=True)
                layer=next((l for l in page.layers if l.id==payload['layer_id']),None)
                if layer is None or layer.kind!='image': raise ValueError('请选择图片图层')
                if layer.locked: raise ValueError('请先解锁图层')
                if layer.content_role=='logo':raise ValueError('标识按整体保留；如需拆分，请先选择“作为普通素材处理”')
                req=SplitRequest.model_validate(payload['request'])
                if req.method!='brush':raise ValueError('模型候选需要先确认完整对象，请重新查找候选')
                image=read_image(project,layer.asset)
                pieces=apply_masks(project,layer,image,split_mask(image,req),req.fill)
                page.layers=[l for l in page.layers if l.id!=layer.id]+pieces
                page.status='needs_review'
            elif spec['operation']=='split-preview':
                from .split_preview import make_preview
                make_preview(project,old,spec['payload']['layer_id'],SplitRequest.model_validate(spec['payload']['request']),job)
                if store.get_job(job)['cancel']:
                    store.update_job(job,status='cancelled',message='已取消候选查找，原素材未改变');return
                store.update_job(job,progress=round(100*(pos+1)/len(pages)),message='候选已生成，原素材未改变')
                continue
            elif spec['operation']=='split-apply':
                from .split_preview import apply_preview
                from .models import SplitApplyRequest
                page=apply_preview(project,old,spec['payload']['layer_id'],SplitApplyRequest.model_validate(spec['payload']['request']))
            elif spec['operation']=='cloud':
                from .cloud import process
                page=process(project,old,spec['payload'],lambda:bool(store.get_job(job)['cancel']),preview_job=job)
                if spec['payload'].get('provider')=='sam3':
                    if store.get_job(job)['cancel']:
                        store.update_job(job,status='cancelled',message='已取消候选查找，原素材未改变');return
                    store.update_job(job,progress=round(100*(pos+1)/len(pages)),message='候选已生成，原素材未改变')
                    continue
            elif spec['operation']=='ocr':
                from .raster import auto_image
                from .local_models import status
                if not status()['ocr']:raise RuntimeError('本地 OCR 未就绪，请先安装模型')
                page=old.model_copy(deep=True)
                layer=next((l for l in page.layers if l.id==spec['payload']['layer_id']),None)
                if layer is None or layer.kind!='image' or layer.locked:raise ValueError('请选择未锁定的图片图层')
                if layer.content_role=='logo':raise ValueError('标识按整体保留；如需拆字，请先选择“作为普通素材处理”')
                if layer.rotation:raise ValueError('请先将该图片旋转设为 0，再识别文字')
                pieces,notes=auto_image(project,layer,segment=False)
                if not any(l.kind=='text' for l in pieces):raise ValueError('本地未识别到可信文字，原素材保持不变')
                page.layers=[l for l in page.layers if l.id!=layer.id]+pieces
                page.warnings.extend(notes);page.status='needs_review'
            elif spec['operation']=='image-role':
                from .logo_policy import set_image_role
                page=set_image_role(project,old,spec['payload']['layer_id'],spec['payload']['role'])
            elif spec['operation']=='merge':
                from .raster import merge_images
                page=merge_images(project,old,spec['payload']['ids'])
            elif spec['operation']=='text-repair':
                from .raster import repair_text
                from .models import TextRepairRequest
                page=old.model_copy(deep=True)
                payload=spec['payload'];layer=next((l for l in page.layers if l.id==payload['layer_id']),None)
                if layer is None:raise ValueError('图层不存在')
                pieces=repair_text(project,layer,TextRepairRequest.model_validate(payload['request']))
                page.layers=[l for l in page.layers if l.id!=layer.id]+pieces;page.status='needs_review'
            else: raise ValueError('未知任务')
            if store.get_job(job)['cancel']:
                store.update_job(job,status='cancelled',message='已取消，当前页结果未覆盖项目'); return
            store.save_page(project,page,expected=old.revision)
            store.update_job(job,progress=round(100*(pos+1)/len(pages)),message=f'已处理 {pos+1} / {len(pages)} 页')
        preview=spec['operation']=='split-preview' or (spec['operation']=='cloud' and spec['payload'].get('provider')=='sam3')
        store.update_job(job,status='done',message='候选已生成，原素材未改变' if preview else '处理完成，请检查需要校正的图层')
    except Exception as exc:
        # HTTP errors may contain credential-bearing URLs, do not persist raw provider errors.
        message=str(exc) if isinstance(exc,(ValueError,RuntimeError)) else f'{type(exc).__name__}：处理失败，原页保留'
        store.update_job(job,status='error',message=message[:500])
