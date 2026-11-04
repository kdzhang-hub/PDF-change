# PDF 转 PPT 的技术路线与开源生态核验

调研日期：2026-10-26。范围：20 个官方项目、组件与工作流。方法：官方仓库 README、许可证原文、官方文档、作者论文；采用中英文检索并核查反证。所有功能均为公开资料核验，**未安装、未上传样本、未运行转换，不能当作效果实测或商用许可意见**。本报告使用 AI 辅助检索和归纳。代码版本、模型许可与运行要求会变化，落地时需固定版本再查。

## 一、先把“转成 PPT”拆成五条不同路线

### 1. 整页图像封装

PDF 每页渲染成 PNG 或 JPEG，放在一页 PPT 里。保留页序和视觉，但文字、表格、图表成为图片内容。真正的直接证据是 kevinmcguinness/pdf2pptx：作者明确写“每页 PNG 再生成 PowerPoint”，并说明用途是展示 Beamer 幻灯片和手写批注。它输出 PPTX，却没有恢复文字或图表的编辑能力。[官方仓库](https://github.com/kevinmcguinness/pdf2pptx)、[PyPI](https://pypi.org/project/pdf2pptx/)

**推断：**这条路线适合“能够放映、加批注”，也适合作为转换失败的显式兜底；不应以“全可编辑”销售。SVG 整页封装同样只证明矢量清晰度，不能自动证明段落、单元格与图表数据恢复。

### 2. 原生 PDF 对象提取与坐标映射

从数字 PDF 读取文字、字体、颜色、位置、图像与绘图路径，把它们映射成 PPT 文本框、图片、线条、形状。PyMuPDF 官方提供文字字级与 span 级坐标，以及绘图指令提取。[文字结构文档](https://pymupdf.readthedocs.io/en/latest/textpage.html)、[绘图接口](https://pymupdf.readthedocs.io/en/latest/page.html)

**推断：**这条路线对本来由 PPT 导出的、文字层完好的横版 PDF 较有希望。但字形路径不等于文本；很多小文本块不等于原有段落；几十个矩形柱子不等于可修改数据的 Office 图表。需要重建字体替换、文本组合、图层顺序与换行规则。

### 3. OCR、擦字与背景复原，再覆盖可编辑文字

先渲染页面并检测文字，OCR 获得文字和坐标，再擦掉背景中的旧文字、修补纹理，最后在原位置加入可编辑文本框。SeanAtsatt/pdf2ppt 与 Ansenchen123/PDF2PPt 都有这类公开实现；前者包含 OCR、背景清理与文字格式，后者明示 Gemini OCR、OpenCV 修复与 python-pptx。[SeanAtsatt](https://github.com/SeanAtsatt/pdf2ppt)、[Ansenchen123](https://github.com/Ansenchen123/PDF2PPt)

**推断：**它解决“原来只是扫描图，但我想改几个字”。难点是文字擦除痕迹、文字压住照片、OCR 错字、中文字体估计、公式与竖排文字。导出后常见状态是“文字可编辑，其他内容仍是背景”。

### 4. 内容理解与重新编排

PDF 解析成 Markdown、JSON 或文档结构，模型提炼大纲，然后模板或代码生成新的演示稿。Presenton、PPTAgent、PPT Master 属于这一大类，虽然生成方式和模板能力各异。[Presenton](https://github.com/presenton/presenton)、[PPTAgent](https://github.com/icip-cas/PPTAgent)、[PPT Master](https://github.com/hugohe3/ppt-master)

**推断：**这条路线适合“几十页报告变十页汇报”，不是“把原来二十页 PPT 的 PDF 原样恢复”。论文解析准确率、生成稿美观程度和原稿还原度是三个指标。

### 5. 混合路线与渲染反馈

按页、按区域决定：数字文字直接提取，扫描文字 OCR，简单表格和形状原生化，复杂插画保留图片，最后渲染 PPT 与原 PDF 对照，发现错位后修正。poirotw66/pdf2ppt 的公开文档就是一个具体实例：具有 SlideIR、预览修订、可选 Gemini 版式规划、LibreOffice 渲染对照与降级机制。[项目 README](https://github.com/poirotw66/pdf2ppt)、[矢量与表格原生化说明](https://raw.githubusercontent.com/poirotw66/pdf2ppt/main/docs/vector-nativization.md)

**推断：**若开发保真转换产品，这比“一种模型包打天下”更贴近实际。代价是工程复杂，必须向用户展示每页实际恢复到了什么层级。

## 二、20 个项目逐项核验

以下将组件和成品分开，避免把“能读取 PDF”误当“能输出 PPT”。

### A. PDF 底层解析与渲染组件

**1. PyMuPDF。**定位是 PDF 提取、渲染与编辑组件，可取文本位置、字体、图像、绘图路径；不是现成 PDF 转 PPT 引擎。无需为普通数字 PDF 提取配置 GPU；OCR 有外部引擎。许可证为 AGPL 与商业双轨，闭源网络产品不能只看“pip 免费”。[文档](https://pymupdf.readthedocs.io/en/latest/about.html)、[官方许可说明](https://pymupdf.io/licensing)

**2. pypdfium2。**PDFium 的 Python 绑定，适合 PDF 渲染与提取底座，不生成 PPTX，也不直接提供整套语义还原。自身许可为 Apache-2.0 与 BSD-3-Clause，PDFium 及其捆绑依赖还要分开保留许可。更适合将许可边界作为选型条件时认真评估。[官方文档与许可](https://pypdfium2-team.github.io/pypdfium2/readme.html)

**3. pdf2image。**封装 Poppler 的 pdftoppm、pdftocairo，将 PDF 变成图像；它不是 OCR，也不是可编辑 PPT 转换器。Windows 需要额外准备 Poppler，不能只安装 Python 包就假定环境齐备。封装层与底层二进制的许可应分别审查。[官方说明](https://pdf2image.readthedocs.io/en/latest/index.html)、[安装要求](https://pdf2image.readthedocs.io/en/latest/installation.html)

**4. pypdf。**纯 Python 的 PDF 操作与文本提取工具，BSD-3-Clause。它本身不做 OCR，也不能从扫描图片读出文字。官方特别解释 PDF 视觉定位与内容结构之间的缺口。适合拆分、元数据与轻量提取，不应作为完整视觉还原引擎。[官方文本提取说明](https://github.com/py-pdf/pypdf/blob/main/docs/user/extract-text.md)、[许可](https://github.com/py-pdf/pypdf/blob/main/pyproject.toml)

### B. PPTX 生成组件

**5. python-pptx。**创建、读取与更新 PPTX 的 Python 库，MIT，官方说明不需要安装 PowerPoint。支持文本、表格、形状与常见图表；不负责从 PDF 判断什么是标题、流程图或图表数据。AI 写代码调用它属于生成路线，不是这个库自动识别 PDF。[官方仓库](https://github.com/scanny/python-pptx)、[文档](https://python-pptx.readthedocs.io/en/stable/index.html)

**6. PptxGenJS。**JavaScript 生成 PPTX，MIT，可创建文本、表格、形状、图片、图表与母版，支持亚洲字体。适合作为 Node 或浏览器产品的导出层。能生成原生图表，仅证明你给它数据后能做图；不证明它能从任意 PDF 自动找回图表数据。[官方仓库](https://github.com/gitbrent/PptxGenJS)

### C. OCR 与文档理解组件

**7. MinerU。**文档解析平台，输出包括 Markdown、HTML、LaTeX、DOCX、JSON 类结构；当前官方列出的渲染目标未包含 PPTX。支持本地与配置后的远端解析，硬件要求按模型引擎和解析层级变化，不是所有模式都必需独显。**当前仓库许可已是 Apache 2.0 加附加条款，不能沿用旧版本 AGPL 印象。**附加条款包含达到规模门槛后的商业授权及第三方在线服务显著标识义务。[官方仓库](https://github.com/opendatalab/MinerU)、[许可原文](https://github.com/opendatalab/MinerU/blob/master/LICENSE.md)

**8. Docling。**将 PDF、Office 与其他文档变成统一结构，含 OCR、表格、阅读顺序和公式；是文档理解底层，不是 PDF 转 PPT 成品。代码 MIT，模型各自另查许可；官方允许先下载模型后离线转换。本地运行不代表所有自选扩展都不出网。[官方仓库](https://github.com/docling-project/docling)、[官方网站](https://docling.ai/)

**9. PaddleOCR、PP-Structure 与 PaddleOCR-VL。**同一生态中的 OCR、结构化解析及视觉语言解析路线，项目 Apache 2.0。PP-StructureV3 负责版面、表格等结构，PaddleOCR-VL 负责复杂元素解析；官方发布页显示该生态仍在更新，因此不要只研究早期 PP-StructureV2 或固定认为 VL 只有最初版本。它们没有因此自动变成 PPTX 导出引擎；CPU、GPU 和特定推理后端需按选定模型核对。[官方仓库](https://github.com/PaddlePaddle/PaddleOCR)、[PP-StructureV3](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/pipeline_usage/PP-StructureV3.en.md)、[发布说明](https://github.com/PaddlePaddle/PaddleOCR/releases)

**10. Marker。**PDF 转 Markdown、JSON 的解析器，可选 LLM 混合模式；不是 PPTX 生成器。**当前代码为 Apache 2.0，模型权重为修改版 Open RAIL-M**，有收入、融资和竞争性使用等限制，不能把 README 的“初创免费”直接扩展成任意商业 SaaS 免费。当前运行后端也区分 CPU、Apple Silicon 与 NVIDIA。[官方仓库](https://github.com/datalab-to/marker)、[模型许可原文](https://github.com/datalab-to/marker/blob/master/MODEL_LICENSE)

**11. Surya。**OCR、版面、阅读顺序、表格识别工具，不直接输出可编辑 PPT。代码 Apache 2.0；模型权重采用修改版 Open RAIL-M，需独立核验，尤其竞争性服务限制。当前官方说明有 vLLM 与 llama.cpp 等不同后端，不能凭旧资料一概说必须 CUDA。[官方仓库](https://github.com/datalab-to/surya)、[模型许可](https://raw.githubusercontent.com/datalab-to/surya/master/MODEL_LICENSE)

**12. GROBID。**面向学术出版物，把论文 PDF 的标题、作者、正文结构、参考文献等转成 TEI XML；Apache 2.0。适合论文汇报的文档结构前处理，不是通用海报或幻灯片的视觉复刻工具，也不输出 PPTX。[官方原理](https://grobid.readthedocs.io/en/latest/Principles/)、[官方仓库](https://github.com/grobidOrg/grobid)

**13. PDF Craft（oomol-lab）。**重点是扫描书籍转 Markdown、EPUB 与翻译工作流，MIT。可选远程 OCR 或本地 NVIDIA GPU OCR。与若干同名 PDF 编辑器不是同一项目；本项目不应被列为已验证的 PDF 转 PPT 成品。[官方仓库](https://github.com/oomol-lab/pdf-craft)

### D. 真正的逐页转换项目

**14. kevinmcguinness/pdf2pptx。**明确是 PDF 每页 PNG 封装成 PPTX，MIT；依赖 PyMuPDF、python-pptx，底层依赖许可不随顶层 MIT 自动变宽松。优点是路径直白；限制是元素不可编辑。它是“文件格式变了不等于结构恢复”的最清晰反例。[官方仓库](https://github.com/kevinmcguinness/pdf2pptx)、[许可证](https://github.com/kevinmcguinness/pdf2pptx/blob/master/LICENSE)

**15. SeanAtsatt/pdf2ppt。**项目标 MIT，公开功能为提取文字位置与格式、OCR、可选背景图及文字清理。作者明确限制：矢量图形不保留、行距不一定精确、项目符号检测基础、OCR 依赖输入质量。适合作为小型实现参考，不能凭 README 认定稳定商用；运行依赖及 PyMuPDF 许可要另算。[官方仓库](https://github.com/SeanAtsatt/pdf2ppt)

**16. poirotw66/pdf2ppt。**项目标 MIT，原生提取优先，扫描页 PaddleOCR，可选布局与 VLM 规划、修复背景、渲染对照；直接依赖 PyMuPDF。官方新增简单形状和表格的原生化：矩形、椭圆、线、部分箭头、带格线及部分推断表格。复杂渐变、软遮罩、密集绘图仍保留栅格；旋转页面与跨渲染器文字度量仍有限制。**“几何柱状图变矩形”不等于“带 Excel 数据的 Office 图表”。**[官方仓库](https://github.com/poirotw66/pdf2ppt)、[细节与限制](https://raw.githubusercontent.com/poirotw66/pdf2ppt/main/docs/vector-nativization.md)、[依赖声明](https://raw.githubusercontent.com/poirotw66/pdf2ppt/main/pyproject.toml)

**17. Ansenchen123/PDF2PPt。**MIT，公开实现为 Gemini OCR、OpenCV 擦字修补和 python-pptx。它是可验证存在的混合转换项目，不是只叫 pdf2ppt 的泛称。需云模型凭据，是否把内容发往外部与配置相关。公开仓库规模很小，不能推出成熟度、质量或成功率。[官方仓库](https://github.com/Ansenchen123/PDF2PPt)

### E. 文档内容生成 PPT 的项目与研究

**18. Presenton。**Apache 2.0，可自部署，支持文档包括 PDF 输入，导出 PPTX、PDF，并明确声称真实可编辑元素。可连接云模型或 Ollama；本地应用配云文本、图像、搜索服务时仍可能出网。它主要回答“从资料生成新演示稿”，而非保证 PDF 原逐页版式的逆变换。[官方仓库](https://github.com/presenton/presenton)、[隐私边界说明](https://presenton.ai/download)

**19. PPTAgent 与 DeepPresenter。**同一官方仓库，MIT，属于从材料生成、编辑、渲染审阅演示稿的代理研究与工作流。PPTAgent 的作者论文采用两阶段、编辑式方法；当前主分支与论文复现版本有明确区分。官方运行要求涉及 agent 宿主、模型、LibreOffice 等，模型调用仍有成本与数据边界。[官方仓库](https://github.com/icip-cas/PPTAgent)、[PPTAgent 论文](https://arxiv.org/abs/2501.03936)、[DeepPresenter 论文](https://arxiv.org/abs/2602.22839)

**20. PPT Master。**MIT，以 agent 工作流从文档或主题生成原生 PPT，公开强调可编辑形状、数据图表、母版、动画等。它主要做重新组织和生成；新生成动画不等于恢复 PDF 原先丢失的动画。官方也明确模型决定效果上限、成稿仍可能要精修；本地流程仍会按所选 AI、搜索、图像和语音服务出网。[官方仓库](https://github.com/hugohe3/ppt-master)

未单独计数：名称含 PPTXGen 的项目没有在本轮检索中定位到一个可以无歧义核验的唯一官方对象，因此不凭名字补入清单。PDF Craft 同名编辑器、分叉和扫描书籍项目也没有混为一个。

## 三、关于可编辑性的六项核验

以下是依据对象模型与已核验实现提出的**建议验收标准，尚未执行**：

1. **页面层：**是否每页只有一个大图片；保留外观不等于元素恢复。
2. **文字层：**能否选中并改字；删除原文本后是否残留背景旧字；中文换字后是否错位。
3. **对象层：**图片、箭头、形状是否可以分别移动；是否只是整页 SVG 或位图。
4. **表格层：**是否真的有单元格、合并单元格和边框；一堆文本框加直线只能称视觉表格。
5. **数据层：**图表能否通过“编辑数据”改数值；条形图变成矩形形状仍未恢复数据语义。
6. **演示层：**母版、备注、动画、过渡是否真实存在，且是新建还是从来源恢复。

可程序化初筛 PPTX 内部 XML：图片、文字 shape、table、chart 与相关工作簿关系分别统计；再在真实 PowerPoint 或 WPS 中执行改字、改数值和重新排版。对象数量只能辅助，不能把更多碎片当更高质量。[PptxGenJS 对象能力](https://github.com/gitbrent/PptxGenJS)、[python-pptx 对象能力](https://python-pptx.readthedocs.io/en/stable/index.html)

## 四、无法普遍逆向恢复的东西

**原始语义并不总在 PDF 中。**普通 PDF 常记录页面绘制结果，而不是完整的标题、段落、表格和编辑逻辑；Tagged PDF 可以补充结构信息，但仍不等于原始 PPT 对象树。扫描 PDF 还可能只有图像。pypdf 官方对缺失语义、绝对位置字符与 OCR 层的解释支持这个边界。[官方解释](https://github.com/py-pdf/pypdf/blob/main/docs/user/extract-text.md)

**推断：**因此不能保证从静态 PDF 找回原 PPT 的原始母版、可调整的 SmartArt、图表来源工作簿、完整公式编辑结构或原动画时序。某些 PDF 可带标签、附件、多媒体或其他扩展，不宜说“PDF 永远没有这些信息”；只能说普通静态导出不保证保留恢复所需信息。

**公式需要另一次结构转换。**OCR 得到 LaTeX，和 PPT 内部能够直接编辑的数学结构不是同一个交付物。把公式放成 SVG 可以清晰显示，但不等于 Office 原生公式。PaddleOCR 和 Docling 的公式识别能力不能直接当作 PPT 公式恢复能力。[PaddleOCR](https://github.com/PaddlePaddle/PaddleOCR)、[Docling](https://github.com/docling-project/docling)

**复杂图片区域通常需要诚实降级。**poirotw66 项目直接列出渐变、软遮罩和密集插画仍保留栅格，以及 PowerPoint 与 LibreOffice 字体度量差异；这些限制不是用一句“AI 已识别”就消失。[限制原文](https://raw.githubusercontent.com/poirotw66/pdf2ppt/main/docs/vector-nativization.md)

## 五、若开发产品，技术上更值得验证什么

以下是本次研究的产品推断，不是已验证市场需求或实现成果。

- 先识别用户到底要“原样恢复”还是“读完重做”，两者应提供不同模式。
- 给每页实际编辑能力标签：图片页、文字可编辑、文字与形状可编辑、原生表格、原生数据图表。按页报告置信度和降级原因。
- 数字 PDF 优先原生提取，避免把本来准确的文字再 OCR 一次；只有必要区域走 OCR、VLM 和背景修复。
- 让用户先预览困难页并改识别结果，再导出整稿；原生对象映射与背景图兜底要显式可选。
- 保留来源页码、原文和数值，AI 重做模式对每个关键结论附来源；否则漂亮不等于忠实。
- 用原生对象统计、渲染对照、语义与数据核验共同评估，不能只用截图相似度，也不能只用文字识别准确率。
- 商业选型要拆成顶层代码、PDF 底层引擎、OCR 模型、修图权重、字体与外部模型服务。顶层 MIT 不会抹掉其他层的许可条件。

## 六、建议的后续实测样本与指标

本轮未跑实测。建议至少包含：原 PPT 导出的中文 PDF、扫描课件、报告纵版 PDF、双栏论文、复杂流程图、数据图表、公式课件、低清晰拍照页、透明叠层和艺术字、混合横竖页面。

建议记录：文本错误率、关键数值正确率、可编辑文字覆盖率、原生表格与图表比例、布局溢出数量、人工修正时间、单页延迟、完整任务费用、失败率、导出后在 PowerPoint 和 WPS 的一致性。分别对“保真模式”和“重做模式”评分；没有统一样本集前不发布“最好产品”名次。

## 七、反证审查结论

- 假设“能下载 PPTX 就能编辑所有内容”：**不成立**。整页 PNG 型 pdf2pptx 为直接反例。
- 假设“识别出图表就能恢复图表原数据”：**没有普遍证据**。形状原生化、图表 OCR 与带数据的 Office chart 是不同能力。
- 假设“解析器支持 PPTX 就表示能把 PDF 导出 PPTX”：**不成立**。很多项目把 PPTX 列作输入格式。
- 假设“GitHub 开源就能无条件用于闭源 SaaS”：**不成立**。PyMuPDF 双许可、Marker 与 Surya 的模型限制、MinerU 当前附加条款都需要逐层判断。
- 假设“用了 AI 就一定比原生解析更保真”：**没有证据**。AI 重做与逐页还原目标不同，本轮没有统一实测。
- 假设“本地自部署就绝不外传”：**不成立**。Presenton 官方明确数据边界取决于配置的云或本地服务。

资料局限：官方文档证明公开宣称与接口存在，不证明真实质量、速度、稳定性与中文边界表现；小仓库缺少独立评测；商业许可解释仅作技术选型线索；未做账户内导出、端到端样本测试或源码全面审计。

