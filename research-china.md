# 中国市场 PDF 转 PPT 产品调查

核验日期：2026-10-26。范围：19 个产品入口或功能模式，另列证据不足的线索。采用官方产品页、官方帮助与接口文档；未注册、未购买、未上传样本，以下为公开资料能力核验，不是转换质量实测。网页没有明确发布时间时，仅能说明核验时的页面内容，不能反推功能上线时间。动态价格、入口和权益会变动。

## 核心判断

中国市场至少有三条不同路线：保留原页面的 PDF 转换；读取材料后生成大纲再套模板；视觉生成图片后作为演示作品。一个品牌可能同时提供三条路线，不能只按品牌名判断“可编辑”。

最重要的反证是：讯飞智能 PPT API 文档明确排除扫描 PDF；福昕中国 PDF 转 PPT 会员说明同样排除扫描件；iSlide 导入文档教程明确不解析原文图片、图形、表格与图表。产品拥有 OCR 或编辑器，并不能证明特定 PDF 转 PPT 链路会恢复这些对象。

AiPPT.cn 的传统流程明确提供文字可编辑 PPT，而同一帮助中心的“小方同学 Agent 专区”写明暂不支持 PPT 与 PPTX 下载。这不是可以忽略的文案差异，实际选型必须选择具体模式。博思 AIPPT 真实官方主体由 pptgo.cn 的关于页面核验；搜索出现的 bosippt.com 不作为本报告的官方证据。

## 一、保留内容与版式的转换工具

### 1. WPS Office PDF 转 PPT 与金山 PDF 在线工具

- 路线：格式转换，目标是保留既有文字、图片、排版，不是摘要重写。
- 官方学堂给出 WPS Office 中的“转换→PDF转PPT”步骤；WPS PDF 工具页宣称输出可编辑 PPT 或 PPTX。国内金山在线页明确使用云端服务器处理，并称转换后24小时内删除。
- 会员、地区、平台不同，权益不能互相套用。旧手机教程“5页免费”只能当旧版说明，不能当现行全平台规则。本轮未确认国内当前价格和扫描 PDF 在该入口的 OCR 行为。
- 不宜承诺：原 PDF 图表恢复为原生图表、公式恢复为公式对象、恢复动画与母版。
- 来源：[WPS 官方学堂](https://www.wps.cn/learning/question/detail/id/13691)、[国内金山 PDF 在线转换](https://pdf.wps.cn/pdf2ppt)、[WPS PDF 工具说明](https://pdf.wps.com/zh/pdf-tools/pdf-to-ppt/)。

### 2. 福昕 PDF 编辑器与 PDF365

- 路线：PDF 转为 PowerPoint，保留原有文本、图像、超链接和布局；另有在线 PDF365 入口，不能把不同版本视为完全同一权益。
- 中国会员页主说明：注册用户可转换前5页，会员与会员 Pro 无此页数限制；支持批量、页码范围和输出设置，明确“不支持扫描件”。
- 另一产品介绍页宣称支持本地离线转换，但在线产品页明确云端处理。需按实际购买产品与入口核对；不能把“下载客户端”自动等同于离线处理。
- 未确认：当前具体价格、扫描件先 OCR 再转换的完整中文流程、图表与公式对象级还原。
- 来源：[官方会员说明](https://vip.foxitsoftware.cn/public/privilegeInfo/PDFToPPT.html)、[官方 PDF 转 PPT 产品页](https://www.foxitsoftware.cn/pdf-to-ppt/)、[阅读器转换介绍](https://www.foxitsoftware.cn/pdf-reader/transform-pdf.html)、[PDF365 转换入口](https://www.pdf365.cn/pdf-to-ppt/)。

### 3. 万兴 PDF（PDFelement）

- 路线：传统转换，另提供 PDF 转 PPT SDK。
- 官方指南说明可输出 PPT 与 PPTX，支持批量、指定页码；扫描 PDF 若需编辑须启用 OCR。转换设置指南专门为 PDF 转 PPT 列出 OCR 与语言识别设置。
- 这比只有“OCR功能”图标的证据更强，但仍未实测中文扫描件识别、排版和对象细分。中国版与海外版套餐不能直接互换。
- 未确认：国内当前价格、离线授权条件、原生图表与公式还原。
- 来源：[官方转换指南](https://www.wondershare.net/pdfelement/guide/convert-pdf-to-ppt.html)、[转换设置指南](https://pdf.wondershare.com/guide/pdf-conversion-settings.html)、[国内 SDK](https://pdf.wondershare.cn/sdk/pdf2ppt.html)。

### 4. 迅捷 PDF 转换器

- 路线：版式转换。当前在线主界面提供 PPT 与 PPTX、页码选择、批量与“易于后续编辑 OCR”“尽量保持排版 OCR”等模式。
- 在线非 VIP 上传提示为0.5MB；更大文件需升级或使用客户端。页面称云端处理，24小时后自动删除，支持手动删除。
- 这些是页面配置和供应商说明，不是本次转换的成功记录。页面隐藏的“已转换完成”模板不算实际状态。
- 未确认：付费价、OCR各模式的中文效果、输出图表是否原生。
- 来源：[官方 PDF 转 PPT 页面](https://app.xunjiepdf.com/pdf2ppt/)。

### 5. 轻闪 PDF（LightPDF）

- 路线：提供 PDF 转 PPT 工具、桌面端、云端应用与转换 API。
- 官方网站列有专门转换入口；官方 API 页面明确提供 PDF 与 Word、Excel、PPT 等互转。客户端页面另介绍编辑、OCR等功能。
- 不把客户端存在 OCR 解释成每一种在线 PDF 转 PPT 都能恢复扫描文字。当前网页工具抽取以导航为主，单项可编辑性、免费限额、OCR 是否附加计费证据不完整。
- 未确认：PPTX 内部对象类型、图表与公式还原、纯本地处理范围、当前价格。
- 来源：[官网](https://lightpdf.cn/)、[PDF 转 PPT 入口](https://lightpdf.cn/pdf-to-ppt)、[转换 API](https://lightpdf.cn/convert-api)、[桌面端介绍](https://lightpdf.cn/desktop)。

### 6. 转转大师

- 路线：传统转换。官方工具页列 PDF 输入、PPT 与 PPTX 输出、指定页码和客户端批量转换。
- 主页面说明在线文件在云服务器处理，并称离开网站24小时后删除；客户端宣称批量与不限制文件转换大小。未据此推断客户端纯离线。
- 官网有“精准提取图表公式”“成功率95%”等宣传，缺少公开基准与本次验证，不纳入质量结论。
- 未确认：免费页数与体积、现价、OCR在此流程的适用性、图表公式是否可编辑对象。
- 来源：[官方工具页](https://pdftoword.55.la/pdf-to-ppt/)、[产品与运营说明](https://pdftoword.55.la/help/)。

### 7. 永中云服务文档格式转换

- 路线：开发者服务与文档转换引擎，非只有面向个人的小工具。
- 官方产品页明确列出 PDF 转 PPT，并宣称 PDF 与 Office、图片互转及保留版式。在线体验单文件5MB以内；提供开发文档入口。
- 永中 DCS 官网另有公有云与私有化部署，但需商务确认 PDF 转 PPT 是否在指定交付范围、系统支持与许可证内。
- 未确认：PDF转PPT实际输出扩展名、文本与图形可编辑细分、OCR、此项服务独立价格。不能把“文档预览”套餐价格当转换单价。
- 来源：[官方格式转换产品](https://open.yozocloud.cn/product/convert)、[DCS 官方](https://www.yozodcs.com/)、[云平台价格页](https://open.yozocloud.cn/price)。

### 8. 360 PDF 工具集

- 路线：官方明确把“PDF转PPT”与“AI生成PPT”列为不同工具，前者属于格式互转。
- PDF工具集支持 PDF 与 Word、Excel、PPT 文件互转及批量；AI办公另包含 AI摘要、问答、生成PPT。
- 未确认：转换输出是整页图片还是可编辑对象、扫描件处理、免费限制、价格、客户端是否本地转换。企业版存在不等于私有化部署。
- 来源：[PDF 工具集官网](https://pdf.360.cn/)、[360 AI办公](https://aiwork.360.cn/)、[企业版](https://saas.360.cn/ai_office)。

## 二、理解 PDF 后重做 PPT 的 AI 产品

### 9. WPS AiPPT 与 WPS 灵犀

- 官方 AiPPT 首页明确提供主题生成、文档生成、粘贴文本或大纲，且标明可编辑；WPS AI 产品页也列文档生成PPT。灵犀官方定位为交付可继续编辑的办公文件。
- 路线：内容组织与演示稿生成，不应与WPS PDF格式转换混为一谈。
- 本轮未在无需登录的主要官方说明中核实文档上传支持 PDF 的完整约束，因此不把“文档生成”直接升级为“已证实任意 PDF 输入”。WPS论坛用户帖子中的“误差率”不采用。
- 未确认：PDF扫描件、原文图表与公式保留、现行价格与导出限制。
- 来源：[WPS AiPPT](https://ppt.wps.cn/)、[WPS AI产品功能](https://x.wps.cn/pc)、[WPS 灵犀](https://www.lingxi.cn/)。

### 10. 讯飞智文与智能 PPT API

- 官方开放平台明确支持根据材料生成大纲、根据大纲生成PPT；新版 API 接收 PDF、Word、TXT、Markdown，返回 PPTX 下载链接示例。
- 关键限制：PDF 明确不支持扫描件。新版文档说明 query 最多12000字，非TXT文件10MB；不同 API 版本的8000字等限制不可混用。
- 个人认证和企业认证有试用点数，付费以服务点数与并发套餐计价；官网提供私有化商务咨询。C端智文账号权益不等于 API 点数套餐。
- 未实测：输出内元素细分、中文复杂排版、原表格图表公式保真、私有化完整依赖。
- 来源：[智能PPT新版接口](https://static.xfyun.cn/doc/spark/PPTv2.html)、[旧版接口](https://www.xfyun.cn/doc/spark/PPTGeneration.html)、[官方产品与定价](https://www.xfyun.cn/services/aippt)。

### 11. AiPPT.cn 传统演示生成流程

- 官方插件帮助明确 PDF 文档上传，PDF最大30MB；Word与TXT最大10MB，建议字数不超过20万字。流程是提取材料核心信息生成PPT草稿。
- 传统帮助（页面标注2023-12-27）写支持 PPT、图片、PDF导出，PPT支持文字可编辑和二次修改。不是逐页恢复原始 PDF 版面。
- 需要账号；开放平台有上传PDF、生成大纲、编辑器、下载等鉴权节点。
- 未确认：当前各模式收费、OCR、对原图表公式处理。传统帮助较旧，最终导出权益仍应核实。
- 来源：[导入文档生成教程](https://www.aippt.cn/plugin/help/article/24)、[帮助中心](https://www.aippt.cn/help-center/?from=home)、[开放平台UI配置](https://open.aippt.cn/docs/zh/ui/config.html)。

### 12. AiPPT.cn 小方同学 Agent

- 与上一条属于同品牌不同功能模式。帮助中心2026-02-03更新的 Agent 专区说明：可上传 PDF、Word、TXT、Markdown，单文件不超过30MB、每个问题最多5附件。
- 同专区明确作品只支持在线预览和PDF下载，暂不支持 PPT 与 PPTX；修改图片文案依靠重绘。这一模式不能拿来证明能得到可编辑PPTX。
- 生成按模型调用与外部 API 动态扣积分；商业权益、更多模式和现行情况未实测。
- 来源：[官方帮助中心，Agent 专区](https://www.aippt.cn/help-center/?from=home)。

### 13. iSlide AI

- 路线：导入材料→AI梳理大纲→在演示工作流生成。企业私有化页面明确新增PDF、Excel、PPTX等导入格式；插件教程与企业版本应分开核实。
- 最有价值的限制来自官方导入教程：暂不识别并生成文档内图片、图形、表格和图表；建议纯文本。官方说明建议5000字内、20MB以内。
- 提供企业私有化部署，支持企业服务器、本地存储和内网使用；API也有对接方案，但必须确认模型请求是否也留在内网。
- 未确认：PDF扫描件、跨版本导出权益和现价、原始页面对象级还原。
- 来源：[导入教程](https://www.islide.cc/help/article/304)、[字数与大小限制](https://www.islide.cc/help/article/381)、[私有化产品](https://www.islide.cc/enterprise/privatization)。

### 14. 博思 AIPPT（PPTGO）

- 官方主体：深圳市博思云创科技有限公司，官网 pptgo.cn；本轮不采用其它自称官网的域名。
- 路线：TXT、Word、PDF 通过 AI 提炼后生成演示稿；Markdown和思维导图另有直接结构导入。
- 官方帮助将 PDF 导入、可编辑源文件下载、PPT导出列为VIP高阶权益。现行价格页展示月VIP45元、年VIP99元、终身VIP218元，均为页面活动价、结算可能变化；免费体验最多25页，VIP最多60页。
- 有SDK、私有化和企业模板入口。未确认OCR、原PDF图表公式保留及私有化模型依赖。
- 来源：[官方帮助](https://pptgo.cn/support/)、[价格](https://pptgo.cn/price/)、[主体说明](https://pptgo.cn/about-us/)。

### 15. MindShow（明秀）

- 官网首页明确“PDF to PPT”为AI驱动，区别于Word或Markdown强调不改文本的结构导入。
- 官方帮助明确导出 PPTX 可在 PowerPoint 等软件编辑；保存与下载需要登录。另有商用授权限制：导出后外部修改可能影响其所保证的商用权益，非高级会员本地修改后不可商用。
- 不能把“可编辑PPTX”解释为原PDF图表公式自动变成原生对象。未知当前会员价格、PDF体积与OCR限制。
- 来源：[官方首页](https://www.mindshow.ai/)、[PPTX二次修改说明](https://www.mindshow.ai/help/zh/export/can-edit-exported-pptx)、[登录要求](https://mindshow.fun/help/zh/account/features-after-login.html)。

### 16. 百度文库智能 PPT

- 官方首页有智能PPT、文档上传与PDF支持，但首页通用“最多100文件、每个200MB”不能视为智能PPT专用配额。
- 百度网盘团队发布的 Dify 插件说明明确：材料或主题→大纲→幻灯片内容→导出PPTX。这能证明对应开放服务的输出链路，不能代替个人文库网页全部权益的证据。
- 未确认：当前个人端PDF到PPTX完整链路约束、OCR、免费次数、图表与公式保留、导出对象粒度。高校版说明不直接套用个人版。
- 来源：[百度文库官网](https://wenku.baidu.com/?lang=1)、[百度团队发布的Dify插件说明](https://marketplace.dify.ai/plugin/baidu-netdisk/aippt)。

### 17. 百度网盘企业版 AI PPT

- 官方企业知识文章说明：在文件列表选择1—5个PPT、Word或PDF，通过AI生成PPT入口将文件带入超级助理，作为附件或上下文生成。
- 路线：基于网盘资料重做演示内容；并非 PDF逐页格式还原。
- 需企业版账号与相关功能。未在该文章核实导出扩展名、原生元素细分、OCR、文件大小、独立收费与私有部署；“企业私域知识库”不等于本地私有化。
- 来源：[官方操作说明](https://eyun.baidu.com/knowledge/%E7%99%BE%E5%BA%A6%E7%BD%91%E7%9B%98%E4%BC%81%E4%B8%9A%E7%89%88AI%E5%8A%9E%E5%85%AC%E5%8A%9F%E8%83%BD%E6%80%8E%E4%B9%88%E5%BC%80%E5%90%AF.html)。

### 18. 夸克 PPT

- 官方手册给出完整路线：上传 PDF、Word、图片等材料→AI整理内容与大纲→生成→在线编辑→导出 PPTX、PDF或长图。
- 手册明确画布中的文字、图片、图形等可编辑，PPTX用于在PowerPoint或WPS继续编辑。属于AI重做演示稿，不承诺原PDF逐页恢复。
- 支持多文件和多种格式，浏览器内完成；“39种格式”是厂商描述，不代表39种都已本轮测试。
- 未确认：扫描PDF链路、OCR字准确率、原始图表公式重建、免费额度与当前价格。
- 来源：[夸克官方PPT手册](https://www.quark.cn/documents/help/ai-ppt)。

### 19. SANDUN

- 官方文档明确PDF参考资料输入，支持多个PDF、单个不超过50MB；后续经过大纲、内容策划、初稿与设计稿。可选择仅使用材料或联网补充，图片可选仅使用PDF内图片。
- 生成有SVG与图片设计两种模式；快速开始页宣称SVG完全可编辑，并提供PPTX、PDF、PNG导出。需进一步验证可编辑性是否同样覆盖导出的PowerPoint对象。
- 需注册登录；未核实现价、OCR、私有化部署及图表公式完整恢复。页面中的生成时间是供应商说明，不是本轮测速。
- 来源：[上传PDF说明](https://sandun.cc/docs/create/reference-pdf)、[快速开始](https://sandun.cc/docs/quickstart)。

## 三、检索过但不应列为“已完整核验”的产品线索

- **闪击PPT**：官方演示编辑器可检索到文本生成与PDF导出，但未找到足以确认PDF输入的官方说明，因此不列为已经证实的PDF转PPT工具。[官方演示编辑器](https://ppt.sankki.com/editor?mode=demo)。
- **Prezto**：搜索索引中的产品页明确是每页高清图片放入PPTX、原文字不可编辑，并声称浏览器本地处理。这是有用的图片封装案例，但直接访问超时，本轮证据停留在该站官方页面的搜索索引，降为待复核线索。[产品页](https://prezto.cn/tools/pdf-to-ppt)。
- **灵页 LingSlide**：检索到图片型PDF转可编辑PPT的产品文章，但直接抓取失败，不能据此认定其实际输出质量、价格与完整服务链路。[待复核产品页](https://lingslide.com/zh/pdf-to-editable-ppt/)。
- **天工、清言、通义或千问相关**：检索中出现大量仿官方域名、AI导航和营销教程，未完成可靠官方PDF输入→PPTX输出链路核验，不据此收录为已证实转换工具。不能因为聊天模型能读PDF、能写大纲，就认定某个消费端能交付可编辑PPTX。
- **bosippt.com、带qianwen字样的第三方站点、wenku.ai等**：不能仅因标题称“官网”就视为博思、阿里或百度的官方产品。每个站点都应单独核验运营主体；本轮未纳入官方同品牌证据。

## 四、给后续样本测试的优先事项

1. 对同一文件分别测试“原版还原”“AI重做”和“图片封装”，报告结果必须分组。
2. 传统路线优先试：WPS、福昕、万兴、迅捷；中文AI重做路线优先试：夸克、博思、AiPPT传统流程、iSlide、讯飞、MindShow。此为覆盖路线的测试选择，不是质量排名。
3. 准备中文原生PDF、中文扫描件、表格财报、复杂公式、混合图文与多栏论文；AI重做另测事实、数字、引用与原文覆盖。
4. 解压PPTX检查文字框、图片、表格、图表、公式等类型，实际在PowerPoint或WPS修改，不能只看扩展名或网页可编辑。
5. 付费前确认“允许生成”与“允许下载可编辑PPTX”是否为两个权益；API与消费者会员、桌面与云端也分别核对。

## 证据边界与研究披露

本报告使用AI辅助检索与归纳，来源均给出直接链接；没有上传用户文档、没有实测转换结果。未标发布日期的帮助页只能作为核验时公开说明；无法访问或缺乏关键链路证据的产品留在候选清单。宣传中的准确率、处理量、用户数、视觉质量、完全保真等表述没有当成已证事实。没有发现公开、可复现、统一中文测试集覆盖以上所有产品，因此不能据此给出客观效果总排名。
