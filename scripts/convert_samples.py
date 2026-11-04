from pathlib import Path
import sys,json,shutil
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend import store
from backend.extract import prepare,convert_page
from backend.export import export_pptx
def main():
 store.init();out=store.ROOT/'deliverables';out.mkdir(exist_ok=True)
 results=[]
 for filename in ('digital.pdf','scanned.pdf'):
  project=store.create(filename)
  shutil.copyfile(store.ROOT/'samples'/filename,store.project_dir(project)/'source.pdf')
  scenes=[]
  for page in prepare(project):
   scene=convert_page(project,page.index,page.original);store.save_page(project,scene);scenes.append(scene)
   print(filename,page.index,len(scene.layers),'objects',scene.status,flush=True)
  export_pptx(project,scenes,out/filename.replace('.pdf','.pptx'))
  (out/filename.replace('.pdf','-scenes.json')).write_text(json.dumps([s.model_dump() for s in scenes],ensure_ascii=False,indent=2),'utf-8')
  results.append({'input':filename,'project':project,'pages':[{'index':s.index,'objects':len(s.layers),'text_count':sum(l.kind=='text' for l in s.layers),'status':s.status,'warnings':s.warnings} for s in scenes]})
 (out/'conversion-results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),'utf-8')
if __name__=='__main__':main()
