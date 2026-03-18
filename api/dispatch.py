from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import List
import json

import sys; sys.path.insert(0, '.')  
from src.tools.database import SessionLocal
from src.tools.SQL import SessionContext

# ==========================================
# 完整版：级联调度与依赖路径信令分发 (支持 Level 1-5)
# ==========================================
class DispatchTaskInput(BaseModel):
    session_id: str = Field(description="当前的会话 ID，用于重置追问状态。")
    user_intent: str = Field(description="老师的具体意图，例如'开始生成大纲'或'帮我重新生成大纲'")
    
    level: int = Field(description="""
        核心级联重构等级 (必须是 1-5 之一)：
        - Level 1 (首次生成): 老师【首次】要求生成大纲。注意：这是从0到1的创建，绝不能称为“修改”！
        - Level 2 (改大纲): 修改已有大纲，这会级联重构 PPT 和 Word。
        - Level 3 (换模版): 大纲不变，仅要求更换 PPT 模板并重新渲染。
        - Level 4 (局部微调): 仅修改特定的 Word 教案或互动小游戏。
        - Level 5 (批量生图安放): 确认不再添加图片，请求将所有待定图片物理写入 PPT。
    """)
    
    target_view: str = Field(description="""
        当且仅当 level 为 4 时必填。
        可选值：'word' (代表教案) 或 'game' (代表互动小游戏)。
    """, default="")

@tool("dispatch_courseware_task", args_schema=DispatchTaskInput)
def dispatch_courseware_task(session_id: str, user_intent: str, level: int, target_view: str = "") -> str:
    """
    统筹全局状态机与级联调度器。
    处理首次生成大纲、修改大纲、重构课件等核心指令。
    """
    
    if level in [1, 2, 3]:
        db = SessionLocal()
        try:
            session = db.query(SessionContext).filter(SessionContext.session_id == session_id).first()
            if session:
                session.is_image_placement_deferred = False
                db.commit()
        except Exception:
            db.rollback()
        finally:
            db.close()

    response_payload = {
        "event": "PIPELINE_START",
        "data": {
            "level": level,
            "intent": user_intent,
            "target_views": [],
            "dependency_chain": "",  
            "impact_scope": "",       
            "scheduler_instruction": "" 
        }
    }
    
    if level == 1:
        response_payload["data"].update({
            "target_views": ["outline", "ppt", "word", "game"],
            "dependency_chain": "intent -> outline -> game -> template_selection -> ppt -> word",
            "impact_scope": "全链路资产初始化",
            "scheduler_instruction": "STREAM_OUTLINE_AND_BATCH_GEN_GAME_WAIT_TEMPLATE"
        })
        # 🌟 强制大模型改口的指令
        response_payload["__llm_instruction__"] = "🚨【回复指令】：这是 Level 1 首次生成。请亲切地对老师说：'好的老师，正在为您首次生成教学大纲及互动小游戏，请稍候...'。严禁使用'修改大纲'、'引发重构'等误导词汇！"
        
    elif level == 2:
        response_payload["data"].update({
            "target_views": ["ppt", "word"],
            "dependency_chain": "modified_outline -> rebuild_ppt -> rewrite_word",
            "impact_scope": "核心内容级联刷新",
            "scheduler_instruction": "CASCADE_REBUILD_BY_OUTLINE"
        })
        response_payload["__llm_instruction__"] = "🚨【回复指令】：已触发大纲修改。请告知老师，大纲的修改会引发 PPT 和教案的同步级联重构，请老师稍候。"
        
    elif level == 3:
        response_payload["data"].update({
            "target_views": ["ppt", "word"],
            "dependency_chain": "new_template -> re_render_ppt -> sync_word",
            "impact_scope": "视觉表现力重构",
            "scheduler_instruction": "REBUILD_PPT_AND_WORD_ONLY"
        })
        
    elif level == 4:
        view = target_view if target_view in ["word", "game"] else "word"
        view_name = "教案" if view == "word" else "互动小游戏"
        response_payload["data"].update({
            "target_views": [view],
            "dependency_chain": f"partial_edit -> {view}",
            "impact_scope": f"{view_name} 局部优化",
            "scheduler_instruction": f"PARTIAL_REFRESH_{view.upper()}"
        })

    elif level == 5:
        response_payload["data"].update({
            "target_views": ["ppt"],
            "dependency_chain": "final_confirm -> bulk_image_injection -> ppt_refresh",
            "impact_scope": "视觉资产最终入库",
            "scheduler_instruction": "EXECUTE_BULK_IMAGE_PLACEMENT"
        })

    return json.dumps(response_payload, ensure_ascii=False)