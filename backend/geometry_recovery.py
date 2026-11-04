"""Conservative local reconstruction of complete, overlapping flat circles.

Only observed arcs and colour compositing are evidence. Covered geometry is
explicitly inferred; ambiguous or visually inconsistent fits keep their raster.
"""
import math
import cv2
import numpy as np
from .models import LayerElement,PathCommand


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


def circle_alpha(center,radius,box):
    x0,y0,x1,y1=box
    yy,xx=np.mgrid[y0:y1,x0:x1]
    # Coordinates address pixel edges, so evaluate coverage at pixel centres.
    return np.clip(radius+.5-np.hypot(xx+.5-center[0],yy+.5-center[1]),0,1)


def circle_path(width,height):
    k=.5522847498307936;rx=width/2;ry=height/2
    commands=[('M',[width,ry]),('C',[width,ry+k*ry,rx+k*rx,height,rx,height]),
              ('C',[rx-k*rx,height,0,ry+k*ry,0,ry]),
              ('C',[0,ry-k*ry,rx-k*rx,0,rx,0]),
              ('C',[rx+k*rx,0,width,ry-k*ry,width,ry]),('Z',[])]
    return [PathCommand(op=op,points=points) for op,points in commands]


def fit_pair(image,first,second):
    """Validate a complete two-object explanation, including overlap colour."""
    circles=[]
    for item in (first,second):
        circles.append((np.array(item['center'])+.5,item['radius']+1))
    a,b=circles
    distance=np.linalg.norm(a[0]-b[0])
    if not abs(a[1]-b[1])+4<distance<a[1]+b[1]-4:return None
    x0,y0=np.floor(np.minimum(a[0]-a[1],b[0]-b[1])-4).astype(int)
    x1,y1=np.ceil(np.maximum(a[0]+a[1],b[0]+b[1])+4).astype(int)
    if x0<0 or y0<0 or x1>image.shape[1] or y1>image.shape[0]:return None
    box=(x0,y0,x1,y1);alphas=[circle_alpha(c,r,box) for c,r in circles]
    raw=image[y0:y1,x0:x1,:3].astype(float)
    exterior=(alphas[0]==0)&(alphas[1]==0)
    if exterior.sum()<100:return None
    background=np.median(raw[exterior],axis=0)
    if np.mean(np.linalg.norm(raw[exterior]-background,axis=1)<5)<.995:return None
    regions=[(alphas[0]>.999)&(alphas[1]<.001),
             (alphas[1]>.999)&(alphas[0]<.001),(alphas[0]>.999)&(alphas[1]>.999)]
    if any(region.sum()<100 for region in regions):return None
    colors=[np.median(raw[region],axis=0) for region in regions]
    if any(np.mean(np.linalg.norm(raw[region]-color,axis=1)<5)<.995 for region,color in zip(regions,colors)):return None
    results=[]
    for back,front in ((0,1),(1,0)):
        bottom=colors[back];visible_top=colors[front];overlap=colors[2]
        vector=bottom-background;denominator=vector@vector
        if denominator<1600:continue
        opacity=1-float((overlap-visible_top)@vector/denominator)
        if not .12<opacity<=1:continue
        foreground=(visible_top-(1-opacity)*background)/opacity
        if np.any(foreground < -2) or np.any(foreground>257):continue
        foreground=np.clip(foreground,0,255)
        predicted=np.broadcast_to(background,raw.shape).copy()
        for index,color,alpha in ((back,bottom,1),(front,foreground,opacity)):
            coverage=alphas[index][:,:,None]*alpha
            predicted=predicted*(1-coverage)+color*coverage
        difference=np.abs(predicted-raw)
        yy,xx=np.mgrid[y0:y1,x0:x1]
        interior=np.ones(raw.shape[:2],bool)
        for center,radius in circles:
            interior&=np.abs(np.hypot(xx+.5-center[0],yy+.5-center[1])-radius)>2
        # A small unrelated icon must not be erased just because it barely
        # affects a page-level similarity score.
        if np.max(difference[interior],initial=0)>9:continue
        error=float(difference.mean())
        if error>2 or np.quantile(difference,.95)>8:continue
        results.append({'error':error,'box':box,'circles':circles,'background':background,
                        'back':back,'front':front,'colors':{back:bottom,front:foreground},
                        'opacity':opacity,'mask':cv2.dilate((np.maximum(*alphas)>0).astype(np.uint8),np.ones((3,3),np.uint8))>0})
    return min(results,key=lambda row:row['error']) if results else None


def recover_circles(parent,image):
    """Return a cleaned bitmap and complete native circles, or change nothing."""
    if parent.opacity<1 or max(image.shape[:2])>2200 or np.any(image[:,:,3]<250):return image,[],[]
    border=np.concatenate((image[0,:,:3],image[-1,:,:3],image[:,0,:3],image[:,-1,:3]))
    background=np.median(border,axis=0)
    if np.mean(np.linalg.norm(border-background,axis=1)<12)<.96:return image,[],[]
    candidates=find(image);used=set();work=image.copy();layers=[];diagnostics=[]
    sx=parent.width/image.shape[1];sy=parent.height/image.shape[0]
    angle=math.radians(parent.rotation);cs=math.cos(angle);sn=math.sin(angle)
    for i,first in enumerate(candidates):
        if i in used:continue
        for j in range(i+1,len(candidates)):
            if j in used:continue
            result=fit_pair(work,first,candidates[j])
            if result is None:continue
            x0,y0,x1,y1=result['box'];patch=work[y0:y1,x0:x1,:3]
            patch[result['mask']]=np.round(result['background']).astype(np.uint8)
            for position,index in enumerate((result['back'],result['front'])):
                center,radius=result['circles'][index]
                px=(center[0]-radius)*sx;py=(center[1]-radius)*sy
                width=radius*2*sx;height=radius*2*sy
                color='#'+''.join(f'{round(v):02x}' for v in result['colors'][index])
                layers.append(LayerElement(kind='path',name=f'还原圆形 {len(layers)+1}',
                    x=parent.x+cs*px-sn*py,y=parent.y+sn*px+cs*py,
                    width=width,height=height,rotation=parent.rotation,
                    z=parent.z+.15+len(layers)*.0001,opacity=parent.opacity,
                    fill=color,fill_opacity=result['opacity'] if position else 1,
                    path=circle_path(width,height),parent_id=parent.id,
                    source='local-circle-reconstruction',confidence=.98,needs_review=True,inferred=True,
                    restoration_asset=parent.restoration_asset or parent.asset,
                    notes=['本地从可见圆弧推断完整圆形；被遮挡轮廓与透明颜色需人工确认',
                           '可改填充色、透明度、大小与位置；原圆形像素已从底层清除']))
            diagnostics.append({'objects':2,'local_mean_absolute_error':result['error'],
                                'foreground_opacity':result['opacity'],'box':[int(v) for v in result['box']]})
            used.update((i,j));break
    return work,layers,diagnostics
