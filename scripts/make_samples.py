"""Known-structure fixtures; synthetic cases are never reported as customer PDFs."""
from pathlib import Path
import io,json,sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import fitz
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'samples'


def make():
    OUT.mkdir(exist_ok=True)
    doc=fitz.open(); p=doc.new_page(width=960,height=540)
    font=Path('C:/Windows/Fonts/msyh.ttc')
    p.insert_font(fontname='yahei',fontfile=str(font))
    p.draw_rect((0,0,960,540),color=None,fill=(.97,.98,1))
    p.draw_rect((48,54,55,102),color=None,fill=(.25,.41,.88))
    p.insert_text((76,91),'把每一层，还给你',fontname='yahei',fontsize=28,color=(.12,.17,.27))
    p.insert_text((76,123),'本地分层还原 · 2026',fontname='yahei',fontsize=13,color=(.4,.47,.58))
    p.draw_rect((48,162,438,382),color=None,fill=(1,1,1))
    p.draw_rect((478,162,912,382),color=None,fill=(1,1,1))
    p.insert_text((70,197),'文字、曲线、透明装饰',fontname='yahei',fontsize=18,color=(.16,.21,.3))
    p.insert_text((70,232),'收入 128.50 万元',fontname='yahei',fontsize=16,color=(.25,.41,.88))
    p.draw_circle((142,302),42,color=None,fill=(.25,.41,.88))
    p.draw_circle((182,302),42,color=None,fill=(.25,.75,.64),fill_opacity=.6)
    s=p.new_shape();s.draw_bezier((252,332),(282,230),(345,365),(406,253));s.finish(color=(.9,.47,.2),width=4);s.commit()
    p.insert_text((500,197),'独立对象与遮挡',fontname='yahei',fontsize=18,color=(.16,.21,.3))
    p.draw_rect((510,230,650,330),fill=(.89,.93,1),color=(.4,.54,.85),width=1)
    p.draw_rect((610,265,765,350),fill=(.95,.68,.36),color=None)
    p.insert_text((648,307),'42%',fontsize=25,color=(1,1,1))
    p.insert_text((822,328),'ROTATE',fontsize=15,rotate=90,color=(.2,.32,.58))
    for i in range(4):p.draw_line((48,418+i*22),(912,418+i*22),color=(.8,.84,.9),width=.5)
    for x in (48,310,600,912):p.draw_line((x,418),(x,484),color=(.8,.84,.9),width=.5)
    for text,x,y in [('指标',60,434),('数值',324,434),('状态',614,434),('测试对象',60,456),('128.50',324,456),('可移动',614,456)]:
        p.insert_text((x,y),text,fontname='yahei',fontsize=11,color=(.25,.3,.4))
    expected=p.get_text()
    # Mixed page size and isolated embedded image with known objects.
    p2=doc.new_page(width=720,height=540);p2.insert_font(fontname='yahei',fontfile=str(font))
    p2.insert_text((40,60),'内嵌图片继续分层',fontname='yahei',fontsize=24,color=(.12,.17,.27))
    im=Image.new('RGB',(600,360),'white');d=ImageDraw.Draw(im)
    d.ellipse((40,50,180,190),fill='#4169e1');d.rounded_rectangle((260,70,450,200),radius=24,fill='#3fb69c');d.polygon([(180,280),(260,220),(340,280)],fill='#eeaa55')
    buff=io.BytesIO();im.save(buff,format='PNG');p2.insert_image((60,120,660,480),stream=buff.getvalue())
    doc.save(OUT/'digital.pdf')
    raster=fitz.open()
    for page in doc:
        target=raster.new_page(width=page.rect.width,height=page.rect.height)
        target.insert_image(target.rect,stream=page.get_pixmap(matrix=fitz.Matrix(1.5,1.5)).tobytes('png'))
    raster.save(OUT/'scanned.pdf');raster.close()
    doc[0].get_pixmap(matrix=fitz.Matrix(1.5,1.5)).save(OUT/'digital-reference.png')
    (OUT/'ground-truth.json').write_text(json.dumps({'source':'synthetic','page0_text':expected,'pages':2,
        'cases':['Chinese text','numbers','cubic curves','transparency','overlap','rotated text','table lines','mixed page sizes','embedded image with 3 objects'],
        'embedded_image_objects':3},ensure_ascii=False,indent=2),'utf-8')
    doc.close();print(str(OUT))

if __name__=='__main__':make()
