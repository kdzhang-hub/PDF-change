"""Preserve a brand mark as one movable picture, without rewriting its glyphs."""
import cv2
import numpy as np
from .geometry_recovery import fit_circle
from .store import asset_path
from PIL import Image

NOTE='完整标识保留原始字形，可整体移动、缩放；不拆分其中的文字'


def preserved_text_region(scene,box):
    """Explicit intact marks are excluded from the ordinary-text inventory."""
    layers=scene['layers']
    for layer in layers:
        if layer['kind']!='image' or layer.get('content_role')!='logo' or not layer['visible']:continue
        if not layer.get('asset') or layer['asset']!=layer.get('restoration_asset'):continue
        if any(child.get('parent_id')==layer['id'] for child in layers):continue
        if layer.get('rotation',0):continue  # Require a verified oriented region before exempting rotated marks.
        x,y,w,h=[layer[k] for k in ('x','y','width','height')]
        if x-1<=box[0] and y-1<=box[1] and box[2]<=x+w+1 and box[3]<=y+h+1:return True
    return False


def detect_mark(image):
    """Conservative local evidence: a seal plus two adjacent wordmark rows.

    This is not a general logo classifier. Opaque photos, standalone labels,
    charts and full-page images must not be exempted merely for containing text.
    """
    height,width=image.shape[:2]
    if min(height,width)<48 or not 2<=width/height<=6 or np.mean(image[:,:,3]<24)<.12:return None
    if width>1200:
        ratio=1200/width;image=cv2.resize(image,(1200,round(height*ratio)));height,width=image.shape[:2]
    alpha=image[:,:,3]
    ink=(image[:,:,:3].min(axis=2)>145)&(alpha>64)
    if ink.sum()<30:ink=alpha>160
    masks=[alpha>16,ink]
    rings=[]
    for mask in masks:
        contours,_=cv2.findContours(mask.astype(np.uint8),cv2.RETR_LIST,cv2.CHAIN_APPROX_NONE)
        for contour in contours:
            x,y,w,h=cv2.boundingRect(contour)
            if min(w,h)<height*.60 or not .88<w/h<1.12:continue
            circle=fit_circle(contour)
            if circle and circle['coverage']>.94 and circle['inlier_ratio']>.82:rings.append(circle)
    for circle in sorted(rings,key=lambda c:c['radius'],reverse=True):
        cx,cy=circle['center'];radius=circle['radius']
        if not .32*height<radius<.55*height or cx>width*.3 or abs(cy-height/2)>height*.08:continue
        concentric=[other for other in rings if .78<other['radius']/radius<=1.01 and np.hypot(cx-other['center'][0],cy-other['center'][1])<radius*.05]
        if len({round(other['radius']/radius*50) for other in concentric})<3:continue
        yy,xx=np.ogrid[:height,:width];center=(xx-cx)**2+(yy-cy)**2<(radius*.45)**2
        if not .12<float(ink[center].mean())<.88:continue
        right=ink[:,min(width,int(cx+radius+2)):]
        if right.shape[1]<radius or right.sum()<30:continue
        occupied=(right.sum(axis=1)>2).astype(np.uint8)[:,None]
        occupied=cv2.morphologyEx(occupied,cv2.MORPH_CLOSE,np.ones((3,1),np.uint8))[:,0]
        edges=np.diff(np.r_[0,occupied,0].astype(int));starts=np.where(edges==1)[0];ends=np.where(edges==-1)[0]
        bands=[(a,b) for a,b in zip(starts,ends) if b-a>height*.06]
        if len(bands)!=2:continue
        return {'kind':'seal-wordmark','center':[cx/width,cy/height],'radius':radius/height}
    return None


def classify_image(layer,image):
    if layer.content_role!='auto' or layer.edited or layer.locked:return False
    if detect_mark(image) is None:return False
    layer.content_role='logo'
    if NOTE not in layer.notes:layer.notes.append(NOTE)
    return True


def classify_scene(project,scene):
    for layer in scene.layers:
        if layer.kind=='image' and layer.original_type=='image' and layer.content_role=='auto':
            with Image.open(asset_path(project,layer.asset)) as image:classify_image(layer,np.array(image.convert('RGBA')))
    return scene


def set_image_role(project,page,identity,role):
    result=page.model_copy(deep=True)
    layer=next((item for item in result.layers if item.id==identity),None)
    if layer is None or layer.kind!='image' or layer.locked:raise ValueError('请选择未锁定的图片素材')
    if role=='content':
        layer.content_role='content';layer.edited=True
        layer.notes=[note for note in layer.notes if note!=NOTE]
        return result
    if role!='logo':raise ValueError('无效素材处理方式')
    # Reunite only descendants created automatically from this picture. Never
    # discard an independently placed label or a user's edited/locked child.
    descendants=[];owners={layer.id}
    while True:
        children=[item for item in result.layers if item.parent_id in owners and item.id not in owners]
        if not children:break
        descendants.extend(children);owners.update(item.id for item in children)
    if any(item.edited or item.locked or item.source not in ('local-ocr','local-ocr-font-fit','local-circle-reconstruction','local-segmentation') for item in descendants):
        raise ValueError('此素材包含人工修改或独立子对象，已保留现有内容；请先恢复所需历史版本')
    original=layer.restoration_asset or layer.asset
    if original is None:raise ValueError('未找到留存的原始标识素材')
    with Image.open(asset_path(project,original)) as source,Image.open(asset_path(project,layer.asset)) as current:
        if source.size!=current.size:raise ValueError('原素材与当前裁切范围不同，请选择完整原始素材后保留标识')
    layer.asset=original;layer.restoration_asset=original;layer.content_role='logo';layer.recognized_text=''
    layer.needs_review=False
    if NOTE not in layer.notes:layer.notes.append(NOTE)
    result.layers=[item for item in result.layers if item.id not in owners or item.id==layer.id]
    return result
