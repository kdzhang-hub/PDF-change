from pathlib import Path
import hashlib,json,tarfile,urllib.request
ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'models'
SOURCES={
 'sam':('sam2.1_hiera_small.pt','https://dl.fbaipublicfiles.com/segment_anything_2/092824/sam2.1_hiera_small.pt'),
 'ocr_det':('PP-OCRv5_mobile_det_infer.tar','https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-OCRv5_mobile_det_infer.tar'),
 'ocr_rec':('PP-OCRv5_mobile_rec_infer.tar','https://paddle-model-ecology.bj.bcebos.com/paddlex/official_inference_model/paddle3.0.0/PP-OCRv5_mobile_rec_infer.tar'),
}
def main():
 DEST.mkdir(exist_ok=True)
 lock_path=ROOT/'models.lock.json'
 locked=json.loads(lock_path.read_text('utf-8')) if lock_path.exists() else {}
 manifest={}
 for key,(name,url) in SOURCES.items():
  path=DEST/name
  if not path.exists():
   print('Downloading',name,flush=True)
   partial=path.with_suffix(path.suffix+'.partial')
   urllib.request.urlretrieve(url,partial)
   partial.replace(path)
  digest=hashlib.sha256(path.read_bytes()).hexdigest()
  if key in locked and digest!=locked[key]['sha256']:raise RuntimeError('Model checksum mismatch: '+name)
  locked[key]={'url':url,'file':name,'sha256':digest}
  if key=='sam':manifest.update(sam_checkpoint=name,sam_sha256=digest,sam_commit='2b90b9f5ceec907a1c18123530e92e794ad901a4')
  else:
   with tarfile.open(path) as archive:archive.extractall(DEST,filter='data')
   manifest[key]=name.removesuffix('.tar')
  lock_path.write_text(json.dumps(locked,indent=2),'utf-8')
  (DEST/'manifest.json').write_text(json.dumps(manifest,indent=2),'utf-8')
  print(key,digest,flush=True)
if __name__=='__main__':main()
