"""Test PDF-owned text groups in a new project, preserving all prior edits."""
from pathlib import Path
import json,shutil,subprocess,sys,collections,argparse
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import fitz
from backend import store
from backend.models import PageScene
from backend.text_groups import recover_pdf_text_groups
from backend.font_calibration import calibrate
from backend.export import export_pptx
from backend.fonts import activate_existing


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);args=parser.parse_args()
    base=store.ROOT/'deliverables'/'v3-movement-20261028';source=base/'ordinary-round-03';out=base/args.output
    if out.exists():raise FileExistsError('Keep prior evidence; choose a new folder')
    out.mkdir();old=json.loads((source/'run.json').read_text('utf-8'));scene=PageScene.model_validate(json.loads((source/'scenes.json').read_text('utf-8'))[0])
    store.init();project=store.create('原生艺术字关联复测 · '+args.output)
    with fitz.open(old['source_pdf']) as doc:
        single=fitz.open();single.insert_pdf(doc,from_page=0,to_page=0);single.save(store.project_dir(project)/'source.pdf');single.close()
    names={scene.original}
    for layer in scene.layers:names.update(n for n in (layer.asset,layer.mask,layer.restoration_asset) if n)
    for name in names:shutil.copy2(store.asset_path(old['project'],name),store.asset_path(project,name))
    result,rows=recover_pdf_text_groups(project,scene)
    fresh={row['native_id'] for row in rows}
    probes=result.model_copy(deep=True);probes.layers=[l for l in probes.layers if l.id in fresh]
    calibrate(project,[probes],match_height=True)
    measured={l.id:l for l in probes.layers};result.layers=[measured.get(l.id,l) for l in result.layers];result.revision=0
    store.save_page(project,result)
    run={'project':project,'pages':[1],'source_pdf':str(store.project_dir(project)/'source.pdf'),'pipeline':'isolated local PDF text-group experiment'}
    for name,value in [('run',run),('scenes',[result.model_dump()]),('text-group-diagnostics',rows),('inventory',[{'page':1,'layers':len(result.layers),'types':dict(collections.Counter(l.kind for l in result.layers)),'missing_native_chars':0}])]:
        (out/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2),'utf-8')
    targets=[dict(slide=1,id=l.id,role='art-'+str(i),dx=0,dy=-60,source=l.source,semantic=l.text) for i,l in enumerate(result.layers) if l.id in fresh and l.text in ('以','代','回应一线')]
    (out/'movement-targets.json').write_text(json.dumps(targets,ensure_ascii=False,indent=2),'utf-8')
    activate_existing(l.font for l in result.layers if l.kind=='text')
    export_pptx(project,[result],out/'converted.pptx')
    subprocess.run(['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(store.ROOT/'scripts'/'render_real_case.ps1'),'-Folder',str(out)],check=True,timeout=120)
    subprocess.run([sys.executable,str(store.ROOT/'scripts'/'compare_real_case.py'),'--folder',str(out)],check=True,timeout=90)
    print(json.dumps({'project':project,'groups':len(rows),'unassociated':sum(len(r['unassociated_paint_ids']) for r in rows),'diagnostics':rows},ensure_ascii=False),flush=True)


if __name__=='__main__':main()
