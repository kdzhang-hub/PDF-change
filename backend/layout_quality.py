"""Bounded local raster evidence for layouts whose native origins also match."""
import math
import fitz
import numpy as np
from skimage.metrics import structural_similarity


def infer_quantum(advances):
    """Accept a measured regular lattice, never assume one Office version."""
    values=np.asarray(advances,dtype=float)
    if len(values)<9 or not np.isfinite(values).all():return None
    unique=np.unique(np.round(values,3))
    if len(unique)<4:return None
    gaps=np.diff(unique);quantum=float(np.median(gaps))
    if not .02<=quantum<=.25:return None
    residual=(values-values.min())/quantum
    if np.max(abs(residual-np.round(residual)))*quantum>max(.003,quantum*.04):return None
    if np.any(np.diff(values)<-.003):return None
    return round(quantum,3)


def quantize(value,quantum):
    # Native spacing sweeps show half steps rounding away from zero.
    return float(np.sign(value)*np.floor(abs(value)/quantum+.500000001)*quantum)


def corrected_spacing(values,selected,delta,quantum=None,precision=100):
    result=values.copy();carry=0.0
    for index,left,right in zip(selected,delta,delta[1:]):
        correction=float(right[0]-left[0])
        if quantum:
            desired=quantize(values[index],quantum)+correction+carry
            result[index]=round(quantize(desired,quantum),6)
            carry=desired-result[index]
        else:result[index]=round((values[index]+correction)*precision)/precision
    return result


def prepare_reference(source,index,scene,max_pixels=8_000_000):
    layers=[l for l in scene.layers if l.text_layout and l.source_ink_bbox]
    if not layers:return None
    with fitz.open(source) as doc:
        page=doc[index]
        if page.rotation or abs(page.rect.width-scene.width)>.01 or abs(page.rect.height-scene.height)>.01:return None
        box=page.rect;area=box.width*box.height;rasters=[]
        scales=sorted({min(s,math.sqrt(max_pixels/max(1,area))) for s in (1.5,3)})
        for scale in scales:
            pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),clip=box,colorspace=fitz.csRGB,alpha=False)
            pixels=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,3).copy()
            rasters.append((scale,pix.x,pix.y,pixels))
        return {'box':box,'rasters':rasters,'layers':layers}


def visual_scores(reference,path):
    if reference is None or not path.is_file():return {}
    scores={l.id:[] for l in reference['layers']}
    with fitz.open(path) as doc:
        page=doc[0]
        for scale,px,py,expected in reference['rasters']:
            pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),clip=reference['box'],colorspace=fitz.csRGB,alpha=False)
            actual=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,3)
            if (pix.x,pix.y)!=(px,py) or actual.shape!=expected.shape:continue
            for layer in reference['layers']:
                box=(fitz.Rect(layer.source_ink_bbox)+(-1,-1,1,1))&reference['box']
                crop=(box*fitz.Matrix(scale,scale)).irect
                x0,x1=max(0,crop.x0-px),min(pix.width,crop.x1-px)
                y0,y1=max(0,crop.y0-py),min(pix.height,crop.y1-py)
                if min(x1-x0,y1-y0)<7:continue
                a=expected[y0:y1,x0:x1];b=actual[y0:y1,x0:x1]
                scores[layer.id].append(float(structural_similarity(a,b,channel_axis=2,data_range=255)))
    return {id:float(np.mean(values)) for id,values in scores.items() if values}
