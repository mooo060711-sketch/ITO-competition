import json
import logging
import asyncio
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

# 1. 引入数据库与模型
import sys;
import os
_api_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(os.path.dirname(_api_dir))
sys.path.insert(0, _root_dir)  # 强制把项目根目录加入搜索路径
from src.tools.SQL import SessionContext, CoursewareVersion
from src.tools.database import get_db, SessionLocal

# 2. 引入大纲引擎组件
from src.tools.blueprint_engine import prompt, init_courseware_llm, parser

# 3. 引入检索工具
from src.tools.search import search_official_curriculum_skill, search_uploaded_materials_skill

logger = logging.getLogger("outline_stream")
router = APIRouter()

# 🌟 增强请求模型：支持接收前端实时状态
class OutlineRequest(BaseModel):
    session_id: str
    teaching_elements: dict = {} # 接收前端传来的实时要素

@router.post("/api/v1/outline/stream")
async def stream_outline_generation(request: OutlineRequest, db: Session = Depends(get_db)):
    session_id = request.session_id
    
    # 清洗 session_id 以符合 Milvus 规范
    sanitized_id = session_id.replace("-", "_")
    
    # --- A. 获取会话记录 ---
    session_record = db.query(SessionContext).filter_by(session_id=session_id).first()
    if not session_record:
        raise HTTPException(status_code=404, detail="会话不存在")
    
    # ==========================================
    # 🌟 核心防线：以数据库为唯一真相来源 (Single Source of Truth)
    # 强制覆盖前端 UI 可能传来的空壳或脏数据，彻底根除“大纲不匹配”问题
    # ==========================================
    if session_record.extracted_slots and session_record.extracted_slots.get("theme"):
        slots = session_record.extracted_slots
        logger.info("✅ 成功从数据库读取确认后的教学要素，已覆盖前端参数。")
    else:
        slots = request.teaching_elements or {}
        logger.warning("⚠️ 数据库中无教学要素，正尝试使用前端回传的参数。")
    
    theme = slots.get("theme", "未命名主题")
    audience = slots.get("audience", "高中生")
    page_range = slots.get("page_range", "12-15页")
    teaching_objectives = slots.get("teaching_objectives", "未明确")
    key_points = slots.get("key_points", "未明确")
    required_knowledge = slots.get("required_knowledge", "未明确")
    
    # --- B. 执行双源检索 (RAG) ---
    logger.info(f"🔍 正在为主题【{theme}】执行双源检索 (ID: {sanitized_id})...")
    trace_evidence_list = [] 
    
    try:
        official_raw = await asyncio.to_thread(search_official_curriculum_skill.invoke, {"query": theme})
        user_material_raw = await asyncio.to_thread(search_uploaded_materials_skill.invoke, {
            "query": theme, 
            "session_id": sanitized_id
        })
        
        off_data = json.loads(official_raw) if (official_raw and official_raw.strip()) else {}
        usr_data = json.loads(user_material_raw) if (user_material_raw and user_material_raw.strip()) else {}
        
        local_context = f"{off_data.get('answer', '')}\n{off_data.get('evidence_md', '')}".strip()
        user_context = f"{usr_data.get('answer', '')}\n{usr_data.get('source_details', '')}".strip()
        
        if not local_context: local_context = "未找到相关官方课标资料。"
        if not user_context: user_context = "未找到用户上传的相关资料。"
        
        # 组装溯源证据清单
        if off_data.get("answer"):
            trace_evidence_list.append({
                "evidence_id": "kb_01",
                "text": off_data.get("answer"),
                "meta": {"source": "官方教材库", "tag": "official"}
            })
        if usr_data.get("answer"):
            trace_evidence_list.append({
                "evidence_id": "usr_01",
                "text": usr_data.get("answer"),
                "meta": {"source": "教师上传资料", "tag": "user_upload"}
            })
            
    except Exception as e:
        logger.error(f"❌ 检索链路中断: {e}")
        local_context = "检索失败，将基于通用模型知识生成。"
        user_context = "检索失败。"

    # --- C. 定义 SSE 生成器 ---
    async def outline_generator():
        llm = init_courseware_llm()
        chain = prompt | llm | parser
        
        full_content = ""
        
        # ==========================================
        # 🌟 核心防线：为大模型戴上“紧箍咒”，防范参考资料劫持
        # ==========================================
        strict_user_context = (
            f"⚠️ 【绝对指令】：以下提供的【参考资料】仅作为补充背景！\n"
            f"你必须、绝对要以设定的'受众群体'({audience})、'重难点'({key_points})和'目标'({teaching_objectives})为核心骨架生成大纲。\n"
            f"绝不允许照抄参考资料而忽略教学要求！仅提取与【{theme}】相关的内容。\n\n"
            f"【参考资料】:\n{user_context}"
        )
        
        # 将要素精准注入 LLM Prompt 变量
        input_vars = {
            "theme": theme,
            "audience": audience,
            "page_range": page_range,
            "teaching_objectives": teaching_objectives,
            "key_points": key_points,
            "required_knowledge": required_knowledge,
            "teaching_logic": slots.get("teaching_logic", "自动生成思路"),
            "other_requirements": slots.get("other_requirements", "无"),
            "local_kb_context": local_context,
            "user_material_context": strict_user_context # 注入带防御指令的上下文
        }

        try:
            async for chunk in chain.astream(input_vars):
                full_content += chunk
                yield f"data: {json.dumps({'chunk': chunk, 'event': 'OUTLINE_CHUNK'}, ensure_ascii=False)}\n\n"
            
            # --- D. 结束后处理：持久化大纲与版本快照 ---
            chapter_count = full_content.count("\n* ") + (1 if full_content.startswith("* ") else 0)
            page_count = full_content.count("\n  * ") + (1 if full_content.startswith("  * ") else 0)
            total_est = chapter_count + page_count + 2
            
            with SessionLocal() as inner_db:
                inner_session = inner_db.query(SessionContext).filter_by(session_id=session_id).first()
                if inner_session:
                    inner_session.baidu_outline_str = full_content
                    inner_session.total_pages = total_est
                    # 同步更新数据库中的要素状态
                    inner_session.extracted_slots = slots 
                    
                    new_version = CoursewareVersion(
                        session_id=session_id,
                        version_note="AI 首次生成大纲",
                        outline_snapshot=full_content,
                        plan_snapshot="",
                        image_layout_snapshot="[]"
                    )
                    inner_db.add(new_version)
                    inner_db.commit()
                
            yield f"data: {json.dumps({'event': 'OUTLINE_DONE', 'total_pages': total_est, 'trace': trace_evidence_list}, ensure_ascii=False)}\n\n"
            
        except Exception as e:
            logger.error(f"❌ 流式生成中断: {e}")
            yield f"data: {json.dumps({'event': 'ERROR', 'msg': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(outline_generator(), media_type="text/event-stream")
