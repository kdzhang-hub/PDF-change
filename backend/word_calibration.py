"""Measure Word's glyph metrics on export copies; never change saved scenes."""
import json,os,subprocess
from functools import lru_cache
import fitz
import numpy as np
from . import store
from .models import PageScene
from .export_docx import export_docx,native_wordart
from .font_calibration import eligible


@lru_cache(maxsize=1)
def available():
    if os.name!='nt':return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,r'Word.Application\CLSID'):return True
    except OSError:return False


def target(layer):
    # Native PDF text object bounds include font layout metrics. Raster
    # text-group bounds describe visible ink; only those justify ink fitting.
    return eligible(layer) and layer.visible and layer.source=='pdf-text-group' and bool(layer.source_ink_bbox)


def render_probe(folder):
    result=subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
        str(store.ROOT/'scripts/render_word_probe.ps1'),'-Folder',str(folder)],
        capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=120,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    (folder/'word-probe.log').write_text(result.stdout+'\n'+result.stderr,encoding='utf-8')
    if result.returncode:raise RuntimeError('本机 Word 字形测量失败，已保留原位置')


def fit_measurement(layer,bounds,probe_size):
    """Return a fitted copy only for a complete, plausible probe measurement."""
    left,top,right,bottom=bounds
    if left<=0 or top<=0 or right>=1439 or bottom>=89 or right<=left or bottom<=top:return None
    box=layer.source_ink_bbox
    if box is None or box[2]<=box[0] or box[3]<=box[1]:return None
    unit=layer.font_size/probe_size
    ratio=(box[3]-box[1])/((bottom-top)*unit)
    if not .85<=ratio<=1.15:return None
    result=layer.model_copy(deep=True)
    result.font_size=max(.5,round(layer.font_size*ratio*2)/2)
    if result.font_size>1000:return None
    unit=result.font_size/probe_size
    result.x=box[0]-left*unit;result.y=box[1]-top*unit
    if len(result.text)>1:
        gap=(box[2]-box[0]-(right-left)*unit)/(len(result.text)-1)
        limit=min(100,result.font_size*.2)
        result.char_spacing=max(-limit,min(limit,gap))
    result.width=max(result.width,box[2]-box[0]+result.font_size)
    result.height=max(result.height,result.font_size*1.4)
    if result.text_gradient:
        start=max(0,min(1,(box[1]-result.y)/result.height))
        end=max(start,min(1,(box[3]-result.y)/result.height))
        result.text_gradient_positions=[start+(end-start)*i/(len(result.text_gradient)-1) for i in range(len(result.text_gradient))]
    return result


def prepare(project,pages,folder):
    copies=[page.model_copy(deep=True) for page in pages]
    targets=[layer for page in copies for layer in page.layers if target(layer)]
    report={'targets':len(targets),'calibrated':[],'skipped':[],'warnings':[]}
    if any(layer.visible and layer.text_fit=='shape' and not native_wordart(layer) for page in copies for layer in page.layers):
        report['warnings'].append('部分含还原字体、复杂特效或字距的随框艺术字使用文字框，Word横向字形适配需核对；内容、字体和特效保留')
    if not targets:return copies,report
    if not available():
        report['warnings'].append('未检测到本机 Word，艺术字未进行 Word 字形校准，请核对导出位置')
        return copies,report
    from .fonts import installed_map
    known=installed_map()
    missing=[layer for layer in targets if layer.font.replace(' ','').lower() not in known]
    if missing:
        report['skipped'].extend(layer.id for layer in missing)
        report['warnings'].append('部分艺术字字体未安装，已保留原位置；请安装字体或在属性中替换')
        missing_ids={id(layer) for layer in missing};targets=[layer for layer in targets if id(layer) not in missing_ids]
    if not targets:return copies,report
    folder.mkdir(parents=True,exist_ok=True)
    probes=[];items=[]
    for index,layer in enumerate(targets):
        sheet=index//12;row=index%12;x=25;y=20+row*96
        if row==0:probes.append(PageScene(index=sheet,width=1500,height=1200,original='probe',status='ready'))
        sample=layer.model_copy(deep=True);sample.id='probe-'+str(index)
        sample.x=x;sample.y=y;sample.width=1440;sample.height=90
        sample.font_size=max(1,round(min(40,1300*layer.font_size/max(layer.width,1))*2)/2)
        sample.opacity=1;sample.char_spacing=0;sample.color='#000000';sample.stroke=None
        sample.text_gradient=[];sample.text_gradient_positions=[];sample.text_shadow=None
        probes[-1].layers.append(sample);items.append((layer,sheet,x,y,sample.font_size))
    export_docx(project,probes,folder/'probe.docx')
    fitted={};cache={}
    try:
        render_probe(folder)
        with fitz.open(folder/'probe.pdf') as rendered:
            if len(rendered)!=len(probes):raise RuntimeError('Word 字形探针页数不一致，已保留原位置')
            for layer,sheet,x,y,size in items:
                if sheet not in cache:
                    cache.clear()  # Bound memory to one probe page.
                    pix=rendered[sheet].get_pixmap(matrix=fitz.Matrix(3,3),alpha=False)
                    cache[sheet]=np.frombuffer(pix.samples,dtype=np.uint8).reshape(pix.height,pix.width,3)
                pixels=cache[sheet][y*3:(y+90)*3,x*3:(x+1440)*3]
                ys,xs=np.where(pixels.min(axis=2)<110)
                bounds=[xs.min()/3,ys.min()/3,(xs.max()+1)/3,(ys.max()+1)/3] if len(xs) else None
                candidate=fit_measurement(layer,bounds,size) if bounds else None
                if candidate is None:
                    report['skipped'].append(layer.id);continue
                fitted[layer.id]=candidate
                report['calibrated'].append({'id':layer.id,'text':layer.text,
                    'before':[layer.x,layer.y,layer.font_size,layer.char_spacing],
                    'after':[candidate.x,candidate.y,candidate.font_size,candidate.char_spacing]})
    except (OSError,RuntimeError,ValueError,subprocess.SubprocessError) as exc:
        # Measurement failure must not leave a partly fitted export.
        report['calibrated']=[]
        report['warnings'].append('本机 Word 字形校准未完成，使用原文字位置；请检查本地 Word 环境')
        (folder/'failure.txt').write_text(str(exc),encoding='utf-8')
        return [page.model_copy(deep=True) for page in pages],report
    for page in copies:page.layers=[fitted.get(layer.id,layer) for layer in page.layers]
    if report['skipped']:report['warnings'].append('部分艺术字的字形测量不可靠，已保留原位置，请核对')
    (folder/'measurements.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return copies,report
