from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import store
from backend.models import PageScene,LayerElement
from backend.export import export_pptx
from backend.fonts import resolve
out=store.ROOT/'work'/'font-resolution';out.mkdir(exist_ok=True)
names=['Source Han Serif SC Heavy','Source Han Serif CN Heavy','思源宋体 CN Heavy','Source Han Serif Heavy','思源宋体 Heavy','Microsoft YaHei','微软雅黑']
pages=[]
for i,font in enumerate(names):
 pages.append(PageScene(index=i,width=600,height=200,original='none',status='ready',layers=[LayerElement(kind='text',name=font,text='自我定位 123',x=30,y=30,width=500,height=100,font=font,font_size=36)]))
project=store.create('Font resolution')
export_pptx(project,pages,out/'probe.pptx')
(out/'names.json').write_text(json.dumps(names,ensure_ascii=False),'utf-8')
print('Resolver',[(s,resolve(s)) for s in names])
