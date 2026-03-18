import logging
import uvicorn
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# 1. 数据库初始化
import sys; sys.path.insert(0, '.')  # 强制把当前目录加入搜索路径
from src.tools.database import engine
from src.tools.SQL import Base

# 配置日志
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

# 初始化数据库表结构
logging.info("正在执行数据库 O/RM 映射初始化...")
try:
    Base.metadata.create_all(bind=engine)
    logging.info("✅ 数据库表结构初始化成功！")
except Exception as e:
    logging.error(f"❌ 数据库初始化失败: {e}")

# 2. 实例化 FastAPI
app = FastAPI(
    title="多模态 AI 互动式教学智能体 API",
    description="支持大纲生成、PPT 渲染、互动游戏及资产管理",
    version="2.0.0"
)

# 3. 🌟 强制挂载静态资源 (核心修复)
# 定义物理路径
import pathlib
OUTPUT_BASE = pathlib.Path(__file__).parent / "outputs"  # 项目根/outputs
THEME_PREVIEW_DIR = pathlib.Path(__file__).parent / "theme_previews"
# 确保文件夹存在
for path in [OUTPUT_BASE, os.path.join(OUTPUT_BASE, "games"), os.path.join(OUTPUT_BASE, "ppts")]:
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

# 挂载静态资源
try:
    app.mount("/outputs", StaticFiles(directory=OUTPUT_BASE), name="outputs")
    logging.info(f"✅ 静态资源路径 /outputs 已挂载: {OUTPUT_BASE}")
    
    if os.path.exists(THEME_PREVIEW_DIR):
        app.mount("/theme_previews", StaticFiles(directory=THEME_PREVIEW_DIR), name="theme_previews")
        logging.info(f"✅ 主题预览路径 /theme_previews 已挂载")
except Exception as e:
    logging.error(f"❌ 静态资源挂载失败: {e}")

# 4. 配置 CORS 跨域
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5. 导入并注册路由
from chat_ import router as chat_router
from export_ import router as export_router
from game_ import router as game_router
from generate_image_ import router as generate_image_router
from knowledge_ import router as knowledge_router
from replace_media_ import router as replace_media_router
from reset_ import router as reset_router
from rollback_ import router as rollback_router
from stream_ import router as stream_router
from asr_ import router as asr_router
from tools.ppt_theme import router as ppt_theme_router
from generate_ppt_ import router as generate_ppt_router
from lesson_plan_ import router as lesson_plan_router 
from refine_ import router as refine_router  

app.include_router(chat_router)
app.include_router(export_router)
app.include_router(game_router)
app.include_router(generate_image_router)
app.include_router(knowledge_router)
app.include_router(replace_media_router)
app.include_router(reset_router)
app.include_router(rollback_router)
app.include_router(stream_router)
app.include_router(asr_router)
app.include_router(ppt_theme_router)
app.include_router(generate_ppt_router)
app.include_router(lesson_plan_router)
app.include_router(refine_router)

# 6. 心跳检查
@app.get("/")
async def root():
    return {"code": 200, "message": "🚀 引擎运行正常"}

if __name__ == "__main__":
    # 使用 reload=False 避免 Windows 文件占用问题
    uvicorn.run("main:app", host="127.0.0.1", port=9527, reload=False)
