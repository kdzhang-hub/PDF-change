"""Test frame removal and isolated glyphs using the already provisioned OCR.

This diagnostic deliberately never supplies expected words to recognition.
"""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from PIL import Image
from backend import local_models


def clean(strip):
    pixels=strip[12:-12,12:-12].copy()
    background=np.median(pixels[pixels.min(axis=2)<100],axis=0).astype(np.uint8)
    rows=(pixels.min(axis=2)>140).mean(axis=1)>.6
    rows=cv2.dilate(rows.astype(np.uint8)[:,None],np.ones((3,1),np.uint8))[:,0]>0
    pixels[rows]=background
    ink=pixels.min(axis=2)>155
    ys,xs=np.where(ink)
    if not len(xs):raise ValueError('No supported glyphs after removing circular frame')
    return pixels[ys.min():ys.max()+1,xs.min():xs.max()+1]


def variants(pixels):
    gray=cv2.cvtColor(pixels,cv2.COLOR_RGB2GRAY)
    inverse=np.round(255-np.clip((gray.astype(float)-70)*255/185,0,255)).astype(np.uint8)
    return [('rgb',pixels),('gray',np.repeat(inverse[:,:,None],3,axis=2))]


if __name__=='__main__':
    source=Path('work/badge-unwrap-round2-20261030');out=Path('work/badge-recognition-20261030');out.mkdir(exist_ok=False)
    records=[]
    first=np.array(Image.open(source/'top-0.61-0.88-False.png').convert('RGB'))
    local_models.ocr(first)
    # The installed, pinned PaddleX wrapper forwards this attribute to its OCR
    # pipeline. Use the existing recognition model without another download.
    recognizer=local_models._OCR_ENGINE.paddlex_pipeline.text_rec_model
    for file in sorted(source.glob('*False.png')):
        pixels=clean(np.array(Image.open(file).convert('RGB')))
        for name,image in variants(pixels):
            bg=(255,255,255) if name=='gray' else tuple(map(int,np.median(image.reshape(-1,3),axis=0)))
            padded=cv2.copyMakeBorder(image,6,6,6,6,cv2.BORDER_CONSTANT,value=bg)
            Image.fromarray(padded).save(out/(file.stem+'-'+name+'.png'))
            line=list(recognizer([padded[:,:,::-1]]))[0]
            row={'source':file.name,'variant':name,'line':line['rec_text'],'score':float(line['rec_score']),'glyphs':[]}
            if file.name.startswith('top'):
                ink=image.min(axis=2)>155 if name=='rgb' else image.min(axis=2)<160
                active=(ink.sum(axis=0)>2).astype(np.uint8)[None,:]
                active=cv2.morphologyEx(active,cv2.MORPH_CLOSE,np.ones((1,7),np.uint8))[0]
                edges=np.diff(np.r_[0,active,0].astype(int));starts=np.where(edges==1)[0];ends=np.where(edges==-1)[0]
                tiles=[];boxes=[]
                for left,right in zip(starts,ends):
                    if right-left<5:continue
                    tile=image[:,left:right]
                    tiles.append(cv2.copyMakeBorder(tile,6,6,6,6,cv2.BORDER_CONSTANT,value=bg)[:,:,::-1]);boxes.append((int(left),int(right)))
                if tiles:
                    for box,result in zip(boxes,recognizer(tiles)):
                        row['glyphs'].append({'interval':box,'text':result['rec_text'],'score':float(result['rec_score'])})
            records.append(row);print(json.dumps(row,ensure_ascii=True),flush=True)
    (out/'results.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),'utf-8')
