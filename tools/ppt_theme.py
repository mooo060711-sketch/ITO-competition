# 在你的 FastAPI 路由中增加
from fastapi import APIRouter
import json
import os

router = APIRouter(prefix="/api/v1")
METADATA_FILE = "./data/ppt_themes_metadata.json"

@router.get("/ppt/themes")
async def get_themes():
    if not os.path.exists(METADATA_FILE):
        return {"code": 404, "msg": "本地模板库尚未同步"}
    
    with open(METADATA_FILE, 'r', encoding='utf-8') as f:
        themes = json.load(f)
    
    # 🌟 核心修改：动态修正图片 URL 端口，确保前端能访问到图片
    for t in themes:
        if "local_preview_url" in t:
            # 将硬编码的 8000 替换为后端的 9527 端口 [cite: 11, 14]
            t["local_preview_url"] = t["local_preview_url"].replace(":8000", ":9527")
            
    return {"code": 200, "data": themes}
