from pathlib import Path
import sys,json,argparse,shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.models import PageScene
from backend.store import ROOT
from backend.export import export_pptx
from backend.fonts import resolve
parser=argparse.ArgumentParser();parser.add_argument('--source',default='12');parser.add_argument('--round',default='13');args=parser.parse_args()
base=ROOT/'deliverables'/'real-case-20261027';source=base/f'round-{args.source}';out=base/f'round-{args.round}';out.mkdir(exist_ok=True)
run=json.loads((source/'run.json').read_text('utf-8'));scenes=[PageScene.model_validate(v) for v in json.loads((source/'scenes.json').read_text('utf-8'))]
for scene in scenes:
    for layer in scene.layers:
        if layer.kind=='text':layer.font=resolve(layer.font)
(out/'scenes.json').write_text(json.dumps([s.model_dump() for s in scenes],ensure_ascii=False,indent=2),'utf-8')
for name in ('inventory.json','run.json'):shutil.copyfile(source/name,out/name)
export_pptx(run['project'],scenes,out/'converted.pptx')
