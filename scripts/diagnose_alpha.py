from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import store
from backend.models import PageScene,LayerElement
from backend.raster import save_image
from backend.export import export_pptx
import numpy as np
from PIL import Image
out=store.ROOT/'work'/'alpha-diagnostic';out.mkdir(parents=True,exist_ok=True)
store.init();p=store.create('Alpha diagnostic')
base=np.full((200,400,4),[5,40,86,255],np.uint8)
overlay=np.full((120,220,4),[64,188,239,128],np.uint8)
canvas=Image.fromarray(base);canvas.alpha_composite(Image.fromarray(overlay),(90,40));canvas.convert('RGB').save(out/'expected.png')
scene=PageScene(index=0,width=400,height=200,original='none',status='ready',layers=[
 LayerElement(kind='image',name='Base',x=0,y=0,width=400,height=200,asset=save_image(p,base)),
 LayerElement(kind='image',name='Alpha',x=90,y=40,width=220,height=120,z=1,asset=save_image(p,overlay))])
export_pptx(p,[scene],out/'alpha.pptx')
print(out)
