from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image,ImageDraw,ImageFont
from backend.store import asset_path,ROOT
folder=ROOT/'deliverables'/'real-case-20261027'/'round-16'
run=json.loads((folder/'run.json').read_text('utf-8'))
scene=json.loads((folder/'scenes.json').read_text('utf-8'))[0]
rows=json.loads((folder/'text-recovery-01.json').read_text('utf-8'))
out=Image.new('RGB',(1200,1000),'#233040');draw=ImageDraw.Draw(out)
for i,row in enumerate(r for r in rows if not r['accepted']):
    layer=next(l for l in scene['layers'] if l['id']==row['id'])
    rgba=Image.open(asset_path(run['project'],layer['asset'])).convert('RGBA')
    colors=np.array(rgba);opaque=colors[:,:,3]>180;quant=colors[:,:,:3][opaque]//24
    values,counts=np.unique(quant,axis=0,return_counts=True);mode=values[counts.argmax()]
    color=np.median(colors[:,:,:3][opaque][np.all(quant==mode,axis=1)],axis=0)
    glyph=(np.linalg.norm(colors[:,:,:3].astype(float)-color,axis=2)<65)&(colors[:,:,3]>60)
    alpha=Image.fromarray(np.where(glyph,colors[:,:,3],0).astype('uint8'));alpha=alpha.crop(alpha.getbbox())
    alpha.thumbnail((550,120));out.paste(alpha,(0,i*190+30))
    fit=row['font_match'];font=ImageFont.truetype(fit['file'],100,index=fit['index'])
    stroke=3 if fit['bold'] else 0;b=font.getbbox(row['text'],stroke_width=stroke)
    im=Image.new('L',(b[2]-b[0]+10,b[3]-b[1]+10));ImageDraw.Draw(im).text((5-b[0],5-b[1]),row['text'],fill=255,font=font,stroke_width=stroke)
    im=im.crop(im.getbbox()).resize(alpha.size);out.paste(im,(600,i*190+30))
    draw.text((0,i*190+5),f"score {fit['score']:.3f} target / fitted",fill='white')
path=ROOT/'work'/'font-match-debug.png';out.save(path);print(path)
