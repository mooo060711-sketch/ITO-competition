# 🚀 运行指南（VSCode）

## 前置条件

- Windows 10/11（推荐WSL2）或 Linux/Mac
- Python 3.10+
- Docker Desktop（用于Milvus向量数据库）
- 阿里云DashScope账号（免费注册）

---

## 第一步：用VSCode打开

```bash
cd edu_rag_FINAL
code .
```

---

## 第二步：创建Python虚拟环境

VSCode中打开终端（`Ctrl+反引号`）：

```bash
# 创建虚拟环境
python -m venv venv

# 激活
# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

# 安装依赖（约5-10分钟）
# 先装GPU版torch
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121

# 再装其他依赖（torch已经装了就会跳过）
pip install -r requirements.txt
pip install pdf2image
```

---

## 第三步：注册DashScope & 设置API Key

1. 打开 https://dashscope.console.aliyun.com/ → 注册/登录 → 获取API Key
2. 设置环境变量：

```bash
# Windows PowerShell:
$env:OPENAI_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
$env:OPENAI_API_KEY = "sk-你的Key"

# Linux/Mac:
export OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
export OPENAI_API_KEY="sk-你的Key"
```

> 每次开终端都要重新设置，建议写到系统环境变量。

---

## 第四步：下载本地模型

```bash
# 设置国内镜像
# Windows: set HF_ENDPOINT=https://hf-mirror.com
# Linux:   export HF_ENDPOINT=https://hf-mirror.com

pip install huggingface_hub

# 下载Embedding模型（~2GB）
huggingface-cli download BAAI/bge-m3 --local-dir models/bge-m3

# 下载Reranker模型（~1.5GB）
huggingface-cli download BAAI/bge-reranker-large --local-dir models/bge-reranker-large
```

---

## 第五步：启动Milvus向量数据库

```bash
docker-compose up -d

# 等30秒，检查：
docker ps
# 应看到 milvus-standalone, milvus-etcd, milvus-minio 三个容器
```

---

## 第六步：放入知识库 & 入库

```bash
mkdir knowledge_base
# 把你的高中生物PDF/图片/视频放进去

# 入库
python -m src.rag.cli ingest --dir knowledge_base --index kb
```

---

## 第七步：启动系统

```bash
python -m src.rag.ui_gradio
```

浏览器打开 **http://127.0.0.1:7860**

---

## 第八步：测试所有功能

### 测试1：教学对话 + 一键生成（Tab 1 左侧）

在对话框依次输入：
```
我想做一节高二生物课，关于中心法则的转录过程，45分钟
```
AI追问后继续：
```
面向高二学生，重点讲RNA聚合酶的作用，需要PPT、教案和互动游戏
```
信息完整后点 **🚀 一键生成全部课件**，右侧出现PPT/Word/游戏/动画的预览和下载。

### 测试2：迭代修改（Tab 2）

输入修改意见如 `把第3页简化，增加案例` → 点 **🔄 应用修改**

### 测试3：知识问答（Tab 3）

输入 `解释中心法则` → 查询 → 查看RAG回答

### 测试4：知识库管理（Tab 4）

刷新索引 / 重新入库

---

## ⚡ 不需要API/Docker也能立刻测试的功能

### 游戏模板（零依赖，直接跑）

```bash
python test_game_demo.py
```
然后浏览器打开 `outputs/games/demo/` 下任意html文件。

### PPT生成（只需python-pptx）

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
用PowerPoint打开 `test_output.pptx` 查看效果。

### Word教案生成（只需python-docx）

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
print('教案已生成，查看当前目录下的docx文件')
"
```

---

## 常见问题

| 问题 | 解决方案 |
|------|---------|
| torch太大装不上 | `pip install torch --index-url https://download.pytorch.org/whl/cpu` |
| docker-compose报错 | 确保Docker Desktop已启动，Windows需开WSL2 |
| 模型下载太慢 | `export HF_ENDPOINT=https://hf-mirror.com` |
| No module 'rank_bm25' | `pip install rank-bm25` |
| PPT预览是文字不是图片 | 需安装LibreOffice：`sudo apt install libreoffice` |
| API Key报错 | 检查环境变量是否设置，DashScope余额是否充足 |

---

## 目录速查

```
edu_rag_FINAL/
├── knowledge_base/          ← 你的资料放这里
├── models/                  ← 下载的模型放这里
├── outputs/                 ← 生成的课件在这里
├── src/rag/ui_gradio.py     ← 主界面入口
├── test_game_demo.py        ← 游戏测试（零依赖）
├── config.yaml              ← 配置文件
└── docker-compose.yml       ← Milvus启动
```
