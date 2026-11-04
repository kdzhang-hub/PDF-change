from pathlib import Path
import json,hashlib,collections
ROOT=Path(__file__).resolve().parents[1]
folder=ROOT/'deliverables'/'v3-movement-20261028'
inputs=json.loads((folder/'input-inventory.json').read_text('utf-8'));summary={}
for kind in ('ordinary','image'):
    out=folder/(kind+'-full');inventory=json.loads((out/'inventory.json').read_text('utf-8'));metrics=json.loads((out/'metrics.json').read_text('utf-8'))
    edits=json.loads((out/'font-edit-validation.json').read_text('utf-8-sig'))
    summary[kind]={'pages':len(inventory),'objects':sum(x['layers'] for x in inventory),'native_text':sum(x['types'].get('text',0) for x in inventory),
      'mean_ssim':sum(x['ssim'] for x in metrics)/len(metrics),'min_ssim':min(x['ssim'] for x in metrics),'font_edit_tests':len(edits),
      'font_edit_passed':all(x['reopened'] and x['fontChanged'] and x['sizeChanged'] and x['textChanged'] for x in edits),
      'source_unchanged':hashlib.sha256(Path(inputs[kind]['source']).read_bytes()).hexdigest()==inputs[kind]['sha256'],
      'run':json.loads((out/'run.json').read_text('utf-8'))}
(folder/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),'utf-8')
lines=['# v3 普通版与图片版转换复测','',
'结论：完成两份全27页测试及本轮本地修复，仍未达到完美转换。原文件哈希均未变化，云端调用为零。', '',
'## 测试方法','',
'只在副本中修改。普通版先移动封面小标签、人物、星光，第2页标题与分组，第4页照片、段落和装饰，共8个对象。图片版只有每页一张整图，移动并等比缩小第1、2、4页的整图，不把整图移动算成内部对象可编辑。两份移动副本各导出27页PDF，通过正式本机HTTP转换与导出。原样PDF仅作移动对照，未将原样PDF另跑一遍转换。参考PPT未参与对象重建。','',
'## 全稿结果','']
for kind,title in [('ordinary','普通版'),('image','图片版')]:
    s=summary[kind]
    lines.extend([f'- {title}：{s["pages"]}页，{s["objects"]}个对象，{s["native_text"]}个文本框；PowerPoint全部文本框改字、中文字体、字号、保存重开：{s["font_edit_tests"]}项通过。平均SSIM {s["mean_ssim"]:.6f}，最低{s["min_ssim"]:.6f}。项目ID {s["run"]["project"]}。'])
lines.extend(['','文本框编辑测试只证明已生成对象能编辑，不证明全部可见文字已覆盖或改字后的视觉合格。图片版仍有艺术字、小照片内文字等未可靠恢复。普通PDF原始文本包含不可见的重复艺术字动作，原始字符计数差不能直接当作可见文字遗漏数量。', '',
'## 本轮问题与修复','',
'1. 首轮图片版三个代表页只得到3张图片、0文本框。修复裁剪和透明组合页面绕过OCR与SAM的分支后，三页得到70个文本框。',
'2. 普通版封面黑色重复字形：不可见文字动作被直接创建为文本框。先验证实际像素贡献后再创建文字，三页平均SSIM从0.864814提升至0.914259。不可见动作已跳过，不以减少对象数当作识别覆盖下降。',
'3. Paddle先初始化后导入PyTorch可复现WinError127。SAM改为独立本地进程，三页正式接口得到45个图片图层，未再出现该错误。缺失CUDA后处理扩展有警告，未把自动遮罩当作人工验收通过。',
'4. OCR白框：改用文字框外邻域估计背景，并尝试本地字体拟合与Office位置校准。图片三页平均SSIM由0.850271到0.852699，提升有限，部分字体仍不匹配。',
'5. 分割补背景时改动了遮罩外边缘：只将修复值写回实际切出的像素，新增纹理背景重组回归。', '',
'## 真实移开检查与失败项','',
'普通版与图片版代表页均实际移开小标签和人物候选，并保存、重开，位置持久化均通过。对应文件为 ordinary-round-02 与 image-round-03 下的 moved、hidden 截图及 movement-validation.json。', '',
'- 普通版人物照片原位置未见同一整幅照片副本；照片内部的人与车仍未分离。',
'- 普通版小标签移开后有阴影残留：失败。文字与阴影的关联和同步重建需优化。',
'- 图片版人物自动切出裤腿等局部，不能当作完整人物分离：失败。',
'- 图片版正文与标题存在近似字体、字重和背景补全痕迹；外观未达到0.98：失败。',
'- 原PPT直接PNG与其Office导出PDF本身也有差别，封面艺术字尤为明显；转换器以实际PDF为输入验收，原PPT与PDF差异记录在 source-export-metrics.json。', '',
'## 验证与证据','',
'29项后端回归通过。代表页及全稿的原生文本字体编辑、保存重开均通过。未运行WPS实机对标，也未对所有可见语义对象进行人工逐对象标注，不能宣称全部装饰、全部字体或所有内容已完美可编辑。', '',
'ordinary-full、image-full 分别保留 converted.pptx、powerpoint.pdf、逐页office截图、对照图、metrics.json、scenes.json与字体验证记录。各轮失败结果、移动副本和原件副本均保留。', '',
'后续优先项：文字及阴影同步、字体与艺术字还原、人物完整遮罩、遮挡背景修复。用户追加的PDF转DOCX作为下个格式功能，现有DOCX只作验收参考。'])
(folder/'测试与修复报告.md').write_text('\n'.join(lines)+'\n','utf-8')
print(json.dumps({k:{x:v for x,v in s.items() if x!='run'} for k,s in summary.items()},ensure_ascii=True))
