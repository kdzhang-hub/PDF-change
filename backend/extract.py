from __future__ import annotations
import io
import math
import re
import json
import fitz
from PIL import Image
import numpy as np
from .models import LayerElement, PageScene, PathCommand, uid
from .store import project_dir,asset_path
from .raster import save_image,auto_image


def color(value):
    if value is None: return None
    if isinstance(value,int): return f'#{value:06x}'
    if len(value)==1: value=tuple(value)*3
    return '#'+''.join(f'{max(0,min(255,round(v*255))):02x}' for v in value[:3])


def prepare(project):
    from .imports import imported_image_frame
    with fitz.open(project_dir(project)/'source.pdf') as doc:
        if doc.needs_pass: raise ValueError('暂不支持加密 PDF，请先解密')
        if len(doc)>500: raise ValueError('单次最多导入 500 页')
        pages=[]
        for i,page in enumerate(doc):
            if page.rect.width*page.rect.height>50_000_000:
                raise ValueError('页面尺寸过大')
            zoom=min(1.5,1800/max(page.rect.width,page.rect.height))
            original=f'original-{i}.png'
            frame=imported_image_frame(project,i)
            if frame is None:
                page.get_pixmap(matrix=fitz.Matrix(zoom,zoom),alpha=False).save(asset_path(project,original))
            else:
                # Source comparison and pending pages must retain transparency,
                # including white paint which is invisible against a white PDF.
                frame.resize((round(page.rect.width*zoom),round(page.rect.height*zoom)),Image.Resampling.LANCZOS).save(asset_path(project,original))
            pages.append(PageScene(index=i,width=page.rect.width,height=page.rect.height,original=original))
        return pages


def font_name(name):
    name=re.sub(r'^[A-Z]{6}\+','',name)
    from .fonts import resolve
    return resolve(name)


def path_commands(drawing,rect):
    result=[]
    last=None
    def point(p):return [float(p.x-rect.x0),float(p.y-rect.y0)]
    for item in drawing['items']:
        op=item[0]
        if op=='re':
            r=item[1]
            ps=[r.tl,r.tr,r.br,r.bl] if len(item)<3 or item[2]>=0 else [r.tl,r.bl,r.br,r.tr]
            result.append(PathCommand(op='M',points=point(ps[0])))
            result.extend(PathCommand(op='L',points=point(p)) for p in ps[1:])
            result.append(PathCommand(op='Z')); last=None
        elif op=='qu':
            q=item[1]; ps=[q.ul,q.ur,q.lr,q.ll]
            result.append(PathCommand(op='M',points=point(ps[0])))
            result.extend(PathCommand(op='L',points=point(p)) for p in ps[1:])
            result.append(PathCommand(op='Z')); last=None
        elif op in ('l','c'):
            if last!=item[1]: result.append(PathCommand(op='M',points=point(item[1])))
            if op=='l': result.append(PathCommand(op='L',points=point(item[2]))); last=item[2]
            else: result.append(PathCommand(op='C',points=point(item[2])+point(item[3])+point(item[4]))); last=item[4]
        else: raise ValueError(f'不支持的路径 {op}')
    if drawing.get('closePath') and result and result[-1].op!='Z': result.append(PathCommand(op='Z'))
    return result


def convert_page(project,index,original):
    warnings=[]; layers=[]
    with fitz.open(project_dir(project)/'source.pdf') as doc:
        page=doc[index]
        if page.rotation: page.remove_rotation()
        from .imports import imported_image_frame
        frame=imported_image_frame(project,index)
        if frame is not None:
            # A normalized PDF is useful for page geometry, but its white
            # rendering cannot be used to decide whether an RGBA object exists.
            layer=LayerElement(kind='image',name=f'原始图片 {index+1}',x=0,y=0,
                width=page.rect.width,height=page.rect.height,z=0,
                asset=save_image(project,np.array(frame),'input-rgba'),source='image-input',
                original_type='image',needs_review=True,
                notes=['直接读取原始图片帧，保留透明度；图内文字与对象仍需检查'])
            pieces,notes=auto_image(project,layer)
            notes.append('原始图片已执行本地识别与拆分；需核对小字、透明边缘和未拆对象')
            return PageScene(index=index,width=page.rect.width,height=page.rect.height,original=original,
                layers=sorted(pieces,key=lambda item:item.z),warnings=list(dict.fromkeys(notes)),status='needs_review')
        bboxlog=page.get_bboxlog()
        extended=page.get_drawings(extended=True)
        if any(kind=='fill-shade' for kind,_ in bboxlog) or any(d.get('type') in ('clip','group') for d in extended):
            from .pdfium_extract import convert_paint
            scene=convert_paint(project,index,original)
            from .logo_policy import classify_scene
            classify_scene(project,scene)
            # Office wraps even a single flattened slide image in clips and a
            # transparency group. Isolation must not bypass raster restoration.
            # Keep the isolated transform and alpha rather than adding a page
            # screenshot; ordinary mixed PDF pages keep their existing route.
            if not page.get_text().strip() and any(kind=='fill-image' for kind,_ in bboxlog):
                restored=[]
                for layer in scene.layers:
                    if layer.kind=='image' and layer.original_type in ('image','form'):
                        pieces,notes=auto_image(project,layer)
                        restored.extend(pieces);scene.warnings.extend(notes)
                    else:restored.append(layer)
                scene.layers=sorted(restored,key=lambda item:item.z)
                scene.status='needs_review'
                scene.warnings.append('图片页面已执行本地文字识别与内部拆分；需核对遗漏文字、遮罩和背景补全')
                return scene
            from .local_models import status
            from .text_groups import recover_pdf_text_groups
            scene,group_diagnostics=recover_pdf_text_groups(project,scene)
            if group_diagnostics:
                (project_dir(project)/f'text-groups-{index}-{uid()}.json').write_text(json.dumps(group_diagnostics,ensure_ascii=False,indent=2),'utf-8')
            # Associate real PDF glyph shadows before OCR can mistake their
            # black bitmap silhouettes for a second copy of the text.
            from .text_shadows import restore_text_shadows
            try:scene,_=restore_text_shadows(project,scene)
            except (RuntimeError,ValueError,OSError):scene.warnings.append('原生文字阴影预关联未完成，需继续校正')
            if status()['ocr']:
                from .text_groups import containment,rect
                text_bounds=[l.source_ink_bbox for l in scene.layers if l.kind=='text' and l.source_ink_bbox]
                restored=[]
                for layer in scene.layers:
                    text_effect=any(containment(rect(layer),[box[0]-3,box[1]-3,box[2]+3,box[3]+3])>.86 for box in text_bounds)
                    if layer.kind=='image' and layer.original_type=='image' and not text_effect and not layer.edited and not layer.locked and not layer.rotation:
                        pieces,notes=auto_image(project,layer,segment=False)
                        restored.extend(pieces);scene.warnings.extend(notes)
                    else:restored.append(layer)
                scene.layers=sorted(restored,key=lambda item:item.z)
            from .text_recovery import recover_simple_text
            scene,diagnostics=recover_simple_text(project,scene,min_score=.78,allow_ocr=status()['ocr'])
            unresolved=sum(not row['accepted'] for row in diagnostics)
            if unresolved:scene.warnings.append(f'{unresolved} 个识别文字区域尚未可靠恢复为可编辑文字')
            if not status()['ocr']:scene.warnings.append('本地 OCR 未就绪，图片文字仍需检查；不会自动使用云端')
            from .text_dedup import redundant_ocr_text
            scene,duplicate_diagnostics=redundant_ocr_text(scene)
            if duplicate_diagnostics:
                (project_dir(project)/f'text-dedup-{index}-{uid()}.json').write_text(json.dumps(duplicate_diagnostics,ensure_ascii=False,indent=2),'utf-8')
            from .text_shadows import restore_text_shadows
            try:scene,_=restore_text_shadows(project,scene)
            except (RuntimeError,ValueError,OSError):scene.warnings.append('文字阴影尚未关联，原素材保留，请检查移动后残影')
            return scene
        traces=page.get_texttrace()
        for drawing in page.get_drawings():
            rect=fitz.Rect(drawing['rect'])
            if rect.is_infinite: continue
            try:
                layers.append(LayerElement(kind='path',name=f'矢量装饰 {len(layers)+1}',
                    x=rect.x0,y=rect.y0,width=max(.01,rect.width),height=max(.01,rect.height),
                    z=drawing.get('seqno',len(layers)),path=path_commands(drawing,rect),
                    fill=color(drawing.get('fill')),stroke=color(drawing.get('color')),
                    stroke_width=drawing.get('width') or 0,
                    fill_opacity=drawing['fill_opacity'] if drawing.get('fill_opacity') is not None else 1,
                    stroke_opacity=drawing['stroke_opacity'] if drawing.get('stroke_opacity') is not None else 1,
                    even_odd=bool(drawing.get('even_odd',False))))
            except Exception as exc: warnings.append(f'矢量装饰未还原：{exc}')
        # Clips/transparency groups cannot simply be treated as independent unbounded paths.
        extended=page.get_drawings(extended=True)
        if any(d.get('type') in ('clip','group') for d in extended):
            warnings.append('存在裁剪或透明组合，请核对边界与混合效果')
        for block in page.get_text('dict',flags=fitz.TEXT_PRESERVE_IMAGES)['blocks']:
            if block['type']==0:
                for line in block['lines']:
                    direction=line.get('dir',(1,0))
                    angle=math.degrees(math.atan2(direction[1],direction[0]))
                    for span in line['spans']:
                        if not span['text'].strip(): continue
                        rect=fitz.Rect(span['bbox']); origin=fitz.Point(span['origin'])
                        seq=next((t['seqno'] for t in traces if fitz.Rect(t['bbox']).intersects(rect)),len(layers))
                        size=span['size']
                        # Use the oriented quad rather than axis-aligned bbox for rotated text.
                        quad=fitz.recover_quad(direction,span)
                        width=max(1,abs(quad.ur-quad.ul)); height=max(size*1.25,1)
                        x,y=quad.ul
                        x-=math.sin(math.radians(angle))*size*.14
                        y+=math.cos(math.radians(angle))*size*.14
                        layer=LayerElement(kind='text',name=span['text'][:30],text=span['text'],
                            x=x,y=y,width=width+size*.12,height=height,rotation=angle,
                            z=seq+.00001*len(layers),font=font_name(span['font']),font_size=size,
                            bold=bool(span['flags']&16),italic=bool(span['flags']&2),color=color(span['color']),
                            opacity=span.get('alpha',255)/255)
                        layers.append(layer)
            elif block['type']==1:
                image=Image.open(io.BytesIO(block['image'])).convert('RGBA')
                if block.get('mask'):
                    image.putalpha(Image.open(io.BytesIO(block['mask'])).convert('L'))
                rect=fitz.Rect(block['bbox'])
                transform=block.get('transform',(rect.width,0,0,rect.height,rect.x0,rect.y0))
                a,b,c,d,e,f=transform
                width=math.hypot(a,b); height=math.hypot(c,d)
                angle=math.degrees(math.atan2(b,a))
                skew=abs(a*c+b*d)>max(width*height*.001,1)
                seq=next((i for i,(kind,box) in enumerate(bboxlog) if kind=='fill-image' and fitz.Rect(box)==rect),len(layers))
                layer=LayerElement(kind='image',name=f'图片 {len(layers)+1}',x=e,y=f,
                    width=max(1,width),height=max(1,height),rotation=angle,z=seq,
                    asset=save_image(project,np.array(image),'embedded'),needs_review=True,
                    source='pdf-image',notes=['图片内部需检查拆分结果'])
                if a*d-b*c<0 or skew:
                    layer.notes.append('图片包含镜像或斜切，当前需人工校正'); warnings.append(layer.notes[-1])
                pieces,notes=auto_image(project,layer)
                layers.extend(pieces); warnings.extend(notes)
        if any(kind=='fill-shade' for kind,_ in bboxlog):
            warnings.append('存在渐变着色，尚未原生还原，请对照原稿补充')
        if not layers: warnings.append('没有提取出对象，需手工处理')
        # Unknown raster and problematic vectors must never pass as fully reconstructed.
        return PageScene(index=index,width=page.rect.width,height=page.rect.height,original=original,
            layers=sorted(layers,key=lambda x:x.z),warnings=list(dict.fromkeys(warnings)),
            status='needs_review' if warnings or any(x.needs_review for x in layers) else 'ready')
