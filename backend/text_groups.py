"""Recover one editable text object from verified PDF paint fragments.

This path uses only the input PDF's own text and local font shapes. It does not
use a reference presentation, recognize unknown words, or declare full coverage.
"""
import cv2,numpy as np
from PIL import Image
from .models import LayerElement
from .store import asset_path
from .text_recovery import source_text_hints,fit_font
from .text_shadows import fit_shadow


def rect(layer):return [layer.x,layer.y,layer.x+layer.width,layer.y+layer.height]


def containment(inner,outer):
    l,t,r,b=inner;left,top,right,bottom=outer
    return max(0,min(r,right)-max(l,left))*max(0,min(b,bottom)-max(t,top))/max(1,(r-l)*(b-t))


def plane(image,layer,bounds,scale):
    left,top,right,bottom=bounds
    canvas=Image.new('RGBA',(max(1,round((right-left)*scale)),max(1,round((bottom-top)*scale))))
    canvas.alpha_composite(Image.fromarray(image).resize((max(1,round(layer.width*scale)),max(1,round(layer.height*scale))),Image.Resampling.LANCZOS),
        (round((layer.x-left)*scale),round((layer.y-top)*scale)))
    return np.array(canvas)


def recover_pdf_text_groups(project,scene):
    result=scene.model_copy(deep=True);diagnostics=[]
    for hint in source_text_hints(project,scene.index):
        text=hint['text'];box=hint['box'];near=[];existing=[]
        for layer in result.layers:
            if layer.content_role=='logo':continue
            test_box=layer.source_ink_bbox if layer.kind=='text' and layer.source_ink_bbox else rect(layer)
            if layer.rotation or containment(test_box,[box[0]-4,box[1]-4,box[2]+4,box[3]+4])<.86:continue
            if layer.kind=='text' and layer.text==text:existing.append(layer)
            if layer.kind=='image' and layer.original_type in ('image','path','shading'):near.append(layer)
        # Never revise the user's manual edits or locked paints.
        if any(l.edited or l.locked for l in [*existing,*near]):continue
        if not near:continue
        candidates=[];images={}
        for layer in near:
            image=np.array(Image.open(asset_path(project,layer.asset)).convert('RGBA'));images[layer.id]=image
            alpha=image[:,:,3];opaque=alpha>160
            if opaque.sum()<15 or np.mean(alpha<30)<.12:continue
            if np.median(image[:,:,:3][opaque].max(axis=1))<55:continue
            ys,xs=np.where(alpha>100)
            target=alpha[ys.min():ys.max()+1,xs.min():xs.max()+1]
            fit=fit_font(text,target,hint['faces'])
            if fit and fit['score']>=.90:candidates.append((fit['score'],layer,fit,(xs.min(),ys.min(),xs.max()+1,ys.max()+1)))
        if not candidates:continue
        _,core,fit,(x0,y0,x1,y1)=max(candidates,key=lambda item:item[0])
        image=images[core.id];factor=core.height/image.shape[0]
        ink=[core.x+x0*factor,core.y+y0*factor,core.x+x1*factor,core.y+y1*factor]
        bounds=[min(l.x for l in near),min(l.y for l in near),max(l.x+l.width for l in near),max(l.y+l.height for l in near)]
        scale=min(3,1200/max(bounds[2]-bounds[0],bounds[3]-bounds[1]))
        reference=plane(image,core,bounds,scale)[:,:,3]
        radius=max(2,round(min(5,(ink[3]-ink[1])*.06)*scale))
        support=cv2.dilate((reference>100).astype(np.uint8),cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(radius*2+1,radius*2+1)))>0
        size=fit['pixel_size']*factor
        members=[];black=[];outlines=[];colored=[]
        for layer in near:
            pixels=plane(images[layer.id],layer,bounds,scale);visible=pixels[:,:,3]>15
            if visible.sum()<15:continue
            opaque=pixels[:,:,3]>180
            colors=pixels[:,:,:3][opaque if opaque.sum()>15 else visible]
            is_black=np.mean(colors.max(axis=1)<20)>.98
            # Shape support rejects a nearby filled plate or photo. Size alone
            # must not grant permission to remove a decorative object.
            if np.mean(support[visible])<.96:
                if not is_black or not fit_shadow(reference,pixels[:,:,3],scale,size):continue
            members.append(layer)
            if is_black:black.append(pixels[:,:,3])
            elif layer.id!=core.id:
                color=np.median(colors,axis=0).astype(int)
                thin=visible.sum()<np.count_nonzero(reference>100)*.5
                if thin:outlines.append((layer,color))
                elif np.mean(np.linalg.norm(colors-color,axis=1)<30)>.90:colored.append((pixels[:,:,3],color))
        if core.id not in {l.id for l in members}:continue
        # Office calibration will measure actual glyph bearings afterwards.
        import fitz
        baseline=core.y+(y0+fit['baseline'])*factor
        y=baseline-(fitz.Font(fontfile=fit['file']).ascender-.14)*size
        color=np.median(image[:,:,:3][image[:,:,3]>160],axis=0).astype(int)
        native=LayerElement(kind='text',name=text[:30],text=text,x=ink[0],y=y,
            width=max(ink[2]-ink[0]+size,size),height=size*1.5,z=max(l.z for l in members),
            font=fit['font'],font_size=size,bold=fit['bold'],italic=fit['italic'],
            color='#'+''.join(f'{v:02x}' for v in color),source='pdf-text-group',source_ink_bbox=ink,
            restoration_asset=core.asset,needs_review=True,
            notes=[f'PDF原文字与本地字形匹配{fit["score"]:.3f}；填充、描边与阴影关联为同一文字，需核对外观'])
        crop=image[y0:y1,x0:x1];stops=[]
        for fraction in (0,.33,.66,1):
            row=round((crop.shape[0]-1)*fraction);window=crop[max(0,row-2):row+3];colors=window[:,:,:3][window[:,:,3]>150]
            rgb=np.median(colors,axis=0).astype(int) if len(colors) else color
            stops.append('#'+''.join(f'{v:02x}' for v in rgb))
        if len(set(stops))>1:native.text_gradient=stops
        if outlines:
            outline,rgb=outlines[0];native.stroke='#'+''.join(f'{v:02x}' for v in rgb)
            native.stroke_width=min(3,max(.3,(outline.width-core.width)/2,(outline.height-core.height)/2))
        if black:
            alpha=np.zeros(reference.shape,float)
            for target in black:alpha=1-(1-alpha)*(1-target/255)
            found=fit_shadow(reference,np.round(alpha*255).astype(np.uint8),scale,size)
            if found:native.text_shadow=found[0]
            else:native.notes.append('原暗色文字效果未可靠拟合，已与旧字形一起移除，效果需校正')
        elif colored:
            for alpha,rgb in colored:
                found=fit_shadow(reference,alpha,scale,size)
                if found:
                    native.text_shadow=found[0];native.text_shadow.color='#'+''.join(f'{v:02x}' for v in rgb);break
        removed={l.id for l in [*members,*existing]}
        result.layers=[l for l in result.layers if l.id not in removed]+[native]
        diagnostics.append({'text':text,'native_id':native.id,'font_match':fit['score'],
            'removed_ids':list(removed),'unassociated_paint_ids':[l.id for l in near if l.id not in removed],
            'shadow':bool(native.text_shadow),'outline':native.stroke,'source_ink':ink})
    if diagnostics:result.warnings.append(f'{len(diagnostics)}组PDF文字绘制已合为可编辑文字；仍需检查遗漏和效果')
    return result,diagnostics
