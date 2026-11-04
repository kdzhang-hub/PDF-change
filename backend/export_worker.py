"""Build one immutable export snapshot in a fresh, local-only process."""
import json,re,sys
from . import store
from .models import PageScene
from .export import export_pptx


def paths(project,token,format='pptx'):
    if not re.fullmatch(r'[a-f0-9]{32}',token):raise ValueError('无效导出身份')
    if format not in ('pptx','docx'):raise ValueError('无效导出格式')
    root=store.project_dir(project)
    return root/f'export-{token}.scene.json',root/f'export-{token}.{format}'


def build(project,token,format='pptx'):
    snapshot,output=paths(project,token,format)
    pages=[PageScene.model_validate(x) for x in json.loads(snapshot.read_text('utf-8'))]
    if not 0<len(pages)<=500:raise ValueError('导出页数无效')
    temporary=output.with_suffix('.building')
    if format=='docx':
        from .export_docx import export_docx
        from .word_calibration import prepare
        prepared,report=prepare(project,pages,output.with_suffix('.word-probe'))
        export_docx(project,prepared,temporary)
        output.with_suffix('.report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    else:export_pptx(project,pages,temporary)
    temporary.replace(output)
    return output


if __name__=='__main__':build(*sys.argv[1:])
