from pathlib import Path
import argparse,json
import fitz,numpy as np
from PIL import Image,ImageDraw
from skimage.metrics import structural_similarity
ROOT=Path(__file__).resolve().parents[1]
base=ROOT/'deliverables'/'real-case-20261027'
parser=argparse.ArgumentParser();parser.add_argument('--round',default='02');parser.add_argument('--folder',type=Path);parser.add_argument('--source',type=Path);args=parser.parse_args()
out=args.folder or base/f'round-{args.round}';inventory=json.loads((out/'inventory.json').read_text('utf-8'))
run=json.loads((out/'run.json').read_text('utf-8')) if (out/'run.json').exists() else {}
source=args.source or run.get('source_pdf') or 'C:/Users/35100/Desktop/答辩可修改_全稿换行修复版.pdf'
original=fitz.open(source);actual=fitz.open(out/'powerpoint.pdf')
metrics=[]
for i,entry in enumerate(inventory):
 number=entry['page'];a=original[number-1].get_pixmap(matrix=fitz.Matrix(1.25,1.25),alpha=False)
 b=actual[i].get_pixmap(matrix=fitz.Matrix(1.25,1.25),alpha=False)
 ia=Image.frombytes('RGB',(a.width,a.height),a.samples);ib=Image.frombytes('RGB',(b.width,b.height),b.samples)
 ib.save(out/f'result-{number:02}.png')
 aa=np.array(ia);bb=np.array(ib);score=float(structural_similarity(aa,bb,channel_axis=2,data_range=255))
 png=out/f'office-{i+1}.png'
 png_score=float(structural_similarity(aa,np.array(Image.open(png).convert('RGB')),channel_axis=2,data_range=255)) if png.exists() else None
 metrics.append({'page':number,'ssim':round(score,6),'office_png_ssim':round(png_score,6) if png_score is not None else None,'layers':entry['layers'],'text_layers':entry['types'].get('text',0),'missing_native_chars':entry['missing_native_chars'],'text_coverage_scope':entry.get('text_coverage_scope','PDF native text only; embedded image text not fully audited'),'fully_editable':False})
 panel=Image.new('RGB',(2400,710),'#e9edf3');panel.paste(ia,(0,30));panel.paste(ib,(1200,30));draw=ImageDraw.Draw(panel);draw.text((10,8),f'PDF {number:02}',fill='#26354b');draw.text((1210,8),f'PPTX | SSIM {score:.4f}',fill='#26354b');panel.save(out/f'compare-{number:02}.png')
for start in range(0,len(metrics),9):
 subset=metrics[start:start+9];sheet=Image.new('RGB',(1200,765),'#e9edf3');draw=ImageDraw.Draw(sheet)
 for pos,m in enumerate(subset):
  im=Image.open(out/f'result-{m["page"]:02}.png');im.thumbnail((390,220));x=pos%3*400+5;y=pos//3*255+25;sheet.paste(im,(x,y));draw.text((x,y-18),f'Page {m["page"]:02} | SSIM {m["ssim"]:.4f}',fill='#26354b')
 sheet.save(out/f'contact-result-{start//9+1}.png')
(out/'metrics.json').write_text(json.dumps(metrics,indent=2),'utf-8')
print(json.dumps({'pages':len(metrics),'mean_ssim':sum(m['ssim'] for m in metrics)/len(metrics),'min_ssim':min(m['ssim'] for m in metrics),'max_ssim':max(m['ssim'] for m in metrics),'missing_native_chars':sum(m['missing_native_chars'] for m in metrics) if all(m['missing_native_chars'] is not None for m in metrics) else None,'text_coverage_scope':sorted({m['text_coverage_scope'] for m in metrics})},indent=2))
