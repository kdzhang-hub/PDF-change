from pathlib import Path
import sys,json,time,socket
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image,ImageDraw
def no_network(*args,**kwargs):raise RuntimeError('Network blocked by offline acceptance test')
socket.socket.connect=no_network
from backend.local_models import ocr,sam_mask
from backend.store import ROOT
import torch
out=ROOT/'deliverables';out.mkdir(exist_ok=True)
result={'network_blocked':True,'cuda':torch.cuda.is_available(),'gpu':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None}
started=time.perf_counter()
texts=ocr(np.array(Image.open(ROOT/'samples'/'digital-reference.png').convert('RGBA')))
result['ocr_seconds']=round(time.perf_counter()-started,3)
result['ocr_texts']=[t for t,s,p in texts]
assert any('128.50' in t for t,s,p in texts)
im=Image.new('RGB',(600,360),'white');draw=ImageDraw.Draw(im);draw.ellipse((40,50,180,190),fill='#4169e1');draw.rectangle((260,70,450,200),fill='#3fb69c')
source=np.array(im)
started=time.perf_counter();masks=sam_mask(source,points=[[100,110]])
result['sam_seconds']=round(time.perf_counter()-started,3)
truth=np.all(source==[65,105,225],axis=2)
mask=masks[0];result['sam_mask_iou']=float(np.logical_and(truth,mask).sum()/np.logical_or(truth,mask).sum())
Image.fromarray(mask.astype(np.uint8)*255).save(out/'sam-mask-test.png')
result['peak_gpu_memory_mb']=round(torch.cuda.max_memory_allocated()/1024/1024,1) if torch.cuda.is_available() else 0
(out/'offline-model-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(result,ensure_ascii=True,indent=2))
assert result['sam_mask_iou']>.9
