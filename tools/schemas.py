from pydantic import BaseModel, Field
from typing import Optional, List

class IntentSlots(BaseModel):
    theme: Optional[str] = Field(description="教学主题", default=None)
    audience: Optional[str] = Field(description="目标受众", default=None)
    page_range: Optional[str] = Field(description="页数范围", default=None)
    teaching_objectives: Optional[str] = Field(description="教学目标（核心驱动力）", default=None)
    key_points: Optional[str] = Field(description="重点难点", default=None)
    required_knowledge: Optional[str] = Field(description="必须包含的知识点", default=None)
    
    # 🌟 新增：互动小游戏类型提取
    interactive_game_types: Optional[str] = Field(
        description="""
        计划生成的【互动小游戏】类型。
        可选类型标识：'quiz' (测验), 'matching' (连连看), 'sorting' (分类), 'fill_blank' (填空), 'true_false' (判断), 'flashcard' (闪卡), 'flow_fill' (流程填空)。
        【提取逻辑】：
        1. 用户明确指定：提取对应的标识（可多个，用逗号分隔）。
        2. 用户意图模糊：如“想要点互动”，设为 None，触发 clarifying_question 的清单追问。
        3. 暂不需要：填入 '无'。
        """,
        default=None
    )
    
    reference_material_purpose: Optional[str] = Field(
        description="""
        参考资料的上传目的或用途。
        - 明确无资料：填入 '无'。
        - 意图明确：如实提取。
        - 🚨 【意图不明/强制拦截】：若上传了资料但未说明用途，务必保持为空 (None)。
        """, 
        default=None
    )
    
    teaching_logic: Optional[str] = Field(
        description="""
        教学思路（A -> B -> C 格式）。
        【自动推导规则】：若用户未提供，需根据 objectives 从“标准新授”、“难点突破”、“通用复习”中三选一。
        """, 
        default=None
    )
    
    other_requirements: Optional[str] = Field(
        description="其他特殊要求（授课风格等）。若无填'无'。", 
        default=None
    )
    
    # ==========================================
    # 🌟 核心状态机：现在包含 8 项核心要素
    # ==========================================
    is_all_extracted: bool = Field(
        description="前 8 项核心教学要素（含互动小游戏类型）是否已全部提取完毕（非空）", 
        default=False
    )
    
    is_confirmed: bool = Field(
        description="""
        用户是否已确认所有要素。
        【拦截规则】：is_all_extracted 为 True 时，is_confirmed 必须先为 False，直到用户明确同意。
        """, 
        default=False
    )
    
    clarifying_question: Optional[str] = Field(
        description="""
        输出给用户的话术逻辑：
        1. 附件意图不明（最高优先级）：追问资料用途。
        2. 互动小游戏类型不明：若 interactive_game_types 为 None，必须主动告知：“为了增强课堂互动，我支持生成测验、连连看、分类、填空、判断、闪卡和流程填空，您想尝试哪种【互动小游戏】？”
        3. 其他要素未齐：引导式追问缺失项。
        4. 要素已齐但待确认：列表汇总展示这 8 项要素。若 teaching_logic 是推导的，需加注声明。
        """, 
        default=None
    )
