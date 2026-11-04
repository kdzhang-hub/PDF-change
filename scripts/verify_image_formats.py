"""Exercise image upload and both editable export formats via localhost."""
from pathlib import Path
import json,time,sys,argparse,re,collections
import httpx
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import store
if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')


def known_text_coverage(expected,actual_texts):
    normalize=lambda text:re.sub(r'\s+','',text)
    actual=normalize(''.join(actual_texts))
    needed=collections.Counter(normalize(''.join(expected)));present=collections.Counter(actual)
    return {'missing_strings':[text for text in expected if normalize(text) not in actual],
            'missing_chars':sum((needed-present).values()),'extra_chars':sum((present-needed).values())}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True);parser.add_argument('--source',type=Path);parser.add_argument('--truth',type=Path);args=parser.parse_args()
    folder=args.folder.resolve()
    if folder.exists():raise FileExistsError('Keep prior evidence')
    folder.mkdir(parents=True)
    source=args.source or store.ROOT/'samples'/'digital-reference.png'
    with httpx.Client(base_url='http://127.0.0.1:8765',timeout=250,trust_env=False) as client:
        with source.open('rb') as file:
            response=client.post('/api/projects',files={'file':(source.name,file,'image/png')});response.raise_for_status();project=response.json()['id']
        response=client.post(f'/api/projects/{project}/convert',json={'pages':[0]});response.raise_for_status();job=response.json()['id']
        state={'project':project,'job':job,'pages':[1],'source_image':str(source),'source_pdf':str(store.project_dir(project)/'source.pdf'),'pipeline':'production HTTP image upload and PPTX/DOCX exports'}
        (folder/'run.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),'utf-8')
        deadline=time.monotonic()+600;last=None
        while time.monotonic()<deadline:
            response=client.get('/api/jobs/'+job);response.raise_for_status();task=response.json()
            signal=(task['status'],task['progress'])
            if signal!=last:print(json.dumps({'status':signal[0],'progress':signal[1]}),flush=True);last=signal
            if task['status'] in ('done','error','cancelled'):
                if task['status']!='done':raise RuntimeError(task['message'])
                break
            time.sleep(1)
        else:raise TimeoutError('Image job is retained for recovery')
        response=client.get(f'/api/projects/{project}');response.raise_for_status();scene=response.json()['pages'][0]
        (folder/'scenes.json').write_text(json.dumps([scene],ensure_ascii=False,indent=2),'utf-8')
        inventory=[{'page':1,'layers':len(scene['layers']),'types':dict(collections.Counter(l['kind'] for l in scene['layers'])),'missing_native_chars':None,'text_coverage_scope':'known synthetic strings; whitespace excluded, no positional proof'}]
        (folder/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),'utf-8')
        for suffix,endpoint in [('pptx','export'),('docx','export-docx')]:
            response=client.post(f'/api/projects/{project}/{endpoint}',json={'pages':[0]});response.raise_for_status()
            (folder/('converted.'+suffix)).write_bytes(response.content)
        truth=json.loads((args.truth or store.ROOT/'samples'/'ground-truth.json').read_text('utf-8'))
        expected=truth['text'] if 'text' in truth else truth['page0_text'].splitlines()
        coverage=known_text_coverage(expected,[l['text'] for l in scene['layers'] if l['kind']=='text'])
        state['expected_strings_missing']=coverage['missing_strings']
        state['known_characters_missing']=coverage['missing_chars']
        state['known_characters_extra']=coverage['extra_chars']
        inventory[0]['missing_native_chars']=coverage['missing_chars']
        (folder/'inventory.json').write_text(json.dumps(inventory,ensure_ascii=False,indent=2),'utf-8')
        state['cloud_calls_after']=len(client.get('/api/budget').json()['calls'])
        state['fully_editable']=False
        (folder/'run.json').write_text(json.dumps(state,ensure_ascii=False,indent=2),'utf-8')
        print(json.dumps({'project':project,'text':inventory[0]['types'].get('text',0),'missing_known_strings':state['expected_strings_missing'],'cloud_calls':state['cloud_calls_after']},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
