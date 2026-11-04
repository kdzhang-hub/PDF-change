"""Local diagnostic crops and contrast variants; never modifies a project."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from backend.local_models import ocr,visible_rgb
from backend.raster import read_image


if __name__=='__main__':
    path=Path('work/logo-ocr-probe-20261030.json')
    if path.exists():raise FileExistsError('Previous evidence is preserved')
    image=read_image('59e644dbdeca4fe48f4af272221f705c','paint-exact-47bdc19ba2954695906ab13d7b9e8f34.png')
    rgb,_=visible_rgb(image,(7,55,104))
    core=(rgb.min(axis=2)>175).astype(np.uint8)
    binary=np.repeat((255-core*255)[:,:,None],3,axis=2)
    variants=[('full',rgb),('full-2x',cv2.resize(rgb,None,fx=2,fy=2)),('full-binary',binary),
              ('top-right',rgb[:100,145:]),('top-right-binary',binary[:100,145:]),
              ('top-right-3x',cv2.resize(rgb[:100,145:],None,fx=3,fy=3))]
    rows=[]
    for name,pixels in variants:
        records=ocr(pixels)
        rows.append({'name':name,'records':[{'text':text,'score':score,'poly':poly.tolist()} for text,score,poly in records]})
        print(json.dumps(rows[-1],ensure_ascii=True),flush=True)
    path.write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf-8')
