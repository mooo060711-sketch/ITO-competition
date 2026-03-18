# ITO-competition
HDU ITO_competition 智绘生物
1. 🧠 核心大脑与中枢调度 (Orchestration)
这部分是系统的指挥中心，负责解析用户意图并调度各个底层工具。

main.py: 应用主入口。负责数据库初始化、静态资源挂载（物理输出路径的绝对映射）、CORS 配置以及所有 API 路由的集中注册。

chat_.py: 核心对话接口（基于 LangGraph）。内置了严格的“系统铁律”（如强制输出 10 项要素核对表、拒绝空回复、探针追踪等），通过 Agent 模式驱动大模型调用修改、生图、召回等工具链。

dispatch.py: 级联调度器。定义了 Level 1 到 Level 5 的核心重构等级。将用户的自然语言意图转化为具体的系统执行路径（如：改大纲必然引发 PPT 和 Word 的级联重构）。

2. 📝 知识生成与精修层 (Generation & Refinement)
负责教学核心内容（大纲、教案）的流式生成与局部调整。

stream_.py: 大纲流式生成引擎。使用 SSE (Server-Sent Events) 技术流式返回内容。内置了 RAG 检索（整合官方课标与用户上传资料），并通过 Prompt 级“紧箍咒”防止大模型被参考资料“劫持”而偏离教学要求。

refine_.py: 局部精修与重构接口。支持对大纲或教案进行微调。亮点机制：内置了“页数熔断拦截”（正则提取目标页数并允许 120% 浮动），防止 AI 拓展过度导致课件失控。

knowledge_.py: RAG 知识库入库接口。处理多模态文件的上传与向量化，并通过字符串追加机制将资料要素强制写入数据库状态机，防止后续生成遗忘。

3. 🎨 视觉与演示引擎 (Visuals & Presentation)
处理从 PPT 渲染到 AI 绘图、再到物理图片安放的完整视觉流。

generate_ppt_.py: PPT 装配中心。调用底层引擎根据大纲和主题渲染 .pptx，并调用 Windows COM 接口 (comtypes) 后台静默生成 PDF，以实现网页端的沉浸式完美预览。

generate_image_.py: AI 绘图接口。根据描述生成图片，并强制将其推入系统的“待处理资产队列”（Target 1）。

replace_media_.py: 视觉资产注入逻辑。实现了类似“消消乐”的接力安放机制。接收前端传来的坐标，批量触发底层引擎重绘 PPT，并重新生成带图片的 PDF 预览。

ppt_theme.py: 模板管理。读取本地 JSON 模板库，并动态修正端口映射，确保前端正确拉取预览图。

4. 🎮 教学拓展与交互层 (Extensions & Interaction)
负责生成附属的教学资产。

lesson_plan_.py: 同步教案生成接口。基于提取的教学意图（受众、重难点等）和生成的 PPT 内容，深度适配并生成 Word 版详案。

game_.py: 互动小游戏批量生成引擎。结合 RAG 检索的知识点，异步并发生成多种类型（Quiz, Matching, Sorting）的 HTML5 互动游戏。

asr_.py: 语音识别入口。集成 faster-whisper，在 CPU 环境下高效处理前端录音的中文转写。

5. 🗄️ 会话控制与资产管理 (Session & Asset Management)
保障用户体验和数据安全的“后悔药”与收尾机制。

rollback_.py: 时光机回滚接口。能够精准还原特定版本的数据库快照（大纲、教案字符串）以及物理文件路径（PPT、Word）和图片排版坐标。

export_.py: 一键打包导出接口。读取会话最新的物理资产路径，在内存中动态构建 ZIP 压缩包，提供无痕下载。

reset_.py: 演示级重置接口。执行物理层（删除文件夹）、向量层（销毁 Milvus 集合）和 SQL 层（暴力清理所有关联表）的 100% 彻底清空。
