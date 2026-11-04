from pathlib import Path
import sys,json,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.models import PageScene
from backend.export import export_pptx
parser=argparse.ArgumentParser();parser.add_argument('--folder',type=Path,required=True);args=parser.parse_args()
run=json.loads((args.folder/'run.json').read_text('utf-8'));scenes=[PageScene.model_validate(s) for s in json.loads((args.folder/'scenes.json').read_text('utf-8'))]
export_pptx(run['project'],scenes,args.folder/'standalone-diagnostic.pptx',on_page=lambda i:print('Page',i+1,flush=True))
print('Export completed',flush=True)
