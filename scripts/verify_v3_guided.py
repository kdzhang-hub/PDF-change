"""Replay local manual correction through production APIs in a new test project."""
from pathlib import Path
import json,time,shutil,argparse,sys,collections
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx,fitz
from PIL import Image
from backend.store import asset_path

parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True);args=parser.parse_args()
out=args.folder.resolve()
if out.exists():raise FileExistsError('Preserve previous evidence')
out.mkdir(parents=True)
source=out.parent/'image-round-04';old=json.loads((source/'run.json').read_text('utf-8'))
scene=json.loads((source/'scenes.json').read_text('utf-8'))[0];scene['revision']=0
with fitz.open(old['source_pdf']) as full:
    first=fitz.open();first.insert_pdf(full,from_page=0,to_page=0);first.save(out/'input.pdf');first.close()
with httpx.Client(base_url='http://127.0.0.1:8765',trust_env=False,timeout=240) as client:
    def post(path,value):
        result=client.post(path,json=value);result.raise_for_status();return result.json()
    def wait(job):
        deadline=time.monotonic()+300
        while time.monotonic()<deadline:
            result=client.get('/api/jobs/'+job);result.raise_for_status();state=result.json()
            if state['status'] in ('done','error','cancelled'):
                if state['status']!='done':raise RuntimeError(state['message'])
                return
            time.sleep(1)
        raise TimeoutError('Local correction did not finish')
    with (out/'input.pdf').open('rb') as file:
        response=client.post('/api/projects',files={'file':('v3 图片版 · 人物框选复测.pdf',file,'application/pdf')});response.raise_for_status();project=response.json()['id']
    # Clone only our generated page. Existing projects and their edits stay intact.
    names={scene['original']}
    for layer in scene['layers']:
        names.update(layer[k] for k in ('asset','mask','restoration_asset') if layer.get(k))
    for name in names:shutil.copy2(asset_path(old['project'],name),asset_path(project,name))
    response=client.put(f'/api/projects/{project}/pages/0',json=scene);response.raise_for_status()
    ids=[l['id'] for l in scene['layers'] if l['kind']=='image']
    wait(post(f'/api/projects/{project}/pages/0/merge',ids)['id'])
    response=client.get(f'/api/projects/{project}');response.raise_for_status();scene=response.json()['pages'][0]
    layer=next(l for l in scene['layers'] if l['kind']=='image')
    with Image.open(asset_path(project,layer['asset'])) as bitmap:w,h=bitmap.size
    def point(x,y):return [(x-layer['x'])/layer['width']*w,(y-layer['y'])/layer['height']*h]
    # User-equivalent box drawn around the visible person, not a semantic auto claim.
    request={'method':'sam','box':[*point(680,300),*point(790,533)],'points':[point(735,395)],'fill':'local'}
    wait(post(f'/api/projects/{project}/pages/0/layers/{layer["id"]}/split',request)['id'])
    response=client.get(f'/api/projects/{project}');response.raise_for_status();scene=response.json()['pages'][0]
    run={'project':project,'pages':[1],'source_pdf':str(out/'input.pdf'),'pipeline':'production HTTP manual merge and SAM box correction','cloud_calls_after':len(client.get('/api/budget').json()['calls'])}
    (out/'run.json').write_text(json.dumps(run,ensure_ascii=False,indent=2),'utf-8')
    (out/'scenes.json').write_text(json.dumps([scene],ensure_ascii=False,indent=2),'utf-8')
    inventory=[{'page':1,'layers':len(scene['layers']),'types':dict(collections.Counter(l['kind'] for l in scene['layers'])),'missing_native_chars':0}]
    (out/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),'utf-8')
    target=next(l for l in scene['layers'] if l['kind']=='image' and l['source']=='local-segmentation')
    targets=[{'slide':1,'id':target['id'],'role':'whole-portrait','dx':-260,'dy':-100,'source':target['source'],'semantic':'本地框选完整人物，背景为本地推断补全'}]
    (out/'movement-targets.json').write_text(json.dumps(targets,ensure_ascii=False,indent=2),'utf-8')
    (out/'correction.json').write_text(json.dumps(request,ensure_ascii=False,indent=2),'utf-8')
    response=client.post(f'/api/projects/{project}/export',json={'pages':[0]});response.raise_for_status();(out/'converted.pptx').write_bytes(response.content)
    print(json.dumps(run,ensure_ascii=True),flush=True)
