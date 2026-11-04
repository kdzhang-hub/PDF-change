"""Review uncertain masks, then keep the selected parts as one whole object."""
import json,re
from pathlib import Path
import numpy as np
from PIL import Image
from . import store


def preview_path(project,job):
    if not re.fullmatch('[a-f0-9]{32}',job):raise ValueError('无效候选身份')
    return store.project_dir(project)/('split-preview-'+job+'.json')


def get_preview(project,job):
    record=store.get_job(job)
    if record['project']!=project or record['status']!='done':raise ValueError('候选尚未完成或不属于当前项目')
    path=preview_path(project,job)
    if not path.is_file():raise ValueError('未找到候选结果，请重新查找')
    return json.loads(path.read_text(encoding='utf-8'))


def make_preview(project,page,layer_id,request,job):
    from .raster import read_image,split_mask
    layer=next((l for l in page.layers if l.id==layer_id),None)
    if layer is None or layer.kind!='image' or layer.locked:raise ValueError('请选择未锁定的图片素材')
    if layer.content_role=='logo':raise ValueError('完整标识无需拆分')
    image=read_image(project,layer.asset)
    if request.method=='backdrop':return stage_backdrop(project,page,layer,image,request.fill,job)
    masks=split_mask(image,request)
    return stage_masks(project,page,layer,image,masks,request.fill,job)


def stage_backdrop(project,page,layer,image,fill,job):
    from .raster import save_image
    from .backdrop_matte import propose,comparison
    if fill!='local':raise ValueError('彩底分层需保留独立背景，请选择本地重建或修复')
    if layer.opacity!=1:raise ValueError('请先将素材不透明度设为100%，以免独立图层产生叠加色差')
    if store.get_job(job)['project']!=project:raise ValueError('候选任务不属于当前项目')
    cut,base,quality=propose(image)
    foreground=save_image(project,cut,'matte-foreground');background=save_image(project,base,'matte-background')
    thumb=Image.fromarray(cut);thumb.thumbnail((256,160),Image.Resampling.LANCZOS)
    previews=[]
    for view in comparison(cut,base):
        preview=Image.fromarray(view);preview.thumbnail((256,200),Image.Resampling.LANCZOS)
        previews.append(save_image(project,np.asarray(preview),'matte-compare'))
    result={'job':job,'project':project,'page':page.index,'layer':layer.id,'revision':page.revision,
        'source_asset':layer.asset,'fill':fill,'source':'local-backdrop-matte','mode':'backdrop-matte',
        'foreground':foreground,'background':background,'quality':quality,'comparisons':previews,
        'candidates':[{'id':0,'mask':save_image(project,cut[:,:,3],'matte-alpha'),
            'thumbnail':save_image(project,np.asarray(thumb),'matte-thumb'),
            'pixels':int(np.count_nonzero(cut[:,:,3])),'box':[0,0,image.shape[1],image.shape[0]]}]}
    path=preview_path(project,job);temporary=path.with_suffix('.building')
    temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(path)
    return result


def stage_masks(project,page,layer,image,masks,fill,job,source='manual-segmentation'):
    """Local and cloud proposals share the same read-only confirmation gate."""
    from .raster import save_image
    if store.get_job(job)['project']!=project:raise ValueError('候选任务不属于当前项目')
    if layer.kind!='image' or layer.locked or layer.content_role=='logo':raise ValueError('当前素材不可拆分')
    candidates=[]
    for mask in sorted(masks,key=np.count_nonzero,reverse=True)[:64]:
        mask=np.asarray(mask,dtype=bool)
        if mask.shape!=image.shape[:2]:raise ValueError('候选遮罩尺寸不匹配')
        mask=mask&(image[:,:,3]>0)
        ys,xs=np.where(mask)
        if len(xs)<4:continue
        left,top,right,bottom=int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)
        mask_name=save_image(project,np.uint8(mask)*255,'preview-mask')
        crop=image[top:bottom,left:right].copy();crop[:,:,3]=np.where(mask[top:bottom,left:right],crop[:,:,3],0)
        crop[:,:,:3][crop[:,:,3]==0]=0
        thumbnail=Image.fromarray(crop);thumbnail.thumbnail((256,160),Image.Resampling.LANCZOS)
        thumb_name=save_image(project,np.array(thumbnail),'preview-thumb')
        candidates.append({'id':len(candidates),'mask':mask_name,'thumbnail':thumb_name,'pixels':len(xs),'box':[left,top,right,bottom]})
    result={'job':job,'project':project,'page':page.index,'layer':layer.id,'revision':page.revision,
        'source_asset':layer.asset,'fill':fill,'source':source,'candidates':candidates}
    path=preview_path(project,job);temporary=path.with_suffix('.building')
    temporary.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');temporary.replace(path)
    return result


def apply_preview(project,page,layer_id,request):
    from .raster import read_image,apply_masks
    preview=get_preview(project,request.preview_job)
    if preview['page']!=page.index or preview['layer']!=layer_id:raise ValueError('候选不属于当前素材')
    if preview['revision']!=page.revision:raise ValueError('页面已更新，请重新查找候选，避免覆盖修改')
    result=page.model_copy(deep=True)
    layer=next((l for l in result.layers if l.id==layer_id),None)
    if layer is None or layer.locked or layer.kind!='image' or layer.content_role=='logo':raise ValueError('当前素材不可拆分')
    if layer.asset!=preview['source_asset']:raise ValueError('素材已改变，请重新查找候选')
    candidates={candidate['id']:candidate for candidate in preview['candidates']}
    if any(identity not in candidates for identity in request.candidate_ids):raise ValueError('候选区域不存在')
    if preview.get('mode')=='backdrop-matte':
        return apply_backdrop(project,result,layer,preview,request)
    image=read_image(project,layer.asset);union=np.zeros(image.shape[:2],bool)
    for identity in request.candidate_ids:
        mask=read_image(project,candidates[identity]['mask'])[:,:,0]>0
        if mask.shape!=union.shape:raise ValueError('候选遮罩尺寸已改变')
        union|=mask
    if np.count_nonzero(union)<4 or np.count_nonzero(union)>=union.size*.98:
        raise ValueError('请选择一个完整对象，保留必要背景；当前素材未改变')
    pieces=apply_masks(project,layer,image,[union],preview['fill'])
    if len(pieces)!=2:raise ValueError('尚未找到可保留的完整对象')
    pieces[1].name=request.name.strip() or '完整对象'
    pieces[1].source=preview.get('source','manual-segmentation');pieces[1].notes.append('用户确认同一对象的区域，作为一个完整素材保留')
    if not read_image(project,pieces[0].asset)[:,:,3].any():pieces=pieces[1:]
    result.layers=[l for l in result.layers if l.id!=layer.id]+pieces
    result.status='needs_review'
    return result


def apply_backdrop(project,page,layer,preview,request):
    from .raster import read_image
    from .models import uid
    if request.candidate_ids!=[0]:raise ValueError('请选择完整前景候选')
    source=read_image(project,layer.asset)
    if any(read_image(project,preview[key]).shape!=source.shape for key in ('foreground','background')):
        raise ValueError('彩底候选尺寸已改变，请重新生成')
    base=layer.model_copy(deep=True);base.asset=preview['background'];base.mask=None
    base.name=layer.name+' · 独立背景';base.restoration_asset=layer.restoration_asset or layer.asset
    base.source='local-backdrop-background';base.inferred=True;base.edited=True;base.needs_review=True;base.group_id=None
    base.notes=['可见彩底拟合并补全被遮挡区域，属于本地推断，不代表原隐藏内容；可整体移动或换底色']
    foreground=layer.model_copy(deep=True);foreground.id=uid();foreground.parent_id=base.id;foreground.group_id=None
    foreground.name=request.name.strip() or '完整前景';foreground.asset=preview['foreground'];foreground.restoration_asset=foreground.asset
    foreground.mask=preview['candidates'][0]['mask'];foreground.z=layer.z+.001
    foreground.source='local-backdrop-matte';foreground.inferred=True;foreground.edited=True;foreground.needs_review=True
    foreground.notes=['确认后按一个完整对象保留；软边缘颜色为本地估计，请在浅底、深底检查头发与衣物边缘']
    page.layers=[l for l in page.layers if l.id!=layer.id]+[base,foreground]
    page.status='needs_review'
    return page
