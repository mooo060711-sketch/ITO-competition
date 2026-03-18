import json
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import List, Optional

# ==========================================
# 1. 定义工具输入模型 (Args Schema)
# ==========================================
class GameTaskInput(BaseModel):
    session_id: str = Field(description="当前的会话 ID")
    action: str = Field(description="动作类型：'generate' (生成/增加) 或 'modify' (修改/刷新现有内容)")
    game_types: List[str] = Field(description="""
        要操作的【互动小游戏】类型列表。可选值：
        'quiz' (测验), 'matching' (连连看), 'sorting' (分类), 
        'fill_blank' (填空), 'true_false' (判断), 'flashcard' (闪卡), 'flow_fill' (流程填空)
    """)
    user_requirement: Optional[str] = Field(
        description="老师对互动小游戏的具体细节要求，例如‘题目关于光合作用’或‘难度加大’", 
        default=""
    )

# ==========================================
# 2. 核心意图分发工具
# ==========================================
@tool("manage_game_task", args_schema=GameTaskInput)
def manage_game_task(session_id: str, action: str, game_types: List[str], user_requirement: str = "") -> str:
    """
    当老师明确提到要创建、增加、修改特定类型的【互动小游戏】时调用此工具。
    game_types 可选值：'quiz', 'matching', 'sorting', 'fill_blank', 'true_false', 'flashcard', 'flow_fill'。
    """
    # 构造标准信令载荷
    response_payload = {
        "event": "GAME_PIPELINE_TRIGGER",
        "data": {
            "session_id": session_id,
            "action": action,
            "game_types": game_types,
            "user_prompt": user_requirement
        }
    }
    
    # 序列化为 JSON 字符串返回给 Agent
    return json.dumps(response_payload, ensure_ascii=False)
