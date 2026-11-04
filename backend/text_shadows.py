"""Fit a raster PDF text shadow to its real source glyph, then make it live.

Never attach a black decoration by proximity alone. Shape agreement is checked
against the isolated PDF glyph, so changing text or moving it cannot leave the
old shadow bitmap behind.
"""
import math
import cv2,numpy as np
from PIL import Image
import pypdfium2 as pdfium,pypdfium2.raw as raw
from .models import TextShadow
from .store import asset_path,project_dir


def moments(alpha):
    total=alpha.sum()
    if total<1:return None
    ys,xs=np.indices(alpha.shape);x=float((xs*alpha).sum()/total);y=float((ys*alpha).sum()/total)
    return x,y,float((((xs-x)**2+(ys-y)**2)*alpha).sum()/total/2)


def fit_shadow(glyph,target,scale,font_size,min_agreement=.84):
    glyph=glyph.astype(np.float32)/255;target=target.astype(np.float32)/255
    a=moments(glyph);b=moments(target)
    if a is None or b is None:return None
    dx,dy=b[0]-a[0],b[1]-a[1];sigma=math.sqrt(max(0,b[2]-a[2]))
    if max(abs(dx),abs(dy))/scale>font_size*.6 or sigma/scale>font_size*.5:return None
    # Native and embedded bitmap renders use different antialiasing grids.
    # Fit blur and translation rather than trusting their second moments alone.
    padding=max(3,round(scale*font_size*.3));padded=np.pad(target,padding)
    best=None
    for deviation in sorted(set([0.,sigma,*[scale*v for v in (.2,.4,.6,.8,1.,1.4,1.8,2.4,3.)]])):
        blurred=cv2.GaussianBlur(glyph,(0,0),max(.01,deviation))
        correlation=cv2.matchTemplate(padded,blurred,cv2.TM_CCORR_NORMED)
        _,_,_,position=cv2.minMaxLoc(correlation);shift=(position[0]-padding,position[1]-padding)
        predicted=cv2.warpAffine(blurred,np.array([[1,0,shift[0]],[0,1,shift[1]]],np.float32),(glyph.shape[1],glyph.shape[0]))
        opacity=float((predicted*target).sum()/max(1e-6,(predicted**2).sum()))
        if not .05<=opacity<=1.05:continue
        predicted*=min(1,opacity)
        agreement=float(np.minimum(predicted,target).sum()/max(1e-6,np.maximum(predicted,target).sum()))
        if best is None or agreement>best[0]:best=(agreement,deviation,shift,opacity)
    if best is None:return None
    agreement,sigma,(dx,dy),opacity=best
    if agreement<min_agreement:return None
    return TextShadow(opacity=round(min(1,opacity),4),blur=round(sigma*2/scale,4),dx=round(dx/scale,4),dy=round(dy/scale,4)),agreement


def restore_text_shadows(project,scene):
    result=scene.model_copy(deep=True);pairs=[]
    texts=[l for l in result.layers if l.kind=='text' and l.source_ink_bbox and not l.text_shadow and not l.rotation and not l.edited]
    for layer in result.layers:
        if layer.kind!='image' or layer.content_role=='logo' or layer.original_type!='image' or layer.rotation or layer.edited:continue
        choices=[]
        for text in texts:
            box=text.source_ink_bbox
            if 0<text.z-layer.z<=2 and layer.x<=box[0] and layer.y<=box[1] and layer.x+layer.width>=box[2] and layer.y+layer.height>=box[3]:choices.append(text)
        if len(choices)!=1:continue
        image=np.array(Image.open(asset_path(project,layer.asset)).convert('RGBA'));mask=image[:,:,3]>15
        if mask.sum()<20 or not 30<image[:,:,3].max()<235:continue
        colors=image[:,:,:3][mask]
        if np.mean(colors.max(axis=1)<12)<.99:continue
        pairs.append((layer,choices[0],image[:,:,3]))
    if not pairs:return result,[]
    groups={}
    for layer,text,alpha in pairs:groups.setdefault(text.id,[]).append((layer,text,alpha))
    doc=pdfium.PdfDocument(str(project_dir(project)/'source.pdf'));page=doc[scene.index];objects=list(page.get_objects(max_depth=1));accepted=[]
    try:
        for obj in objects:raw.FPDFPageObj_SetIsActive(obj.raw,False)
        for members in groups.values():
            layer,text,_=members[0]
            left=min(l.x for l,_,_ in members);top=min(l.y for l,_,_ in members)
            right=max(l.x+l.width for l,_,_ in members);bottom=max(l.y+l.height for l,_,_ in members)
            scale=max(alpha.shape[1]/l.width for l,_,alpha in members)
            target=np.zeros((max(1,round((bottom-top)*scale)),max(1,round((right-left)*scale))),np.float32)
            for item,_,alpha in members:
                mask=np.array(Image.fromarray(alpha).resize((max(1,round(item.width*scale)),max(1,round(item.height*scale))),Image.Resampling.BILINEAR)).astype(np.float32)/255
                x=round((item.x-left)*scale);y=round((item.y-top)*scale);h=min(mask.shape[0],target.shape[0]-y);w=min(mask.shape[1],target.shape[1]-x)
                target[y:y+h,x:x+w]=1-(1-target[y:y+h,x:x+w])*(1-mask[:h,:w])
            alpha=np.round(target*255).astype(np.uint8)
            layer=layer.model_copy(update={'x':left,'y':top,'width':right-left,'height':bottom-top})
            box=text.source_ink_bbox;selected=[]
            for obj in objects:
                if obj.type!=raw.FPDF_PAGEOBJ_TEXT:continue
                left,bottom,right,top=obj.get_bounds();cx=(left+right)/2;cy=scene.height-(top+bottom)/2
                if box[0]-.1<=cx<=box[2]+.1 and box[1]-.1<=cy<=box[3]+.1:selected.append(obj)
            if not selected:continue
            for obj in selected:raw.FPDFPageObj_SetIsActive(obj.raw,True)
            scale=alpha.shape[1]/layer.width
            crop=(max(0,layer.x),max(0,scene.height-layer.y-layer.height),max(0,scene.width-layer.x-layer.width),max(0,layer.y))
            bitmap=page.render(scale=scale,crop=crop,fill_color=(0,0,0,0))
            glyph=np.array(bitmap.to_pil().convert('RGBA').resize((alpha.shape[1],alpha.shape[0]),Image.Resampling.BILINEAR))[:,:,3];bitmap.close()
            for obj in selected:raw.FPDFPageObj_SetIsActive(obj.raw,False)
            fit=fit_shadow(glyph,alpha,scale,text.font_size)
            if fit:
                shadow,agreement=fit;text.text_shadow=shadow;text.needs_review=True
                text.notes.append(f'原阴影按真实字形匹配 {agreement:.3f}，已改为随文字变化的原生阴影；原素材 {layer.asset} 保留对照')
                accepted.append({'shadow_ids':[l.id for l,_,_ in members],'text_id':text.id,'text':text.text,'agreement':agreement,'shadow':shadow.model_dump()})
        remove={identity for row in accepted for identity in row['shadow_ids']};result.layers=[l for l in result.layers if l.id not in remove]
        if accepted:result.warnings.append(f'{len(accepted)} 个文字阴影已与文本合并，请检查字体及移动后效果')
        return result,accepted
    finally:
        page.close();doc.close()
