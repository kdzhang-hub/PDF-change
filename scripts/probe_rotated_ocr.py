"""Inspect local OCR at three orientations without editing any project."""
from pathlib import Path
import sys,json
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
from backend.local_models import ocr


def main():
    root=Path(__file__).resolve().parents[1]
    image=np.array(Image.open(root/'samples'/'digital-reference.png').convert('RGBA'));height,width=image.shape[:2]
    rows=[]
    for turns in (0,1,3):
        for text,score,poly in ocr(np.rot90(image,turns).copy()):
            p=poly.copy()
            if turns==1:p=np.column_stack((width-1-poly[:,1],poly[:,0]))
            if turns==3:p=np.column_stack((poly[:,1],height-1-poly[:,0]))
            if turns and np.ptp(p[:,1])<np.ptp(p[:,0])*1.3:continue
            rows.append({'turns':turns,'text':text,'score':score,'poly':p.tolist()})
    out=root/'work'/'rotation-ocr-20261030.json'
    if out.exists():raise FileExistsError('Previous rotation evidence preserved')
    out.write_text(json.dumps(rows,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps(rows,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
