import sys
from pathlib import Path
from fastapi import APIRouter
from pydantic import BaseModel
import uuid

# 🌟 核心修改：动态获取项目根目录并加入搜索路径
# 当前文件：src/api/generate_image_.py
# .parent -> api | .parent.parent -> src | .parent.parent.parent -> 项目根目录
_root_dir = Path(__file__).resolve().parent.parent.parent
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

# 🌟 现在引入组件
from src.tools.image import generate_image_by_desc
from src.tools.database import SessionLocal
from src.tools.SQL import TempImage

router = APIRouter(prefix="/api/v1/ai")

class ImageGenRequest(BaseModel):
    session_id: str
    description: str
    style: str = "教学配图"
    aspect_ratio: str = "16:9"

@router.post("/generate_image")
async def api_generate_image(req: ImageGenRequest):
    """
    视觉增强接口：生成图片并强制进入待处理资产队列
    """
    db = SessionLocal()
    new_img_id = f"img_{uuid.uuid4().hex[:6]}"
    
    try:
        # 1. 调用生图 API
        final_url = generate_image_by_desc(
            description=req.description,
            style=req.style,
            aspect_ratio=req.aspect_ratio
        )
        
        if not final_url:
            return {"event": "ERROR", "data": {"message": "生图服务暂时不可用"}}

        # 2. 🌟 对齐新版 SQL 字段落库
        new_record = TempImage(
            image_id=new_img_id,
            session_id=req.session_id,
            url=final_url,               
            image_prompt=req.description, 
            target=1,                    
            target_page=None,            
            position_code=None           
        )
        db.add(new_record)
        db.commit()

        # 3. 返回前端渲染信令
        return {
            "event": "IMAGE_GENERATED_AND_READY",
            "data": {
                "image_id": new_img_id,
                "url": final_url,
                "prompt": req.description,
                "message": "AI 已为您生成配图，请安放位置。"
            }
        }

    except Exception as e:
        db.rollback()
        return {"event": "ERROR", "data": {"message": f"生图落库失败: {str(e)}"}}
    finally:
        db.close()
