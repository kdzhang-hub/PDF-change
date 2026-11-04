"""Compare locally detected visible text with actual editable scene text boxes."""
from pathlib import Path
import sys,json,argparse,re,unicodedata,difflib
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import fitz,numpy as np
from backend.local_models import ocr
from backend.store import ROOT

parser=argparse.ArgumentParser();parser.add_argument('--round',default='11');parser.add_argument('--pages',default='1,2,4');args=parser.parse_args()
folder=ROOT/'deliverables'/'real-case-20261027'/f'round-{args.round}'
scenes=json.loads((folder/'scenes.json').read_text('utf-8'));pdf=fitz.open('C:/Users/35100/Desktop/答辩可修改_全稿换行修复版.pdf')
selected={int(p)-1 for p in args.pages.split(',')} if args.pages!='all' else {s['index'] for s in scenes}
normalize=lambda text:re.sub(r'\s+','',unicodedata.normalize('NFKC',text))
result=[]
for scene in scenes:
    index=scene['index']
    if index not in selected:continue
    pix=pdf[index].get_pixmap(matrix=fitz.Matrix(3,3),alpha=False)
    image=np.frombuffer(pix.samples,np.uint8).reshape(pix.height,pix.width,3);regions=[]
    windows=[(0,0,image.shape[1],image.shape[0],False)]
    windows.extend((x,y,min(x+1024,image.shape[1]),min(y+1024,image.shape[0]),True) for y in range(0,image.shape[0],896) for x in range(0,image.shape[1],896))
    for x,y,right_edge,bottom_edge,tiled in windows:
            tile=image[y:bottom_edge,x:right_edge]
            if min(tile.shape[:2])<40:continue
            rgba=np.dstack((tile,np.full(tile.shape[:2],255,np.uint8)))
            for text,confidence,poly in ocr(rgba):
                # Ignore words clipped by internal tile boundaries. Full-page
                # recognition supplies long lines which cannot fit one tile.
                if tiled and ((x>0 and poly[:,0].min()<8) or (y>0 and poly[:,1].min()<8) or (right_edge<image.shape[1] and poly[:,0].max()>tile.shape[1]-8) or (bottom_edge<image.shape[0] and poly[:,1].max()>tile.shape[0]-8)):continue
                left=(poly[:,0].min()+x)/3;right=(poly[:,0].max()+x)/3;top=(poly[:,1].min()+y)/3;bottom=(poly[:,1].max()+y)/3
                box=fitz.Rect(left,top,right,bottom)
                if box.is_empty:continue
                duplicate=next((r for r in regions if (normalize(text) in normalize(r['text']) or normalize(r['text']) in normalize(text)) and abs(fitz.Rect(r['bbox'])&box)/max(1,min(abs(fitz.Rect(r['bbox'])),abs(box)))>.6),None)
                if duplicate:continue
                regions.append({'text':text,'confidence':confidence,'bbox':list(box)})
    for region in regions:
        from backend.logo_policy import preserved_text_region
        if preserved_text_region(scene,region['bbox']):
            region.update(editable_text='',matched_ids=[],covered=False,status='preserved_brand_mark',
                reason='用户要求完整标识保持原图，不作为普通文字恢复项')
            continue
        box=fitz.Rect(region['bbox']);matched=[]
        for layer in scene['layers']:
            if layer['kind']!='text' or not layer['visible']:continue
            bounds=layer.get('source_ink_bbox') or [layer['x'],layer['y'],layer['x']+layer['width'],layer['y']+layer['height']]
            target=fitz.Rect(bounds);intersection=abs(box&target)
            if intersection/max(1,min(abs(box),abs(target)))>.45:matched.append(layer)
        matched.sort(key=lambda l:(round(l['y']/8),l['x']))
        editable=''.join(l['text'] for l in matched)
        expected=normalize(region['text']);actual=normalize(editable)
        ratio=difflib.SequenceMatcher(None,expected,actual).ratio()
        covered=bool(expected and (expected in actual or ratio>.9))
        region.update(editable_text=editable,matched_ids=[l['id'] for l in matched],covered=covered,similarity=ratio,
                      status='covered' if covered else 'needs_review',reason='' if covered else '未找到对应可编辑文字或识别内容不一致')
    row={'page':index+1,'detected_regions':len(regions),'covered_regions':sum(r['covered'] for r in regions),
         'preserved_brand_regions':sum(r['status']=='preserved_brand_mark' for r in regions),
         'ordinary_text_regions':sum(r['status']!='preserved_brand_mark' for r in regions),
         'unresolved_regions':sum(not r['covered'] and r['status']!='preserved_brand_mark' for r in regions),
         'scope':'Tiled local OCR audit; not a proof that every tiny or stylized glyph was detected.','regions':regions}
    result.append(row);print(json.dumps({k:v for k,v in row.items() if k not in ('regions','scope')},ensure_ascii=True),flush=True)
    (folder/'visible-text-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),'utf-8')
