import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import sys; sys.path.insert(0, '.')  # 强制把当前目录加入搜索路径
from src.tools.database import SessionLocal
from src.tools.SQL import SessionContext
from src.tools.word import generate_word_lesson_plan_from_ppt
import pathlib
# ==========================================
# 🌟 核心绝对物理路径 (与 game_.py 完全保持同源)
# ==========================================
BASE_OUTPUT_DIR = pathlib.Path(__file__).parent.parent / "outputs"
PLAN_OUTPUT_DIR = os.path.join(BASE_OUTPUT_DIR, "lesson_plans")

router = APIRouter(prefix="/api/v1/extensions")

class LessonPlanRequest(BaseModel):
    session_id: str
    ppt_path: str 

@router.post("/lesson_plan")
async def generate_lesson_plan(req: LessonPlanRequest):
    """
    同步教案生成接口：仅依赖意图要素与 PPT 内容
    """
    db = SessionLocal()
    try:
        session_record = db.query(SessionContext).filter(SessionContext.session_id == req.session_id).first()
        if not session_record:
            raise HTTPException(status_code=404, detail="未找到会话记录")
        
        slots = session_record.extracted_slots or {}

        class IntentSlotsAdapter:
            def __init__(self, s):
                self.theme = s.get("theme", "未命名主题")
                self.teaching_objectives = s.get("teaching_objectives", "未设置目标")
                self.audience = s.get("audience", "常规受众")
                self.key_points = s.get("key_points", "未明确重难点")
                self.required_knowledge = s.get("required_knowledge", "无")
                self.other_requirements = s.get("other_requirements", "无")
        
        adapter = IntentSlotsAdapter(slots)

        # 🌟 确保统一的绝对路径文件夹存在
        os.makedirs(PLAN_OUTPUT_DIR, exist_ok=True)

        result = generate_word_lesson_plan_from_ppt(
            intent_slots=adapter,
            ppt_filepath=req.ppt_path,  # 这里接收的已经是上一环节产生的绝对路径
            output_dir=PLAN_OUTPUT_DIR  # 传入绝对存放路径
        )

        if not result:
            return {"event": "ERROR", "data": {"message": "教案引擎运行失败"}}

        session_record.lesson_plan_str = result["lesson_plan_str"]
        session_record.lesson_plan_path = result["docx_filepath"]
        db.commit()

        return {
            "event": "LESSON_PLAN_SUCCESS",
            "data": {
                "download_path": result["docx_filepath"],
                "lesson_plan_content": result["lesson_plan_str"],
                "message": "同步教案已生成！已根据您的教学意图完成深度内容适配。"
            }
        }

    except Exception as e:
        db.rollback()
        return {"event": "ERROR", "data": {"message": str(e)}}
    finally:
        db.close()
