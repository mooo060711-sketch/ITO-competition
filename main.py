import logging
import uvicorn
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

PROJECT_ROOT = Path(__file__).resolve().parent.parent 
load_dotenv(PROJECT_ROOT / ".env") # 保留这句，如果系统有变量，系统优先

# 🌟 自检：检查系统环境变量是否读取成功
logging.info("--- 环境变量自检 ---")
env_key = os.getenv("OPENAI_API_KEY")  # 这里换成你电脑里设置的变量名
env_url = os.getenv("OPENAI_BASE_URL") # 这里换成你电脑里设置的变量名

if env_key:
    logging.info(f"✅ 系统 API Key 已加载: {env_key[:6]}****")
else:
    logging.warning("❌ 系统 API Key 读取失败，请检查环境变量设置或重启编辑器")

if env_url:
    logging.info(f"✅ 系统 API URL 已加载: {env_url}")
else:
    logging.info("ℹ️ 未检测到系统 API URL，将使用默认值")
logging.info("------------------")

# 强制把项目根目录加入搜索路径，确保 from src.xxx 导入正常
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# 🌟 2. 数据库初始化
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

# 🌟 3. 实例化 FastAPI
app = FastAPI(
    title=os.getenv("APP_TITLE", "多模态 AI 互动式教学智能体 API"),
    description="支持大纲生成、PPT 渲染、互动游戏及资产管理",
    version="2.0.0"
)

# 🌟 4. 静态资源挂载 (使用绝对路径)
# 从环境变量获取输出目录，默认为根目录下的 outputs
OUTPUT_DIR = PROJECT_ROOT / os.getenv("OUTPUT_DIR_NAME", "outputs")
THEME_PREVIEW_DIR = PROJECT_ROOT / "theme_previews"

# 确保文件夹存在
for path in [OUTPUT_DIR, OUTPUT_DIR / "games", OUTPUT_DIR / "ppts", OUTPUT_DIR / "images"]:
    path.mkdir(parents=True, exist_ok=True)

try:
    app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")
    logging.info(f"✅ 静态资源路径 /outputs 已挂载: {OUTPUT_DIR}")
    
    if THEME_PREVIEW_DIR.exists():
        app.mount("/theme_previews", StaticFiles(directory=str(THEME_PREVIEW_DIR)), name="theme_previews")
        logging.info(f"✅ 主题预览路径 /theme_previews 已挂载")
except Exception as e:
    logging.error(f"❌ 静态资源挂载失败: {e}")

# 🌟 5. 配置 CORS 跨域 (从环境变量读取)
allowed_origins = os.getenv("ALLOWED_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 🌟 6. 导入并注册路由
# 注意：确保 api 包在搜索路径内
from api.chat_ import router as chat_router
from api.export_ import router as export_router
from api.game_ import router as game_router
from api.generate_image_ import router as generate_image_router
from api.knowledge_ import router as knowledge_router
from api.replace_media_ import router as replace_media_router
from api.reset_ import router as reset_router
from api.rollback_ import router as rollback_router
from api.stream_ import router as stream_router
from api.asr_ import router as asr_router
from src.tools.ppt_theme import router as ppt_theme_router
from api.generate_ppt_ import router as generate_ppt_router
from api.lesson_plan_ import router as lesson_plan_router 
from api.refine_ import router as refine_router  

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

# 7. 心跳检查
@app.get("/")
async def root():
    return {
        "code": 200, 
        "message": "🚀 引擎运行正常",
        "env": os.getenv("ENV_NAME", "development")
    }

if __name__ == "__main__":
    # 使用 getenv 读取运行参数
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", 9527))
    
    logging.info(f"正在启动服务: http://{host}:{port}")
    
    # 使用 reload=False 避免 Windows 文件占用问题
    uvicorn.run("main:app", host=host, port=port, reload=False)