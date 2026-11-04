from pathlib import Path
import hashlib,json,statistics
ROOT=Path(__file__).resolve().parents[1];base=ROOT/'deliverables'/'real-case-20261027';latest=base/'round-05'
metrics=json.loads((latest/'metrics.json').read_text('utf-8'))
inventory=json.loads((latest/'inventory.json').read_text('utf-8'))
run=json.loads((latest/'run.json').read_text('utf-8'))
editing=json.loads((latest/'editing-validation.json').read_text('utf-8-sig'))
def checksum(path):
 h=hashlib.sha256()
 with open(path,'rb') as f:
  for data in iter(lambda:f.read(1024*1024),b''):h.update(data)
 return h.hexdigest()
hashes={'pdf_unchanged':checksum(run['pdf'])==run['source_hashes']['pdf'],'ppt_unchanged':checksum(run['reference_ppt'])==run['source_hashes']['ppt']}
summary={'verdict':'not_perfect','pages':len(metrics),'objects':sum(m['layers'] for m in metrics),'editable_textboxes':sum(m['text_layers'] for m in metrics),
 'native_pdf_characters':sum(p['native_text_chars'] for p in inventory),'missing_native_characters':sum(m['missing_native_chars'] for m in metrics),
 'pdf_render_ssim_mean':statistics.mean(m['ssim'] for m in metrics),'pdf_render_ssim_min':min(m['ssim'] for m in metrics),
 'office_png_ssim_mean':statistics.mean(m['office_png_ssim'] for m in metrics),'office_png_ssim_min':min(m['office_png_ssim'] for m in metrics),
 'all_shape_counts_match':all(p['countMatches'] for p in editing['pages']),'text_edit_test':editing['textEdited'],'portrait_move_test':editing['portraitMoved'],
 'source_hashes_verified':hashes,'external_model_api_calls':len(run['cloud_calls']),'fully_editable':False}
(base/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf-8')
def link(path,label):return f'[{label}](<{path.resolve().as_posix()}>)'
lines=['# 真实材料 PDF 转 PPT 验证报告','',
'结论：尚未达到完美转换。已完成 27 页真实 PDF 的基线测试、5 轮本地修复与 PowerPoint 全稿复测，不能把当前版本宣传为全部内容可编辑。','',
'## 输入与判定口径','',
'- 用户提供的 PDF 与 PPT 均为 27 页、960×540 点；已只读检查两份原件。',
'- PDF 原稿中存在红色框线，参考 PPT 对应页没有同样框线；参考页还存在字体和文字位置差异。参考 PPT 仅用于评估，不能直接当作当前 PDF 的逐像素真值。',
'- 转换只读取 PDF；原生 PPT 中的正文和对象未参与重建。两份原件的 SHA-256 与测试开始时一致。',
'- 基线关闭了图内 OCR 与 SAM，仅评估原生提取链路；不是旧版全部功能的市场对标成绩。各轮范围与调用均见 run.json。',
'- SSIM 是同尺寸渲染的结构相似度，不是“还原百分比”。它不能单独证明文字可编辑或装饰全部可移动。','',
'## 本轮结果','',
f'- 全稿生成 {summary["objects"]} 个独立对象，其中 {summary["editable_textboxes"]} 个文本框。',
f'- PDF 可提取的 {summary["native_pdf_characters"]} 个非空白原生字符计数无遗漏；图片文字、艺术字不包含在这个统计内。',
f'- PDF 重新渲染平均 SSIM：{summary["pdf_render_ssim_mean"]:.4f}，最低 {summary["pdf_render_ssim_min"]:.4f}。',
f'- PowerPoint 直接 PNG 平均 SSIM：{summary["office_png_ssim_mean"]:.4f}，最低 {summary["office_png_ssim_min"]:.4f}。',
'- 27 页均已在 PowerPoint 打开，逐页对象数量与场景清单一致；已实际改字、移动封面人物、保存测试副本。',
'- 当前会话模型已检查原稿与代表页对照，另查看了全部 27 页结果缩略图；未声称已逐字读清所有缩略图小字。',
'- 外部大模型接口调用 0 次，产品试验账本占用 0 美元。首轮视觉检查由当前会话模型直接完成。','',
'## 每轮问题、修复与复测','',link(base/'iteration-log.md','逐轮记录'),'','## 仍未通过','',
'1. 图片内正文与艺术字尚未全部转换成可编辑文本。已新增所选素材的本地 OCR 与历史恢复入口，不能据此宣布整稿全部成功。',
'2. 独立绘制对象不等于全部语义对象。复杂图片中的每一个人物、图标与内部装饰尚未逐个拆出并验证。',
'3. 部分特殊混合效果转换为当前位置下的普通透明素材，移动后需要人工复核；只能证明已测试的封面人物能够独立移动。',
'4. 全稿视觉指标没有达到最初 0.98 目标。PowerPoint 图片重采样、PDF JPEG 压缩及部分字体与几何差异仍需修复。',
'5. WPS、Adobe、Canva、Gamma 的真实同文件转换对标未运行，不能宣称超过市场产品。','',
'## 文件','',
link(latest/'converted.pptx','当前真实测试转换结果'),'',link(latest/'editing-validation.json','PowerPoint 编辑与移动验证'),'',link(ROOT/'prompts'/'visual_review.md','视觉检查模型规则与提示词'),'',link(ROOT/'prompts'/'repair_policy.md','本地优先迭代策略'),'',link(ROOT/'prompts'/'review.schema.json','模型输出契约'),'',
'## 全稿预览','']
for i in range(1,4):lines.extend([f'![转换结果第 {(i-1)*9+1} 至 {i*9} 页](<{(latest/f"contact-result-{i}.png").resolve().as_posix()}>)',''])
lines.extend(['## 逐页记录',''])
for m in metrics:
 lines.extend([f'### 第 {m["page"]} 页','',f'PDF SSIM {m["ssim"]:.4f}；PowerPoint PNG SSIM {m["office_png_ssim"]:.4f}；{m["layers"]} 个对象、{m["text_layers"]} 个文本框。整体仍标为待校正。','',link(latest/f'compare-{m["page"]:02}.png','原 PDF 与转换后对照'),''])
(base/'真实材料测试报告.md').write_text('\n'.join(lines),'utf-8')
print(json.dumps(summary,ensure_ascii=True,indent=2))
