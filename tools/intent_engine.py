import json
import contextvars
from pathlib import Path
import sys
from langchain_core.tools import tool

# 🌟 路径锁定逻辑
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.tools.schemas import IntentSlots
from src.tools.database import SessionLocal
from src.tools.SQL import SessionContext
from sqlalchemy.orm.attributes import flag_modified

# 全局上下文变量
current_session_var = contextvars.ContextVar("current_session_var", default="default")

# 支持的游戏类型常量（用于追问）
SUPPORTED_GAMES_MD = (
    "1. **测验 (quiz)**\n"
    "2. **连连看 (matching)**\n"
    "3. **分类 (sorting)**\n"
    "4. **填空 (fill_blank)**\n"
    "5. **判断 (true_false)**\n"
    "6. **闪卡 (flashcard)**\n"
    "7. **流程填空 (flow_fill)**"
)

@tool("update_teaching_elements", args_schema=IntentSlots)
def update_teaching_elements(**kwargs) -> str:
    """
    更新并存储教学设计核心要素。
    """
    actual_session_id = current_session_var.get()
    
    is_all_extracted = kwargs.get("is_all_extracted", False)
    is_confirmed = kwargs.get("is_confirmed", False)
    clarifying_question = kwargs.get("clarifying_question", "")

    db = SessionLocal()
    extracted_slots = {}
    try:
        session_record = db.query(SessionContext).filter(SessionContext.session_id == actual_session_id).first()
        if session_record:
            extracted_slots = session_record.extracted_slots or {}
            
            # 增量更新槽位
            fields = [
                "theme", "audience", "page_range", "teaching_objectives",
                "key_points", "required_knowledge", "interactive_game_types",
                "reference_material_purpose", "teaching_logic", "other_requirements"
            ]
            for field in fields:
                val = kwargs.get(field)
                if val is not None and str(val).strip() != "" and str(val) != "None":
                    extracted_slots[field] = val

            session_record.extracted_slots = dict(extracted_slots)
            flag_modified(session_record, "extracted_slots") 
            db.commit()
    except Exception as e:
        db.rollback()
        return f"❌ 数据库写入异常: {e}"
    finally:
        db.close()

    # =====================================================================
    # 🌟 状态机回复逻辑
    # =====================================================================
    
    # 1. 收集阶段：要素未齐 -> 自然语言引导（重点增加游戏类型说明）
    # 1. 收集阶段：要素未齐 -> 启发式引导与严格红线拦截
    if not is_all_extracted:
        theme = extracted_slots.get("theme", "该课题")
        
        # 如果当前互动小游戏还没定，改变干瘪罗列的方式，引入场景化推荐
        game_instruction = ""
        if not extracted_slots.get("interactive_game_types"):
            game_instruction = (
                f"\n🚨【互动小游戏推荐策略】：若老师尚未选定【互动小游戏】，请结合【{theme}】的特性向老师进行场景化推荐，千万不要像报菜名一样死板罗列。\n"
                f"例如你可以这样引导：'为了让课堂更活跃，我们可以穿插一些互动小游戏！针对这节课，比如用【连连看 (matching)】来配对专业术语，或者用【流程填空 (flow_fill)】来梳理机制步骤效果都会很好。我们的引擎目前支持：测验、连连看、分类、填空、判断、闪卡和流程填空。老师您想尝试哪一种？'\n"
            )

        return (
            f"✅ 系统后台已记录已提供信息。\n"
            f"🚨【回复指令】：目前教学要素尚未收齐。请你以专业教研助理的身份，用【自然、启发式】的口吻继续与老师交流。\n"
            f"⚠️【严格红线】：**绝对禁止**在当前阶段向老师展示任何类似“教学要素核对表”的清单！只要要素没收齐，就绝不允许输出带有“未明确”字样的罗列项。\n"
            f"💡【启发式追问策略】：请直接使用或润色以下基础追问：'{clarifying_question}'。在追问缺失要素时，你必须结合【{theme}】的学科内容，为老师提供 1~2 个具体的【参考示例】。比如问重难点时，主动举例该主题常见的易错点；问授课逻辑时，给出一种常见的引入方案，以此启发老师的灵感。\n"
            f"{game_instruction}"
        )
        
    # 2. 收齐阶段：要素已齐，但用户未确认 -> 正式核对表
    elif is_all_extracted and not is_confirmed:
        items_map = {
            "教学主题": "theme", "授课对象": "audience", "课件页数": "page_range",
            "教学目标": "teaching_objectives", "重点难点": "key_points",
            "必备知识": "required_knowledge", "互动游戏": "interactive_game_types",
            "教学思路": "teaching_logic", "资料用途": "reference_material_purpose",
            "其他要求": "other_requirements"
        }
        checklist = "\n".join([f"- **{k}**：{extracted_slots.get(v, '（已自动推导）')}" for k, v in items_map.items()])
        
        return (
            f"✅ 教学要素已全部收齐。\n"
            f"🚨【回复指令】：请你向老师展示这一份正式的【📝 教学设计要素核对表】，并请求最后确认：\n\n"
            f"{checklist}\n\n"
            f"--- \n"
            f"请询问老师：'老师，以上是为您整理的教学设计画像。如果您确认无误，请回复“确认”，我将立刻为您生成教学大纲！'"
        )
        
    # 3. 执行阶段：用户已确认 -> 吐出 JSON
    else:
        game_types = extracted_slots.get("interactive_game_types")
        target_views = ["outline"]
        # 判定是否需要生成游戏
        if game_types and game_types not in ["无", "None", "待补充", "待定"]:
            target_views.append("game")
            
        pipeline_data = {
            "event": "PIPELINE_START",
            "data": {
                "level": 1, 
                "target_views": target_views, 
                "slots": extracted_slots,
                "message": f"收到您的确认！正在为您构建《{extracted_slots.get('theme', '新课程')}》的深度大纲及匹配的互动游戏，请稍候..."
            }
        }
        
        return (
            f"🚨【最终指令】：要素已确认！你【必须且只能】原封不动地输出以下 JSON 字符串，"
            f"严禁添加任何文字说明或标签：\n{json.dumps(pipeline_data, ensure_ascii=False)}"
        )