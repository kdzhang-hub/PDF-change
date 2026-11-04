"""Reproducible evaluation on user files; never modify the originals."""
from __future__ import annotations
from pathlib import Path
import argparse,collections,hashlib,json,shutil,sys,time
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import fitz
from PIL import Image,ImageDraw
from pptx import Presentation
from backend import store,extract
from backend.export import export_pptx

PDF=Path('C:/Users/35100/Desktop/答辩可修改_全稿换行修复版.pdf')
PPT=Path('D:/桌面项目/职规赛/参赛材料/office可用 v1.pptx')
BASE=store.ROOT/'deliverables'/'real-case-20261027'

def all_shapes(shapes):
 for shape in shapes:
  yield shape
  if shape.shape_type==6:yield from all_shapes(shape.shapes)

def sha(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for block in iter(lambda:f.read(2**20),b''):h.update(block)
 return h.hexdigest()

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--round',default='00');parser.add_argument('--pages',default='all');parser.add_argument('--full-image-analysis',action='store_true');parser.add_argument('--recover-text',action='store_true');args=parser.parse_args()
 out=BASE/f'round-{args.round}';out.mkdir(parents=True,exist_ok=True)
 store.init();project=store.create('真实材料测试 '+args.round)
 shutil.copyfile(PDF,store.project_dir(project)/'source.pdf')
 prepared=extract.prepare(project)
 indices=list(range(len(prepared))) if args.pages=='all' else [int(x)-1 for x in args.pages.split(',')]
 source=fitz.open(PDF);reference=Presentation(PPT)
 if not args.full_image_analysis:
  def native_only(project,layer):
   layer.needs_review=True;layer.notes.append('原生提取基线：图片内部尚未自动拆分')
   return [layer],[]
  extract.auto_image=native_only
 scenes=[];report=[]
 for index in indices:
  start=time.perf_counter()
  if int(args.round)>=3:
   from backend.pdfium_extract import convert_paint
   scene=convert_paint(project,index,prepared[index].original)
  elif args.round!='00':
   from backend.svg_extract import convert_complex
   scene=convert_complex(project,source[index],prepared[index].original)
  else:scene=extract.convert_page(project,index,prepared[index].original)
  if args.recover_text:
   from backend.text_recovery import recover_simple_text
   scene,diagnostics=recover_simple_text(project,scene,min_score=.78)
   (out/f'text-recovery-{index+1:02}.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2),'utf-8')
  store.save_page(project,scene);scenes.append(scene)
  original=source[index];original.get_pixmap(matrix=fitz.Matrix(1.25,1.25),alpha=False).save(out/f'original-{index+1:02}.png')
  reference_shapes=list(all_shapes(reference.slides[index].shapes))
  reference_text='\n'.join(s.text for s in reference_shapes if s.has_text_frame)
  pdf_text=original.get_text();converted_text='\n'.join(l.text for l in scene.layers if l.kind=='text')
  chars=collections.Counter(c for c in pdf_text if not c.isspace());actual=collections.Counter(c for c in converted_text if not c.isspace())
  blocks=original.get_text('dict',flags=fitz.TEXT_PRESERVE_IMAGES)['blocks']
  images=[{'size':[b['width'],b['height']],'bbox':b['bbox'],'transform':b.get('transform'),'mask':bool(b.get('mask'))} for b in blocks if b['type']==1]
  item={'page':index+1,'seconds':round(time.perf_counter()-start,2),'layers':len(scene.layers),'types':dict(collections.Counter(l.kind for l in scene.layers)),
   'native_text_chars':sum(chars.values()),'missing_native_chars':sum((chars-actual).values()),'pdf_text':pdf_text,'converted_text':converted_text,
   'reference_ppt_text':reference_text,'reference_shapes':len(reference_shapes),'images':images,
   'fonts':sorted({l.font for l in scene.layers if l.kind=='text'}),'warnings':scene.warnings,'status':scene.status}
  report.append(item);print(json.dumps({k:v for k,v in item.items() if k in ('page','seconds','layers','types','missing_native_chars','warnings')},ensure_ascii=True),flush=True)
  (out/'inventory.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),'utf-8')
 export_pptx(project,scenes,out/'converted.pptx',on_page=lambda index:print('Exporting page',index+1,flush=True))
 (out/'scenes.json').write_text(json.dumps([s.model_dump() for s in scenes],ensure_ascii=False,indent=2),'utf-8')
 (out/'run.json').write_text(json.dumps({'project':project,'pdf':str(PDF),'reference_ppt':str(PPT),'source_hashes':{'pdf':sha(PDF),'ppt':sha(PPT)},'pages':[i+1 for i in indices],
  'image_analysis':args.full_image_analysis,'cloud_calls':store.budget()['calls'],'note':'Reference PPT is for evaluation only. Conversion reads PDF only.'},ensure_ascii=False,indent=2),'utf-8')
 for batch in range(0,len(indices),9):
  subset=indices[batch:batch+9];sheet=Image.new('RGB',(1200,3*245),'#e9edf3');draw=ImageDraw.Draw(sheet)
  for pos,index in enumerate(subset):
   im=Image.open(out/f'original-{index+1:02}.png');im.thumbnail((388,218));x=(pos%3)*400+6;y=(pos//3)*245+20;sheet.paste(im,(x,y));draw.text((x,y-17),f'PDF {index+1:02}',fill='#26354b')
  sheet.save(out/f'contact-original-{batch//9+1}.png')
 print('OUTPUT',out,flush=True)

if __name__=='__main__':main()
