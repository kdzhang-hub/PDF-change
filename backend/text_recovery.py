"""Recover simple raster text using offline OCR and installed-font matching."""
from functools import lru_cache
from pathlib import Path
import math,os,re,hashlib,struct
import numpy as np
import cv2,fitz
from PIL import Image,ImageDraw,ImageFont
from .models import LayerElement,uid
from .store import asset_path
from .fonts import font_names,user_font_dirs,resolve
from . import local_models

@lru_cache(maxsize=1)
def candidates():
    paths=[Path('C:/Windows/Fonts')/f for f in ('simsun.ttc','simhei.ttf','msyh.ttc','msyhbd.ttc','arial.ttf','arialbd.ttf','times.ttf','timesbd.ttf')]
    for folder in user_font_dirs():paths.extend(p for p in folder.iterdir() if p.suffix.lower() in ('.ttf','.otf','.ttc'))
    result=[]
    for path in dict.fromkeys(paths):
        if not path.exists():continue
        try:
            for index,names in enumerate(font_names(path)):
                result.append((str(path),index,names.get(1001,names[1])))
        except (OSError,ValueError):continue
    return result

def fit_font(text,alpha,font_candidates=None):
    target=alpha.astype(float)/255;h,w=target.shape
    target_binary=target>.4
    best=None
    for path,index,name in (candidates() if font_candidates is None else font_candidates):
        try:
            font=probe_font(path,index);size=100
            face_style=font.getname()[1].lower()
            chinese=next((c for c in text if '\u3400'<=c<='\u9fff'),None)
            if chinese and bytes(font.getmask(chinese))==bytes(font.getmask('\uffff')):continue
            for stroke in (0,1,2,3):
                bbox=font.getbbox(text,anchor='ls',stroke_width=stroke)
                image=Image.new('L',(max(1,bbox[2]-bbox[0]+8),max(1,bbox[3]-bbox[1]+8)))
                ImageDraw.Draw(image).text((4-bbox[0],4-bbox[1]),text,fill=255,font=font,anchor='ls',stroke_width=stroke)
                crop=image.getbbox()
                if not crop:continue
                image=image.crop(crop)
                width_ratio=(w/h)/(image.width/image.height)
                if not .85<width_ratio<1.15:continue
                mask=np.array(image.resize((w,h),Image.Resampling.LANCZOS)).astype(float)/255
                binary=mask>.4
                iou=np.logical_and(binary,target_binary).sum()/max(1,np.logical_or(binary,target_binary).sum())
                score=.7*iou+.3*(1-np.mean(np.abs(mask-target)))
                if best is None or score>best['score']:
                    precise_size=size*w/max(1,image.width)
                    baseline=-bbox[1]*precise_size/size
                    best={'score':float(score),'font':name,'file':path,'index':index,'pixel_size':precise_size,'baseline':baseline,'width_ratio':width_ratio,
                          'bold':stroke>0 or 'bold' in face_style,'italic':'italic' in face_style or 'oblique' in face_style,'synthetic_stroke':stroke}
        except (OSError,ValueError):continue
    return best

@lru_cache(maxsize=96)
def probe_font(path,index):
    return ImageFont.truetype(path,100,index=index)


def fit_with_word_spaces(text,alpha,fit):
    """Recover missing Latin spaces only with gaps and stronger glyph evidence."""
    if not text.isascii() or not text.isalnum() or not 4<=len(text)<=100:return text,fit
    occupied=(alpha>102).any(axis=0)
    edges=np.diff(np.r_[False,occupied,False].astype(np.int8))
    starts=np.where(edges==1)[0];ends=np.where(edges==-1)[0]
    # Do not guess character boundaries for touching glyphs or extra marks.
    if len(starts)!=len(text):return text,fit
    gaps=starts[1:]-ends[:-1];normal=float(np.median(gaps))
    cuts=np.where(gaps>=max(alpha.shape[0]*.2,normal*2.2,normal+2))[0]
    if not len(cuts) or len(cuts)>max(1,len(text)//6):return text,fit
    candidate=''.join(char+(' ' if i in cuts else '') for i,char in enumerate(text))
    found=fit_font(candidate,alpha)
    baseline=fit['score'] if fit else 0
    if found and found['score']>=.84 and found['score']-baseline>=.12:return candidate,found
    return text,fit


def fit_with_punctuation(text,alpha,fit):
    """Only restore one visible edge mark, with stronger shape evidence.

    No words are rewritten; low matches leave the OCR candidate untouched.
    """
    baseline=fit['score'] if fit else 0
    if baseline>=.78 or len(text)<3:return text,fit
    choices=[]
    for mark in ('（','）','(',')','“','”'):
        for candidate in (mark+text,text+mark):
            found=fit_font(candidate,alpha)
            if found:choices.append((found['score'],candidate,found))
    if choices:
        score,candidate,found=max(choices,key=lambda item:item[0])
        if score>=.84 and score-baseline>=.12:return candidate,found
    return text,fit


def source_text_hints(project,index):
    """Use the PDF's own text and embedded font names, never a reference PPT."""
    from .store import project_dir
    with fitz.open(project_dir(project)/'source.pdf') as doc:
        page=doc[index];families={}
        for entry in page.get_fonts():
            xref,_,_,base,*_=entry;name=re.sub(r'^[A-Z]{6}\+','',base);family=resolve(name)
            if family==name:
                try:
                    data=doc.extract_font(xref)[3]
                    for names in font_names(data):
                        for key in (6,4,1):
                            alias=names.get(key,'');found=resolve(alias)
                            if found!=alias or any(n==found for p,i,n in candidates()):family=found;break
                        if family!=name:break
                except (RuntimeError,ValueError,OSError,IndexError,struct.error):pass
            families[name]=family
        hints=[];seen=set()
        for block in page.get_text('dict')['blocks']:
            if block['type']!=0:continue
            for line in block['lines']:
                if line.get('dir',(1,0))!=(1,0):continue
                for span in line['spans']:
                    text=span['text'].strip();box=span['bbox'];family=families.get(span['font'],resolve(span['font']))
                    face=[value for value in candidates() if value[2]==family]
                    key=(text,tuple(round(n,2) for n in box),family)
                    if text and len(text)<=100 and face and key not in seen:
                        hints.append({'text':text,'box':box,'faces':face});seen.add(key)
        return hints

def recover_simple_text(project,scene,min_score=.86,allow_ocr=True,allow_pdf_hints=False):
    entries=[];hints=source_text_hints(project,scene.index) if allow_pdf_hints else []
    for layer in scene.layers:
        if layer.kind!='image' or layer.content_role=='logo' or layer.original_type not in ('image','shading','path') or layer.rotation:continue
        if not 1.5<=layer.height<=160 or layer.width<layer.height*.35:continue
        with Image.open(asset_path(project,layer.asset)) as original:
            im=np.array(original.convert('RGBA'))
        opaque=im[:,:,3]>180
        if opaque.sum()<15 or np.mean(im[:,:,3]<30)<.15:continue
        area=layer.width*layer.height;rect=fitz.Rect(layer.x,layer.y,layer.x+layer.width,layer.y+layer.height)
        nearby=[]
        for hint in hints:
            intersection=rect&fitz.Rect(hint['box'])
            overlap=max(0,intersection.width)*max(0,intersection.height)/max(1,area)
            if overlap>.88 and .6<(hint['box'][2]-hint['box'][0])/layer.width<1.8 and .6<(hint['box'][3]-hint['box'][1])/layer.height<1.8:nearby.append(hint)
        hint=nearby[0] if len(nearby)==1 else None
        if not allow_ocr and hint is None:continue
        colors=im[:,:,:3][opaque];quant=colors//24
        unique,counts=np.unique(quant,axis=0,return_counts=True);mode=unique[counts.argmax()]
        gradient=(layer.original_type=='shading' or hint is not None) and counts.max()/len(colors)<.65
        if counts.max()/len(colors)<.65 and not gradient:continue
        color=np.median(colors[np.all(quant==mode,axis=1)],axis=0).astype(int)
        entries.append({'layer':layer,'image':im,'color':color,'gradient':gradient,'hint':hint})
    if not entries:return scene,[]
    recovered=[];diagnostics=[]
    # Batch into atlas pages so Paddle initializes once and sees useful context.
    batches=[];batch=[];height=12
    for e in entries:
        im=e['image'];newh=max(32,min(im.shape[0],110));factor=newh/im.shape[0]
        neww=max(1,round(im.shape[1]*factor))
        if neww>1800:factor*=1800/neww;neww=1800;newh=max(1,round(im.shape[0]*factor))
        if height+newh+24>2200 and batch:batches.append((batch,height));batch=[];height=12
        e.update(atlas_y=height,factor=factor,atlas_h=newh,atlas_w=neww)
        batch.append(e);height+=newh+24
    if batch:batches.append((batch,height))
    for batch,height in batches:
        atlas=Image.new('RGB',(max(e['atlas_w'] for e in batch)+40,height),(28,35,48))
        for e in batch:
            background=(18,25,40) if np.mean(e['color'])>128 else (248,248,248)
            im=Image.fromarray(e['image']).resize((e['atlas_w'],e['atlas_h']),Image.Resampling.LANCZOS)
            block=Image.new('RGBA',im.size,background+(255,));block.alpha_composite(im)
            atlas.paste(block.convert('RGB'),(20,e['atlas_y']))
        records=[] if all(e['hint'] for e in batch) else local_models.ocr(np.array(atlas.convert('RGBA')))
        for e in batch:
            matches=[]
            low=[]
            for text,confidence,poly in records:
                cy=np.mean(poly[:,1])
                if e['atlas_y']<=cy<e['atlas_y']+e['atlas_h'] and confidence>=.88:matches.append((poly[:,0].min(),text,confidence))
                elif e['atlas_y']<=cy<e['atlas_y']+e['atlas_h']:low.append((text,confidence))
            if e['hint']:matches=[(0,e['hint']['text'],1.0)]
            if not matches:
                if low:diagnostics.append({'id':e['layer'].id,'text':''.join(t for t,c in low),'ocr_confidence':min(c for t,c in low),'font_match':None,'accepted':False,'reason':'小字或复杂字识别置信度不足，需继续处理'})
                continue
            text=''.join(item[1] for item in sorted(matches));confidence=min(item[2] for item in matches)
            if not e['hint'] and e['layer'].content_role!='content' and not any(c.isalnum() for c in text):
                diagnostics.append({'id':e['layer'].id,'text':text,'ocr_confidence':confidence,
                    'font_match':None,'accepted':False,'reason':'仅有标点或符号，不能据此拆开完整图标；原素材保留待确认'})
                continue
            raw_text=text
            image=e['image']
            glyph=(image[:,:,3]>100) if e['gradient'] else (np.linalg.norm(image[:,:,:3].astype(float)-e['color'],axis=2)<65)&(image[:,:,3]>60)
            ys,xs=np.where(glyph)
            if len(xs)<10:continue
            x0,x1=xs.min(),xs.max()+1;y0,y1=ys.min(),ys.max()+1
            alpha=np.where(glyph,image[:,:,3],0)[y0:y1,x0:x1]
            fit=fit_font(text,alpha,e['hint']['faces'] if e['hint'] else None)
            if confidence>=.95 and not e['hint']:text,fit=fit_with_punctuation(text,alpha,fit)
            threshold=max(min_score,.9) if len(text)==1 else min_score
            if len(text)==1 and confidence<.98:threshold=1.01
            row={'id':e['layer'].id,'text':text,'raw_ocr_text':raw_text,'ocr_confidence':confidence,'font_match':fit,'accepted':bool(fit and fit['score']>=threshold)}
            diagnostics.append(row)
            if not row['accepted']:
                old=e['layer'];old.recognized_text=text[:4000];old.needs_review=True
                old.name='待恢复文字 · '+text[:22]
                old.color='#'+''.join(f'{v:02x}' for v in e['color'])
                old.notes=[*old.notes,f'OCR 候选：{text}；字体或字形未可靠匹配，当前仍是图片，需校正']
                continue
            old=e['layer'];factor=old.height/image.shape[0];size=fit['pixel_size']*factor
            y=old.y+(y0+fit['baseline']-(fitz.Font(fontfile=fit['file']).ascender-.14)*fit['pixel_size'])*factor
            native=LayerElement(kind='text',name=text[:30],text=text,x=old.x+x0*factor,y=y,width=(x1-x0)*factor+size*.2,height=max(old.height,size*1.4),z=old.z,
                font=fit['font'],font_size=size,bold=fit.get('bold',False),italic=fit.get('italic',False),color='#'+''.join(f'{v:02x}' for v in e['color']),
                source='local-ocr-font-fit',confidence=confidence,needs_review=True,restoration_asset=old.asset,
                notes=[f'本地 OCR 与字体像素匹配 {fit["score"]:.3f}；原素材保留，需检查文字与字体'])
            native.original_type=old.original_type
            if e['hint']:
                native.source='pdf-metadata-font-fit'
                # Some vendor fonts expose a numeric English family name.
                # Office binds that real family, while PIL also accepts its
                # localized alias; treating the alias as identical can fall back.
                native.font=font_names(fit['file'])[fit['index']][1]
                native.notes=[f'PDF 原有文字与嵌入字体名核对，字形匹配 {fit["score"]:.3f}；原素材保留，需复核效果']
            if text!=raw_text:native.notes.append(f'OCR 漏标点已按原字形验证：{raw_text} → {text}')
            native.source_ink_bbox=[old.x+x0*factor,old.y+y0*factor,old.x+x1*factor,old.y+y1*factor]
            if e['gradient']:
                crop=image[y0:y1,x0:x1];stops=[]
                for fraction in (0,.33,.66,1):
                    row=round((crop.shape[0]-1)*fraction);window=crop[max(0,row-2):row+3]
                    colors=window[:,:,:3][window[:,:,3]>150]
                    if len(colors):rgb=np.median(colors,axis=0).astype(int)
                    else:rgb=e['color']
                    stops.append('#'+''.join(f'{v:02x}' for v in rgb))
                native.text_gradient=stops
                from .paint_recovery import linear_gradient
                try:
                    paint=linear_gradient(crop,crop[:,:,3]>150)
                    if paint.mean_error<=8:
                        native.text_gradient=paint.colors
                        native.text_gradient_positions=paint.positions
                        native.text_gradient_angle=paint.angle
                        native.notes.append(f'本地字芯拟合渐变方向 {paint.angle:g}°；颜色仍需对照原稿')
                    else:native.notes.append('渐变颜色分布较复杂，保留原采样并标为需核对')
                except ValueError:
                    native.notes.append('渐变字芯支持不足，保留原采样并标为需核对')
            recovered.append((old.id,native))
    replacements=dict(recovered)
    scene.layers=[replacements.get(layer.id,layer) for layer in scene.layers]
    # Some Office PDFs paint the same visible glyph twice. Do not turn exact
    # duplicate paint assets into two independent editable copies.
    fingerprints=set();unique=[];duplicates=0;recovered_ids={native.id for _,native in recovered}
    for layer in scene.layers:
        if layer.id in recovered_ids and layer.restoration_asset:
            digest=hashlib.sha256(asset_path(project,layer.restoration_asset).read_bytes()).hexdigest()
            key=(layer.text,tuple(round(v,3) for v in (layer.x,layer.y,layer.width,layer.height)),digest)
            if key in fingerprints:duplicates+=1;continue
            fingerprints.add(key)
        unique.append(layer)
    scene.layers=unique
    if duplicates:scene.warnings.append(f'{duplicates} 个完全相同的重复文字绘制已合并')
    if replacements:scene.warnings.append(f'{len(replacements)} 个图片文字行已本地识别为文本框，需人工核对')
    return scene,diagnostics
