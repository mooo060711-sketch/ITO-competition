import json
import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import and_
import sys
import os

# 引入数据库组件
_api_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(os.path.dirname(_api_dir))
sys.path.insert(0, _root_dir)  # 强制把项目根目录加入搜索路径
from src.tools.database import get_db
from src.tools.SQL import SessionHistory, SessionContext, TempImage, CoursewareVersion

# 引入核心工具技能
from src.tools.intent_engine import update_teaching_elements, current_session_var
from src.tools.image_intent import process_image_intelligence  
from src.api.dispatch import dispatch_modification_task      
from src.tools.timeline_recall import timeline_recall           
from src.tools.game_intent import manage_game_task              

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

from src.llm_config import load_llm_config

config = load_llm_config()

router = APIRouter(prefix="/api/v1")
logger = logging.getLogger("chat_commander")

class ChatRequest(BaseModel):
    session_id: str
    message: str
    uploaded_files: Optional[List[str]] = []

# =====================================================================
# 🌟 统一主控逻辑：全面封杀“空回复”，强制大模型确认所有要素
# =====================================================================
SYSTEM_PROMPT = """
你是专业的“AI 课件教研助理”，请称呼用户为“老师”。

🚨 【最高生存铁律：绝对禁止空回复】
在任何情况下，无论是日常闲聊，还是在【调用完任何工具之后】，你都【绝对禁止】停止输出或返回空字符串！
工具调用成功只是中间过程，你【必须】永远将最终的处理结果、核对表或下一步引导用清晰的自然语言告诉老师！

【第一铁律：教学要素全量核对表（强制动作）】
只要老师的话语中提供了任何教学设定，你【必须立刻调用】 `update_teaching_elements` 工具。
调用成功后，你【必须】在回复中展示一份包含全部10项的【📝 教学要素全景核对表】：
（涵盖：主题、对象、页数、游戏、目标、重难点、前置知识、资料用途、教学逻辑、其他要求）。
- 如果某项已提供，标明具体内容。
- 如果某项未提供，必须清晰标明“未明确”。
展示完核对表后，你必须针对标为“未明确”的核心项向老师发起精准追问。绝对禁止保持沉默！

🚨 【第二铁律：级联告知义务】
当老师要求修改【大纲】或触发 Level 2 等级的重构时，你调用 `dispatch_modification_task` 后，必须在回复中明确告知老师：
“老师，大纲的修改会引发 PPT 页面和 Word 教案的同步重构。我已经为您启动了级联更新流程，以确保所有教学资产内容一致。”

🚨 【第三铁律：关于图片处理的消消乐追问与闭环机制】
1. **生图要素拦截**：当老师要求生图时，必须反问：具体内容？美术风格？图片比例？
2. **主动安放追问 (消消乐审计)**：有图片待安放且坐标为空时，必须优先追问目标页码和位置。
3. **资产闭环触发 (Level 5 强制调用)**：所有图片安放满且老师确认后，必须调用 `dispatch_modification_task` 设置 `level=5`。

🚨 【第四铁律：页数死线与格式穿透禁令】
1. 大纲生成的页数必须严格遵守老师设定的页数（目前为：{slots.get('page_range', '10')}）。
2. 当你调用 `process_image_intelligence` 或 `dispatch_modification_task` 时，如果工具返回的是一个 JSON，你【必须原封不动】地输出该 JSON。严禁在 JSON 外面添加文字或 ```json 标签！
"""

@router.post("/chat")
async def chat_handler(req: ChatRequest, db: Session = Depends(get_db)):
    session_id = req.session_id
    try:
        session = db.query(SessionContext).filter_by(session_id=session_id).first()
        if not session:
            session = SessionContext(session_id=session_id)
            db.add(session)
            db.commit()

        tools = [
            dispatch_modification_task,
            update_teaching_elements, 
            process_image_intelligence,
            timeline_recall,
            manage_game_task 
        ]
        
        llm = ChatOpenAI(
        model=config['models']['intent'],  # qwen-max
        api_key=config['api_key'],
        base_url=config['base_url'],
        temperature=0,
        timeout=120,
        max_retries=3
    )
        
        agent_executor = create_react_agent(model=llm, tools=tools)

        db.refresh(session)
        slots = session.extracted_slots if session.extracted_slots else {}
        audit_prefix = ""
        
        # 探针逻辑
        if not session.is_image_placement_deferred and "精修" not in req.message:
            lost_asset = db.query(TempImage).filter(
                TempImage.session_id == session_id,
                TempImage.target == 1,
                TempImage.position_code == None
            ).first()
            
            if lost_asset:
                audit_prefix = f"【系统探针：画廊中有资产 {lost_asset.image_id} 待安放。若老师上一句没给位置，请追问；若给了，请直接调用 process_image_intelligence。】\n"
            else:
                placed_count = db.query(TempImage).filter_by(session_id=session_id, target=1).count()
                if placed_count > 0:
                    audit_prefix = "【系统探针：画廊图片已全部安放完毕。请主动询问老师是否可以开始批量写入。】\n"

        if req.uploaded_files:
            audit_prefix += f"【系统探针：老师上传了文件 {req.uploaded_files}。请确认用途！】\n"

        raw_history = db.query(SessionHistory).filter(SessionHistory.session_id == session_id).order_by(SessionHistory.timestamp.asc()).limit(10).all()
        
        messages = [SystemMessage(content=SYSTEM_PROMPT)] 
        for h in raw_history:
            messages.append(HumanMessage(content=h.content) if h.role == "user" else AIMessage(content=h.content))
        
        messages.append(HumanMessage(content=audit_prefix + req.message))
        current_session_var.set(session_id)

        # ==========================================
        # 1. 触发 Agent 执行
        # ==========================================
        response = agent_executor.invoke({"messages": messages})
        
        last_message = response["messages"][-1]
        output_content = last_message.content.strip() if hasattr(last_message, 'content') and last_message.content else ""
        
        logger.info(f"🤖 [LLM 原始输出]: {repr(output_content)}")

        # 防御性兜底：万一大模型网络卡了真的回了空，给个基础回声防止前端报错
                # ==========================================
        if not output_content:
            db.refresh(session)
            slots = session.extracted_slots or {}
            
            # 自动生成 10 项全量清单
            items = {
                "教学主题": slots.get("theme", "未明确"),
                "授课对象": slots.get("audience", "未明确"),
                "课件页数": slots.get("page_range", "未明确"),
                "教学目标": slots.get("teaching_objectives", "未明确"),
                "重点难点": slots.get("key_points", "未明确"),
                "前置知识": slots.get("required_knowledge", "未明确"),
                "教学逻辑": slots.get("teaching_logic", "未明确"),
                "互动游戏": slots.get("interactive_game_types", "未明确"),
                "资料用途": slots.get("reference_material_purpose", "未明确"),
                "其他要求": slots.get("other_requirements", "未明确")
            }
            
            checklist_md = "\n".join([f"- **{k}**: {v}" for k, v in items.items()])
            output_content = (
                f"✅ 已为您更新系统记录。\n\n📝 **当前教学要素核对表：**\n{checklist_md}\n\n"
                f"--- \n老师，请核对以上要素。如果有【未明确】的项目，请告知我以便进一步优化。"
            )
            logger.info("🔧 [自动兜底]: 触发了智能核对表展示")
        # ==========================================
        # 2. 强制清洗 LLM 违规包裹的 Markdown 标签
        # ==========================================
        if "```json" in output_content:
            output_content = output_content.replace("```json\n", "").replace("```json", "").replace("\n```", "").replace("```", "").strip()
        elif "```" in output_content:
            output_content = output_content.replace("```", "").strip()

        # ==========================================
        # 3. 核心拦截层：精准提取系统信令 (JSON)
        # ==========================================
        start_idx = output_content.find('{')
        end_idx = output_content.rfind('}') + 1
        
        parsed_json_event = None
        if start_idx != -1 and end_idx > start_idx:
            try:
                parsed_json_event = json.loads(output_content[start_idx:end_idx])
            except json.JSONDecodeError:
                pass

        if parsed_json_event and "event" in parsed_json_event:
            logger.info(f"⚡ 成功捕获工具返回信令: {parsed_json_event['event']}")
            db.add(SessionHistory(session_id=session_id, role="user", content=req.message))
            intent = parsed_json_event.get("data", {}).get("intent", "执行系统工具调度")
            db.add(SessionHistory(session_id=session_id, role="assistant", content=f"*(已通过后台执行操作：{intent})*"))
            db.commit()

            db.refresh(session)
            parsed_json_event.setdefault("data", {})["slots_update"] = session.extracted_slots or {}
            return parsed_json_event

        # ==========================================
        # 4. 处理纯文本聊天 (CHAT_TEXT)
        # ==========================================
        # 判断要素是否齐全（如果是齐的，大模型会自动带上确认引导语，如果没有，我们做个保险）
        db.refresh(session)
        current_slots = session.extracted_slots or {}
        
        # 记录对话历史
        db.add(SessionHistory(session_id=session_id, role="user", content=req.message))
        db.add(SessionHistory(session_id=session_id, role="assistant", content=output_content))
        db.commit()

        return {
            "event": "CHAT_TEXT", 
            "data": {
                "chunk": output_content, 
                "slots_update": current_slots, 
                "is_done": True
            }
        }

    except Exception as e:
        db.rollback()
        logger.error(f"❌ 中枢分发异常: {e}")
        return {"event": "ERROR", "data": {"message": f"中枢分发异常: {str(e)}"}}
    finally:
        db.close()
