"""Recover whole-word gradient fills from local visible glyph cores."""
from dataclasses import dataclass
import cv2
import numpy as np


@dataclass(frozen=True)
class GradientFit:
    colors: list[str]
    positions: list[float]
    mean_error: float
    supported_rows: int
    core_pixels: int
    method: str
    angle: float = 90


def vertical_gradient(image,ink=None):
    image=np.asarray(image)
    if image.ndim!=3 or image.shape[2] not in (3,4) or min(image.shape[:2])<1:
        raise ValueError('渐变采样需要 RGB 或 RGBA 图片')
    rgb=image[:,:,:3].astype(float);height=image.shape[0]
    if ink is not None:
        selected=np.asarray(ink,dtype=bool)
        if selected.shape!=image.shape[:2]:raise ValueError('字芯遮罩与图片尺寸不符')
        if image.shape[2]==4:selected=selected&(image[:,:,3]>=240)
        core=cv2.erode(selected.astype(np.uint8),np.ones((3,3),np.uint8),borderType=cv2.BORDER_CONSTANT,borderValue=0)>0
        # Narrow strokes still contain useful evidence. Do not erase a label
        # simply because its glyphs cannot survive the interior erosion.
        if core.sum()>=max(12,selected.sum()*.12):selected=core
    elif image.shape[2]==4:
        selected=image[:,:,3]>=240
        if not selected.any():selected=image[:,:,3]>=150
    else:
        selected=np.ones(image.shape[:2],bool)
    if not selected.any():raise ValueError('没有足够可见字芯用于渐变采样')
    ys=np.flatnonzero(selected.any(axis=1))
    values=np.array([np.median(rgb[y,selected[y]],axis=0) for y in ys])
    x=ys/max(1,height-1);counts=selected.sum(axis=1)[ys]
    method='observed-rows';profile=values
    if len(ys)>=6:
        matrix=np.vander(x,4,increasing=True);base=np.sqrt(np.minimum(counts,64));weights=base.copy()
        for _ in range(4):
            coefficients=np.linalg.lstsq(matrix*weights[:,None],values*weights[:,None],rcond=None)[0]
            fitted=matrix@coefficients;residual=np.linalg.norm(fitted-values,axis=1)
            weights=base*np.sqrt(np.minimum(1,8/np.maximum(1,residual)))
        # A sharp multistop fill must not be replaced by a smooth polynomial.
        if np.percentile(np.abs(fitted-values),90)<=5:
            method='supported-smooth-fit';profile=fitted
    positions=np.linspace(0,1,8)
    if method=='supported-smooth-fit':stops=np.vander(positions,4,increasing=True)@coefficients
    else:stops=np.array([np.interp(positions,x,profile[:,c]) for c in range(3)]).T
    stops=np.clip(np.rint(stops),0,255).astype(np.uint8)
    reconstructed=np.array([np.interp(x,positions,stops[:,c]) for c in range(3)]).T
    error=float(np.abs(reconstructed-values).mean())
    return GradientFit(['#'+''.join(f'{int(v):02x}' for v in stop) for stop in stops],positions.tolist(),error,len(ys),int(selected.sum()),method)


def linear_gradient(image,ink):
    """Fit one angled fill for a complete word; no per-letter objects."""
    image=np.asarray(image);selected=np.asarray(ink,dtype=bool)
    if image.ndim!=3 or image.shape[2] not in (3,4) or min(image.shape[:2])<1 or selected.shape!=image.shape[:2]:
        raise ValueError('渐变采样图片与字芯遮罩不符')
    if image.shape[2]==4:selected=selected&(image[:,:,3]>=240)
    radius=min(6,max(1,round(min(image.shape[:2])*.012)))
    core=cv2.erode(selected.astype(np.uint8),np.ones((radius*2+1,radius*2+1),np.uint8),borderType=cv2.BORDER_CONSTANT,borderValue=0)>0
    if core.sum()>=max(12,selected.sum()*.12):selected=core
    yy,xx=np.where(selected)
    if len(xx)<8:return vertical_gradient(image,selected)
    stride=max(1,int(np.ceil(len(xx)/4000)));yy,xx=yy[::stride],xx[::stride]
    values=image[yy,xx,:3].astype(float);height,width=image.shape[:2]

    def fit(angle):
        radians=np.radians(angle);dx,dy=np.cos(radians),np.sin(radians)
        minimum=min(0,(width-1)*dx)+min(0,(height-1)*dy)
        span=abs((width-1)*dx)+abs((height-1)*dy)
        projection=(xx*dx+yy*dy-minimum)/max(1,span)
        positions=np.linspace(projection.min(),projection.max(),8)
        basis=np.array([np.interp(projection,positions,np.eye(8)[i]) for i in range(8)]).T
        weights=np.ones(len(xx))
        for _ in range(4):
            colors=np.linalg.lstsq(basis*weights[:,None],values*weights[:,None],rcond=None)[0]
            residual=np.abs(basis@colors-values).mean(axis=1)
            weights=np.sqrt(np.minimum(1,8/np.maximum(1,residual)))
        objective=float(np.minimum(residual,25).mean())
        return objective,angle,colors,positions,float(residual.mean())

    best=min((fit(angle) for angle in range(0,181,10)),key=lambda v:v[0])
    best=min((fit(angle) for angle in np.arange(max(0,best[1]-10),min(180,best[1]+10)+.1,1)),key=lambda v:v[0])
    best=min((fit(angle) for angle in np.arange(max(0,best[1]-1),min(180,best[1]+1)+.01,.25)),key=lambda v:v[0])
    _,angle,colors,positions,error=best;colors=np.clip(np.rint(colors),0,255).astype(np.uint8)
    return GradientFit(['#'+''.join(f'{int(v):02x}' for v in color) for color in colors],positions.tolist(),error,
        int(selected.any(axis=1).sum()),int(selected.sum()),'directional-piecewise',float(angle))
