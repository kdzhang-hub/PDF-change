from pathlib import Path
import json
import fitz
import numpy as np
from PIL import Image,ImageChops
from skimage.metrics import structural_similarity
ROOT=Path(__file__).resolve().parents[1];out=ROOT/'deliverables'
report=[]
for stem in ('digital','scanned'):
 doc=fitz.open(ROOT/'samples'/f'{stem}.pdf')
 converted=fitz.open(out/f'{stem}-powerpoint.pdf')
 for i,page in enumerate(doc):
  scale=min(1440/page.rect.width,810/page.rect.height)
  pix=page.get_pixmap(matrix=fitz.Matrix(scale,scale),alpha=False)
  original=Image.new('RGB',(1440,810),'white');render=Image.frombytes('RGB',(pix.width,pix.height),pix.samples)
  original.paste(render,((1440-render.width)//2,(810-render.height)//2))
  office_png=Image.open(out/f'{stem}-page-{i+1}.png').convert('RGB')
  p=converted[i];pix2=p.get_pixmap(matrix=fitz.Matrix(1440/p.rect.width,810/p.rect.height),alpha=False)
  actual=Image.frombytes('RGB',(pix2.width,pix2.height),pix2.samples)
  a,b=np.array(original),np.array(actual)
  score=float(structural_similarity(a,b,channel_axis=2,data_range=255))
  original.save(out/f'{stem}-original-{i+1}.png')
  panel=Image.new('RGB',(2880,810),'white');panel.paste(original,(0,0));panel.paste(actual,(1440,0));panel.save(out/f'{stem}-comparison-{i+1}.png')
  diff=np.minimum(np.abs(a.astype(float)-b.astype(float))*5,255).astype('uint8');Image.fromarray(diff).save(out/f'{stem}-difference-{i+1}.png')
  report.append({'fixture':stem,'page':i+1,'ssim':round(score,6),'renderer':'Both PDFs rendered by MuPDF at 1440x810','powerpoint_png_ssim':round(float(structural_similarity(a,np.array(office_png),channel_axis=2,data_range=255)),6),'initial_target':.98,'pass':score>=.98})
(out/'visual-metrics.json').write_text(json.dumps(report,indent=2),'utf-8')
print(json.dumps(report,indent=2))
