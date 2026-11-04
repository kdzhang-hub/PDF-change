"""Copy a verified scene snapshot into a separate editable local project."""
from pathlib import Path
import sys,json,os,shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import store
from backend.models import PageScene
folder=store.ROOT/'deliverables'/'real-case-20261027'/'round-20'
run=json.loads((folder/'run.json').read_text('utf-8'));source=run['project']
scenes=[PageScene.model_validate(x) for x in json.loads((folder/'scenes.json').read_text('utf-8'))]
store.init();project=store.create('答辩材料 · 最新本地测试（待校正）')
names={scene.original for scene in scenes}
for scene in scenes:
    for layer in scene.layers:names.update(x for x in (layer.asset,layer.mask,layer.restoration_asset) if x)
for name in names:
    src=store.asset_path(source,name);dest=store.asset_path(project,name)
    try:os.link(src,dest)
    except OSError:shutil.copy2(src,dest)
shutil.copy2(store.project_dir(source)/'source.pdf',store.project_dir(project)/'source.pdf')
for scene in scenes:scene.revision=0;store.save_page(project,scene)
record={'project':project,'source_round':'20','status':'needs_review','note':'Separate local project; previous test projects and user originals preserved.'}
(folder.parent/'latest-local-project.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),'utf-8')
print(project)
