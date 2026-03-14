# 🎓 代码融合说明：files → ITO 项目集成指南

## 一、融合后的项目结构

```
edu_rag_FINAL/
├── config.yaml                    # 原有配置（不需要修改）
├── docker-compose.yml             # Milvus Docker
├── requirements.txt               # 依赖（已包含所有需要的库）
├── test_game_demo.py              # 游戏模板测试（不需要API也能跑）
│
├── src/
│   ├── __init__.py
│   └── rag/
│       ├── __init__.py
│       ├── config.py              # [原有] 配置加载
│       ├── service.py             # [原有] RAG 服务层
│       ├── rag_engine.py          # [原有] RAG 引擎
│       ├── ui_gradio.py           # [已替换] ★ 完整集成UI（4个标签页）
│       ├── api_server.py          # [原有] FastAPI
│       ├── cli.py                 # [原有] 命令行
│       ├── schemas.py             # [原有]
│       ├── evidence_renderer.py   # [原有]
│       │
│       ├── embedder/              # [原有] BGE-M3 向量化
│       ├── generator/             # [原有] Qwen LLM 生成器
│       ├── parsers/               # [原有] 多模态解析
│       ├── reranker/              # [原有] 交叉编码重排
│       ├── retriever/             # [原有] BM25+Dense+Sparse 混合检索
│       ├── vector_store/          # [原有] Milvus 向量库
│       ├── tools/                 # [原有] OCR/ASR/VLM 工具
│       ├── utils/                 # [原有] 辅助工具
│       │
│       ├── game/                  # [新增★] 互动小游戏模块
│       │   ├── __init__.py
│       │   ├── __main__.py        # 独立启动入口
│       │   ├── game_engine.py     # 游戏生成引擎
│       │   ├── game_prompts.py    # LLM Prompt 模板
│       │   ├── game_templates.py  # 7种 HTML5 游戏渲染器
│       │   └── ui_game.py         # 游戏独立 Gradio UI
│       │
│       └── dialogue/              # [新增★] 多轮对话+教学意图模块
│           ├── __init__.py
│           ├── prompts.py         # 对话/意图提取 Prompt 模板
│           ├── intent_extractor.py # 教学意图结构化提取
│           ├── dialogue_manager.py # 多轮对话状态机
│           └── reference_handler.py # 参考资料上传解析
│
└── outputs/games/demo/            # [新增] 7个示范HTML5游戏
    ├── demo_quiz_game.html
    ├── demo_matching_game.html
    ├── demo_sorting_game.html
    ├── demo_fillblank_game.html
    ├── demo_truefalse_game.html
    ├── demo_flashcard_game.html
    └── demo_flowfill_game.html
```

## 二、融合做了什么

### 原有文件（ITO项目，未修改）
你的 RAG 核心代码保持不变：embedder、generator、parsers、retriever、reranker、vector_store、tools、utils、service.py、rag_engine.py、config.yaml 等全部原样保留。

### 新增文件（来自 files.zip + 第二批新增）

| 文件 | 来源 | 功能 | A04 对应 |
|------|------|------|----------|
| `src/rag/game/` 整个目录 | files.zip | 7种HTML5互动小游戏生成 | 4c) + 5c) |
| `src/rag/dialogue/` 整个目录 | 本次新增 | 多轮对话+意图提取+资料上传 | 2a-2c) + 3) |
| `outputs/games/demo/` | files.zip | 7个示范游戏（可直接浏览器打开） | 演示用 |
| `test_game_demo.py` | files.zip | 游戏模板独立测试 | 测试用 |

### 替换文件

| 文件 | 变化 | 说明 |
|------|------|------|
| `src/rag/ui_gradio.py` | **完全替换** | 从单页RAG问答 → 4标签页完整UI |

**新UI包含4个标签页：**
1. 💬 教学对话 — 多轮对话需求收集、参考资料上传、意图提取
2. 🔍 知识问答 — 原有RAG问答功能（完全保留）
3. 🎮 互动小游戏 — 7种游戏类型生成
4. 📚 知识库管理 — 入库、索引管理

## 三、A04 赛题要求覆盖情况

| A04 要求 | 覆盖状态 | 对应模块 |
|----------|---------|----------|
| 1) 本地知识库 RAG | ✅ 原有 | rag_engine + retriever + embedder + reranker |
| 2a) 语音/文字输入 | ✅ 新增 | dialogue/ + ui_gradio.py（语音+文字输入） |
| 2b) 智能多轮对话 | ✅ 新增 | dialogue/dialogue_manager.py（状态机+追问） |
| 2c) 参考资料上传 | ✅ 新增 | dialogue/reference_handler.py（PDF/Word/PPT/图片/视频） |
| 3a) 教学意图结构化提取 | ✅ 新增 | dialogue/intent_extractor.py |
| 3b) 参考资料内容解析 | ✅ 新增 | dialogue/reference_handler.py |
| 3c) 意图+资料+知识库融合 | ✅ 新增 | dialogue/intent_extractor.py → generate_instructions() |
| 4a) PPT 生成 | ⏳ 第3批 | 需后续开发 |
| 4b) Word 教案生成 | ⏳ 第4批 | 需后续开发 |
| **4c) 互动小游戏生成** | **✅ 完成** | **game/game_engine.py（7种类型）** |
| 5a) 课件预览 | ✅ 游戏部分 | 游戏HTML预览 + 源码查看 |
| 5b) 迭代修改 | ⏳ 部分 | 对话模块支持迭代 |
| 5c) 导出(pptx/docx/html5) | ✅ 游戏部分 | HTML5导出已完成 |

## 四、运行步骤

### 1. 环境准备

```bash
cd edu_rag_FINAL

# 安装依赖
pip install -r requirements.txt

# 设置 DashScope API
export OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export OPENAI_API_KEY="你的DashScope API Key"
# 注册地址: https://dashscope.console.aliyun.com/
```

### 2. 下载本地模型

```bash
export HF_ENDPOINT=https://hf-mirror.com
pip install huggingface_hub

# Embedding 模型（必须）
huggingface-cli download BAAI/bge-m3 --local-dir models/bge-m3
# Reranker 模型（必须）
huggingface-cli download BAAI/bge-reranker-large --local-dir models/bge-reranker-large
```

### 3. 启动 Milvus（RAG检索需要）

```bash
docker-compose up -d
```

### 4. 入库知识库

```bash
# 将你的高中生物教材资料放入 knowledge_base/ 目录
python -m src.rag.cli ingest --dir knowledge_base --index kb
```

### 5. 启动系统

```bash
# 方式1: 完整UI（推荐，包含所有功能）
python -m src.rag.ui_gradio
# 浏览器打开 http://127.0.0.1:7860

# 方式2: 仅游戏模块（独立运行）
python -m src.rag.game
# 浏览器打开 http://127.0.0.1:7861

# 方式3: 游戏模板测试（不需要API/Milvus）
python test_game_demo.py
# 直接用浏览器打开 outputs/games/demo/ 下的 .html 文件
```

## 五、快速验证

### 不需要任何服务也能测试的功能

1. **打开 `outputs/games/demo/` 下的任意 HTML 文件** — 直接在浏览器中体验7种互动小游戏

2. **运行模板测试**：
```bash
python test_game_demo.py
```
这会生成7个HTML5游戏文件，完全不需要 API 或 Milvus。

### 需要API的功能

设置好 `OPENAI_API_KEY` 后：
- 教学对话（多轮对话、意图提取）
- 互动小游戏生成（LLM生成题目内容）
- 知识问答（RAG检索 + LLM生成回答）

### 需要 Milvus + API 的功能

- RAG 知识库检索
- 基于知识库的游戏生成（`使用RAG知识库` 选项）

## 六、后续开发计划

| 批次 | 模块 | 状态 |
|------|------|------|
| ✅ 第1批 | 互动小游戏生成引擎 | 已完成 |
| ✅ 第2批 | 多轮对话 + 教学意图理解 | 已完成 |
| ⏳ 第3批 | PPT 课件生成引擎 (python-pptx) | 待开发 |
| ⏳ 第4批 | Word 教案生成 (python-docx) | 待开发 |
| ⏳ 第5批 | 迭代优化 + 完善导出 | 待开发 |
