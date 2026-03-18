import os
import time
import tempfile
import logging
import re  # 🌟 新增正则库用于解析页数
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import desc
from pydantic import BaseModel, Field
from typing import Dict, Any

# ==========================================
# 1. 引入数据库模型与依赖
# ==========================================
import sys; sys.path.insert(0, '.')  # 强制把当前目录加入搜索路径
from src.tools.SQL import SessionContext, CoursewareVersion, TempImage
from src.tools.database import get_db

# ==========================================
# 2. 引入业务模块与精修引擎
# ==========================================
from src.tools.word import markdown_to_docx, generate_word_lesson_plan_from_ppt
from src.tools.generate import generate_ppt
from src.tools.note import parse_markdown_for_notes, inject_speaker_notes
from src.tools.modify import agent_refine_courseware, agent_refine_lesson_plan

logger = logging.getLogger("refine_engine")

# ==========================================
# 3. 数据契约
# ==========================================
class RefineRequest(BaseModel):
    session_id: str
    target_type: str = Field(..., description="要精修的目标：'outline' (大纲) 或 'lesson_plan' (教案)")
    user_prompt: str = Field(..., description="用户的局部修改指令")

class RefineResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: Dict[str, Any] 

# ==========================================
# 4. 路由与核心业务逻辑
# ==========================================
router = APIRouter()

@router.post("/api/v1/chat/refine", response_model=RefineResponse)
def refine_content(request: RefineRequest, db: Session = Depends(get_db)):
    session_id = request.session_id
    
    try:
        # 获取会话与最新版本快照
        session_context = db.query(SessionContext).filter_by(session_id=session_id).first()
        if not session_context:
            raise HTTPException(status_code=404, detail="Session not found")
            
        latest_version = db.query(CoursewareVersion).filter_by(session_id=session_id).order_by(desc(CoursewareVersion.created_at)).first()

        final_outline = ""
        final_plan = ""
        final_layout_str = [] 
        new_docx_path = session_context.lesson_plan_path
        new_ppt_path = session_context.ppt_path 
        
        # ==========================================
        # 🛤️ 轨道 A：局部微调教案
        # ==========================================
        if request.target_type == "lesson_plan":
            if not session_context.lesson_plan_str:
                raise HTTPException(status_code=400, detail="教案为空，无法精修")
                
            refine_result = agent_refine_lesson_plan(session_context.lesson_plan_str, request.user_prompt)
            if not refine_result or "lesson_plan_str" not in refine_result:
                raise Exception("教案精修引擎返回异常")

            new_plan_text = refine_result["lesson_plan_str"]
            
            output_dir = "./output_docs"
            if not os.path.exists(output_dir): os.makedirs(output_dir)
            new_docx_path = os.path.join(output_dir, f"精修教案_{session_id}_{int(time.time())}.docx")
            markdown_to_docx(new_plan_text, new_docx_path) 
            
            final_outline = session_context.baidu_outline_str
            final_plan = new_plan_text
            final_layout_str = latest_version.image_layout_snapshot if latest_version else []

        # ==========================================
        # 🛤️ 轨道 B：全链路重构 (加入页数熔断)
        # ==========================================
        elif request.target_type == "outline":
            if not session_context.baidu_outline_str:
                raise HTTPException(status_code=400, detail="大纲为空，无法精修")
                
            refine_result = agent_refine_courseware(session_context.baidu_outline_str, request.user_prompt)
            if not refine_result or "baidu_outline_str" not in refine_result:
                raise Exception("大纲精修引擎返回异常")
                
            new_outline_text = refine_result["baidu_outline_str"]
            theme = refine_result.get("theme", "课件重构")
            
            # 🌟🌟🌟 核心新增：页数狂飙硬性熔断拦截 🌟🌟🌟
            slots = session_context.extracted_slots or {}
            page_range_str = str(slots.get("page_range", "10"))
            # 提取目标数字 (例如从 "25页" 中提取 25)
            target_match = re.search(r'\d+', page_range_str)
            target_pages = int(target_match.group()) if target_match else 10
            
            # 允许 120% 的浮动误差，并加上 2 页的保底缓冲以防基数太小
            max_allowed_pages = int(target_pages * 1.2) + 2 
            
            # 使用正则精准统计 Markdown 中的页面数量 (匹配 `* 页面 x` 或 `- 第 x 页`)
            generated_page_count = len(re.findall(r'^\s*[-*]\s*(?:页面|第.*?页)', new_outline_text, re.MULTILINE))
            if generated_page_count == 0:
                # 降级统计：直接数 "页面" 关键词出现的次数
                generated_page_count = new_outline_text.count("页面")
                
            if generated_page_count > max_allowed_pages:
                logger.warning(f"🚨 页数溢出拦截: 目标 {target_pages}页, 实际生成 {generated_page_count}页")
                raise Exception(
                    f"AI 拓展过度导致页数严重超标！\n"
                    f"目标限制：{max_allowed_pages} 页以内\n"
                    f"实际生成：{generated_page_count} 页\n"
                    f"💡 建议：请在精修要求中明确加上“保持原页数”或“删减部分内容”。"
                )
            # 🌟🌟🌟 熔断逻辑结束 🌟🌟🌟

            # 失效旧图片坐标
            db.query(TempImage).filter_by(session_id=session_id).update({"target_page": -1, "position_code": None})
            db.flush() 
            
            # 生成新 PPT
            output_dir_ppt = "./output_ppts"
            if not os.path.exists(output_dir_ppt): os.makedirs(output_dir_ppt)
            raw_ppt_path = os.path.abspath(os.path.join(output_dir_ppt, f"重构课件_{session_id}_{int(time.time())}.pptx"))
            
            gen_result = generate_ppt(
                outline_data={"baidu_outline_str": new_outline_text, "theme": theme},
                query_id=int(time.time()), chat_id=int(time.time()),
                query=f"重写大纲生成新课件", save_filename=raw_ppt_path
            )
            
            if gen_result.get("status") != "success":
                raise Exception(f"PPT 生成失败: {gen_result.get('message')}")
            new_ppt_path = gen_result["local_file"]

            # 注入演讲者备注
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix=".md") as temp_md:
                temp_md.write(new_outline_text)
                temp_md_path = temp_md.name
            try:
                notes_mapping = parse_markdown_for_notes(temp_md_path)
                inject_speaker_notes(ppt_path=new_ppt_path, notes_mapping=notes_mapping, output_path=new_ppt_path)
            finally:
                if os.path.exists(temp_md_path): os.remove(temp_md_path)

            # 同步生成新教案
            class IntentSlotsAdapter:
                def __init__(self, s):
                    self.theme = s.get("theme", "未命名主题")
                    self.teaching_objectives = s.get("teaching_objectives", "未设置目标")
                    self.audience = s.get("audience", "常规受众")
                    self.key_points = s.get("key_points", "未明确重难点")
                    self.required_knowledge = s.get("required_knowledge", "无")
                    self.other_requirements = s.get("other_requirements", "无")
            
            adapter = IntentSlotsAdapter(session_context.extracted_slots or {})
            plan_result = generate_word_lesson_plan_from_ppt(adapter, new_ppt_path)
            
            final_outline = new_outline_text
            final_plan = plan_result["lesson_plan_str"]
            new_docx_path = plan_result["docx_filepath"]
            final_layout_str = [] 

        # ==========================================
        # 5. 📸 保存版本快照并更新实时路径
        # ==========================================
        new_version = CoursewareVersion(
            session_id=session_id,
            version_note=f"精修了 {request.target_type}",
            outline_snapshot=final_outline,
            plan_snapshot=final_plan,
            image_layout_snapshot=final_layout_str,
            lesson_plan_path_snapshot=new_docx_path,
            ppt_path=new_ppt_path, 
            game_path_snapshot=session_context.game_path 
        )
        db.add(new_version)
        
        # 更新 SessionContext 实时状态
        session_context.baidu_outline_str = final_outline
        session_context.lesson_plan_str = final_plan
        session_context.lesson_plan_path = new_docx_path
        session_context.ppt_path = new_ppt_path 
            
        db.commit()

        return RefineResponse(
            data={
                "target_type": request.target_type,
                "refined_text": final_outline if request.target_type == "outline" else final_plan,
                "docx_filepath": new_docx_path,
                "ppt_filepath": new_ppt_path,
                "current_version_id": new_version.version_id
            }
        )
    except Exception as e:
        db.rollback()
        logger.error(f"❌ 精修服务执行失败: {e}")
        raise HTTPException(status_code=500, detail=str(e))
