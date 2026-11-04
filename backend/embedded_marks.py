"""Extract supported whole marks from opaque raster pages before ordinary OCR.

The crop retains source pixels. The concealed backdrop is a local smooth-colour
inference, explicitly flagged; it is never described as recovered hidden data.
"""
import cv2
import numpy as np
from .geometry_recovery import fit_circle
from .logo_policy import detect_mark,NOTE
from .models import LayerElement


def smooth_backdrop(crop):
    height,width=crop.shape[:2]
    yy,xx=np.mgrid[:height,:width]
    border=(xx<3)|(xx>=width-3)|(yy<3)|(yy>=height-3)
    design=np.stack([np.ones((height,width)),xx/width,yy/height],axis=-1)
    use=border.copy();rgb=crop[:,:,:3].astype(float)
    for _ in range(3):
        if use.sum()<20:return None
        model=np.linalg.lstsq(design[use],rgb[use],rcond=None)[0]
        prediction=design@model;errors=np.linalg.norm(rgb-prediction,axis=2)
        use=border&(errors<max(8,float(np.median(errors[border]))*3))
    error=float(np.percentile(errors[border],80))
    if error>7 or use.sum()/border.sum()<.88 or np.abs(model[1:]).max()>25:return None
    return np.round(np.clip(prediction,0,255)).astype(np.uint8),errors,error


def raw_rings(crop,errors,center,radius):
    """Require source evidence; smoothing must not invent a second seal ring."""
    radii=[];cx,cy=center
    for mask in (errors>20,crop[:,:,:3].min(axis=2)>145):
        contours,_=cv2.findContours(mask.astype(np.uint8),cv2.RETR_LIST,cv2.CHAIN_APPROX_NONE)
        for contour in contours:
            x,y,w,h=cv2.boundingRect(contour)
            if min(w,h)<radius*1.5 or not .88<w/h<1.12:continue
            circle=fit_circle(contour)
            if not circle or circle['coverage']<.94 or circle['inlier_ratio']<.60:continue
            if not .78<circle['radius']/radius<1.1:continue
            if np.hypot(cx-circle['center'][0],cy-circle['center'][1])>radius*.05:continue
            radii.append(circle['radius'])
    distinct=[]
    for value in sorted(radii):
        if not distinct or value-distinct[-1]>radius*.018:distinct.append(value)
    return len(distinct)>=3


def locate(image):
    height,width=image.shape[:2]
    if min(height,width)<200 or width<600 or np.mean(image[:,:,3]>250)<.85:return []
    factor=min(1,2000/width)
    scan=cv2.resize(image,(round(width*factor),round(height*factor))) if factor<1 else image
    ink=((scan[:,:,:3].min(axis=2)>145)&(scan[:,:,3]>128)).astype(np.uint8)
    contours,_=cv2.findContours(ink,cv2.RETR_LIST,cv2.CHAIN_APPROX_NONE)
    circles=[]
    for contour in contours:
        x,y,w,h=cv2.boundingRect(contour)
        if not 25<min(w,h)<scan.shape[0]*.24 or not .88<w/h<1.12:continue
        perimeter=cv2.arcLength(contour,True)
        if perimeter<1 or 4*np.pi*cv2.contourArea(contour)/(perimeter*perimeter)<.72:continue
        circle=fit_circle(contour)
        if circle and circle['coverage']>.94 and circle['inlier_ratio']>.82:circles.append(circle)
    regions=[]
    for circle in sorted(circles,key=lambda c:c['radius'],reverse=True):
        cx,cy=np.array(circle['center'])/factor;radius=circle['radius']/factor/.92
        if any(np.hypot(cx-region['center'][0],cy-region['center'][1])<radius for region in regions):continue
        left=max(0,int(cx-radius*1.12));top=max(0,int(cy-radius*1.12))
        right=min(width,int(cx+radius*5.4));bottom=min(height,int(cy+radius*1.12))
        if (right-left)*(bottom-top)>height*width*.12:continue
        crop=image[top:bottom,left:right]
        if not np.all(crop[:,:,3]==255):continue
        fit=smooth_backdrop(crop)
        if fit is None:continue
        background,errors,error=fit
        if not raw_rings(crop,errors,(cx-left,cy-top),radius):continue
        # Smooth only a detection proxy. The extracted mark is an unchanged
        # rectangular source crop, including its original edge/background pixels.
        # Normalize detection scale: a fixed one-pixel smoothing at native
        # resolution misses high-DPI glow edges. Export always uses the crop.
        proxy=crop.copy();proxy_errors=errors
        if crop.shape[0]>100:
            size=(max(1,round(crop.shape[1]*100/crop.shape[0])),100)
            proxy=cv2.resize(proxy,size,interpolation=cv2.INTER_AREA)
            proxy_errors=cv2.resize(errors,size,interpolation=cv2.INTER_AREA)
        alpha=np.where(proxy_errors>12,255,0).astype(np.uint8)
        proxy[:,:,3]=np.where(cv2.GaussianBlur(alpha,(0,0),1)>155,255,0)
        mark=detect_mark(proxy)
        if mark is None:continue
        found_x=left+mark['center'][0]*(right-left);found_y=top+mark['center'][1]*(bottom-top)
        if np.hypot(found_x-cx,found_y-cy)>radius*.15:continue
        regions.append({'bounds':[left,top,right,bottom],'center':[float(cx),float(cy)],
            'background':background,'background_error':error})
    return regions


def extract(project,layer,image):
    if layer.content_role!='auto' or layer.edited or layer.locked or layer.rotation or layer.opacity<.999:return image,[],[]
    regions=locate(image)
    if not regions:return image,[],[]
    from .raster import save_image
    layer.restoration_asset=layer.restoration_asset or layer.asset
    work=image.copy();children=[];diagnostics=[]
    sx=layer.width/image.shape[1];sy=layer.height/image.shape[0]
    for index,region in enumerate(regions):
        left,top,right,bottom=region['bounds']
        original=image[top:bottom,left:right].copy()
        asset=save_image(project,original,'whole-mark')
        child=LayerElement(kind='image',name=layer.name+' · 完整标识',x=layer.x+left*sx,y=layer.y+top*sy,
            width=(right-left)*sx,height=(bottom-top)*sy,z=layer.z+.75+index*.0001,
            opacity=layer.opacity,visible=layer.visible,group_id=layer.group_id,parent_id=layer.id,
            asset=asset,restoration_asset=asset,content_role='logo',original_type='image',
            source='local-mark-cutout',needs_review=True,
            notes=[NOTE,'从图片页面裁剪原像素，包含少量原背景；移动后需核对裁剪边缘'])
        children.append(child)
        work[top:bottom,left:right,:3]=region['background']
        diagnostics.append({'id':child.id,'bounds':region['bounds'],'background_error':region['background_error']})
    layer.asset=save_image(project,work,'mark-clean')
    layer.inferred=True;layer.needs_review=True
    layer.notes.append('标识原位置已用周边平滑颜色推断补全，请检查底层；不是原始隐藏背景')
    return work,children,diagnostics
