# PDF 转 PPT：国际 AI 产品核验分报告

研究日期：2026 年 10 月 26 日。范围：17 个产品。执行方式：AI 辅助检索，逐项核对官方帮助、产品页与发布公告；未注册、未付费、未上传 PDF、未运行同一文件的转换测试。下述“支持”“可编辑”均指官方公开能力或声明，不代表通过实测。中国市场及传统 PDF 转换器由其他分报告覆盖。

## 最影响判断的发现

1. 同一个 PDF 转 PPT 标签覆盖三种工作：每页放一张图片、还原原位文字与图形、理解内容后重新组织演示稿。同一产品也可能有多条路线。MagicSlides 官方对前两类输出的区分尤其明确：Without AI 是每页图片，With AI 重写结构。其教程还承认没有测试导出后在 PowerPoint 内编辑的表现。[MagicSlides 操作教程](https://www.magicslides.app/guides/how-to-convert-pdf-to-ppt)
2. 不能沿用“Gamma 只抽取文字”的旧结论。Gamma 当前帮助区分 Gamma 5 与经典生成器：前者宣称保留 PDF 和 PPTX 的布局及结构，并保持可编辑；经典入口仍主要抽取文字。两者应分开实测。[Gamma 导入帮助](https://help.gamma.app/en/articles/11047840-how-can-i-import-slides-or-content-into-gamma)
3. 不能沿用“NotebookLM 只导出 PDF”的旧结论。Google 于 2026 年 3 月 20 日已宣布新增 PPTX 导出。这个公告没有证明输出对象可逐一编辑。[Google 官方发布](https://workspaceupdates.googleblog.com/2026/03/new-ways-to-customize-and-interact-with-your-content-in-NotebookLM.html)
4. “可编辑”需要拆到对象：文字是否文本框、图形是否矢量、表格是否原生表格、图表是否带数据。Slaide 官方坦言表格是定位文本框，图表是图形或图片，扫描页仍是图片。它比“fully editable”的总称更有判别力。[Slaide 说明](https://www.slaide.de/pdf-to-powerpoint)

## 产品逐家核验

### 1. Gamma

- 路线：Gamma 5 宣称可以保留 PDF 原设计，也可要求 AI 改写重做；经典生成器则属于内容重做。
- 输入输出：PDF、PPTX、DOCX；导出 PPTX、PDF、PNG。PDF 上限 100 MB，PPTX 与 Word 上限 200 MB。
- 可编辑性：官方明确宣称新导入流程保持可编辑；导出帮助还明确支持原生可编辑表格。不能据此推断任意扫描图、复杂公式、图表均恢复语义结构。
- 限制：无统一样本实测；新旧入口行为不同。导出的幻灯片母版为空，不能把对象可编辑等同于模板结构恢复。导入帮助还明确承认部分图表会以静态图片进入，要改数据需在 Gamma 中重建图表。
- 收费与隐私：本分报告未完整核对当前各计划额度及数据保留条款，不填价格。
- 证据：官方帮助，较强的功能证据，非效果验证。
- 来源：[导入](https://help.gamma.app/en/articles/11047840-how-can-i-import-slides-or-content-into-gamma)、[导出](https://help.gamma.app/en/articles/8022861-what-s-the-easiest-way-to-export-my-gamma)。

### 2. Canva

- 路线：导入 PDF 后在设计编辑器中尽量还原，支持的文字和图片可拆开修改。
- 输入：官方 PDF 帮助列出 500 页、300 MB、最多 1,400 个元素和图片等限制。扫描页或扁平化文本以单张图片导入，不能直接编辑其文字。
- 关键反证：不能写“任意 PDF 导入都能完全编辑”。字体可能替换、复杂文件可能缺失内容，版式可能移动。
- PPTX 输出：补充核验的官方 PDF 转 PPT 专用产品页明确说明上传 PDF、形成可自定义设计、编辑后转换成 PowerPoint。因此完整产品链路已获得官方声明支持；实际下载与对象粒度尚未实测，扫描页仍受上述限制。
- 文档差异：通用上传要求页称 PDF 页成为 A4 中的图片；更专门的 PDF 编辑帮助又说明支持内容可编辑。应保留这种文档差异，优先按具体导入入口测试，不能直接宣布所有 PDF 都变图。
- 来源：[PDF 转 PPT 专用入口](https://www.canva.com/features/pdf-to-ppt-converter/)、[PDF 导入与编辑](https://www.canva.com/help/import-and-edit-pdfs-canva/)、[通用上传要求](https://www.canva.com/help/upload-formats-requirements/)。

### 3. Plus AI

- 路线：在 PowerPoint 和 Google Slides 内，用 PDF 内容生成演示稿，或 Remix 既有演示稿的结构并套用新设计。
- 输入输出：PDF、PPTX 等文件；网页端可导出 PPTX。
- 关键限制：官方上传帮助明确写不能从输入文档中提取图片、示意图或图表。这是对“把原 PDF 全部图文还原”的重要反证。Remix 保留页结构不等于保留原视觉设计。
- 付费限制：上传文件需要 Pro 或 Team；官网有 7 天试用。帮助页称每次大约最多 30 页，长稿建议分章。
- 可编辑性：结果在 PowerPoint 或 Google Slides 内生成，具有继续编辑的工作流证据；图表与公式重建质量仍未测试。
- 来源：[上传帮助](https://guide.plusai.com/ai-for-presentations/generate-a-presentation/upload-a-file)、[网页端导出](https://guide.plusai.com/plus-ai/use-plus-in-your-web-browser)、[官网](https://plusai.com/)。

### 4. SlidesAI

- 路线：从 PDF 或 Word 抽取重点，先生成逐页大纲，再选主题生成新演示稿。
- 输入输出：PDF、Word；可在网页编辑器导出 PPTX，也可直接向当前 PowerPoint 或 Google Slides 文件加入页面。
- 付费限制：文档上传需要 Pro 或 Premium。
- 隐私声明：官方帮助称不保存上传文档，重复生成需重新上传。这是厂商声明，未审计服务器行为。
- 未知：保留原版式、OCR 语种、复杂公式和图表的对象级重建未获得充分证据。
- 来源：[从文件生成](https://help.slidesai.io/generate-from-an-uploaded-document-4m68h)、[PPTX 导出](https://help.slidesai.io/export-as-a-powerpoint-file-s95ww)。

### 5. Presentations.AI

- 路线：理解 PDF 并重组内容、应用品牌与模板；不应当成逐页像素还原工具。
- 输入输出：PDF、扫描 PDF 等；产品页声明 PPTX 输出包含文字、原生表格和可移动对象，并称支持扫描 OCR。
- 限制：产品页的“30 秒”“复杂版式精准处理”“charts stay charts”均未被本轮实测证明。图表是否带工作簿数据，仍需检查导出包。
- 免费条件：产品页说可免注册开始，但准备下载或分享时需注册；不能把“免费开始”写成“永久免费无限制下载”。本次打开 FAQ 发生重定向，未稳定确认历史搜索摘要中的按页导出积分规则，因此不采用该数字。
- 隐私声明：工具页称加密并在处理后自动删除文件；未审计。
- 来源：[PDF 转 PPT 产品页](https://www.presentations.ai/tools/pdf-to-ppt)、[FAQ](https://www.presentations.ai/faq)。

### 6. Beautiful.ai

- 路线：PDF 作为素材，AI 生成可修改大纲，再用 Smart Slides 重做。官方明确说不保留 PDF 原来的像素级版式。
- 输入输出：PDF 输入；可选 Editable PowerPoint、PowerPoint Images、Google Slides、PDF 等输出。
- 可编辑性：Editable PowerPoint 官方声明元素可继续编辑；PowerPoint Images 则明确每页是静态图片。这两种选项不能混为一谈。
- 付费限制：可编辑 PPTX 与 Google Slides 输出属于 Pro、Team、Enterprise；产品页称 14 天试用。
- 兼容限制：动画和转场在外部输出中丢失，字体缺失会影响版式。
- 来源：[PDF 生成流程](https://www.beautiful.ai/pdf-to-ppt)、[导出帮助](https://support.beautiful.ai/hc/en-us/articles/30629528652685-Exporting-your-slides-and-presentations)。

### 7. Pitch

- 定位：在线演示工具与 AI 制作相邻竞品。
- 已核实：官方导入帮助列的是 PowerPoint PPTX；PPTX 导出是付费功能，支持文字、形状、表格、图表等，并列出字体、视频和动画兼容限制。
- 未核实：本轮未找到足够官方证据证明直接接收 PDF 并转为 PPTX。应列为相邻产品，不计为已确认的直接 PDF 转 PPT 工具。
- 来源：[导入帮助](https://help.pitch.com/en/articles/4615453-import-a-presentation)、[导出帮助](https://help.pitch.com/en/articles/6713988-export-a-presentation-to-power-point)。

### 8. Decktopus

- 路线：上传 PDF 作为 context 或 Use as a Resource，抽取要点并构建新演示稿。另有导入已有 PDF、PPTX、HTML deck 的路径，应与资源重做区分。
- 输入输出：PDF；帮助明确可以下载 PowerPoint，MCP 介绍说明在 Decktopus 内导出 PPT 需要 Pro 或 Business。
- 可编辑性：在线可修改文字并通过 AI 改页；本轮未获得足以证明全部 PowerPoint 对象可编辑、图表带数据的文档。
- 限制：原稿图文与布局的保留程度需实际测试，不能仅按“Redesign”理解为无损还原。
- 来源：[创建教程](https://help.decktopus.com/en/articles/111-how-to-create-a-presentation-with-ai)、[资源模式](https://www.decktopus.com/presentation-maker-online)、[导出计划及导入说明](https://www.decktopus.com/mcp)。

### 9. Slidesgo

- 路线：上传材料、由 AI 生成演示稿并选模板。
- 输入输出：官方 converter 支持 PDF、DOC、DOCX、TXT、MD，单文件 25 MB；产品页称可生成可自定义 PowerPoint。
- 限制：生成与文件上传需登录；模板及额外功能受套餐限制。OCR、原版式保留、图表和公式对象级编辑没有充分官方证据。
- 品牌辨别：本轮使用 slidesgo.com；搜索同时出现 slidesgo.io，不应当作同一公司或同一产品。
- 来源：[官方 PDF converter](https://slidesgo.com/ai/pdf-to-ppt-converter)、[AI 生成器](https://slidesgo.com/ai/presentation-maker)。

### 10. MagicSlides

- 路线一：Without AI，每个 PDF 页面作为一张图片放入 PPTX；视觉原样、文字不可编辑。
- 路线二：With AI，读 PDF 文字、确认受众和逐页计划、套模板重做，消耗一次 presentation credit。教程中的 PPTX 导出标记为 Plus。
- 可编辑性边界：教程说 AI 版在其编辑器中可编辑，但明确承认未测试下载后在 PowerPoint 内编辑；不能替厂商补足这个验证。
- 附加路线：Chrome 扩展可选取 PDF 中局部图表区域并重建；这仍属于厂商演示，非本轮实测。
- 数据风险示例：官方教程自己的样稿里，AI 把未声明币种的“24 million”写成“$24M”，说明重做内容须核对单位与币种。
- 来源：[两种模式与限制](https://www.magicslides.app/guides/how-to-convert-pdf-to-ppt)、[API](https://www.magicslides.app/ppt-api)。

### 11. SlidesPilot

- 路线：理解文档并提炼、组织成演示故事，官方明确区别于单纯格式转换。
- 输入输出：PDF、Word、PPTX，最多 50 MB；可导出 PPTX、PDF 或 Google Slides。
- 图像：可开关 Include image from your file，使用原文中的图、表等视觉素材。提取图像不等于重建为原生可编辑图表。
- 限制：官方建议复核复杂图表准确性。帮助中有长文档与最多 200 页输出的描述，但实际计划额度、最大成功样本未测试。
- 隐私声明：官方称上传文件私有且不公开分享；不能据此推断从不保留、从不使用第三方模型。
- 来源：[转换操作帮助](https://help.slidespilot.com/how-to/convert-pdf-word-to-ppt)、[产品定位](https://www.slidespilot.com/)。

### 12. SlideSpeak

- 路线：从 PDF 等文件生成演示稿，兼有生成、编辑和摘要 API。
- 输入输出：官方 API 文档列 PDF、PowerPoint、Word、Excel；下载帮助列 PPTX、PDF、Google Slides。
- 可编辑性：下载帮助明确声明 PPTX 含可编辑文字、形状、图片、表格和图表，以及演讲者备注。图表数据结构仍需实测。
- 付费限制：下载和导出要求 Premium、Premium Plus 或 Lifetime；翻译工具生成的文稿有免费导出例外。普通 PPTX、PDF、Google Slides 下载不耗积分。
- 来源：[下载及可编辑性](https://slidespeak.co/help/articles/how-do-i-download-my-presentation)、[API 文档](https://docs.slidespeak.co/)。

### 13. NoteGPT

- 已核实：官方帮助中心存在 AI Presentation 导航，旧官方功能总览曾写可从文件、链接或文字生成 PPT；当前帮助总览可确认 PDF、PPT、图片摘要和多模态学习工具。
- 核验缺口：直接 PDF 转 PPT 产品页在本轮浏览工具不可访问；当前 AI Presentation 导航跳转到总览，没有提供足够 PPTX 导出与对象级编辑细节。
- 结论：保留为待验证候选，不写“已确认直接 PDF 转可编辑 PPTX”；不以搜索中其他 notegptapp.com 网站替代 notegpt.io 的证据。
- 来源：[官方帮助中心](https://help.notegpt.io/)、[当前功能总览](https://help.notegpt.io/notegpt-features-overview)、[旧功能总览](https://notegpt.crisp.help/en/article/feature-overview-1yzo48i/)。

### 14. NotebookLM 与 Gemini Notebook

- 路线：根据 PDF 等来源生成演示讲解，不是逐页恢复原稿。
- 当前变化：Google 官方 2026 年 3 月公告已支持 PPTX 和 PDF 导出；当前帮助使用 Gemini Notebook 名称。应记录名称变化，避免把旧教程当当前能力。
- 可编辑性：官方确认的是导出格式与自然语言 Revise 后重新生成，不等于 PowerPoint 内的文字、形状、表格可单独编辑。本轮不采用第三方“每页图片”反馈作为已证实事实。
- 内容限制：帮助明确说 AI 幻灯片可能存在视觉或事实错误，且当前修订操作不重新参考来源；需特别复核修订后数字与来源一致性。
- 套餐：帮助里的 Ultra 限制针对 co-create 大纲审阅功能，不能误写成所有 Slide Deck 或 PPTX 导出都要求 Ultra。
- 来源：[2026 年 3 月更新](https://workspaceupdates.googleblog.com/2026/03/new-ways-to-customize-and-interact-with-your-content-in-NotebookLM.html)、[当前幻灯片帮助](https://support.google.com/gemininotebook/answer/16757456)。

### 15. Slaide

- 路线：非 AI 的逐页原位重建，将 PDF 中的文字、形状、图片分别转成 PPTX 对象。
- 关键边界：无 OCR，扫描页仍是图片；表格是定位文本框，不是 PowerPoint 表格；图表是形状和图片，不带可编辑数据表；缺失字体可能替换。
- 公开额度：免账户前 3 页、每天最多 5 个 PDF，带品牌；Plus 页面标价 €7.99 每月、最多 12 页无品牌；Pro 最多 150 页。上传最多 30 MB。价格仅为当日官网展示，未付款验证。
- 隐私声明：无账户转换在欧盟服务端运行，读完后删除；异常中断最长 7 小时清理；不用于训练。
- 来源：[产品页及清晰边界](https://www.slaide.de/pdf-to-powerpoint)。

### 16. Reslide

- 路线：面向 PDF 与页面图片的保留布局重建，官方称 GPU pipeline 将页面拆为文本框、矢量形状和独立图片；同时提供网页工作区与 REST API。
- 输入输出：PDF、PNG、JPG、WebP；PPTX 下载，可签名回调。
- 额度与价格：官方展示免费一次性 10 页，1 credit 对应 1 页；Starter 每月 $19、300 页，Pro $49、1,000 页，Ultra $149、4,000 页。网页开关可能影响年付展示，购买需再核对结算周期。失败或取消任务零净计费。
- 未知：中文、数学公式、原生表格及数据图表的真实重建质量未测试。官方“完全一致”属于宣传，不能作为质量结论。
- 来源：[产品及 API 入口](https://reslide.tosea.ai/)。

### 17. EditLM

- 路线：专门将 NotebookLM 或 Gemini Notebook 的 PDF、PNG、JPG 页面解锁为可修改文字的 PowerPoint，强调保留既有视觉风格。
- 输入限制：50 MB、最多 20 页。官网明确文字、数字、标签及常见文字样式和位置可修改；没有足够证据证明复杂图表与表格会成为原生对象。
- 收费：第一张免费；一次购买页数，官网显示 10 页 $5.99、30 页 $14.99、100 页 $39.99，无订阅，未付款验证。
- 隐私：官网称文件对账户私有、七天后删除；隐私页说明收集上传文件、转换偏好、生成文件等信息。
- 来源：[产品](https://editlm.com/)、[隐私政策](https://editlm.com/privacy)。

## 产品研究的判据与未验证项

这批官方材料支持“路线与公开契约”的比较，不能支持转换质量排行榜。所有产品均未做中文稿、扫描件、复杂表格、公式、多栏论文的统一文件测试，未测等待时间、成功率和修复耗时，也未验证付款、退款、账单与实际免费额度。厂商对自己的竞争比较只视为营销，不能用 Presentations.AI 对 iLovePDF 或 Smallpdf 的描述证明后两家具体如何实现。

后续应至少分别准备：文字型幻灯片 PDF、扫描幻灯片、AI 生成图片型幻灯片、多栏论文、含可核对数据的图表和复杂公式。每次导出都检查：文本框数量、整页图片覆盖、原生表格数量、原生图表及其数据、字体替换、遗漏内容、数字单位、视觉相似度、人工修复时间。这是建议的验证方案，本轮未执行。

本报告由 AI 辅助检索及整理；产品功能属于厂商公开声明，推断与未验证项已分别标明。未使用用户私有文件或账户资料。
