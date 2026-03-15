# 🚀 运行指南

## 前置条件

- Windows 10/11（推荐WSL2）或 Linux/Mac
- Python 3.10+
- Docker Desktop（用于Milvus向量数据库）
- 阿里云DashScope账号（免费注册）

---

## 第一步：用编辑器打开

```bash
cd edu_rag_FINAL
code .
```

---

## 第二步：创建 Python 环境 & 安装 PyTorch

> ⚠️ **这是最关键的一步，之前所有报错的根源都在这里。**

### 2.1 创建 Conda 环境（推荐）

```bash
conda create -n edu_rag python=3.10 -y
conda activate edu_rag
```

如果不用 Conda，也可以用 venv：

```bash
python -m venv venv
# Windows: venv\Scripts\activate
# Linux:   source venv/bin/activate
```

### 2.2 安装 PyTorch

> ⚠️ **必须用 `cu124` 索引**。`cu121` 索引最高只有 torch 2.5.1，而 `transformers>=4.48` 因安全漏洞 CVE-2025-32434 强制要求 torch≥2.6，会直接报 `ValueError` 拒绝加载模型。

**有 NVIDIA GPU（推荐）：**

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu124
```

**无 GPU / 纯 CPU：**

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu
```

**安装后必须验证：**

```bash
python -c "import torch; print(f'torch={torch.__version__}  CUDA={torch.cuda.is_available()}')"
# ✅ 正确输出: torch=2.6.x+cu124  CUDA=True
# ❌ 如果版本 < 2.6 或显示 +cu121，说明装错了，重新来
```

### 2.3 安装项目依赖

```bash
pip install -r requirements.txt
```

**常见子问题：**

| 报错 | 原因 & 修复 |
|------|------------|
| `No module 'rank_bm25'` | `pip install rank-bm25` |
| `pdf2image` 缺失 | `pip install pdf2image` |
| Pillow 版本冲突 | requirements.txt 已锁定 `<13.0`，正常装即可 |

---

## 第三步：注册 DashScope & 设置 API Key

1. 打开 https://dashscope.console.aliyun.com/ → 注册/登录 → 获取 API Key
2. 设置环境变量：

```bash
# Windows PowerShell:
$env:OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:OPENAI_API_KEY = "sk-你的Key"

# Linux/Mac:
export OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export OPENAI_API_KEY="sk-你的Key"
```

> 💡 **建议**：写到系统环境变量或 `.env` 文件，避免每次开终端重新设置。

---

## 第四步：下载本地模型

```bash
# 设置国内镜像（在中国大陆必须设置，否则极慢）
# Windows PowerShell:
$env:HF_ENDPOINT = "https://hf-mirror.com"
# Linux:
export HF_ENDPOINT=https://hf-mirror.com

pip install huggingface_hub

# 下载 Embedding 模型（约 2GB）
huggingface-cli download BAAI/bge-m3 --local-dir models/bge-m3

# 下载 Reranker 模型（约 1.5GB）
huggingface-cli download BAAI/bge-reranker-large --local-dir models/bge-reranker-large
```

下载完成后，确认 `config.yaml` 中模型路径指向本地目录：

```yaml
embedding:
  name_or_path: "models/bge-m3"    # 指向本地路径
  device: "cuda"                    # 无 GPU 改为 "cpu"
```

---

## 第五步：启动向量数据库

### 方案 A：Milvus Lite（零配置，免 Docker，推荐开发用）

在 `config.yaml` 中设置：

```yaml
vector_store:
  type: "milvus"
  uri: "./milvus_data/milvus.db"    # 本地文件存储，无需 Docker
```

无需任何额外操作，直接跳到第六步。

### 方案 B：Docker Milvus Standalone（生产环境推荐）

```bash
docker-compose up -d
# 等 30 秒后检查：
docker ps
# 应看到 milvus-standalone, milvus-etcd, milvus-minio 三个容器
```

> ⚠️ **不推荐 Zilliz Cloud 免费层**：限流极低（rate=0.1），ingest 时会反复报 `MilvusException: rate limit exceeded`，几乎无法正常使用。如必须用云端，需付费升级或在 ingest 代码中加 retry + 退避逻辑。

---

## 第六步：安装 Tesseract OCR（可选）

> 如果知识库中有 PDF 扫描件或图片需要 OCR 识别，才需要装。纯文本 PDF 不需要。

**Windows：**

1. 下载安装 [Tesseract-OCR](https://github.com/UB-Mannheim/tesseract/wiki)
2. 安装时**必须勾选** `Chinese Simplified` 语言包（否则运行时会卡死）
3. 将安装路径加入系统 PATH，例如 `C:\Program Files\Tesseract-OCR`
4. 验证：

```bash
tesseract --version
tesseract --list-langs
# 输出中应包含 chi_sim
```

**Linux：**

```bash
sudo apt install tesseract-ocr tesseract-ocr-chi-sim -y
```

> ⚠️ **已知问题**：如果 Tesseract 未正确安装或缺少 `chi_sim` 语言包，`pytesseract.image_to_string` 会无限卡死（不是报错，是 hang 住）。如果 ingest 过程卡住不动，先检查这一步。

---

## 第七步：放入知识库 & 入库

```bash
mkdir knowledge_base
# 把高中生物 PDF / 图片 / 视频等资料放进去

# 入库（首次建议加 --reset 重建索引）
python -m src.rag.cli ingest --dir knowledge_base --index kb --reset
```

---

## 第八步：启动系统

```bash
python -m src.rag.ui_gradio
```

浏览器打开 **http://127.0.0.1:7860**

> ⚠️ **如果报 `localhost is not accessible` 或 502 错误**：
> 这是本地代理（Clash / v2ray / SSR 等）拦截了 127.0.0.1。解决方式二选一：
>
> 1. **关闭代理软件**后重试
> 2. 在 `ui_gradio.py` 的 `demo.launch()` 中改为 `share=True`：
>    ```python
>    demo.launch(server_name="127.0.0.1", server_port=7860, share=True)
>    ```

---

## 第九步：测试所有功能

### 测试 1：教学对话 + 一键生成（Tab 1）

在对话框依次输入：

```
我想做一节高二生物课，关于中心法则的转录过程，45分钟
```

AI 追问后继续：

```
面向高二学生，重点讲RNA聚合酶的作用，需要PPT、教案和互动游戏
```

信息完整后点 **⚡ 一键生成全部课件**，右侧出现 PPT / Word / 游戏 / 动画的预览和下载。

### 测试 2：迭代修改（Tab 2）

输入修改意见如 `把第3页简化，增加案例` → 点 **✨ 应用修改**

### 测试 3：知识问答（Tab 3）

输入 `解释中心法则` → 查询 → 查看 RAG 回答

### 测试 4：知识库管理（Tab 4）

刷新索引 / 重新入库

---

## ⚡ 不需要 API / Docker 也能立刻测试的功能

### 游戏模板（零依赖）

```bash
python test_game_demo.py
```

然后浏览器打开 `outputs/games/demo/` 下任意 html 文件。

### PPT 生成（只需 python-pptx）

```bash
python -c "
from src.rag.ppt_generator import *
from pptx import Presentation
from pptx.util import Inches
prs = Presentation()
prs.slide_width = Inches(10)
prs.slide_height = Inches(5.625)
_make_cover_slide(prs, '中心法则', '高二生物')
_make_toc_slide(prs, ['DNA复制', '转录', '翻译'])
_make_content_slide(prs, '概念', ['mRNA：信使RNA', 'tRNA：转运RNA', 'rRNA：核糖体RNA'], layout='cards')
_make_content_slide(prs, '步骤', ['起始','延伸','终止','释放'], layout='steps')
_make_summary_slide(prs, '总结', ['中心法则三过程'])
_make_thanks_slide(prs)
prs.save('test_output.pptx')
print('生成 test_output.pptx')
"
```

### Word 教案生成（只需 python-docx）

```bash
python -c "
from src.rag.docx_generator import DocxGenerator
g = DocxGenerator.__new__(DocxGenerator)
g.generate_from_outline({
    'title':'中心法则教案','subject':'生物','grade':'高二','duration':'45分钟',
    'teaching_goal':['理解中心法则'],
    'key_points':['转录'],
    'difficulties':['方向性'],
    'teaching_method':['讲授法','讨论法'],
    'teaching_process':[
        {'stage':'导入','duration':'5分钟','content':'回顾','activity':'提问'},
        {'stage':'新授','duration':'25分钟','content':'讲解','activity':'演示'},
        {'stage':'练习','duration':'10分钟','content':'练习','activity':'讨论'},
        {'stage':'总结','duration':'5分钟','content':'总结','activity':'回顾'}
    ],
    'activities':[{'name':'角色扮演','description':'扮演DNA和RNA聚合酶'}],
    'homework':['画流程图'],
    'board_design':'左:流程 右:关键酶',
    'reflection':'关注学生理解'
}, output_dir='.')
print('教案已生成')
"
```

---

## 常见问题速查

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| `ValueError: torch.load ... upgrade torch to at least v2.6` | cu121 索引最高只有 torch 2.5.1 | 换 cu124 索引重装：`pip install torch --index-url https://download.pytorch.org/whl/cu124` |
| `AssertionError: Torch not compiled with CUDA enabled` | 装了 CPU 版 torch 但 config 设了 cuda | config.yaml 中 `device: "cpu"`，或重装 GPU 版 torch |
| `ImportError: cannot import name 'HfFolder'` | gradio 版本太旧，与新版 huggingface_hub 不兼容 | `pip install "gradio>=5.14,<6.0"` |
| `TypeError: argument of type 'bool' is not iterable` | gradio 5.12 的 pydantic schema bug | 升级到 gradio ≥5.14 |
| `Blocks constructor ... theme, css` | gradio 6.x 改了 API | 降级到 gradio <6.0 |
| `localhost is not accessible` / `502` | 本地代理拦截了 127.0.0.1 | 关闭 Clash/v2ray，或设 `share=True` |
| `MilvusException: rate limit exceeded` | Zilliz Cloud 免费层限流 | 改用本地 Milvus Lite 或 Docker Standalone |
| ingest 时卡住不动（不报错） | Tesseract 未装或缺 chi_sim 语言包 | 装好 Tesseract + chi_sim，见第六步 |
| `No module 'rank_bm25'` | 缺依赖 | `pip install rank-bm25` |
| PPT 预览是文字不是图片 | 缺 LibreOffice | `sudo apt install libreoffice` |
| 模型下载极慢 | 默认从 HuggingFace 下载 | 设置 `HF_ENDPOINT=https://hf-mirror.com` |

---

## 目录速查

```
edu_rag_FINAL/
├── knowledge_base/          ← 你的资料放这里
├── models/                  ← 下载的模型放这里
│   ├── bge-m3/
│   └── bge-reranker-large/
├── outputs/                 ← 生成的课件在这里
├── src/rag/
│   ├── ui_gradio.py         ← 主界面入口
│   ├── service.py           ← RAG 服务层
│   ├── rag_engine.py        ← RAG 引擎
│   ├── cli.py               ← 命令行入口
│   ├── embedder/            ← Embedding 模块
│   ├── vector_store/        ← 向量存储
│   ├── parsers/             ← 文档解析器
│   ├── tools/               ← OCR / ASR 等工具
│   └── dialogue/            ← 对话管理
├── test_game_demo.py        ← 游戏测试（零依赖）
├── config.yaml              ← 配置文件
├── requirements.txt         ← Python 依赖
├── docker-compose.yml       ← Milvus 启动
└── RUN_GUIDE.md             ← 本文件
```

---
