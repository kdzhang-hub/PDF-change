"""Inspect local polar OCR on a circular badge; no project writes or answers."""
from pathlib import Path
import sys,json,math,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from PIL import Image
from backend.geometry_recovery import fit_circle
from backend.local_models import ocr,visible_rgb
from backend.raster import read_image


def locate(image):
    contours,_=cv2.findContours((image[:,:,3]>16).astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)
    candidates=[]
    for contour in contours:
        x,y,w,h=cv2.boundingRect(contour)
        if min(w,h)<50 or not .85<w/h<1.15:continue
        fit=fit_circle(contour)
        if fit and fit['coverage']>.85:candidates.append(fit)
    if len(candidates)!=1:raise ValueError(f'Expected one supported circle; found {len(candidates)}')
    return candidates[0]


def unwrap(rgb,center,radius,top=True,inner=.70,outer=.95,angular_range=None):
    angle0,angle1=angular_range or ((-155,-25) if top else (155,25))
    length=max(1,round(abs(math.radians(angle1-angle0))*radius*(inner+outer)/2))
    height=max(1,round(radius*(outer-inner)))
    angles=np.linspace(math.radians(angle0),math.radians(angle1),length)
    radii=np.linspace(radius*outer,radius*inner,height) if top else np.linspace(radius*inner,radius*outer,height)
    xx=(center[0]+radii[:,None]*np.cos(angles)).astype(np.float32)
    yy=(center[1]+radii[:,None]*np.sin(angles)).astype(np.float32)
    return cv2.remap(rgb,xx,yy,cv2.INTER_CUBIC,borderMode=cv2.BORDER_CONSTANT,borderValue=(7,55,104))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,default=Path('work/badge-unwrap-20261030'));parser.add_argument('--wide',action='store_true');args=parser.parse_args()
    folder=args.folder
    folder.mkdir(exist_ok=False)
    image=read_image('59e644dbdeca4fe48f4af272221f705c','paint-exact-47bdc19ba2954695906ab13d7b9e8f34.png')
    circle=locate(image);rgb,_=visible_rgb(image,(7,55,104));rows=[]
    (folder/'circle.json').write_text(json.dumps(circle,indent=2),'utf-8')
    for top in (True,False):
        for inner,outer in (((.58,.90),(.61,.88)) if args.wide else ((.70,.95),(.75,.92))):
            angles=((-160,-20) if top else (176,4)) if args.wide else None
            strip=unwrap(rgb,circle['center'],circle['radius']+1,top,inner,outer,angles)
            for binary in (False,True):
                pixels=strip
                if binary:
                    core=pixels.min(axis=2)>175
                    core[core.mean(axis=1)>.75]=False
                    pixels=np.repeat(np.where(core,0,255).astype(np.uint8)[:,:,None],3,axis=2)
                pixels=cv2.resize(pixels,None,fx=3,fy=3,interpolation=cv2.INTER_CUBIC)
                pixels=cv2.copyMakeBorder(pixels,12,12,12,12,cv2.BORDER_CONSTANT,value=(255,255,255) if binary else (7,55,104))
                name=f'{"top" if top else "bottom"}-{inner:.2f}-{outer:.2f}-{binary}'
                Image.fromarray(pixels).save(folder/(name+'.png'))
                records=ocr(pixels)
                row={'variant':name,'records':[{'text':t,'score':s,'poly':p.tolist()} for t,s,p in records]}
                rows.append(row);print(json.dumps(row,ensure_ascii=True),flush=True)
    (folder/'ocr.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf-8')
