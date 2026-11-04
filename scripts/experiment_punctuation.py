from pathlib import Path
import sys,json,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
from backend.store import ROOT,asset_path
from backend.text_recovery import fit_font
base=ROOT/'deliverables'/'real-case-20261027'/'round-16'
run=json.loads((base/'run.json').read_text('utf-8'));scene=json.loads((base/'scenes.json').read_text('utf-8'))[0]
rows=json.loads((base/'text-recovery-01.json').read_text('utf-8'));output=[]
for row in rows:
    if row['accepted'] or row['text'] not in ('前沿部署工程师','的成长之路'):continue
    layer=next(l for l in scene['layers'] if l['id']==row['id'])
    im=np.array(Image.open(asset_path(run['project'],layer['asset'])).convert('RGBA'))
    colors=im[:,:,:3][im[:,:,3]>180];quant=colors//24;values,counts=np.unique(quant,axis=0,return_counts=True)
    color=np.median(colors[np.all(quant==values[counts.argmax()],axis=1)],axis=0)
    glyph=(np.linalg.norm(im[:,:,:3].astype(float)-color,axis=2)<65)&(im[:,:,3]>60)
    ys,xs=np.where(glyph);alpha=np.where(glyph,im[:,:,3],0)[ys.min():ys.max()+1,xs.min():xs.max()+1]
    text=row['text'];candidates=[text,text+'(',text+'（',')'+text,'）'+text,text+')','('+text]
    variants=[]
    for candidate in candidates:
        start=time.monotonic();fit=fit_font(candidate,alpha)
        item={'text':candidate,'fit':fit,'seconds':round(time.monotonic()-start,2)};variants.append(item)
        print(json.dumps({'text':candidate,'score':fit['score'] if fit else None,'font':fit['font'] if fit else None,'seconds':item['seconds']},ensure_ascii=True),flush=True)
    output.append({'raw_text':text,'variants':variants})
folder=ROOT/'deliverables'/'optimization-20261028';folder.mkdir(exist_ok=True)
(folder/'punctuation-experiment.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),'utf-8')
