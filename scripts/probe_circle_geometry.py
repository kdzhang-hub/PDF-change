"""Inspect visible colour arcs; no ground-truth coordinates are used for fitting."""
import sys,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import cv2,numpy as np
from PIL import Image


def circle_from_points(points):
    a=np.column_stack((2*points[:,0],2*points[:,1],np.ones(len(points))))
    x,y,c=np.linalg.lstsq(a,np.sum(points*points,axis=1),rcond=None)[0]
    return np.array([x,y]),float(np.sqrt(max(0,c+x*x+y*y)))


def fit_circle(contour):
    points=contour.reshape(-1,2).astype(float)
    if len(points)<50:return None
    rng=np.random.default_rng(0);best=None
    for _ in range(200):
        sample=points[rng.choice(len(points),3,replace=False)]
        if abs(np.linalg.det(np.column_stack((sample,np.ones(3)))))<10:continue
        center,radius=circle_from_points(sample)
        if not 12<radius<min(600,np.ptp(points,axis=0).max()):continue
        distances=np.abs(np.linalg.norm(points-center,axis=1)-radius)
        inside=distances<max(1,radius*.012)
        score=inside.sum()
        if best is None or score>best[0]:best=(score,center,radius,inside)
    if best is None:return None
    _,center,radius,inside=best
    for _ in range(2):
        center,radius=circle_from_points(points[inside])
        inside=np.abs(np.linalg.norm(points-center,axis=1)-radius)<max(1,radius*.012)
    angles=np.arctan2(*(points[inside]-center).T[::-1])
    bins=np.unique(np.floor((angles+np.pi)*72/(2*np.pi)).astype(int)%72)
    coverage=len(bins)/72;ratio=inside.mean()
    return {'center':center.tolist(),'radius':radius,'coverage':coverage,'inlier_ratio':float(ratio)} if coverage>.55 and ratio>.52 else None


def find(image):
    rgb=image[:,:,:3];quant=(rgb//16).astype(np.int32)
    codes=quant[:,:,0]*256+quant[:,:,1]*16+quant[:,:,2]
    values,counts=np.unique(codes,return_counts=True);output=[]
    for value in values[np.argsort(counts)[-24:]]:
        pixels=rgb[codes==value];color=np.median(pixels,axis=0)
        mask=(np.linalg.norm(rgb.astype(float)-color,axis=2)<3).astype(np.uint8)
        count,labels,stats,_=cv2.connectedComponentsWithStats(mask,8)
        for i in range(1,count):
            area=stats[i,cv2.CC_STAT_AREA]
            if not 300<area<image.shape[0]*image.shape[1]*.15:continue
            contour=max(cv2.findContours((labels==i).astype(np.uint8),cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_NONE)[0],key=cv2.contourArea)
            fitted=fit_circle(contour)
            if fitted and area/(np.pi*fitted['radius']**2)>.45:
                output.append({**fitted,'color':color.tolist(),'area':int(area)})
    return output


if __name__=='__main__':
    image=np.array(Image.open('samples/digital-reference.png').convert('RGBA'))
    result=find(image);path=Path('work/circle-geometry-probe-20261030.json')
    if path.exists():raise FileExistsError('Keep prior evidence')
    path.write_text(json.dumps(result,indent=2),'utf-8');print(json.dumps(result))
