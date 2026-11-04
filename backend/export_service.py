"""Keep heavy/native export work out of the long-lived HTTP process."""
import json,os,subprocess,sys,threading
from . import store
from .models import uid
from .export_worker import paths

_SLOT=threading.BoundedSemaphore(1)


def create_export(project,pages,format='pptx'):
    if format not in ('pptx','docx'):raise ValueError('无效导出格式')
    if not pages or any(page.status=='pending' for page in pages):raise ValueError('所选页面尚未转换')
    if not _SLOT.acquire(blocking=False):raise ValueError('另一份文件正在导出，请稍后重试')
    try:
        # Hold user-font registration in the long-lived service as well as the
        # short-lived builder; otherwise Office can fall back after it exits.
        from .fonts import activate_existing
        activate_existing(layer.font for page in pages for layer in page.layers if layer.kind=='text')
        token=uid();snapshot,output=paths(project,token,format)
        snapshot.write_text(json.dumps([page.model_dump() for page in pages],ensure_ascii=False),'utf-8')
        environment={**os.environ,'LAYERDECK_DATA':str(store.DATA),'PYTHONUTF8':'1'}
        try:
            command=[sys.executable,'-m','backend.export_worker',project,token]
            if format!='pptx':command.append(format)
            result=subprocess.run(command,cwd=store.ROOT,env=environment,
                capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=240,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        except subprocess.TimeoutExpired as exc:raise ValueError('本地导出超时，项目已保留，请缩小所选页数后重试') from exc
        if result.returncode or not output.is_file():
            log=store.project_dir(project)/f'export-{token}.log'
            log.write_text(result.stdout+'\n'+result.stderr,'utf-8')
            raise ValueError('本地导出失败，项目及诊断记录已保留，可以重试')
        return output
    finally:_SLOT.release()
