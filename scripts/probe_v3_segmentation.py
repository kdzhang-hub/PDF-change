"""Inspect automatic and manually guided masks; never modify a project."""
from pathlib import Path
import argparse,json
import cv2,numpy as np
from PIL import Image,ImageDraw
from backend.raster import read_image
from backend.local_models import sam_mask

parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True);args=parser.parse_args()
root=Path(__file__).resolve().parents[1];out=args.folder
if out.exists():raise FileExistsError('Keep previous segmentation evidence')
out.mkdir(parents=True)
source=root/'deliverables'/'v3-movement-20261028'/'image-round-04'
project=json.loads((source/'run.json').read_text('utf-8'))['project']
scene=json.loads((source/'scenes.json').read_text('utf-8'))[0]
layer=next(l for l in scene['layers'] if l['kind']=='image' and l.get('restoration_asset'))
image=read_image(project,layer['restoration_asset']);scale=min(1,1536/max(image.shape[:2]))
image=cv2.resize(image,(round(image.shape[1]*scale),round(image.shape[0]*scale)))
def point(x,y):return [(x-layer['x'])/layer['width']*image.shape[1],(y-layer['y'])/layer['height']*image.shape[0]]
box=[*point(680,300),*point(790,533)]
groups={'automatic':sam_mask(image,automatic=True),'guided':sam_mask(image,box=box,points=[point(735,395)])}
rows=[]
for name,masks in groups.items():
    np.savez_compressed(out/(name+'.npz'),**{f'mask_{i}':m for i,m in enumerate(masks)})
    sheet=Image.new('RGB',(1000,240*max(1,(len(masks)+3)//4)),'#e8edf2');draw=ImageDraw.Draw(sheet)
    for i,mask in enumerate(masks):
        ys,xs=np.where(mask)
        if not len(xs):continue
        cut=image.copy();cut[:,:,3]=np.where(mask,cut[:,:,3],0)
        bitmap=Image.fromarray(cut).crop((xs.min(),ys.min(),xs.max()+1,ys.max()+1))
        bitmap.thumbnail((245,210));x=i%4*250;y=i//4*240
        sheet.paste(bitmap,(x,y+25),bitmap);draw.text((x+5,y+5),str(i)+' area '+str(int(mask.sum())),fill='black')
        rows.append({'kind':name,'index':i,'area':int(mask.sum()),'box':[int(xs.min()),int(ys.min()),int(xs.max()+1),int(ys.max()+1)]})
    sheet.save(out/(name+'.png'))
Image.fromarray(image).save(out/'input.png')
(out/'masks.json').write_text(json.dumps({'layer':layer,'masks':rows,'guided_box':box},ensure_ascii=False,indent=2),'utf-8')
print(json.dumps(rows),flush=True)
