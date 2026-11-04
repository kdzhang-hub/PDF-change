"""Offline comparison of a larger official recognizer on retained crops."""
from pathlib import Path
import sys,json,hashlib,tempfile,shutil,socket
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import numpy as np
from PIL import Image
from backend import local_models


if __name__=='__main__':
    out=Path('work/badge-strong-recognition-20261030');out.mkdir(exist_ok=False)
    provisioned=Path('models/experimental-ocr')
    lock=json.loads((provisioned/'server-rec-v5.lock.json').read_text('utf-8'))
    cache=Path(tempfile.gettempdir())/'layerdeck-models'/('server-rec-'+lock['archive_sha256'][:12])
    cache.mkdir(parents=True,exist_ok=True)
    for name,digest in lock['files'].items():
        source=provisioned/name
        if hashlib.sha256(source.read_bytes()).hexdigest()!=digest:raise ValueError('Model file checksum mismatch')
        target=cache/source.name
        if not target.exists() or hashlib.sha256(target.read_bytes()).hexdigest()!=digest:shutil.copy2(source,target)
    def no_network(*args,**kwargs):raise RuntimeError('Network is blocked in this local-model acceptance test')
    socket.socket.connect=no_network
    from paddleocr import TextRecognition
    recognizer=TextRecognition(model_name='PP-OCRv5_server_rec',model_dir=str(cache),device='cpu')
    inputs=[*sorted(Path('work/badge-unwrap-round2-20261030').glob('*False.png')),
            *sorted(Path('work/badge-recognition-20261030').glob('*.png'))]
    rows=[]
    for path in inputs:
        pixels=np.array(Image.open(path).convert('RGB'))
        result=list(recognizer.predict(input=pixels[:,:,::-1]))[0]
        row={'input':str(path),'text':result['rec_text'],'score':float(result['rec_score'])}
        rows.append(row);print(json.dumps(row,ensure_ascii=True),flush=True)
    (out/'results.json').write_text(json.dumps({'model':'PP-OCRv5_server_rec','network_blocked':True,
        'archive_sha256':lock['archive_sha256'],'rows':rows},ensure_ascii=False,indent=2),'utf-8')
