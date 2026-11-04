from __future__ import annotations
import cv2
import numpy as np
from PIL import Image
from PIL import ImageFont
from pathlib import Path
from .models import LayerElement, SplitRequest, uid
from .store import asset_path
from . import local_models


def save_image(project, array, prefix='layer'):
    name = f'{prefix}-{uid()}.png'
    Image.fromarray(array.astype(np.uint8)).save(asset_path(project,name))
    return name


def read_image(project, name):
    return np.array(Image.open(asset_path(project,name)).convert('RGBA'))


def background_color(image):
    rgb = image[:,:,:3]
    border = np.concatenate((rgb[0],rgb[-1],rgb[:,0],rgb[:,-1]))
    if image.shape[2]==4:
        alpha=np.concatenate((image[0,:,3],image[-1,:,3],image[:,0,3],image[:,-1,3]))
        # RGB concealed by transparency is not a background paint colour.
        if np.mean(alpha>=250)<.96:return np.zeros(3,np.uint8),False
    color = np.median(border,axis=0).astype(np.uint8)
    flat = np.mean(np.linalg.norm(border.astype(float)-color,axis=1)<12) > .96
    return color,flat


def text_foreground(roi,background,min_extent=None):
    """Separate high-contrast glyph colour from a varying local background."""
    pixels=roi.reshape(-1,3);quant=pixels//16
    colors,counts=np.unique(quant,axis=0,return_counts=True)
    distance=np.linalg.norm(colors.astype(float)*16+8-background,axis=1)
    quality=distance*np.sqrt(counts);quality[distance<40]=0
    if not np.any(quality):return np.zeros(roi.shape[:2],bool),background.astype(int)
    for index in np.argsort(quality)[::-1][:16]:
        if quality[index]<=0:break
        winner=colors[index]
        color=np.median(pixels[np.all(quant==winner,axis=1)],axis=0).astype(int)
        contrast=max(1,np.linalg.norm(color-background))
        difference=np.linalg.norm(roi.astype(float)-background,axis=2)
        ink=(np.linalg.norm(roi.astype(float)-color,axis=2)<min(90,contrast*.4))&(difference>25)
        if min_extent:
            ys,xs=np.where(ink)
            if len(xs)<3 or np.ptp(xs)+1<roi.shape[1]*min_extent[0] or np.ptp(ys)+1<roi.shape[0]*min_extent[1]:continue
        return ink,color
    return np.zeros(roi.shape[:2],bool),background.astype(int)


def text_removal_mask(roi,ink,background):
    """Include nearby dark text effects so moving OCR text leaves no copy."""
    background=np.asarray(background,dtype=float)
    radius=max(2,round(roi.shape[0]*.18))
    near=cv2.dilate(ink.astype(np.uint8),cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(radius*2+1,radius*2+1)))>0
    rgb=roi.astype(float)
    ratio=(rgb*background).sum(axis=2)/max(1,float(background@background))
    # Clear only dark effects supported by the local background colour.
    residual=np.linalg.norm(rgb-ratio[:,:,None]*background,axis=2)
    dark=(ratio<.78)&(residual<24)&((background.mean()-rgb.mean(axis=2))>6)
    removal=ink|(dark&near)
    return cv2.dilate(removal.astype(np.uint8),np.ones((3,3),np.uint8))>0


def transparent_text_removal(alpha,ink):
    """Clear coloured outlines only when connected to a detected glyph core."""
    visible=alpha>0
    _,labels=cv2.connectedComponents(visible.astype(np.uint8),8)
    owners=np.unique(labels[ink&visible]);owners=owners[owners!=0]
    if not len(owners):return np.zeros_like(visible)
    radius=max(3,min(6,round(ink.shape[0]*.055)))
    support=cv2.dilate(ink.astype(np.uint8),cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(radius*2+1,radius*2+1)))>0
    return support&np.isin(labels,owners)


def complete_transparent_text_removal(alpha,ink,allowed):
    """Finish effects only for components covered by accepted text regions."""
    _,labels=cv2.connectedComponents((alpha>0).astype(np.uint8),8)
    owners=np.unique(labels[ink&(alpha>0)]);owners=owners[owners!=0]
    removal=np.zeros(alpha.shape,bool)
    for owner in owners:
        component=labels==owner
        if np.mean(allowed[component])>=.995:removal|=component
    return removal


def components(image):
    color,flat = background_color(image)
    alpha_border=np.concatenate((image[0,:,3],image[-1,:,3],image[:,0,3],image[:,-1,3]))
    if np.mean(alpha_border<10)>.96:
        # Keep faint antialiasing and glow pixels attached to their cutout.
        mask=(image[:,:,3]>0).astype(np.uint8)
    elif flat:
        mask = ((np.linalg.norm(image[:,:,:3].astype(float)-color,axis=2)>25) & (image[:,:,3]>10)).astype(np.uint8)
    else:return []
    count, labels, stats, _ = cv2.connectedComponentsWithStats(mask,8)
    return [labels==i for i in range(1,count) if 50 <= stats[i,cv2.CC_STAT_AREA] < image.shape[0]*image.shape[1]*.85][:100]


def split_mask(image, req: SplitRequest):
    height,width = image.shape[:2]
    if req.method == 'sam':
        return local_models.sam_mask(image,req.box,req.points)
    if req.method == 'auto':
        masks = components(image)
        if local_models.status()['sam'] and not masks:
            # Bound peak memory. Coordinates are restored to the source resolution.
            scale = min(1,1536/max(height,width))
            small = cv2.resize(image,(max(1,round(width*scale)),max(1,round(height*scale))))
            masks = [cv2.resize(m.astype(np.uint8),(width,height),interpolation=cv2.INTER_NEAREST)>0
                     for m in local_models.sam_mask(small,automatic=True)]
        return masks
    mask = np.zeros((height,width),np.uint8)
    if req.method in ('box','rectangle'):
        if not req.box:
            raise ValueError('需要框选区域')
        x0,y0,x1,y1 = [round(x) for x in req.box]
        x0,x1=sorted((max(0,min(width,x0)),max(0,min(width,x1))))
        y0,y1=sorted((max(0,min(height,y0)),max(0,min(height,y1))))
        if x1-x0<2 or y1-y0<2:
            raise ValueError('区域过小')
        if req.method=='box' and local_models.status()['sam']:
            return local_models.sam_mask(image,[x0,y0,x1,y1])
        # A manual rectangular cut is exact, but not advertised as semantic segmentation.
        mask[y0:y1,x0:x1]=1
    elif req.method == 'brush':
        for point in req.points:
            if len(point)!=2:
                raise ValueError('画笔坐标不正确')
            cv2.circle(mask,tuple(map(round,point)),round(req.radius),1,-1)
        for a,b in zip(req.points,req.points[1:]):
            cv2.line(mask,tuple(map(round,a)),tuple(map(round,b)),1,round(req.radius*2))
    elif req.method == 'point':
        if not req.points:
            raise ValueError('需要选择一个点')
        if local_models.status()['sam']:
            return local_models.sam_mask(image,points=req.points)
        x,y = map(round,req.points[0])
        if not (0<=x<width and 0<=y<height):
            raise ValueError('点不在素材内')
        flood=np.zeros((height+2,width+2),np.uint8)
        cv2.floodFill(image[:,:,:3].copy(),flood,(x,y),(0,0,0),loDiff=(18,18,18),upDiff=(18,18,18),flags=cv2.FLOODFILL_MASK_ONLY|8|(1<<8))
        mask=flood[1:-1,1:-1]
    return [mask>0] if mask.any() else []


def apply_masks(project, layer: LayerElement, image, masks, fill='local'):
    """Disjoint alpha cutouts and one repaired residual; original never remains underneath."""
    h,w=image.shape[:2]
    taken=np.zeros((h,w),bool)
    output=[]
    # Small masks first keeps nested foregrounds independently selectable.
    for mask in sorted(masks,key=lambda m:np.count_nonzero(m)):
        mask=np.asarray(mask,dtype=bool)&~taken&(image[:,:,3]>0)
        area=np.count_nonzero(mask)
        if area<4 or area>=h*w*.98:
            continue
        taken|=mask
        # Keep a full-size transparent plane to preserve arbitrary layer transforms.
        cut=image.copy()
        cut[:,:,3]=np.where(mask,image[:,:,3],0)
        alpha=np.where(mask,255,0).astype(np.uint8)
        child=layer.model_copy(deep=True)
        child.id=uid(); child.parent_id=layer.id; child.group_id=None
        child.name=f'{layer.name} · 对象 {len(output)+1}'
        child.asset=save_image(project,cut)
        child.restoration_asset=child.asset
        child.mask=save_image(project,alpha,'mask')
        child.z=layer.z+(len(output)+1)*.001
        child.source='local-segmentation'; child.edited=True
        child.needs_review=True; child.notes=['遮罩需检查；透明素材支持继续拆分']
        output.append(child)
    if not output:
        raise ValueError('本地未识别到可分离对象，请框选或用遮罩画笔校正')
    residual=image.copy()
    color,flat=background_color(image)
    inferred=False
    ring=(cv2.dilate(taken.astype(np.uint8),np.ones((5,5),np.uint8))>0)&~taken
    transparent_surround=bool(ring.any() and np.mean(image[:,:,3][ring]<10)>.9)
    if fill=='transparent' or transparent_surround:
        # Isolated RGBA objects already have a known transparent backdrop.
        # Filling their old alpha plane with a hidden RGB colour creates ghosts.
        residual[:,:,3][taken]=0
    elif flat:
        residual[:,:,:3][taken]=color
    else:
        # Include object edges in the inpaint mask to avoid fringes/ghosts.
        repair=cv2.dilate(taken.astype(np.uint8),np.ones((3,3),np.uint8))*255
        repaired=cv2.inpaint(image[:,:,:3],repair,3,cv2.INPAINT_TELEA)
        # The cutouts cover exactly `taken`. Never change uncovered pixels or
        # the recomposed slide gains a visible halo around every segment.
        residual[:,:,:3][taken]=repaired[taken]
        inferred=True
    base=layer.model_copy(deep=True)
    base.asset=save_image(project,residual,'residual')
    base.restoration_asset=layer.restoration_asset or layer.asset
    base.mask=save_image(project,taken.astype(np.uint8)*255,'removed')
    base.name=f'{layer.name} · 剩余内容'
    base.inferred=layer.inferred or inferred; base.needs_review=True; base.edited=True
    base.notes=['保留残余内容，请检查是否仍有待拆对象']+(['本地推断补全，需人工确认，不代表原隐藏内容'] if inferred else [])
    return [base,*output]


def restore_ocr_text(layer,image,records):
    """Fit and clear upright OCR glyphs on a pixel-sized temporary scene."""
    warnings=[];text_layers=[];work=image.copy()
    mask=np.zeros(image.shape[:2],np.uint8)
    transparent_seeds=np.zeros(image.shape[:2],bool)
    transparent_allowed=np.zeros(image.shape[:2],bool)
    for text,score,poly in records:
        # Large display lettering is often detected as separate radicals or
        # individual words. Keep its complete artwork until a whole-text
        # explanation has been verified, instead of silently creating fragments.
        if layer.content_role!='content' and len(records)>1 and cv2.boundingRect(poly)[3]>=max(48,image.shape[0]*.07):
            layer.recognized_text=(layer.recognized_text+'\n'+text).strip()[:4000]
            warnings.append('大标题或艺术字按完整素材保留，尚未确认整词字形；未拆成单字或偏旁')
            continue
        if score<.88:
            warnings.append('存在低置信度图片文字，原区域保留，请手工校正')
            continue
        if layer.content_role!='content' and not any(c.isalnum() for c in text):
            # An icon stroke can score highly as "-", "+" or an arrow. OCR
            # confidence does not establish that the stroke is a text object.
            # Preserve its pixels unless the user explicitly requests text.
            warnings.append('仅识别出标点或符号，可能属于图标；原素材完整保留，需确认后校正')
            continue
        x,y,w,h=cv2.boundingRect(poly)
        x=max(0,x);y=max(0,y);w=min(w,image.shape[1]-x);h=min(h,image.shape[0]-y)
        if w<1 or h<1:continue
        sx=layer.width/image.shape[1]; sy=layer.height/image.shape[0]
        # Estimate background outside the detected text, where white
        # glyphs cannot win the dominant-colour vote in a tight box.
        pad=max(2,round(h*.12));left=max(0,x-pad);right=min(image.shape[1],x+w+pad)
        top=max(0,y-pad);bottom=min(image.shape[0],y+h+pad)
        rgba_context=image[top:bottom,left:right]
        context,_=local_models.visible_rgb(rgba_context,local_models.ocr_background(rgba_context))
        roi=context[y-top:y-top+h,x-left:x-left+w]
        ring=np.ones(context.shape[:2],bool);ring[y-top:y-top+h,x-left:x-left+w]=False
        samples=context[ring] if ring.any() else roi.reshape(-1,3)
        quant=(samples//16).reshape(-1,3)
        colors,counts=np.unique(quant,axis=0,return_counts=True)
        dominant=colors[counts.argmax()]
        background=np.median(samples[np.all(samples//16==dominant,axis=1)],axis=0)
        difference=np.linalg.norm(roi.astype(float)-background,axis=2)
        ink,ink_color=text_foreground(roi,background,min_extent=(.35,.4))
        if ink.sum()<3:
            layer.recognized_text=(layer.recognized_text+'\n'+text).strip()[:4000]
            warnings.append('已识别文字但字形前景不可靠，原字保留，请局部校正')
            continue
        ys,xs=np.where(ink)
        source=image[y:y+h,x:x+w]
        coverage=source[:,:,3][ink]
        alpha=float(np.quantile(coverage,.95))/255
        core=ink&(source[:,:,3]>=max(1,round(alpha*255*.8)))
        source_color=np.median(source[:,:,:3][core],axis=0).astype(int) if core.any() else ink_color
        text_color='#'+''.join(f'{v:02x}' for v in source_color)
        font='Microsoft YaHei' if any(ord(c)>127 for c in text) else 'Arial'
        fontfile=Path('C:/Windows/Fonts/msyh.ttc' if font=='Microsoft YaHei' else 'C:/Windows/Fonts/arial.ttf')
        estimated=h*.78
        tx=x;ty=y;bold=False;italic=False;spacing_note=[]
        if fontfile.exists():
            import fitz
            measure=ImageFont.truetype(str(fontfile),1000)
            bbox=measure.getbbox(text,anchor='ls')
            estimated=min((xs.max()-xs.min()+1)*1000/max(1,measure.getlength(text)),(ys.max()-ys.min()+1)*1000/max(1,bbox[3]-bbox[1]))
            baseline=y+ys.min()-bbox[1]*estimated/1000
            tx=x+xs.min()-bbox[0]*estimated/1000
            ty=baseline-(fitz.Font(fontfile=str(fontfile)).ascender-.14)*estimated
            if len(text)<=100:
                from .text_recovery import fit_font,fit_with_word_spaces
                glyph=(ink.astype(np.uint8)*255)[ys.min():ys.max()+1,xs.min():xs.max()+1]
                fit=fit_font(text,glyph)
                raw_text=text
                text,fit=fit_with_word_spaces(text,glyph,fit)
                if text!=raw_text:spacing_note=[f'根据原图间隙与字形匹配补回空格；OCR原文：{raw_text}']
                if fit and fit['score']>=.75:
                    font=fit['font'];bold=fit['bold'];italic=fit['italic'];estimated=fit['pixel_size']
                    tx=x+xs.min();ty=y+ys.min()+fit['baseline']-(fitz.Font(fontfile=fit['file']).ascender-.14)*estimated
        text_layers.append(LayerElement(kind='text',name=text[:24],text=text,
            x=layer.x+tx*sx,y=layer.y+ty*sy,width=max(w*sx*1.1,1),height=max(h*sy*1.5,1),
            font=font,color=text_color,bold=bold,italic=italic,font_size=max(1,estimated*sy),z=layer.z+.5+len(text_layers)*.0001,
            opacity=layer.opacity*alpha,
            source='local-ocr',confidence=score,needs_review=True,
            source_ink_bbox=[layer.x+(x+xs.min())*sx,layer.y+(y+ys.min())*sy,layer.x+(x+xs.max()+1)*sx,layer.y+(y+ys.max()+1)*sy],
            notes=['OCR 文字、字体、颜色与位置需要校正',*spacing_note]))
        # OCR boxes are tight around foreground glyphs. Include their
        # local context when clearing antialiasing and black shadows.
        padded_ink=np.zeros(context.shape[:2],bool)
        padded_ink[y-top:y-top+h,x-left:x-left+w]=ink
        removal=text_removal_mask(context,padded_ink,background)
        # Restore this text's local background, never the page's global border colour.
        local_flat=np.mean(difference<20)>.45
        patch=work[top:bottom,left:right,:3]
        transparent_region=np.mean(image[top:bottom,left:right,3]<250)>.2
        if transparent_region:
            removal=transparent_text_removal(image[top:bottom,left:right,3],padded_ink)
            work[top:bottom,left:right,3][removal]=0
            transparent_seeds[top:bottom,left:right]|=padded_ink
            transparent_allowed[top:bottom,left:right]=True
        elif local_flat:patch[removal]=background.astype(np.uint8)
        else:
            repaired=cv2.inpaint(context,removal.astype(np.uint8)*255,3,cv2.INPAINT_TELEA)
            patch[removal]=repaired[removal]
            layer.inferred=True
        mask[top:bottom,left:right][removal]=255
    if transparent_seeds.any():
        complete=complete_transparent_text_removal(image[:,:,3],transparent_seeds,transparent_allowed)
        work[:,:,3][complete]=0;mask[complete]=255
    return work,text_layers,warnings,bool(mask.any())


def map_ocr_layer(text,turns,parent,width,height):
    """Convert pixel text geometry to the parent's top-left rotation convention."""
    import math
    origin=local_models.quarter_turn_points([[text.x,text.y]],turns,width,height)[0]
    basis=local_models.quarter_turn_points([[0,0],[1,0],[0,1]],turns,width,height)
    u=basis[1]-basis[0];v=basis[2]-basis[0]
    scale=np.array([parent.width/width,parent.height/height])
    angle=math.radians(parent.rotation)
    matrix=np.array([[math.cos(angle),-math.sin(angle)],[math.sin(angle),math.cos(angle)]])
    point=matrix@(origin*scale)+np.array([parent.x,parent.y])
    horizontal=matrix@(u*scale);vertical=matrix@(v*scale)
    text.x,text.y=map(float,point)
    text.rotation=math.degrees(math.atan2(horizontal[1],horizontal[0]))
    text.width*=float(np.linalg.norm(horizontal));text.height*=float(np.linalg.norm(vertical))
    text.font_size=max(1,text.font_size*float(np.linalg.norm(vertical)))
    if text.source_ink_bbox:
        x0,y0,x1,y1=text.source_ink_bbox
        corners=local_models.quarter_turn_points([[x0,y0],[x1,y0],[x1,y1],[x0,y1]],turns,width,height)
        corners=(corners*scale)@matrix.T+np.array([parent.x,parent.y])
        text.source_ink_bbox=[*corners.min(axis=0).tolist(),*corners.max(axis=0).tolist()]
    return text


def auto_image(project, layer,segment=True):
    layer.restoration_asset=layer.restoration_asset or layer.asset
    image=read_image(project,layer.asset)
    from .logo_policy import classify_image,NOTE
    classify_image(layer,image)
    if layer.content_role=='logo':return [layer],[NOTE]
    warnings=[];text_layers=[];work=image.copy()
    from .embedded_marks import extract as extract_marks
    work,marks,mark_diagnostics=extract_marks(project,layer,work)
    if marks:warnings.append(f'已独立保留 {len(marks)} 个完整标识；其原位置背景由本地推断，请核对补全与裁剪边缘')
    if local_models.status()['ocr']:
        try:
            changed=False
            for turns,records in local_models.ocr_passes(work):
                upright=np.rot90(work,turns).copy()
                proxy=layer.model_copy(deep=True)
                proxy.x=proxy.y=proxy.rotation=0
                proxy.width=upright.shape[1];proxy.height=upright.shape[0]
                cleaned,texts,notes,modified=restore_ocr_text(proxy,upright,records)
                work=np.rot90(cleaned,-turns).copy()
                for text in texts:
                    text.z=layer.z+.5+len(text_layers)*.0001
                    text.parent_id=layer.id
                    text.restoration_asset=layer.restoration_asset or layer.asset
                    text_layers.append(map_ocr_layer(text,turns,layer,image.shape[1],image.shape[0]))
                layer.recognized_text=proxy.recognized_text
                warnings.extend(notes);changed|=modified;layer.inferred|=proxy.inferred
            if changed:layer.asset=save_image(project,work,'ocr-clean')
        except Exception as exc:
            # Keep successful passes and their matching cleaned raster together.
            # A later orientation failure must not put a second old glyph below them.
            if text_layers:layer.asset=save_image(project,work,'ocr-clean')
            warnings.append(f'本地 OCR 失败：{type(exc).__name__}；原图已保留，未使用云端')
    else:
        warnings.append('本地 OCR 模型未安装，图片文字仍需处理')
    # Once every visible pixel became text, retaining a selectable empty
    # bitmap adds an apparent object without representing any source content.
    if not work[:,:,3].any():return [*text_layers,*marks],warnings
    if not segment:
        layer.needs_review=True
        return [layer,*text_layers,*marks],warnings
    geometry=[]
    try:
        from .geometry_recovery import recover_circles
        work,geometry,diagnostics=recover_circles(layer,work)
        if geometry:
            layer.asset=save_image(project,work,'geometry-clean')
            warnings.append(f'已从可见圆弧推断 {len(geometry)} 个完整圆形，轮廓与透明颜色需人工确认')
    except (ValueError,RuntimeError,cv2.error):
        warnings.append('简单装饰几何尚未可靠还原，原素材保留，请手工校正')
    # Automatic SAM and connected components are mask proposals, not evidence
    # that each mask is a complete icon, word or object. Only apply those after
    # the user has reviewed and combined the parts of one intended object.
    layer.needs_review=True
    layer.notes.append('复杂图标与艺术字保留整体；可查找候选并确认完整对象，不自动拆出碎片')
    warnings.append('未确认完整边界的图标、艺术字与图片内部对象按原素材保留，仍需校正')
    return [layer,*geometry,*text_layers,*marks],warnings


def merge_images(project,page,ids):
    selected=sorted([l for l in page.layers if l.id in ids],key=lambda l:l.z)
    if len(selected)<2 or any(l.kind!='image' or l.locked for l in selected):
        raise ValueError('仅能合并未锁定的图片素材；文字和图形请使用组合')
    geometry=lambda l:(l.x,l.y,l.width,l.height,l.rotation)
    if any(geometry(l)!=geometry(selected[0]) for l in selected):
        raise ValueError('仅支持合并同一位置、尺寸与旋转的分层素材，请先恢复共同位置或使用组合')
    base=selected[0].model_copy(deep=True);base.id=uid();base.name='合并素材'
    canvas=None
    for layer in selected:
        bitmap=Image.fromarray(read_image(project,layer.asset))
        if canvas is None:canvas=Image.new('RGBA',bitmap.size)
        if bitmap.size!=canvas.size:bitmap=bitmap.resize(canvas.size,Image.Resampling.LANCZOS)
        bitmap.putalpha(bitmap.getchannel('A').point(lambda a:round(a*layer.opacity)))
        canvas=Image.alpha_composite(canvas,bitmap)
    base.asset=save_image(project,np.array(canvas),'merged');base.opacity=1;base.z=selected[-1].z
    base.inferred=any(l.inferred for l in selected);base.needs_review=True;base.edited=True
    base.source='manual-merge';base.mask=None;base.group_id=None
    page.layers=[l for l in page.layers if l.id not in ids]+[base]
    page.status='needs_review'
    return page


def repair_text(project,layer,request):
    """Replace an explicitly selected raster region; retain the original asset.

    This is a manual correction, never evidence of automatic transcription or
    exact recovery of the background hidden by the old glyphs.
    """
    if layer.kind!='image' or layer.locked or layer.rotation:
        raise ValueError('请选择未锁定、旋转为 0 的图片图层')
    if layer.content_role=='logo':raise ValueError('标识按整体保留；如需拆字，请先选择“作为普通素材处理”')
    image=read_image(project,layer.asset);height,width=image.shape[:2]
    left,top,right,bottom=request.box
    if not (0<=left<right<=width and 0<=top<bottom<=height):
        raise ValueError('文字选区必须完整位于素材内')
    x0,y0=int(np.floor(left)),int(np.floor(top));x1,y1=int(np.ceil(right)),int(np.ceil(bottom))
    region=image[y0:y1,x0:x1];work=image.copy()
    transparent=np.mean(region[:,:,3]<250)>.15
    if transparent:
        work[y0:y1,x0:x1,3]=0
    else:
        mask=np.zeros((height,width),np.uint8);mask[y0:y1,x0:x1]=255
        if np.all(mask):raise ValueError('不透明素材需要保留选区外的背景，请缩小文字选区')
        work[:,:,:3]=cv2.inpaint(image[:,:,:3],mask,3,cv2.INPAINT_TELEA)
    base=layer.model_copy(deep=True);base.asset=save_image(project,work,'text-repaired')
    base.restoration_asset=layer.restoration_asset or layer.asset
    base.edited=True;base.needs_review=True;base.inferred=layer.inferred or not transparent
    base.notes=[*layer.notes,'人工框选文字区域已移除，原素材保留用于对照']
    if not transparent:base.notes.append('文字底部由本地算法推断补全，需人工确认')
    sx,sy=layer.width/width,layer.height/height
    native=LayerElement(kind='text',name=request.text[:30],text=request.text,
        x=layer.x+left*sx,y=layer.y+top*sy,width=max((right-left)*sx,request.font_size),height=max((bottom-top)*sy,request.font_size*1.4),
        font=request.font,font_size=request.font_size,color=request.color,z=layer.z+.0001,
        opacity=layer.opacity,visible=layer.visible,parent_id=layer.id,group_id=layer.group_id,
        source='manual-text-repair',edited=True,needs_review=True,
        notes=['人工录入文字；请核对字体、字号、标点、位置与清除边界'])
    return [base,native]
