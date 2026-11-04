from __future__ import annotations
import json
import os
import re
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from .models import PageScene, uid

ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get('LAYERDECK_DATA', str(ROOT / 'data'))).resolve()


@contextmanager
def db():
    DATA.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DATA / 'projects.sqlite3', timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute('PRAGMA journal_mode=WAL')
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init():
    with db() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS pages(project TEXT,idx INTEGER,scene TEXT,revision INTEGER DEFAULT 0,PRIMARY KEY(project,idx));
        CREATE TABLE IF NOT EXISTS history(id INTEGER PRIMARY KEY,project TEXT,idx INTEGER,scene TEXT,created REAL);
        CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY,project TEXT,pages TEXT,status TEXT,progress INTEGER DEFAULT 0,message TEXT,cancel INTEGER DEFAULT 0,created REAL);
        CREATE TABLE IF NOT EXISTS charges(id TEXT PRIMARY KEY,provider TEXT,amount REAL,status TEXT,details TEXT,created REAL);
        ''')


def project_dir(project: str) -> Path:
    if not re.fullmatch(r'[a-f0-9]{32}', project):
        raise ValueError('无效项目 ID')
    return DATA / project


def asset_path(project: str, name: str) -> Path:
    if not re.fullmatch(r'[a-zA-Z0-9_.-]+', name) or name in ('.', '..'):
        raise ValueError('无效素材路径')
    return project_dir(project) / 'assets' / name


def create(name: str) -> str:
    project = uid()
    (project_dir(project) / 'assets').mkdir(parents=True)
    with db() as c:
        c.execute('INSERT INTO projects VALUES(?,?,?)', (project, name, time.time()))
    return project


def list_projects():
    with db() as c:
        return [dict(r) for r in c.execute('SELECT * FROM projects WHERE EXISTS (SELECT 1 FROM pages WHERE project=projects.id) ORDER BY created DESC')]


def get_project(project):
    with db() as c:
        row = c.execute('SELECT * FROM projects WHERE id=?', (project,)).fetchone()
        if not row:
            raise FileNotFoundError('项目不存在')
        result = dict(row)
        result['pages'] = [json.loads(r['scene']) for r in c.execute('SELECT scene FROM pages WHERE project=? ORDER BY idx', (project,))]
        return result


def get_page(project, index) -> PageScene:
    with db() as c:
        r = c.execute('SELECT scene FROM pages WHERE project=? AND idx=?', (project,index)).fetchone()
    if not r:
        raise FileNotFoundError('页面不存在')
    return PageScene.model_validate_json(r['scene'])


def save_page(project, page: PageScene, expected: int | None = None):
    for layer in page.layers:
        for asset in (layer.asset, layer.mask,layer.restoration_asset):
            if asset and not asset_path(project, asset).is_file():
                raise ValueError('素材不存在')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        old = c.execute('SELECT scene,revision FROM pages WHERE project=? AND idx=?', (project,page.index)).fetchone()
        if expected is not None and old and old['revision'] != expected:
            raise ValueError('页面已更新，请重新载入，避免覆盖其他修改')
        if old:
            c.execute('INSERT INTO history(project,idx,scene,created) VALUES(?,?,?,?)', (project,page.index,old['scene'],time.time()))
        page.revision = old['revision'] + 1 if old else 0
        c.execute('INSERT OR REPLACE INTO pages VALUES(?,?,?,?)', (project,page.index,page.model_dump_json(),page.revision))
    return page


def get_job(job):
    with db() as c:
        row = c.execute('SELECT * FROM jobs WHERE id=?', (job,)).fetchone()
    if not row:
        raise FileNotFoundError('任务不存在')
    return dict(row)


def update_job(job, **fields):
    if not set(fields) <= {'status','progress','message','cancel'}:
        raise ValueError('无效任务字段')
    with db() as c:
        c.execute('UPDATE jobs SET ' + ','.join(f'{key}=?' for key in fields) + ' WHERE id=?', (*fields.values(),job))


def recover_jobs():
    with db() as c:
        c.execute("UPDATE jobs SET status='interrupted',message='服务重启，可从未完成页继续' WHERE status IN ('queued','running')")


def reserve(provider, amount, details):
    if not isinstance(amount, (int,float)) or not 0 < amount <= 5:
        raise ValueError('价格未知或单次金额超过预算')
    with db() as c:
        c.execute('BEGIN IMMEDIATE')
        used = c.execute("SELECT COALESCE(SUM(amount),0) FROM charges WHERE status IN ('reserved','spent','uncertain')").fetchone()[0]
        if used + amount > 5 + 1e-9:
            raise ValueError('5 美元试验预算不足，已停止云端调用')
        charge = uid()
        c.execute('INSERT INTO charges VALUES(?,?,?,?,?,?)', (charge,provider,amount,'reserved',json.dumps(details,ensure_ascii=False),time.time()))
    return charge


def settle(charge, status):
    if status not in ('spent','released','uncertain'):
        raise ValueError('无效费用状态')
    with db() as c:
        c.execute('UPDATE charges SET status=? WHERE id=?', (status,charge))


def budget():
    with db() as c:
        rows = [dict(r) for r in c.execute('SELECT * FROM charges ORDER BY created DESC')]
    used = sum(r['amount'] for r in rows if r['status'] != 'released')
    return {'limit':5,'committed':round(used,6),'remaining':round(5-used,6),'calls':rows}
