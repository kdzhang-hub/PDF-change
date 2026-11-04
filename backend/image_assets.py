"""Encode independent images without carrying RGB concealed by zero alpha.

Source assets stay untouched. Every visible and faint-alpha sample, the image
dimensions and its transform remain unchanged; no downsampling is performed.
"""
import io,math
from pathlib import Path
import numpy as np
import cv2
from PIL import Image


def png_bytes(image,size=None):
    pixels=np.array(image.convert('RGBA'))
    # Retain neighbouring RGB as a resampling guard, widened for small images.
    # This does not promise identical JPEG re-encoding during Office PDF export.
    radius=16
    if size:radius=max(radius,math.ceil(4*max(image.width/size[0],image.height/size[1])))
    if radius<max(image.size):
        near=cv2.dilate((pixels[:,:,3]>0).astype(np.uint8),np.ones((radius*2+1,radius*2+1),np.uint8))>0
        pixels[~near,:3]=0
    compact=Image.fromarray(pixels)
    options={key:image.info[key] for key in ('icc_profile','dpi') if key in image.info}
    buffer=io.BytesIO();compact.save(buffer,format='PNG',**options)
    return buffer.getvalue()


def picture_source(path,width=None,height=None):
    """Keep original bytes when no smaller transparent PNG can be produced."""
    path=Path(path)
    with Image.open(path) as image:
        if 'A' not in image.getbands() and 'transparency' not in image.info:return str(path)
        rgba=image.convert('RGBA');alpha=np.array(rgba.getchannel('A'))
        if not np.any(alpha==0):return str(path)
        encoded=png_bytes(image,(width,height) if width and height else None)
    return io.BytesIO(encoded) if len(encoded)<path.stat().st_size else str(path)
