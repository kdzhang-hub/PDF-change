from pathlib import Path
import sys,json,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import store
from backend.models import PageScene
from backend.text_recovery import recover_simple_text
from backend.export import export_pptx
from backend.fonts import resolve
parser=argparse.ArgumentParser();parser.add_argument('--source',default='09');parser.add_argument('--round',default='10');args=parser.parse_args()
base=store.ROOT/'deliverables'/'real-case-20261027';source=base/f'round-{args.source}';out=base/f'round-{args.round}';out.mkdir(exist_ok=True)
run=json.loads((source/'run.json').read_text('utf-8'));project=run['project'];scenes=[PageScene.model_validate(s) for s in json.loads((source/'scenes.json').read_text('utf-8'))];inventory=json.loads((source/'inventory.json').read_text('utf-8'))
for scene,item in zip(scenes,inventory):
    for layer in scene.layers:
        if layer.kind=='text':layer.font=resolve(layer.font)
    scene,diagnostics=recover_simple_text(project,scene,min_score=.78)
    (out/f'text-recovery-{scene.index+1:02}.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2),'utf-8')
    item['types']={k:sum(l.kind==k for l in scene.layers) for k in ('image','text','path')};item['layers']=len(scene.layers)
    print('PAGE',scene.index+1,'text',item['types']['text'],'recognized',len(diagnostics),'accepted',sum(d['accepted'] for d in diagnostics),flush=True)
(out/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),'utf-8');(out/'scenes.json').write_text(json.dumps([s.model_dump() for s in scenes],ensure_ascii=False,indent=2),'utf-8');(out/'run.json').write_text(json.dumps(run,ensure_ascii=False,indent=2),'utf-8')
export_pptx(project,scenes,out/'converted.pptx',on_page=lambda i:print('Export',i+1,flush=True))
