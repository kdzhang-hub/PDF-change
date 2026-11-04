"""Local coloured-screen proposals, never semantic or automatic icon splitting.

The observed backdrop is a smooth RGB plane. Hidden background and soft-edge
colours are estimates; a user must inspect the whole foreground before applying.
"""
import cv2
import numpy as np
from skimage.metrics import structural_similarity


def propose(image):
    if image.ndim!=3 or image.shape[2]!=4 or min(image.shape[:2])<64 or image.shape[0]*image.shape[1]>2_000_000:
        raise ValueError('彩底分层需要64像素以上、200万像素以内的局部素材，请先裁剪照片区域')
    if np.any(image[:,:,3]!=255):raise ValueError('当前素材已有透明边缘，请用完整对象候选或画笔校正')
    rgb=image[:,:,:3].astype(float);h,w=rgb.shape[:2]
    hsv=cv2.cvtColor(image[:,:,:3],cv2.COLOR_RGB2HSV).astype(float)
    tile=max(3,round(min(h,w)*.06))
    corners=np.concatenate([hsv[:tile,:tile].reshape(-1,3),hsv[:tile,-tile:].reshape(-1,3)])
    angle=corners[:,0]*np.pi/90
    hue=float(np.arctan2(np.sin(angle).mean(),np.cos(angle).mean())*90/np.pi)%180
    sat,val=np.median(corners[:,1:],axis=0)
    corner_distance=np.abs(corners[:,0]-hue);corner_distance=np.minimum(corner_distance,180-corner_distance)
    if sat<90 or val<50 or np.percentile(corner_distance,95)>6 or np.max(np.abs(np.median(hsv[:tile,:tile],axis=(0,1))[1:]-np.median(hsv[:tile,-tile:],axis=(0,1))[1:]))>30:
        raise ValueError('上方两角没有一致彩色底，未修改原素材；请框选完整对象或使用本地SAM')
    distance=np.abs(hsv[:,:,0]-hue);distance=np.minimum(distance,180-distance)
    samples=(distance<8)&(hsv[:,:,1]>sat*.7)&(hsv[:,:,2]>val*.6)
    y,x=np.mgrid[:h,:w];design=np.stack([np.ones_like(x),x/w,y/h],-1).astype(float)
    for _ in range(4):
        ys,xs=np.where(samples)
        if len(xs)<h*w*.12 or np.ptp(xs)<w*.8 or np.ptp(ys)<h*.4:
            raise ValueError('可见背景样本不足，无法可靠补全，原素材已保留')
        coef,_,rank,_=np.linalg.lstsq(design[samples],rgb[samples],rcond=None)
        if rank!=3:raise ValueError('背景采样退化，原素材已保留')
        background=np.clip(design@coef,0,255);residual=np.linalg.norm(rgb-background,axis=2)
        samples&=residual<8
    hard=np.uint8(residual>20)
    count,labels,stats,_=cv2.connectedComponentsWithStats(hard,8)
    if count<2:raise ValueError('没有找到可分离前景，原素材已保留')
    areas=stats[1:,cv2.CC_STAT_AREA];largest=1+int(np.argmax(areas));area=int(areas.max())
    if not .1<area/(h*w)<.9 or area/max(1,int(areas.sum()))<.95:
        raise ValueError('没有找到单一完整前景，请使用候选合并或框选，原素材已保留')
    hard=np.uint8(labels==largest)
    core=cv2.erode(np.uint8((hard>0)&(residual>65)),np.ones((5,5),np.uint8),borderType=cv2.BORDER_CONSTANT,borderValue=0)>0
    if core.sum()<h*w*.04:raise ValueError('前景与底色过于接近，无法可靠分层，原素材已保留')
    near=cv2.dilate(hard,np.ones((7,7),np.uint8))>0
    _,owners=cv2.distanceTransformWithLabels(np.uint8(~core),cv2.DIST_L2,5,labelType=cv2.DIST_LABEL_PIXEL)
    sources=np.zeros((owners.max()+1,3));sources[owners[core]]=rgb[core]
    foreground=sources[owners];direction=foreground-background
    alpha=np.clip(np.sum((rgb-background)*direction,axis=2)/np.maximum(1,np.sum(direction*direction,axis=2)),0,1)
    alpha[core]=1;alpha[~near|(residual<8)]=0
    alpha=np.round(alpha*255)/255
    colour=(rgb-(1-alpha[:,:,None])*background)/np.maximum(1/255,alpha[:,:,None])
    # JPEG ringing can imply out-of-gamut RGB. Raising alpha to hide clipping
    # makes opaque blue specks. Keep soft alpha and gently use nearby core RGB.
    weight=1-.25*(1-np.clip((alpha-.8)/.2,0,1)[:,:,None])
    colour=weight*colour+(1-weight)*foreground
    cut=np.uint8(np.clip(np.dstack([np.round(colour),np.round(alpha*255)]),0,255));cut[alpha==0,:3]=0
    base=np.dstack([np.uint8(np.round(background)),np.full((h,w),255,np.uint8)])
    composed=np.uint8(np.round(cut[:,:,:3]*alpha[:,:,None]+base[:,:,:3]*(1-alpha[:,:,None])))
    quality=float(structural_similarity(image[:,:,:3],composed,channel_axis=2,data_range=255))
    if quality<.98:raise ValueError('彩底分层重合外观未通过0.98门槛，保留原素材，请用局部遮罩校正')
    return cut,base,{'ssim':quality,'background_plane':coef.tolist(),'soft_pixels':int(np.count_nonzero((alpha>0)&(alpha<1)))}


def comparison(cut,background):
    """Show the source-sized whole object on light and dark backdrops."""
    alpha=cut[:,:,3:4]/255
    return [np.uint8(np.round(cut[:,:,:3]*alpha+np.asarray(colour)*(1-alpha))) for colour in (background[:,:,:3],[255,255,255],[20,20,20])]
