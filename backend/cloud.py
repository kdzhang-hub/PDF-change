"""Explicit cropped fallbacks; environment failures never invoke this module."""
from __future__ import annotations
import base64
import io
import json
import math
import os
import time
from urllib.parse import urlparse
import httpx
import numpy as np
from PIL import Image
from .models import CloudRequest
from . import store
from .raster import read_image,save_image


def data_url(image):
    out=io.BytesIO(); Image.fromarray(image).save(out,format='PNG')
    return 'data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()


def config_status():
    return {'enabled':os.environ.get('LAYERDECK_CLOUD')=='1',
            'qwen_key':bool(os.environ.get('DASHSCOPE_API_KEY')),
            'fal_key':bool(os.environ.get('FAL_KEY')),
            'qwen_price_configured':bool(os.environ.get('QWEN_MAX_CALL_USD'))}


def crop_bounds(image,box):
    x0,y0,x1,y1=map(round,box)
    h,w=image.shape[:2]
    if not (0<=x0<x1<=w and 0<=y0<y1<=h): raise ValueError('裁剪区域超出素材范围')
    return x0,y0,x1,y1


def process(project,page,payload,cancelled=lambda:False,preview_job=None):
    req=CloudRequest.model_validate(payload)
    if os.environ.get('LAYERDECK_CLOUD')!='1': raise ValueError('云端未启用，本地项目保持不变')
    layer=next((l for l in page.layers if l.id==req.layer_id),None)
    if layer is None or layer.kind!='image' or not layer.needs_review: raise ValueError('仅允许对本地仍需处理的图片图层使用兜底')
    if layer.locked: raise ValueError('请先解锁图层')
    if layer.content_role=='logo':raise ValueError('标识按整体保留，无需云端拆分；可先改为普通素材')
    if req.provider=='sam3':
        if not preview_job or store.get_job(preview_job)['project']!=project:raise ValueError('云端分割需要完整对象确认任务，原素材未改变')
    image=read_image(project,layer.asset); x0,y0,x1,y1=crop_bounds(image,req.box)
    crop=image[y0:y1,x0:x1]
    if req.provider=='qwen':
        key=os.environ.get('DASHSCOPE_API_KEY')
        estimate=float(os.environ.get('QWEN_MAX_CALL_USD','0'))
    else:
        key=os.environ.get('FAL_KEY')
        estimate=.005 if req.provider=='sam3' else .05*math.ceil((x1-x0)*(y1-y0)/1_000_000)
    if not key: raise ValueError('后端未配置所需密钥，云端步骤已暂停')
    mask_crop=None
    if req.provider=='flux':
        if not req.mask_asset: raise ValueError('补全必须提供明确遮罩')
        mask=read_image(project,req.mask_asset)[:,:,0]
        if mask.shape!=image.shape[:2]: raise ValueError('遮罩尺寸不匹配')
        mask_crop=mask[y0:y1,x0:x1]
        if not mask_crop.any(): raise ValueError('遮罩区域为空')
    if cancelled(): raise ValueError('已取消，未发送')
    charge=store.reserve(req.provider,estimate,{'project':project,'page':page.index,'layer':layer.id,'crop':req.box,'reason':req.reason})
    sent=False
    try:
        with httpx.Client(timeout=90,trust_env=True) as client:
            if req.provider=='qwen':
                base=os.environ.get('QWEN_BASE_URL','https://dashscope.aliyuncs.com/compatible-mode/v1').rstrip('/')
                sent=True
                response=client.post(base+'/chat/completions',headers={'Authorization':'Bearer '+key},json={
                    'model':os.environ.get('QWEN_MODEL','qwen3-vl-plus'),'max_tokens':1024,
                    'messages':[{'role':'system','content':(store.ROOT/'prompts'/'visual_review.md').read_text('utf-8')},
                        {'role':'user','content':[{'type':'image_url','image_url':{'url':data_url(crop)}},
                        {'type':'text','text':req.prompt or '识别这一区域里应当独立分层的对象、文字与遮挡关系。不得声称知道被遮挡的原始内容。'}]}]})
                response.raise_for_status()
                result=response.json()['choices'][0]['message']['content']
                layer.notes.append('云端识别建议：'+str(result)[:6000]); layer.source='cloud-qwen-assisted'
            else:
                model='fal-ai/sam-3/image' if req.provider=='sam3' else 'fal-ai/flux-pro/v1/fill'
                body={'image_url':data_url(crop),'prompt':req.prompt or 'foreground objects'}
                if mask_crop is not None: body['mask_url']=data_url(mask_crop)
                headers={'Authorization':'Key '+key}
                sent=True
                response=client.post('https://queue.fal.run/'+model,headers=headers,json=body)
                response.raise_for_status(); ticket=response.json()
                def queue_url(name):
                    url=ticket[name]
                    if urlparse(url).scheme!='https' or urlparse(url).hostname!='queue.fal.run': raise ValueError('提供商返回了非预期队列地址')
                    return url
                for _ in range(180):
                    if cancelled():
                        if 'cancel_url' in ticket: client.put(queue_url('cancel_url'),headers=headers)
                        raise RuntimeError('云端已请求取消；费用按已预留上限保留，需核对账单')
                    state=client.get(queue_url('status_url'),headers=headers); state.raise_for_status()
                    if state.json().get('status')=='COMPLETED': break
                    time.sleep(2)
                else: raise RuntimeError('云端超时，费用预留保留，避免重复收费')
                response=client.get(queue_url('response_url'),headers=headers); response.raise_for_status(); result=response.json()
                entries=result.get('masks',[]) if req.provider=='sam3' else result.get('images',[])
                if not entries: raise RuntimeError('云端未返回可用图片，保留原始内容')
                arrays=[]
                for item in entries[:32]:
                    url=item['url'] if isinstance(item,dict) else item
                    parsed=urlparse(url)
                    if parsed.scheme!='https' or not (parsed.hostname or '').endswith(('.fal.media','.fal.ai')):
                        raise ValueError('提供商返回了非预期素材域名')
                    downloaded=client.get(url); downloaded.raise_for_status()
                    if len(downloaded.content)>50_000_000: raise ValueError('返回素材过大')
                    arrays.append(np.array(Image.open(io.BytesIO(downloaded.content)).resize((x1-x0,y1-y0)).convert('RGBA')))
                if req.provider=='sam3':
                    masks=[]
                    for a in arrays:
                        full=np.zeros(image.shape[:2],bool); full[y0:y1,x0:x1]=a[:,:,0]>127; masks.append(full)
                    from .split_preview import stage_masks
                    stage_masks(project,page,layer,image,masks,'local',preview_job,source='cloud-sam3-reviewed')
                else:
                    updated=image.copy(); target=updated[y0:y1,x0:x1]; use=mask_crop>0
                    target[use]=arrays[0][use]
                    layer.asset=save_image(project,updated,'cloud-fill'); layer.inferred=True
                    layer.source='cloud-flux-fill'; layer.notes.append('云端推断补全：须人工确认')
        store.settle(charge,'spent')
        if req.provider!='sam3':page.status='needs_review'
        return page
    except Exception:
        store.settle(charge,'uncertain' if sent else 'released')
        raise RuntimeError('云端步骤失败或取消，原页保留；已发送请求的费用保守计入预算，请查看账本') from None
