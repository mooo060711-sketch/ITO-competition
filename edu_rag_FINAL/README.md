# Edu-RAG 多模态 AI 互动式教学智能体 - 模块一：本地知识库 RAG

## 项目概述

本仓库实现 **“多模态 AI 互动式教学智能体”** 中的 **模块一：本地知识库 RAG**，并提供 **可直接给队友集成的接口化服务层**。

本版本已做稳定性收敛：
- **Milvus Standalone（Docker）+ HNSW**（满足"必须用 HNSW"的要求）
- 检索链路：**BM25 + BGE-M3（Dense+Sparse）Hybrid + RRF 融合 + 邻近块扩展 + 多样性约束 + Cross-Encoder Rerank**
- 生成链路：**Qwen API（OpenAI-compatible）**，避免 CPU 本地推理慢
- UI：Gradio（已对 `trace/evidence` 等字段做 **强 JSON 化**，避免 `strip()`/序列化报错）

## 1. 架构总览

### 1.1 核心逻辑图

```
knowledge_base/  uploads/<session_id>/
        │
        ▼
  parsers（多模态解析/清洗/切片）
        │
        ▼
 embedder（BGE-M3：dense + sparse）
        │
        ▼
 vector_store（Milvus Standalone: HNSW + SPARSE_INVERTED_INDEX）
        │
        ▼
 retriever（BM25 + dense + sparse；RRF/加权融合；邻近块扩展；多样性约束）
        │
        ▼
 reranker（bge-reranker-large）
        │
        ▼
 generator（Qwen API）
        │
        ▼
 Answer + Evidence + Trace
```

### 1.2 目录结构

```
edu_rag_final/
├── src/
│   └── rag/
│       ├── cli.py              # 命令行入口（ingest/query/list/reset）
│       ├── rag_engine.py       # RAG 核心编排（检索/重排/生成/trace）
│       ├── service.py          # ✅ 给 UI/队友用的稳定接口层（强兼容/强序列化）
│       ├── ui_gradio.py        # ✅ Gradio UI（与 service.py 完全匹配）
│       ├── vector_store/
│       │   ├── milvus_store.py # Milvus 连接/建表/索引/检索（HNSW + sparse）
│       │   └── doc_store.py    # 本地文档库（text+metadata）
│       ├── embedder/           # BGE-M3 embedding
│       ├── retriever/          # hybrid 检索 + 融合 + 邻近块扩展
│       ├── reranker/           # Cross-encoder rerank
│       ├── generator/          # Qwen（OpenAI-compatible）
│       ├── parsers/            # 多模态解析入口
│       └── tools/              # OCR/ASR/VLM/Media 工具
├── knowledge_base/             # 固定知识库（教材/讲义/...）
├── uploads/                    # 教师上传资料（按 session_id 分目录）
├── rag_store/                  # BM25/缓存/证据渲染输出 + docker volumes
├── models/                     # ✅ 需要本地下载的模型（BGE-M3 + reranker）
├── config.yaml                 # ✅ 最终配置
├── requirements.txt
├── environment_wsl_cpu.yml
└── docker-compose.yml          # ✅ Milvus Standalone
```

## 2. 支持入库的资料类型

你可以把下列类型文件放入：

- 文档：`.docx`（推荐）、`.doc`（建议先转成 docx）
- 幻灯片：`.pptx`（推荐）、`.ppt`（建议先转成 pptx）
- PDF：文本版 PDF、扫描版 PDF（扫描版会触发 OCR）
- 图片：`.png/.jpg/.jpeg/.webp`
- 视频：`.mp4/.mov/.mkv`（会抽音频做 ASR + 抽帧做 VLM 描述）
- 音频：`.wav/.mp3/.m4a`
- 表格：`.xlsx`（openpyxl）；（可扩展 csv）
- 纯文本：`.txt`
- 网页：`.html/.htm`（BeautifulSoup 提取正文）

> 说明：解析策略与工具均可在 `config.yaml -> parsing:` 中调整。

## 3. 多模态解析与"可检索证据"统一

所有文件最终都会被统一成可检索证据块：

- `text`：用于 embedding & BM25 的文本
- `meta`：来源、页码、时间戳、帧号等元数据（用于引用、回溯）
- `asset pointers`（可选）：如 PDF 页截图、视频关键帧路径，供模块四 PPT 直接取图

### 3.1 PDF
1) `pdfplumber.extract_tables()`：表格 → 强制重建为 Markdown 表格文本
2) `pdfplumber.extract_text()`：正文抽取
3) 清洗：正则去页码/页眉页脚噪声；并做"重复页眉页脚行"移除
4) 熔断 OCR：若某页抽取字符数 `< ocr_threshold_chars`（默认 50），判定扫描件 → OCR

### 3.2 图片
1) OCR（tesseract）提取可见文字
2) 智能分流：若文字稀疏/疑似图表（Hough lines） → 走 VLM（Qwen-VL）生成"可检索描述"
3) 输出文本 = OCR 文本 + VLM 描述（按配置决定）

### 3.3 视频
1) `ffmpeg` 提取音轨 → `faster-whisper` ASR → 解说词/逐字稿
2) `OpenCV/ffmpeg` 每 `frame_interval_sec` 秒抽帧
3) 关键帧走 VLM（Qwen-VL）得到画面描述（可选 OCR）
4) 合并：`ASR 文本 + 关键帧描述` → 作为"视频证据"入库

### 3.4 音频
- 直接 `faster-whisper` 转写，作为可检索证据文本

### 3.5 Word / PPT
- Word：`python-docx` 提取段落/标题/表格
- PPT：`python-pptx` 提取每页标题/要点/备注

### 3.6 Excel
- `openpyxl` 抽取前 `max_rows * max_cols`，转成"带表头/行列结构"的文本块

### 3.7 HTML
- `BeautifulSoup` 去脚本样式，抽正文，保留标题/段落结构

## 4. 检索质量优化

### 4.1 真 Hybrid（Dense + Sparse）
- BGE-M3 同时产出：
  - Dense embedding：语义召回
  - Sparse embedding：关键词/专有名词召回

### 4.2 多路召回 + 融合
- BM25：召回专有名词、教材术语
- Dense：语义相似
- Sparse：关键词权重

融合策略：
- 默认 **RRF**（Reciprocal Rank Fusion），稳定且不敏感
- 可在 `config.yaml -> retrieval.fusion` 切换为 `weighted_sum`

### 4.3 邻近块扩展（neighbor expansion）
- 命中 chunk 后补齐 `i-1`/`i+1`，避免"只命中半段定义"导致回答缺上下文

### 4.4 多样性约束（per-doc cap）
- 最终证据中每个文档最多保留 `final_max_per_doc` 个 chunk
- 避免同一 PDF 某一页霸屏

### 4.5 Rerank（Cross-Encoder）
- `bge-reranker-large` 对候选 Top-N（默认 50）重排
- 提升最终证据精度

## 5. 与其它模块无缝结合（详细：5种整合方式）

### 5.1 接口化整合
队友直接 import：

```python
from src.rag.service import RAGService
svc = RAGService("config.yaml")
res = svc.query(question="解释中心法则", indexes=["kb"], top_k=5)
print(res["answer"])
print(res["evidence_raw"])  # list[dict]
```

### 5.2 数据流整合（模块二 → 模块一）
模块二（多模态交互输入）解析后得到结构化证据 items：

```json
[
  {
    "text": "本节课重点：中心法则...",
    "meta": {"source": "老师上传-教案.docx", "page": 3, "tag": "outline"}
  }
]
```

调用：

```python
svc.ingest_items(index="ref:demo01", session_id="demo01", items=items, reset=False)
```

### 5.3 事件驱动整合（模块五迭代优化）
- 前端/后端产生事件：`UploadFinished(session_id)` → 触发 `ingest_ref(session_id)`
- `BlueprintUpdated(json)` → 触发 `query()` 补证据 / 生成讲解材料

### 5.4 层内嵌入整合（模块三蓝图生成）
模块三输出 Blueprint JSON 后：
- 用每个知识点标题/关键问句作为 query
- 将证据写回 Blueprint 的 `references[]` 字段

### 5.5 生态级整合（模块四生成引擎）
模块四需要"可实证的配图"时：
- 直接从 evidence 的 `meta` 中获取：
  - PDF 页截图路径
  - 视频关键帧路径
- 插入 PPT 时附带引用（`[1]`）实现可追溯

## 6. 环境与运行（WSL2 + E盘 + Docker + Conda）

### 6.1 安装/启动 WSL（Windows PowerShell 管理员）

```powershell
wsl --install -d Ubuntu-22.04
wsl -d Ubuntu-22.04
```

### 6.2（可选）把 WSL 迁移到 E 盘（解决 C 盘爆满）

```powershell
wsl --shutdown
wsl --export Ubuntu-22.04 E:\WSL\Ubuntu-22.04\ubuntu2204.tar
wsl --unregister Ubuntu-22.04
wsl --import Ubuntu-22.04 E:\WSL\Ubuntu-22.04 E:\WSL\Ubuntu-22.04\ubuntu2204.tar --version 2
wsl -d Ubuntu-22.04
```

设置默认用户（在 WSL 内）：

```bash
sudo sh -c 'cat > /etc/wsl.conf <<EOF
[user]
default=ddzh
EOF'
exit
```

回到 PowerShell：

```powershell
wsl --shutdown
wsl -d Ubuntu-22.04
```

> 迁移后 Linux 文件实际存放在：`E:\WSL\Ubuntu-22.04\ext4.vhdx`。

### 6.3 系统依赖（WSL 内）

```bash
sudo apt-get update && sudo apt-get upgrade -y
sudo apt-get install -y unzip git curl build-essential
sudo apt-get install -y ffmpeg
sudo apt-get install -y tesseract-ocr
sudo apt-get install -y poppler-utils
sudo apt-get install -y libreoffice
```

### 6.4 安装 Docker（WSL 内）

```bash
sudo apt-get install -y ca-certificates curl gnupg lsb-release
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update -y
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo service docker start
sudo usermod -aG docker $USER
```

重开终端让 docker 组生效，然后验证：

```bash
docker version
docker compose version
```

**如果拉镜像超时（国内常见）**，配置 Docker mirror：

```bash
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json >/dev/null <<'EOF'
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://mirror.baidubce.com",
    "https://hub-mirror.c.163.com"
  ],
  "dns": ["223.5.5.5", "8.8.8.8"]
}
EOF
sudo systemctl restart docker
```

### 6.5 启动 Milvus Standalone（HNSW 必需）

在项目根目录：

```bash
cd ~/projects/edu_rag_final
docker compose up -d
docker ps
```

验证端口：

```bash
ss -lntp | grep 19530
```

### 6.6 安装 Miniconda（WSL 内）

```bash
cd ~
curl -fsSL https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -o miniconda.sh
bash miniconda.sh -b -p "$HOME/miniconda3"
echo 'export PATH="$HOME/miniconda3/bin:$PATH"' >> ~/.bashrc
source ~/.bashrc
conda config --set auto_activate_base false
```

### 6.7 创建 Conda 环境并安装依赖

```bash
cd ~/projects/edu_rag_final
conda env create -f environment_wsl_cpu.yml
conda activate edu_rag_cpu
```

## 7. 需要下载到本地的模型

本项目（当前实现）Embedding/Rerank 以 **本地路径**加载：

- `models/bge-m3/`
- `models/bge-reranker-large/`

### 7.1 使用 HuggingFace 镜像加速

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

### 7.2 下载模型（step-by-step）

```bash
pip install -U huggingface_hub

python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download('BAAI/bge-m3', local_dir='models/bge-m3', local_dir_use_symlinks=False)
snapshot_download('BAAI/bge-reranker-large', local_dir='models/bge-reranker-large', local_dir_use_symlinks=False)
print('done')
PY

ls models/bge-m3 | head
ls models/bge-reranker-large | head
```

> 注意：如果你曾经安装过 `milvus-lite` 并遇到 `pkg_resources` 相关问题：
> - 本项目默认 **不再依赖 milvus-lite**（requirements 已注释），避免这一坑。

## 8. 调用 API 的模型（Qwen）与配置（必须）

本项目 Generator/VLM 使用 **OpenAI-compatible API**。

### 8.1 DashScope（通义千问）兼容模式示例

```bash
export OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export OPENAI_API_KEY="你的DashScopeKey"
```

### 8.2 使用的 API 模型
- 文本生成：`qwen-plus-latest`
- 视觉理解（可选，图片/视频关键帧）：`qwen2.5-vl-7b-instruct`

（可在 `config.yaml -> generator.api_model / vlm.api_model` 修改。）

## 9. 如何上传新知识库资料并入库（你最常用）

### 9.1 固定知识库（kb）
把文件复制到：

```bash
~/projects/edu_rag_final/knowledge_base/
```

然后重建 kb（推荐 reset，最干净）：

```bash
conda activate edu_rag_cpu
python -m src.rag.cli ingest \
  --dir knowledge_base \
  --index kb \
  --source-type knowledge_base \
  --session-id kb \
  --reset
```

### 9.2 教师上传资料（ref:<session_id>）

```bash
mkdir -p uploads/demo01
cp /mnt/c/Users/<WINUSER>/Desktop/xxx.pdf uploads/demo01/

python -m src.rag.cli ingest \
  --dir uploads/demo01 \
  --index ref:demo01 \
  --source-type uploads \
  --session-id demo01 \
  --reset
```

查询时选择两个索引：
- `kb`
- `ref:demo01`

## 10. 运行方式（CLI / UI / 给队友接口）

### 10.1 CLI

```bash
conda activate edu_rag_cpu
python -m src.rag.cli list

python -m src.rag.cli query \
  --question "解释中心法则" \
  --index kb \
  --top-k 5 \
  --with-trace
```

### 10.2 Gradio UI

```bash
conda activate edu_rag_cpu
python -m src.rag.ui_gradio
```

浏览器打开：`http://127.0.0.1:7860`

### 10.3 方便队友集成

```python
from src.rag.service import RAGService
svc = RAGService('config.yaml')

# 查询
res = svc.query(question='解释中心法则', indexes=['kb'], top_k=5)
print(res['answer'])
print(res['evidence_raw'])

# 入库（ref）
# svc.ingest_ref('demo01', 'uploads/demo01', reset=False)
```

## 11. 完整运行指令（一键复制）

```bash
# 1. 解压项目
mkdir -p ~/projects
cp "/mnt/e/pythonprojects/edu_rag_final_FINAL.zip" ~/projects/
cd ~/projects
unzip -o edu_rag_final_FINAL.zip

# 2. 查看实际目录名
ls -lah ~/projects | grep edu_rag

# 3. 进入文件夹
cd ~/projects/edu_rag_FINAL
ls

# 4. 启动Milvus（使用 HNSW）
cd ~/projects/edu_rag_FINAL
docker compose up -d
docker ps

# 5. 激活conda环境
source ~/miniconda3/etc/profile.d/conda.sh
conda activate edu_rag_cpu || conda env create -f environment_wsl_cpu.yml -n edu_rag_cpu
conda activate edu_rag_cpu

conda install -y "setuptools<81"

# 6. 下载模型
export HF_ENDPOINT=https://hf-mirror.com
pip install -U huggingface_hub

python - <<'PY'
from huggingface_hub import snapshot_download
snapshot_download("BAAI/bge-m3", local_dir="models/bge-m3", local_dir_use_symlinks=False)
snapshot_download("BAAI/bge-reranker-large", local_dir="models/bge-reranker-large", local_dir_use_symlinks=False)
print("models downloaded")
PY

cd ~/projects/edu_rag_FINAL

python - <<'PY'
from huggingface_hub import snapshot_download

ignore = ["**/.DS_Store", "**/.DS_Store*", "**/Thumbs.db", "**/.AppleDouble/**"]

# 补全/续传 bge-m3
snapshot_download(
    "BAAI/bge-m3",
    local_dir="models/bge-m3",
    ignore_patterns=ignore,
)

# 下载 reranker
snapshot_download(
    "BAAI/bge-reranker-large",
    local_dir="models/bge-reranker-large",
    ignore_patterns=ignore,
)

print("done")
PY

# 7. 设置API环境变量
export OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export OPENAI_API_KEY="sk-c82d3e04c90f43a5bbc8b6c40d3a98e4"

# 8. 入库
python -m src.rag.cli ingest \
  --dir knowledge_base \
  --index kb \
  --source-type knowledge_base \
  --session-id kb \
  --reset

# 9. 询问
python -m src.rag.cli query \
  --question "什么是转录？" \
  --index kb \
  --top-k 5 \
  --with-trace

# 10. 启动UI
python -m src.rag.ui_gradio
# 浏览器打开：http://127.0.0.1:7860
```

## 12. 常见故障排查

### 12.1 UI 报 Milvus 连接失败
- 确认容器在跑：`docker ps`
- 确认端口：`ss -lntp | grep 19530`

### 12.2 Docker 拉镜像超时
- 配置 Docker mirror（见 6.4）

### 12.3 模型下载慢
- 设置 `HF_ENDPOINT=https://hf-mirror.com`


## 13. 项目特点总结

1. **稳定性优先**：所有接口强序列化，避免 JSON 解析错误
2. **检索质量**：Hybrid + RRF + 邻近扩展 + 多样性约束 + Rerank
3. **多模态支持**：PDF/图片/视频/音频/Word/PPT/Excel/HTML 全支持
4. **易集成**：提供 `RAGService` 类，队友可直接调用
5. **可追溯**：证据块带完整元数据，支持引用和回溯
6. **配置灵活**：所有参数可在 `config.yaml` 中调整
7. **部署简单**：Docker + Conda，环境隔离清晰
