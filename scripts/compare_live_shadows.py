"""Paired Office experiment while this process holds the same user fonts."""
from pathlib import Path
import json,shutil,subprocess,collections,sys
from backend.models import PageScene
from backend.text_shadows import restore_text_shadows
from backend.export import export_pptx
from backend.fonts import activate_existing

root=Path(__file__).resolve().parents[1];source=root/'deliverables'/'v3-movement-20261028'/'ordinary-round-02'
out=root/'deliverables'/'v3-movement-20261028'/'shadow-round-02'
if out.exists():raise FileExistsError('Keep prior experiment evidence; use a new folder')
run=json.loads((source/'run.json').read_text('utf-8'));original=[PageScene.model_validate(x) for x in json.loads((source/'scenes.json').read_text('utf-8'))]
activate_existing(l.font for scene in original for l in scene.layers if l.kind=='text')
results=[];matches=[]
for scene in original:
    changed,found=restore_text_shadows(run['project'],scene);results.append(changed);matches.extend(found)
for name,scenes in [('baseline',original),('repaired',results)]:
    folder=out/name;folder.mkdir(parents=True)
    (folder/'run.json').write_text(json.dumps(run,ensure_ascii=False,indent=2),'utf-8')
    (folder/'scenes.json').write_text(json.dumps([x.model_dump() for x in scenes],ensure_ascii=False,indent=2),'utf-8')
    inventory=json.loads((source/'inventory.json').read_text('utf-8'))
    for row,scene in zip(inventory,scenes):row['layers']=len(scene.layers);row['types']=dict(collections.Counter(l.kind for l in scene.layers))
    (folder/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),'utf-8')
    export_pptx(run['project'],scenes,folder/'converted.pptx')
    subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(root/'scripts'/'render_real_case.ps1'),'-Folder',str(folder)],check=True,timeout=120)
    subprocess.run([sys.executable,str(root/'scripts'/'compare_real_case.py'),'--folder',str(folder)],check=True,timeout=90)
(out/'shadow-matches.json').write_text(json.dumps(matches,ensure_ascii=False,indent=2),'utf-8')
print('Native text shadows',len(matches),'removed bitmap effects',sum(len(x['shadow_ids']) for x in matches),flush=True)
