"""Retry export of an existing agent test run without reconverting pages."""
from pathlib import Path
import argparse,json,hashlib
import httpx


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True);args=parser.parse_args()
    folder=args.folder.resolve();run=json.loads((folder/'run.json').read_text('utf-8'))
    output=folder/'converted.pptx'
    if output.exists():raise FileExistsError('Existing exported evidence is preserved')
    with httpx.Client(base_url='http://127.0.0.1:8765',timeout=250,trust_env=False) as client:
        response=client.post(f'/api/projects/{run["project"]}/export',json={'pages':[i-1 for i in run['pages']]})
        if response.status_code!=200:raise RuntimeError(response.json().get('detail','Local export failed'))
        output.write_bytes(response.content)
        run['cloud_calls_after']=len(client.get('/api/budget').json()['calls'])
        run['source_sha256']=hashlib.sha256(Path(run['source_pdf']).read_bytes()).hexdigest()
        run['export_retried_without_reconversion']=True
        (folder/'run.json').write_text(json.dumps(run,ensure_ascii=False,indent=2),'utf-8')
        print(json.dumps({'project':run['project'],'pptx_bytes':output.stat().st_size,'cloud_calls':run['cloud_calls_after']}))


if __name__=='__main__':main()
