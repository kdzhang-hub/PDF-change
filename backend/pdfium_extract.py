"""Preserve PDF paint contributions, including blend modes, as separate assets.

Each asset is derived from exactly one paint action against its preceding state.
No final-page screenshot is inserted behind the foreground. Context-dependent
blend conversion is explicitly marked and requires a movement check.
"""
from __future__ import annotations
import ctypes,math
import fitz
import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as raw
from PIL import Image
from .models import LayerElement,PageScene
from .store import project_dir
from .raster import save_image


def convert_paint(project,index,original,scale=3):
    from .extract import font_name
    source=fitz.open(project_dir(project)/'source.pdf');fp=source[index]
    doc=pdfium.PdfDocument(str(project_dir(project)/'source.pdf'));page=doc[index]
    width,height=fp.rect.width,fp.rect.height
    if page.get_rotation()!=0:
        page.close();doc.close();source.close()
        raise ValueError('复杂旋转页需要先规范旋转')
    spans=[(s,line) for b in fp.get_text('dict')['blocks'] if b['type']==0 for line in b['lines'] for s in line['spans'] if s['text'].strip()]
    objects=list(page.get_objects(max_depth=1));actions=[]
    for obj in objects:
        bounds=obj.get_bounds();left,bottom,right,top=bounds
        match=None
        if obj.type==raw.FPDF_PAGEOBJ_TEXT:
            cx=(left+right)/2;cy=height-(top+bottom)/2
            candidates=[(i,s,line) for i,(s,line) in enumerate(spans) if fitz.Rect(s['bbox']).contains(fitz.Point(cx,cy))]
            if candidates:match=min(candidates,key=lambda v:abs(v[1]['bbox'][0]-left))[0]
        if match is not None and actions and actions[-1]['span']==match:
            actions[-1]['objects'].append(obj)
            l,b,r,t=actions[-1]['bounds'];actions[-1]['bounds']=(min(l,left),min(b,bottom),max(r,right),max(t,top))
        else:actions.append({'objects':[obj],'span':match,'bounds':bounds})
        if not raw.FPDFPageObj_SetIsActive(obj.raw,False):raise RuntimeError('PDFium 无法隔离绘制对象')
    W=round(width*scale);H=round(height*scale)
    layers=[];used=set();warnings=[]
    try:
        previous_objects=[]
        for z,action in enumerate(actions):
            left,bottom,right,top=action['bounds'];padding=3
            x0=max(0,math.floor((left-padding)*scale));x1=min(W,math.ceil((right+padding)*scale))
            y0=max(0,math.floor((height-top-padding)*scale));y1=min(H,math.ceil((height-bottom+padding)*scale))
            if x1<=x0 or y1<=y0:
                for obj in action['objects']:raw.FPDFPageObj_SetIsActive(obj.raw,True)
                previous_objects.extend(action['objects'])
                continue
            # Before/after must use the identical crop and render transform.
            # Reusing a page canvas assembled from differently cropped renders
            # introduced backdrop resampling differences into later objects.
            prior=page.render(scale=scale,crop=(x0/scale,(H-y1)/scale,(W-x1)/scale,y0/scale),fill_color=(255,255,255,255))
            before=np.array(prior.to_pil().convert('RGB'))[:y1-y0,:x1-x0];prior.close()
            for obj in action['objects']:
                if not raw.FPDFPageObj_SetIsActive(obj.raw,True):raise RuntimeError('PDFium 无法恢复绘制对象')
            bitmap=page.render(scale=scale,crop=(x0/scale,(H-y1)/scale,(W-x1)/scale,y0/scale),fill_color=(255,255,255,255))
            current=np.array(bitmap.to_pil().convert('RGB'));bitmap.close()
            # Floating-point crop rounding can add one pixel in PDFium.
            current=current[:y1-y0,:x1-x0]
            if current.shape[:2]!=(y1-y0,x1-x0):raise RuntimeError('PDFium 裁剪尺寸不一致')
            change=np.max(np.abs(current.astype(np.int16)-before.astype(np.int16)),axis=2)>0
            if not change.any():
                # Gradient WordArt PDFs contain text paint actions whose clip
                # has no visible contribution. Emitting their extracted span
                # creates a black duplicate behind the actual gradient asset.
                previous_objects.extend(action['objects'])
                continue
            if action['span'] is not None:
                previous_objects.extend(action['objects'])
                si=action['span']
                if si in used:continue
                used.add(si);span,line=spans[si];direction=line.get('dir',(1,0));angle=math.degrees(math.atan2(direction[1],direction[0]));size=span['size'];quad=fitz.recover_quad(direction,span);x,y=quad.ul
                x-=math.sin(math.radians(angle))*size*.14;y+=math.cos(math.radians(angle))*size*.14
                layers.append(LayerElement(kind='text',name=span['text'][:30],text=span['text'],x=x,y=y,width=max(1,abs(quad.ur-quad.ul)+size*.12),height=max(1,size*1.3),rotation=angle,z=z,
                    font=font_name(span['font']),font_size=size,bold=bool(span['flags']&16),italic=bool(span['flags']&2),color=f"#{span['color']:06x}",source='pdf-native'))
                layers[-1].source_ink_bbox=[left,height-top,right,height-bottom]
                continue
            B=before.astype(np.float32)/255;C=current.astype(np.float32)/255;delta=C-B
            # Smallest ordinary-alpha contribution that reproduces this paint,
            # even when the PDF used Screen/ColorDodge/etc. at this location.
            amount=np.where(delta>=0,delta/np.maximum(1-B,1e-7),-delta/np.maximum(B,1e-7)).max(axis=2)
            # Retain the object's real coverage. Minimal alpha alone amplifies
            # quantization and interpolation errors on dark, textured pages.
            for previous in previous_objects:raw.FPDFPageObj_SetIsActive(previous.raw,False)
            isolated=page.render(scale=scale,crop=(x0/scale,(H-y1)/scale,(W-x1)/scale,y0/scale),fill_color=(0,0,0,0))
            isolated_pixels=np.array(isolated.to_pil().convert('RGBA'))[:y1-y0,:x1-x0]
            natural=isolated_pixels[:,:,3].astype(np.float32)/255
            isolated.close()
            for previous in previous_objects:raw.FPDFPageObj_SetIsActive(previous.raw,True)
            previous_objects.extend(action['objects'])
            amount=np.maximum(amount,natural)
            alpha=np.ceil(np.clip(amount,0,1)*255)/255
            alpha[natural==0]=0
            # Keep coverage even where this paint happens to match its backdrop.
            # Punching holes there is pixel-exact at the extraction resolution
            # but produces halos/noise when Office resamples overlapping assets.
            rgb=np.clip((C-B*(1-alpha[:,:,None]))/np.maximum(alpha[:,:,None],1/255),0,1)
            pixels=np.dstack((np.rint(rgb*255).astype(np.uint8),np.rint(alpha*255).astype(np.uint8)))
            predicted=isolated_pixels[:,:,:3].astype(np.float32)*natural[:,:,None]+before*(1-natural[:,:,None])
            visible=natural>.01
            ordinary_error=np.abs(predicted-current)[visible]
            ordinary=bool(ordinary_error.size and ordinary_error.mean()<.65 and np.percentile(ordinary_error,99)<3)
            if ordinary:
                # Most paints already use ordinary alpha. Preserve the original
                # smooth colour field instead of inversely solving quantized RGB.
                pixels=isolated_pixels
                alpha=natural
            ys,xs=np.where(alpha>0);bx0,bx1=xs.min(),xs.max()+1;by0,by1=ys.min(),ys.max()+1
            pixels=pixels[by0:by1,bx0:bx1]
            is_context=not ordinary and any(raw.FPDFPageObj_HasTransparency(o.raw) for o in action['objects'])
            original_type={1:'text',2:'path',3:'image',4:'shading',5:'form'}.get(action['objects'][0].type)
            if ordinary and len(action['objects'])==1 and original_type=='image' and left>=0 and bottom>=0 and right<=width and top<=height:
                # Avoid an unnecessary upsample/downsample cycle for photographs,
                # backgrounds, and raster text. Validate mask coverage against the
                # full renderer before using PDFium's native-resolution bitmap.
                try:
                    native_bitmap=action['objects'][0].get_bitmap(render=True)
                    native_image=native_bitmap.to_pil().convert('RGBA').copy()
                    # The independent PIL copy no longer references the foreign buffer.
                    native_bitmap.warn_on_close=False;native_bitmap.close()
                    nx0=round(left*scale)-x0;ny0=round((height-top)*scale)-y0
                    nw=max(1,round((right-left)*scale));nh=max(1,round((top-bottom)*scale))
                    check=Image.new('RGBA',(x1-x0,y1-y0))
                    check.alpha_composite(native_image.resize((nw,nh),Image.Resampling.BICUBIC),(nx0,ny0))
                    check_pixels=np.array(check);valid=natural>.1
                    alpha_error=np.mean(np.abs(check_pixels[:,:,3].astype(float)-isolated_pixels[:,:,3]))
                    color_error=np.mean(np.abs(check_pixels[:,:,:3].astype(float)-isolated_pixels[:,:,:3])[valid]) if valid.any() else 100
                    if alpha_error<2 and color_error<4:
                        layers.append(LayerElement(kind='image',name=f'原始清晰素材 {z+1}',x=left,y=height-top,width=right-left,height=top-bottom,z=z,
                            asset=save_image(project,np.array(native_image),'native-image'),source='pdf-native-image',needs_review=True,original_type='image',
                            notes=['保留原始像素分辨率、变换与透明蒙版；图片文字仍需检查']))
                        continue
                except (RuntimeError,ValueError):pass
            layers.append(LayerElement(kind='image',name=f'独立绘制对象 {z+1}',x=(x0+bx0)/scale,y=(y0+by0)/scale,width=pixels.shape[1]/scale,height=pixels.shape[0]/scale,z=z,
                asset=save_image(project,pixels,'paint-exact'),source='pdf-context-paint' if is_context else 'pdf-paint',needs_review=True,
                original_type=original_type,
                notes=['保留实际绘制顺序、裁剪与透明效果；内部文字与子对象仍需检查']+(['PDF 混合效果已转换为当前位置的普通透明素材，移动后需复核外观'] if is_context else [])))
        if len(used)<len(spans):warnings.append(f'{len(spans)-len(used)} 组原生文字未独立匹配，需校正')
        warnings.append('复杂对象已独立保留；图片内文字与子对象尚需检查，不计为完全可编辑')
        return PageScene(index=index,width=width,height=height,original=original,layers=layers,status='needs_review',warnings=warnings)
    finally:
        page.close();doc.close();source.close()
