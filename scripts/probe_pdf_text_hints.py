from pathlib import Path
import json,collections,subprocess,sys,argparse
from backend.models import PageScene
from backend.text_recovery import recover_simple_text
from backend.export import export_pptx
from backend.fonts import activate_existing

parser=argparse.ArgumentParser();parser.add_argument('--output',default='metadata-round-02');args=parser.parse_args()
root=Path(__file__).resolve().parents[1];base=root/'deliverables'/'v3-movement-20261028';source=base/'shadow-round-02'/'repaired';out=base/args.output
if out.exists() and any(out.iterdir()):raise FileExistsError('Preserve previous evidence; use a new experiment folder')
out.mkdir(exist_ok=True)
run=json.loads((source/'run.json').read_text('utf-8'));scenes=[];diagnostics=[]
for data in json.loads((source/'scenes.json').read_text('utf-8')):
    scene,rows=recover_simple_text(run['project'],PageScene.model_validate(data),min_score=.78,allow_pdf_hints=True)
    from backend.font_calibration import calibrate_page
    scene,_=calibrate_page(run['project'],scene)
    scenes.append(scene);diagnostics.extend(rows)
    print('Page',scene.index+1,'text',sum(l.kind=='text' for l in scene.layers),flush=True)
(out/'run.json').write_text(json.dumps(run,ensure_ascii=False,indent=2),'utf-8')
(out/'scenes.json').write_text(json.dumps([s.model_dump() for s in scenes],ensure_ascii=False,indent=2),'utf-8')
(out/'text-diagnostics.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2),'utf-8')
inventory=json.loads((source/'inventory.json').read_text('utf-8'))
for row,scene in zip(inventory,scenes):row['layers']=len(scene.layers);row['types']=dict(collections.Counter(l.kind for l in scene.layers))
(out/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),'utf-8')
activate_existing(l.font for s in scenes for l in s.layers if l.kind=='text')
export_pptx(run['project'],scenes,out/'converted.pptx')
subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(root/'scripts'/'render_real_case.ps1'),'-Folder',str(out)],check=True,timeout=120)
subprocess.run([sys.executable,str(root/'scripts'/'compare_real_case.py'),'--folder',str(out)],check=True,timeout=90)
