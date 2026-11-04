"""Measure real Office glyph placement; do not guess a universal ascent offset."""
from pathlib import Path
from functools import lru_cache
import json,subprocess,os,math
import numpy as np
import fitz,pypdfium2 as pdfium,pypdfium2.raw as raw
from PIL import Image
from .models import PageScene,LayerElement
from .store import project_dir,ROOT
from .export import export_pptx


@lru_cache(maxsize=1)
def available():
    if os.name!='nt':return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,r'PowerPoint.Application\CLSID'):return True
    except OSError:return False


def eligible(layer):
    return (layer.kind=='text' and layer.text_fit!='shape' and not layer.text_layout and not layer.edited and not layer.locked
            and not layer.rotation and '\n' not in layer.text and '\r' not in layer.text and bool(layer.text.strip()))

def source_tracking(traces,layer):
    """Trust wide tracking only when the original PDF positions prove it.

    A wide OCR rectangle may include decorations or nearby text. It must not
    relax the safety limit. Require an exact native string, matching location,
    a horizontal baseline and consistent gaps between the original glyphs.
    """
    if not eligible(layer) or layer.source!='pdf-native' or not layer.source_ink_bbox:return None
    box=layer.source_ink_bbox;tolerance=max(2,layer.font_size*.08)
    for trace in traces:
        chars=trace['chars']
        if len(chars)<2 or ''.join(chr(c[0]) for c in chars)!=layer.text:continue
        if trace.get('type',0)>=3 or abs(trace.get('dir',(1,0))[0]-1)>.001 or abs(trace.get('dir',(1,0))[1])>.001:continue
        bounds=trace['bbox']
        if abs(bounds[0]-box[0])>tolerance or abs(bounds[2]-box[2])>tolerance:continue
        overlap=max(0,min(bounds[3],box[3])-max(bounds[1],box[1]))
        if overlap<.5*max(1,box[3]-box[1]):continue
        if any(abs(c[2][1]-chars[0][2][1])>max(.2,layer.font_size*.02) for c in chars):continue
        gaps=np.array([b[2][0]-a[3][2] for a,b in zip(chars,chars[1:])])
        gap=float(np.median(gaps))
        if gap<=layer.font_size*.2 or gap>100:continue
        if np.max(np.abs(gaps-gap))>max(.25,layer.font_size*.05):continue
        return gap
    return None

def attach_source_bounds(project,scenes):
    fitz_doc=fitz.open(project_dir(project)/'source.pdf');pdf=pdfium.PdfDocument(str(project_dir(project)/'source.pdf'))
    tracking={}
    for scene in scenes:
        page=pdf[scene.index];height=scene.height;objects=[obj for obj in page.get_objects(max_depth=1) if obj.type==raw.FPDF_PAGEOBJ_TEXT]
        spans=[s for b in fitz_doc[scene.index].get_text('dict')['blocks'] if b['type']==0 for line in b['lines'] for s in line['spans']]
        traces=fitz_doc[scene.index].get_texttrace()
        for layer in scene.layers:
            if layer.kind!='text' or layer.rotation:continue
            if not layer.source_ink_bbox:
                choices=[s for s in spans if s['text']==layer.text]
                if not choices:continue
                span=min(choices,key=lambda s:abs(s['bbox'][0]-layer.x)+abs(s['bbox'][1]-layer.y))
                rect=fitz.Rect(span['bbox']);bounds=[]
                for obj in objects:
                    l,b,r,t=obj.get_bounds()
                    if rect.contains(fitz.Point((l+r)/2,height-(b+t)/2)):bounds.append((l,height-t,r,height-b))
                if bounds:layer.source_ink_bbox=[min(b[0] for b in bounds),min(b[1] for b in bounds),max(b[2] for b in bounds),max(b[3] for b in bounds)]
            gap=source_tracking(traces,layer)
            if gap is not None:tracking[layer.id]=gap
        page.close()
    pdf.close();fitz_doc.close()
    return tracking

def calibrate(project,scenes,match_height=False):
    tracking=attach_source_bounds(project,scenes) or {}
    targets=[l for page in scenes for l in page.layers if eligible(l) and l.source_ink_bbox]
    if not targets:return []
    if not available():raise RuntimeError('未检测到本机 PowerPoint，文字位置未进行 Office 校准')
    folder=project_dir(project)/'font-calibration';folder.mkdir(exist_ok=True)
    probes=[];items=[]
    for i,target in enumerate(targets):
        sheet=i//18;row=i%18;x=30;y=30+row*96
        if row==0:probes.append(PageScene(index=sheet,width=3200,height=1800,original='probe',status='ready'))
        sample=target.model_copy(deep=True);sample.id='probe-'+str(i);sample.x=x;sample.y=y;sample.width=3100;sample.height=90
        probe_size=min(40,2900*target.font_size/max(target.width,1))
        sample.font_size=max(1,probe_size);sample.rotation=0;sample.color='#000000';sample.text_gradient=[];sample.text_gradient_positions=[];sample.text_shadow=None;sample.stroke=None;sample.opacity=1;sample.char_spacing=0
        probes[-1].layers.append(sample);items.append((target,sheet,row,x,y,sample.font_size))
    export_pptx(project,probes,folder/'probe.pptx')
    try:
        result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(ROOT/'scripts'/'render_font_probe.ps1'),'-Folder',str(folder)],
            capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    except subprocess.TimeoutExpired as exc:raise RuntimeError('本机 PowerPoint 测量超时，原文字位置保留') from exc
    if result.returncode:raise RuntimeError('本机 PowerPoint 字形测量失败，已保留原文字位置')
    measurements=[];cache={}
    for target,sheet,row,x,y,probe_size in items:
        if sheet not in cache:cache[sheet]=np.array(Image.open(folder/f'probe-{sheet+1}.png').convert('RGB'))
        region=cache[sheet][y:y+90,x:x+3100];mask=region.min(axis=2)<110
        ys,xs=np.where(mask)
        if not len(xs):continue
        unit=target.font_size/probe_size;box=target.source_ink_bbox
        old=[target.x,target.y,target.char_spacing,target.font_size]
        if match_height or target.source=='pdf-text-group':
            measured_height=(ys.max()-ys.min()+1)*unit
            ratio=(box[3]-box[1])/max(measured_height,1e-6)
            # Reject implausible bounds rather than resizing from a bad OCR box.
            if .85<=ratio<=1.15:
                target.font_size=round(target.font_size*ratio,4);unit=target.font_size/probe_size
                target.height=max(target.height,target.font_size*1.4)
        target.x=box[0]-xs.min()*unit;target.y=box[1]-ys.min()*unit
        measured_width=(xs.max()-xs.min()+1)*unit
        spacing=(box[2]-box[0]-measured_width)/max(1,len(target.text)-1)
        upper=target.font_size*.2
        if target.id in tracking:upper=max(upper,tracking[target.id]+target.font_size*.15)
        target.char_spacing=max(-min(100,target.font_size*.2),min(100,upper,spacing))
        target.width=max(target.width,box[2]-box[0]+target.font_size)
        if target.source=='pdf-text-group' and target.text_gradient:
            # Text fills use the whole shape's coordinate system in Office.
            # Anchor colour stops to the measured ink, not to empty margins.
            start=max(0,min(1,(box[1]-target.y)/target.height))
            end=max(start,min(1,(box[3]-target.y)/target.height))
            target.text_gradient_positions=[start+(end-start)*i/(len(target.text_gradient)-1) for i in range(len(target.text_gradient))]
        note='已在本机 PowerPoint 测量字形并校准位置与字间距'
        if note not in target.notes:target.notes.append(note)
        measurements.append({'id':target.id,'font':target.font,'text':target.text,'before':old,'after':[target.x,target.y,target.char_spacing,target.font_size],'target_ink':box,'source_tracking_evidence':tracking.get(target.id)})
    (folder/'measurements.json').write_text(json.dumps(measurements,ensure_ascii=False,indent=2),'utf-8')
    return measurements


def calibrate_page(project,page,rebuild_native=False):
    """Use a copy so an unavailable/failed Office never partially moves a page."""
    candidate=page.model_copy(deep=True)
    measurements=calibrate(project,[candidate])
    from .native_text_layout import calibrate as calibrate_native_layout
    candidate,diagnostics=calibrate_native_layout(project,candidate,force=rebuild_native)
    measured_ids={row['id'] for row in measurements}
    for layer in candidate.layers:
        previous=next((l for l in page.layers if l.id==layer.id),None)
        if (layer.id not in measured_ids and layer.text_layout and previous
                and layer.text_layout!=previous.text_layout and any(row['id']==layer.id for row in diagnostics)):
            measurements.append({'id':layer.id,'font':layer.font,'text':layer.text,'native_layout':True})
    return candidate,measurements
