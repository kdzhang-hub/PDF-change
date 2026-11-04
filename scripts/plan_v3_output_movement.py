"""Choose visible conversion objects, never borrow assets from the reference PPT."""
from pathlib import Path
import json,argparse
import numpy as np
from PIL import Image,ImageDraw
from backend.store import asset_path

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True);parser.add_argument('--kind',choices=['ordinary','image'],required=True);args=parser.parse_args()
    folder=args.folder;scenes=json.loads((folder/'scenes.json').read_text('utf-8'));project=json.loads((folder/'run.json').read_text('utf-8'))['project'];targets=[];candidates=[]
    for slide,scene in enumerate(scenes,1):
        if scene['index'] not in (0,1,3):continue
        for layer in scene['layers']:
            if layer['kind']=='text' and '参赛赛道' in layer['text'] and scene['index']==0:
                targets.append(dict(slide=slide,id=layer['id'],role='small-label',dx=0,dy=-75,source=layer['source'],semantic='小标签文字'))
                break
        if scene['index']!=0:continue
        for layer in scene['layers']:
            if layer['kind']!='image':continue
            if args.kind=='image' and layer['source']!='local-segmentation':continue
            with Image.open(asset_path(project,layer['asset'])) as image:
                image=image.convert('RGBA');alpha=np.array(image.getchannel('A'));ys,xs=np.where(alpha>180)
                if len(xs)<30:continue
                box=[layer['x']+xs.min()/image.width*layer['width'],layer['y']+ys.min()/image.height*layer['height'],layer['x']+(xs.max()+1)/image.width*layer['width'],layer['y']+(ys.max()+1)/image.height*layer['height']]
                if box[0]<400 or box[1]<130 or box[3]-box[1]<90:continue
                # Prefer the person's lower-right region; visual identity must
                # still be checked in the candidate contact sheet.
                center=((box[0]+box[2])/2,(box[1]+box[3])/2)
                rank=abs(center[0]-700)+abs(center[1]-370)
                preview=Image.new('RGBA',image.size,'#e4e9ef');preview.alpha_composite(image);preview=preview.crop(image.getbbox());preview.thumbnail((290,210))
                candidates.append((rank,layer,box,preview.copy()))
    candidates.sort(key=lambda item:item[0]);sheet=Image.new('RGB',(900,260*max(1,(min(6,len(candidates))+2)//3)),'#e4e9ef');draw=ImageDraw.Draw(sheet)
    for i,(_,layer,box,preview) in enumerate(candidates[:6]):
        x=i%3*300;y=i//3*260;sheet.paste(preview.convert('RGB'),(x,y+30));draw.text((x+4,y+4),str(i)+' '+layer['id'][:12],fill='black')
    sheet.save(folder/'movement-candidates.png')
    if candidates:
        _,layer,box,_=candidates[0];targets.append(dict(slide=1,id=layer['id'],role='portrait-candidate',dx=-260,dy=-100,source=layer['source'],semantic='待目视确认的人物候选',ink_box=box))
    (folder/'movement-targets.json').write_text(json.dumps(targets,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({'targets':len(targets),'image_candidates':len(candidates)},ensure_ascii=True))

if __name__=='__main__':main()
