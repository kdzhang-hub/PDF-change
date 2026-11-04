"""Exercise the production HTTP conversion, never bypass its worker pipeline."""
from pathlib import Path
import sys,json,time,collections,hashlib,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import httpx,fitz
from backend.store import ROOT

parser=argparse.ArgumentParser();parser.add_argument('--project');parser.add_argument('--all-pages',action='store_true');parser.add_argument('--pages',type=int,nargs='+',help='One-based source page numbers');parser.add_argument('--output',default='web-round-01');parser.add_argument('--source',type=Path,default=Path('C:/Users/35100/Desktop/答辩可修改_全稿换行修复版.pdf'));parser.add_argument('--folder',type=Path);parser.add_argument('--deadline',type=int,default=3600);args=parser.parse_args()
source=args.source.resolve()
folder=args.folder or ROOT/'deliverables'/'optimization-20261028'/args.output;folder.mkdir(parents=True,exist_ok=True)
if (folder/'run.json').exists() and not args.project:raise FileExistsError('Use a new evidence folder; existing run is preserved')
with fitz.open(source) as original:
    if args.pages and args.all_pages:parser.error('--pages and --all-pages cannot be combined')
    indices=list(dict.fromkeys(n-1 for n in args.pages)) if args.pages else list(range(len(original))) if args.all_pages else [0,1,3]
    if any(i<0 or i>=len(original) for i in indices):parser.error('Selected page is outside the source PDF')
with httpx.Client(base_url='http://127.0.0.1:8765',timeout=240,trust_env=False) as client:
    health=client.get('/api/health');health.raise_for_status()
    assert health.json().get('office_calibration'), 'Local Office calibration unavailable'
    if args.project:
        project=args.project
        response=client.get(f'/api/projects/{project}');response.raise_for_status()
    else:
        with source.open('rb') as file:
            response=client.post('/api/projects',files={'file':(source.name,file,'application/pdf')});response.raise_for_status()
        project=response.json()['id']
    response=client.post(f'/api/projects/{project}/convert',json={'pages':indices});response.raise_for_status();job=response.json()['id']
    state={'project':project,'job':job,'pages':[i+1 for i in indices],'source_pdf':str(source),'pipeline':'production HTTP default conversion including local Office calibration','cloud_calls_before':len(health.json()['budget']['calls'])}
    (folder/'run.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),'utf-8')
    previous=None;deadline=time.monotonic()+args.deadline
    while time.monotonic()<deadline:
        response=client.get(f'/api/jobs/{job}');response.raise_for_status();current=response.json()
        signal=(current['status'],current['progress'],current['message'])
        if signal!=previous:print(json.dumps({'status':signal[0],'progress':signal[1],'message':signal[2]},ensure_ascii=True),flush=True);previous=signal
        if current['status'] not in ('queued','running'):
            if current['status']!='done':raise RuntimeError(current['message'])
            break
        time.sleep(1)
    else:raise TimeoutError('HTTP conversion deadline exceeded; job retained for inspection')
    response=client.get(f'/api/projects/{project}');response.raise_for_status()
    scenes=[p for p in response.json()['pages'] if p['index'] in indices]
    (folder/'scenes.json').write_text(json.dumps(scenes,ensure_ascii=False,indent=2),'utf-8')
    doc=fitz.open(source);inventory=[]
    for scene in scenes:
        number=scene['index'];expected=collections.Counter(c for c in doc[number].get_text() if not c.isspace())
        actual=collections.Counter(c for l in scene['layers'] if l['kind']=='text' for c in l['text'] if not c.isspace())
        inventory.append({'page':number+1,'layers':len(scene['layers']),'types':dict(collections.Counter(l['kind'] for l in scene['layers'])),'missing_native_chars':sum((expected-actual).values()),
            'text_coverage_scope':'PDF extracted text multiplicity may include invisible or duplicate paints; embedded image text not fully audited',
            'office_calibrated':sum(any('PowerPoint 测量字形' in n for n in l['notes']) for l in scene['layers'] if l['kind']=='text'),
            'pending_text_images':sum(l['kind']=='image' and bool(l.get('recognized_text')) for l in scene['layers']),'warnings':scene['warnings']})
    (folder/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),'utf-8')
    response=client.post(f'/api/projects/{project}/export',json={'pages':indices});response.raise_for_status();(folder/'converted.pptx').write_bytes(response.content)
    state['cloud_calls_after']=len(client.get('/api/health').json()['budget']['calls'])
    state['source_sha256']=hashlib.sha256(source.read_bytes()).hexdigest()
    (folder/'run.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),'utf-8')
    print(json.dumps({'project':project,'objects':sum(x['layers'] for x in inventory),'native_text':sum(x['types'].get('text',0) for x in inventory),'pending_text_images':sum(x['pending_text_images'] for x in inventory),'folder':str(folder)},ensure_ascii=True),flush=True)
