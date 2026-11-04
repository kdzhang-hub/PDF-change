from pathlib import Path
import sys,json,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import fitz,numpy as np
from PIL import Image,ImageDraw,ImageFont
from backend import store
from backend.models import LayerElement,PageScene,PathCommand
from backend.raster import save_image
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--name',default='小标签手工校正验证');args=parser.parse_args()
    store.init();project=store.create(args.name)
    bitmap=Image.new('RGBA',(320,80));ImageDraw.Draw(bitmap).text((20,15),'小标签',fill='white',font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',38))
    asset=save_image(project,np.array(bitmap))
    layer=LayerElement(id='tiny-label',kind='image',name='小标签图片',x=50,y=40,width=160,height=40,asset=asset,needs_review=True)
    original=Image.new('RGB',(800,400),'#163c66');original.paste(bitmap,(100,80),bitmap)
    original.save(store.asset_path(project,'original.png'))
    background=LayerElement(id='background',kind='path',name='背景',x=0,y=0,width=400,height=200,z=-1,locked=True,fill='#163c66',
        path=[PathCommand(op='M',points=[0,0]),PathCommand(op='L',points=[400,0]),PathCommand(op='L',points=[400,200]),PathCommand(op='L',points=[0,200]),PathCommand(op='Z')])
    scene=PageScene(index=0,width=400,height=200,original='original.png',layers=[background,layer],status='needs_review')
    doc=fitz.open();doc.new_page(width=400,height=200);doc.save(store.project_dir(project)/'source.pdf');doc.close()
    store.save_page(project,scene)
    (store.ROOT/'work'/'manual-text-project.json').write_text(json.dumps({'id':project,'asset':asset}),'utf-8')
    print(project)


if __name__=='__main__':main()
