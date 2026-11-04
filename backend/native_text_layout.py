"""Measure local Office glyph origins against the input PDF, in one text shape.

No source presentation, network model, inferred wording or page image is used.
The canonical positions and measured native formatting live in the same scene.
"""
import json
import os
import subprocess
from pathlib import Path

import fitz
import numpy as np
from . import store
from .models import TextLayout,NativeTextLayout,LayerElement,PageScene,uid
from .layout_quality import corrected_spacing,infer_quantum,prepare_reference,visual_scores

_QUANTA={}


def eligible(layer,force=False):
    return (layer.kind=='text' and layer.source=='pdf-native' and layer.text_fit=='natural'
            and (force or not layer.text_layout or not (layer.text_layout.pptx and layer.text_layout.docx))
            and not layer.edited and not layer.locked and layer.visible
            and not layer.rotation and 0<len(layer.text)<=4000 and not any(c in layer.text for c in '\r\n')
            and not layer.font_asset and not layer.text_gradient and not layer.stroke and not layer.text_shadow)


def source_positions(page,layer):
    spans=[s for b in page.get_text('rawdict')['blocks'] if b['type']==0 for l in b['lines'] for s in l['spans']]
    matches=[s for s in spans if ''.join(c['c'] for c in s['chars'])==layer.text]
    if not matches:return None
    span=min(matches,key=lambda s:abs(s['bbox'][0]-layer.x)+abs(s['bbox'][1]-layer.y))
    if abs(span['bbox'][0]-layer.x)>max(4,layer.font_size) or abs(span['bbox'][1]-layer.y)>layer.font_size*2:return None
    return [(c['origin'][0]-layer.x,c['origin'][1]-layer.y) for c in span['chars']]


def native_lines(page):
    lines=[]
    for block in page.get_text('rawdict')['blocks']:
        if block['type']!=0:continue
        for line in block['lines']:
            chars=[c for span in line['spans'] for c in span['chars'] if not c['c'].isspace()]
            if chars:lines.append((''.join(c['c'] for c in chars),np.array([c['origin'] for c in chars])))
    return lines


def actual_positions(lines,layer):
    selected=[i for i,c in enumerate(layer.text) if not c.isspace()]
    expected=''.join(layer.text[i] for i in selected)
    target=np.array([layer.text_layout.positions[i] for i in selected])+[layer.x,layer.y]
    if not expected:return None
    choices=[]
    for text,positions in lines:
        start=0
        while (index:=text.find(expected,start))>=0:
            subset=positions[index:index+len(expected)]
            choices.append((float(np.linalg.norm(subset[0]-target[0])),subset));start=index+1
    if not choices:return None
    distance,positions=min(choices,key=lambda c:c[0])
    return (selected,target,positions) if distance<max(12,layer.font_size*2) else None


def render(project,page,kind,folder):
    folder.mkdir(parents=True,exist_ok=True)
    # An uncorrected font may initially be wider than the source line. Measure
    # it on a wider diagnostic page so wrapping cannot hide the final glyphs.
    # Physical coordinates stay in points; the saved source scene is untouched.
    probe=page.model_copy(deep=True)
    targets=[l for l in probe.layers if l.text_layout]
    if targets and page.width<=1584:
        probe.width=max(page.width,min(1584,max(l.x+l.font_size*(len(l.text)+2) for l in targets)))
        for l in targets:
            l.width=max(l.width,probe.width-l.x)
            l.height=max(l.height,l.font_size*2)
    if kind=='pptx':
        from .export import export_pptx
        export_pptx(project,[probe],folder/'converted.pptx')
    else:
        from .export_docx import export_docx
        export_docx(project,[probe],folder/'converted.docx')
    result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
        str(store.ROOT/'scripts/render_native_layout.ps1'),'-Folder',str(folder),'-Kind',kind],
        capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    (folder/'office.log').write_text(result.stdout+'\n'+result.stderr,'utf-8')
    path=folder/('powerpoint.pdf' if kind=='pptx' else 'word-render.pdf')
    if result.returncode or not path.exists():raise RuntimeError('本机Office逐字坐标测量失败')
    with fitz.open(path) as pdf:
        if len(pdf)!=1:raise RuntimeError('本机Office逐字测量页数不匹配')
        return native_lines(pdf[0])


def spacing_quantum(project,seed,folder):
    key=(seed.font,seed.bold,seed.italic)
    if key in _QUANTA:return _QUANTA[key]
    layers=[];requested=[i/100 for i in range(-25,26)]
    for index,value in enumerate(requested):
        layer=LayerElement(kind='text',name='本机字距测量',text='中中',x=10,y=10+index*18,width=150,height=18,
            font=seed.font,font_size=10,bold=seed.bold,italic=seed.italic,source='native-quantum-probe')
        layer.text_layout=TextLayout(text=layer.text,font=layer.font,font_size=10,bold=layer.bold,italic=layer.italic,
            positions=[(0,10),(10,10)],pptx=NativeTextLayout(spacing=[value,0]))
        layers.append(layer)
    page=PageScene(index=0,width=250,height=950,original='native-quantum-probe',status='ready',layers=layers)
    try:
        lines=render(project,page,'pptx',folder)
        matches=sorted((positions for text,positions in lines if text=='中中'),key=lambda positions:positions[0,1])
        advances=[float(p[1,0]-p[0,0]) for p in matches]
        quantum=infer_quantum(advances) if len(matches)==len(requested) else None
    except (RuntimeError,OSError,ValueError,subprocess.TimeoutExpired):return None
    (folder/'quantum.json').write_text(json.dumps({'requested':requested,'advances':advances,'quantum':quantum},indent=2),'utf-8')
    if quantum:_QUANTA[key]=quantum
    return quantum


def calibrate(project,page,force=False):
    source=store.project_dir(project)/'source.pdf'
    if not source.exists() or not any(eligible(l,force) for l in page.layers):return page,[]
    candidate=page.model_copy(deep=True);targets=[];needed=set();preserved={kind:{} for kind in ('pptx','docx')};initial={kind:{} for kind in ('pptx','docx')}
    with fitz.open(source) as pdf:
        for layer in candidate.layers:
            if not eligible(layer,force):continue
            positions=source_positions(pdf[page.index],layer)
            if positions is None:continue
            if layer.text_layout is None:
                layer.text_layout=TextLayout(text=layer.text,font=layer.font,font_size=layer.font_size,
                    bold=layer.bold,italic=layer.italic,char_spacing=layer.char_spacing,positions=positions)
            for kind in ('pptx','docx'):
                native=getattr(layer.text_layout,kind)
                if native:
                    initial[kind][layer.id]=native.model_copy(deep=True)
                    if force:needed.add((layer.id,kind))
                    else:preserved[kind][layer.id]=(-1,native.model_copy(deep=True))
                else:
                    needed.add((layer.id,kind))
                    setattr(layer.text_layout,kind,NativeTextLayout(spacing=[layer.char_spacing]*len(layer.text)))
            targets.append(layer)
    if not targets:return page,[]
    root=store.project_dir(project)/('native-layout-'+uid());root.mkdir()
    quantum=spacing_quantum(project,targets[0],root/'spacing-quantum') if any(kind=='pptx' for _,kind in needed) else None
    reference=prepare_reference(source,page.index,candidate)
    diagnostics=[];disabled=set();verified=preserved
    for round_index in range(4):
        for kind in ('pptx','docx'):
            if kind in disabled:continue
            current=[l for l in targets if (l.id,kind) in needed and getattr(l.text_layout,kind) is not None]
            if not current:continue
            folder=root/f'{kind}-{round_index}'
            try:
                lines=render(project,candidate,kind,folder)
                scores=visual_scores(reference,folder/('powerpoint.pdf' if kind=='pptx' else 'word-render.pdf'))
            except (RuntimeError,OSError,ValueError,subprocess.TimeoutExpired):
                disabled.add(kind)
                for layer in targets:setattr(layer.text_layout,kind,None)
                candidate.warnings.append(('PowerPoint' if kind=='pptx' else 'Word')+'局部字距测量未完成，已有布局保留，未验证部分使用自然排版；不会上传云端')
                continue
            for layer in current:
                native=getattr(layer.text_layout,kind);match=actual_positions(lines,layer)
                if match is None:
                    setattr(layer.text_layout,kind,None)
                    diagnostics.append({'id':layer.id,'format':kind,'round':round_index,'matched':False})
                    continue
                selected,target,actual=match;delta=target-actual
                max_error=float(abs(delta).max())
                visual=scores.get(layer.id)
                diagnostics.append({'id':layer.id,'format':kind,'round':round_index,'matched':True,'maxOriginError':max_error,'visualSimilarity':visual})
                if max_error<=1:
                    coordinate_error=float(np.abs(delta).mean())
                    score=(0,1-visual,coordinate_error) if visual is not None else (1,coordinate_error,0)
                    best=verified[kind].get(layer.id)
                    if best is None or score<best[0]:verified[kind][layer.id]=(score,native.model_copy(deep=True))
                if round_index==3:
                    continue
                values=corrected_spacing(native.spacing,selected,delta,
                    quantum=quantum if kind=='pptx' else None,precision=100 if kind=='pptx' else 20)
                if any(abs(v)>100 for v in values):setattr(layer.text_layout,kind,None);continue
                native.spacing=values
                native.offset=(native.offset[0]+float(delta[0,0]),native.offset[1]+float(np.median(delta[:,1])))
            (folder/'scene.json').write_text(candidate.model_dump_json(indent=2),'utf-8')
    for layer in targets:
        for kind in ('pptx','docx'):
            best=verified[kind].get(layer.id)
            setattr(layer.text_layout,kind,best[1] if best else initial[kind].get(layer.id))
        if not layer.text_layout.pptx and not layer.text_layout.docx:layer.text_layout=None
    for kind in ('pptx','docx'):
        missed=len(targets)-len(verified[kind])
        if missed and kind not in disabled:candidate.warnings.append(f'{missed}处'+('PowerPoint' if kind=='pptx' else 'Word')+'局部字距未通过原点误差1磅门槛，保留已有布局或自然排版，需校正')
    (root/'measurements.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2),'utf-8')
    return candidate,diagnostics
