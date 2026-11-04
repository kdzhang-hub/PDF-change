"""Local paint-group extraction for PDF masks, clipping and gradient shading.

Independent alpha assets retain paint order. Native PDF text is kept editable.
This is not a full-page screenshot fallback.
"""
from __future__ import annotations
import json,os,shutil,subprocess,hashlib
from pathlib import Path
import fitz
import numpy as np
from PIL import Image
from .models import LayerElement,PageScene,uid
from .store import ROOT,project_dir,asset_path


def convert_complex(project,page,original,analyze_images=False):
    from .extract import font_name
    prefix=f'paint-{page.number}-{uid()[:8]}'
    work=project_dir(project)/'paint';work.mkdir(exist_ok=True)
    svg=work/(prefix+'.svg');svg.write_text(page.get_svg_image(text_as_path=False),'utf-8')
    node=os.environ.get('LAYERDECK_NODE') or shutil.which('node')
    if not node:raise RuntimeError('复杂 PDF 需要本地 Node 与 Chrome 渲染器，请运行 setup.ps1')
    assets=project_dir(project)/'assets'
    process=subprocess.run([node,str(ROOT/'scripts'/'render_svg_layers.cjs'),str(svg),str(assets),prefix],
        capture_output=True,text=True,encoding='utf-8',timeout=240,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    if process.returncode:raise RuntimeError('本地复杂对象渲染失败：'+process.stderr[-500:])
    meta=json.loads((assets/(prefix+'.json')).read_text('utf-8'))
    spans=[(span,line) for block in page.get_text('dict')['blocks'] if block['type']==0 for line in block['lines'] for span in line['spans'] if span['text'].strip()]
    layers=[];warnings=[];used=set()
    for item in meta['layers']:
        if item['tag']=='text' and item['texts']:
            content=''.join(t['text'] for t in item['texts'])
            # A PDF span can correspond to multiple adjacent SVG text runs. Match
            # using character positions from the PDF, not a font-name heuristic.
            candidates=[(i,s,line) for i,(s,line) in enumerate(spans) if content in s['text']]
            if candidates:
                i,span,line=min(candidates,key=lambda v:abs(v[1]['bbox'][0]-item['x'])+abs(v[1]['bbox'][1]-item['y']))
                if i in used:continue
                used.add(i);quad=fitz.recover_quad(line.get('dir',(1,0)),span)
                import math
                size=span['size'];angle=math.degrees(math.atan2(line.get('dir',(1,0))[1],line.get('dir',(1,0))[0]))
                x,y=quad.ul;x-=math.sin(math.radians(angle))*size*.14;y+=math.cos(math.radians(angle))*size*.14
                layers.append(LayerElement(kind='text',name=span['text'][:30],text=span['text'],x=x,y=y,
                    width=max(1,abs(quad.ur-quad.ul)+size*.12),height=max(1,size*1.3),rotation=angle,
                    z=item['index'],font=font_name(span['font']),font_size=size,bold=bool(span['flags']&16),
                    italic=bool(span['flags']&2),color=f"#{span['color']:06x}",source='pdf-native'))
            else:
                warnings.append('SVG 文字与 PDF 原生文字未匹配，需要检查')
            continue
        if not item.get('asset'):continue
        with Image.open(asset_path(project,item['asset'])) as image:
            image=image.convert('RGBA');alpha=image.getchannel('A');box=alpha.getbbox()
            if not box:continue
            # Crop transparent planes so hit testing selects the visible decoration.
            crop=image.crop(box);crop.save(asset_path(project,item['asset']))
            x=item['x']+box[0]/meta['scale'];y=item['y']+box[1]/meta['scale']
            width=crop.width/meta['scale'];height=crop.height/meta['scale']
        layer=LayerElement(kind='image',name=f'独立装饰 {item["index"]+1}',x=x,y=y,width=max(.01,width),height=max(.01,height),
            z=item['index'],asset=item['asset'],source='pdf-paint-group',needs_review=True,
            notes=['本地保留裁剪、蒙版与渐变；对象可移动，内部文字或子对象需要检查'])
        layers.append(layer)
    if len(used)<len(spans):warnings.append(f'{len(spans)-len(used)} 组原生文字未匹配，需处理')
    warnings.append('复杂装饰已按绘制组保留为独立透明素材；图片内部拆分尚需检查')
    return PageScene(index=page.number,width=page.rect.width,height=page.rect.height,original=original,layers=layers,status='needs_review',warnings=warnings)
