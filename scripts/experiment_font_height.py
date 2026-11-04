from pathlib import Path
import json,sys,shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.models import PageScene
from backend.font_calibration import calibrate
from backend.export import export_pptx
from backend.store import ROOT
base=ROOT/'deliverables'/'optimization-20261028';src=base/'web-round-01';out=base/'height-experiment';out.mkdir(exist_ok=True)
run=json.loads((src/'run.json').read_text('utf-8'));scenes=[PageScene.model_validate(x) for x in json.loads((src/'scenes.json').read_text('utf-8'))]
measurements=calibrate(run['project'],scenes,match_height=True)
(out/'measurements.json').write_text(json.dumps(measurements,ensure_ascii=False,indent=2),'utf-8')
(out/'scenes.json').write_text(json.dumps([x.model_dump() for x in scenes],ensure_ascii=False,indent=2),'utf-8')
for name in ('run.json','inventory.json'):shutil.copy2(src/name,out/name)
export_pptx(run['project'],scenes,out/'converted.pptx')
print('Measured',len(measurements),'text objects',flush=True)
