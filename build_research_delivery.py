from pathlib import Path
import json
import re
from html import escape

ROOT = Path(__file__).resolve().parent
VIZ = Path(r'C:\Users\35100\.codex\visualizations\2026\10\26\01a17893-fd47-7af0-aa25-109ba7e58ec6\pdf-ppt-market-map.html')

traditional_text = (ROOT / 'research-traditional.md').read_text(encoding='utf-8')
traditional = []
for match in re.finditer(r'^## (\d+)\. ([^\n]+)\n(.*?)(?=^## |\Z)', traditional_text, re.M | re.S):
    number, name, body = match.groups()
    bullets = re.findall(r'^- (.+)$', body, re.M)
    urls = re.findall(r'\]\((https?://[^\s)]+)\)', body)
    traditional.append({
        'name': name, 'category': '商业引擎与集成' if int(number) >= 19 else 'Office 生成入口' if int(number) == 18 else 'Office 图片与附件入口' if int(number) == 17 else '传统或混合转换',
        'capability': bullets[0] if bullets else '',
        'limitations': next((b for b in bullets if b.startswith(('尚未验证', '未确认', '本轮没有', '本页没有'))), bullets[-2] if len(bullets) > 1 else ''),
        'sources': urls, 'evidence': '官方公开资料，未实测', 'tested': False,
    })

assert len(traditional) == 24
ai = json.loads((ROOT / 'research-ai-global.json').read_text(encoding='utf-8'))['products']
china = json.loads((ROOT / 'research-china.json').read_text(encoding='utf-8'))['products']
technical = json.loads((ROOT / 'research-technical.json').read_text(encoding='utf-8'))['items']
assert len(ai) == 17 and len(china) == 19 and len(technical) == 20

groups = [
    ('传统产品、Office 入口与商业引擎', traditional, 'research-traditional.md'),
    ('国际 AI、视觉重建与相邻候选', ai, 'research-ai-global.md'),
    ('中国市场产品入口与功能模式', china, 'research-china.md'),
    ('开源组件、转换项目与生成工作流', technical, 'research-technical.md'),
]
all_items = [dict(item, research_group=label) for label, items, _ in groups for item in items]
source_urls = sorted({url for item in all_items for url in item.get('sources', [])})
registry = {
    'checked_date': '2026-10-26', 'record_count': len(all_items),
    'counting_note': '80 条记录含同品牌不同模式、相邻候选、商业引擎与开源组件，不是 80 款直接转换产品或独立品牌。',
    'method': '官方公开资料核查；未运行转换、未上传用户文件、未登录或购买。',
    'unique_source_urls_in_registry': len(source_urls),
    'items': all_items,
}
(ROOT / 'PDF转PPT产品与技术清单_2026-10-26.json').write_text(json.dumps(registry, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

master = (ROOT / 'research-synthesis.md').read_text(encoding='utf-8')
for i, (label, _, filename) in enumerate(groups, 1):
    content = (ROOT / filename).read_text(encoding='utf-8')
    content = re.sub(r'^(#{1,5}) ', r'#\1 ', content, flags=re.M)
    master += f'\n\n---\n\n# 附录 {i}：{label}\n\n' + content
master += '\n\n---\n\n# 资料与复核记录\n\n'
master += f'结构化总清单包含 80 条记录、{len(source_urls)} 个去重后的来源 URL。正文与补充候选的链接可能更多；URL 数不是独立证据数量。\n\n'
master += (ROOT / 'research-review.md').read_text(encoding='utf-8')
output = ROOT / 'PDF转PPT市场与技术调研_2026-10-26.md'
output.write_text(master, encoding='utf-8')

chunks = ['''<div id="pdf-ppt-research-map">
<style>
#pdf-ppt-research-map {color:var(--foreground)}
#pdf-ppt-research-map details {border-top:1px solid var(--border);padding:12px 0}
#pdf-ppt-research-map summary {padding:6px 0;font-weight:500}
#pdf-ppt-research-map table {width:100%;border-collapse:collapse}
#pdf-ppt-research-map th,#pdf-ppt-research-map td {padding:10px 8px;text-align:left;vertical-align:top;border-bottom:1px solid var(--border)}
#pdf-ppt-research-map th {font-weight:500}
#pdf-ppt-research-map td:first-child {min-width:110px;width:19%}
#pdf-ppt-research-map td:nth-child(2) {width:25%}
#pdf-ppt-research-map a {color:var(--foreground);text-decoration:underline}
#pdf-ppt-research-map .metadata {color:var(--muted-foreground);margin:8px 0 16px}
#pdf-ppt-research-map .table-responsive {overflow-x:auto}
@media (max-width:600px) {
 #pdf-ppt-research-map table,#pdf-ppt-research-map tbody,#pdf-ppt-research-map tr,#pdf-ppt-research-map td {display:block;width:auto}
 #pdf-ppt-research-map thead {display:none}
 #pdf-ppt-research-map tr {padding:10px 0;border-bottom:1px solid var(--border)}
 #pdf-ppt-research-map td,#pdf-ppt-research-map td:first-child,#pdf-ppt-research-map td:nth-child(2) {width:auto;min-width:0;border:0;padding:4px 0}
 #pdf-ppt-research-map td:first-child {font-weight:500}
}
</style>
<h2>PDF 转 PPT：产品与技术地图</h2>
<div class="metadata text-small">2026-10-26 · 80 条记录，含不同功能入口、相邻候选与组件 · 官方资料核查，全部未实测</div>
''']
for label, items, _ in groups:
    chunks.append(f'<details><summary class="cursor-interaction">{escape(label)} · {len(items)} 条</summary><div class="table-responsive"><table class="table"><thead><tr><th scope="col">产品或项目 · 官方来源</th><th scope="col">路线与定位</th><th scope="col">编辑能力、限制与待核实项</th></tr></thead><tbody>')
    for item in items:
        capability = item.get('editability') or item.get('capability', '')
        limits = item.get('key_limit') or item.get('limitations') or item.get('license', '')
        if item.get('license'):
            limits = '许可：' + item['license'] + '；' + item.get('deployment', '')
        source = item.get('sources', [''])[0]
        chunks.append(f'<tr><td><a href="{escape(source, quote=True)}" target="_blank" rel="noopener noreferrer">{escape(item["name"])}</a></td><td>{escape(item.get("category", ""))}</td><td>{escape(capability)}<br><span class="text-small">{escape(limits)}</span></td></tr>')
    chunks.append('</tbody></table></div></details>')
chunks.append('</div>\n')
VIZ.write_text('\n'.join(chunks), encoding='utf-8')

assert len(all_items) == 80
assert all(item.get('sources') for item in all_items)
assert '\\"' not in VIZ.read_text(encoding='utf-8')
assert 'fetch(' not in VIZ.read_text(encoding='utf-8')
assert VIZ.stat().st_size < 1_000_000
assert '本轮 PDF 专用帮助未讲清完整 PPTX 链路' not in master
print(json.dumps({'records': len(all_items), 'groups': [len(g[1]) for g in groups], 'registry_source_urls': len(source_urls), 'report_bytes': output.stat().st_size, 'visual_bytes': VIZ.stat().st_size, 'report': str(output), 'visual': str(VIZ)}, ensure_ascii=False))
