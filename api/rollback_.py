import os
import time
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import asc
from pydantic import BaseModel
from typing import List, Optional, Dict, Any

# ==========================================
# 1. 引入数据库模型与依赖
# ==========================================
import sys; sys.path.insert(0, '.')  # 强制把当前目录加入搜索路径
from src.tools.SQL import SessionContext, CoursewareVersion, TempImage
from src.tools.database import get_db  

logger = logging.getLogger("rollback_engine")

class RollbackRequest(BaseModel):
    session_id: str
    target_version_id: str 

class RollbackResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: Dict[str, Any] 

router = APIRouter()

@router.post("/api/v1/version/rollback", response_model=RollbackResponse)
def rollback_version(request: RollbackRequest, db: Session = Depends(get_db)):
    """
    版本回滚引擎：
    同时还原大纲、教案（Markdown+Word文件）、PPT（物理文件+预览）及图片坐标。
    """
    session_id = request.session_id
    target_version_id = request.target_version_id
    
    try:
        # 1. 验证会话与目标版本快照
        session_context = db.query(SessionContext).filter_by(session_id=session_id).first()
        target_version = db.query(CoursewareVersion).filter_by(
            version_id=target_version_id, 
            session_id=session_id
        ).first()
        
        if not session_context or not target_version:
            raise HTTPException(status_code=404, detail="会话或版本快照不存在")

        # --- 🌟 步骤 A: 还原数据库核心内容快照 ---
        # 还原大纲文字
        session_context.baidu_outline_str = target_version.outline_snapshot
        
        # 🌟 修复点 1：还原教案文字与物理 Word 路径
        session_context.lesson_plan_str = target_version.plan_snapshot
        session_context.lesson_plan_path = target_version.lesson_plan_path_snapshot
        
        # 🌟 修复点 2：还原 PPT 物理路径
        session_context.ppt_path = target_version.ppt_path 
        session_context.game_path = target_version.game_path_snapshot or []
        
        # --- 🌟 步骤 B: 还原图片排版坐标记录 ---
        layout_snapshot = target_version.image_layout_snapshot if isinstance(target_version.image_layout_snapshot, list) else []
        current_images = db.query(TempImage).filter_by(session_id=session_id).all()
        
        for img in current_images:
            snapshot_record = next((item for item in layout_snapshot if item.get('image_id') == img.image_id), None)
            if snapshot_record:
                img.position_code = snapshot_record.get('position_code')
                img.target_page = snapshot_record.get('target_page') 
            else:
                img.position_code = None 
                img.target_page = -1

        # --- 🌟 步骤 C: 构建还原后的“双资产”预览 HTML ---
         # 1. 基础路径判定
        ppt_path = session_context.ppt_path or ""
        ppt_filename = os.path.basename(ppt_path) if ppt_path else ""
        # 对应的 PDF 路径 (假设生成逻辑是 pptx 同目录下生成同名 pdf)
        pdf_filename = ppt_filename.replace(".pptx", ".pdf")
        pdf_path = ppt_path.replace(".pptx", ".pdf")
        
        ppt_web_url = f"/outputs/ppts/{ppt_filename}?t={int(time.time())}"
        pdf_web_url = f"/outputs/ppts/{pdf_filename}?t={int(time.time())}"

        # 2. 逻辑分支：如果 PDF 存在，则嵌入 PDF 预览；否则降级
        if ppt_path and os.path.exists(pdf_path):
            # PDF 完美预览模式
            ppt_preview_html = f"""
            <div style="width:100%; height:480px; border-radius:12px; overflow:hidden; border:1px solid #e2e8f0; background:white;">
                <iframe src="{pdf_web_url}#toolbar=0" style="width:100%; height:100%; border:none;"></iframe>
            </div>
            """
        elif ppt_path and os.path.exists(ppt_path):
            # 只有 PPT 原件，没有 PDF 预览的降级模式
            ppt_preview_html = f"""
            <div style="display:flex; align-items:center; justify-content:center; height:480px; background:#f8fafc; border:1px solid #e2e8f0; border-radius:12px;">
                <div style="text-align:center;">
                    <p style="color:#64748b;">该版本物理文件已恢复，但未生成 PDF 预览</p>
                    <a href="{ppt_web_url}" target="_blank" style="color:#6366f1; text-decoration:underline;">点击直接下载 PPT</a>
                </div>
            </div>
            """
        else:
            ppt_preview_html = "<div>⚠️ 该版本物理文件已丢失，无法预览。</div>"

        # 2. 🌟 修复点 3：构建教案（Word）的下载与状态标识
        word_filename = os.path.basename(session_context.lesson_plan_path) if session_context.lesson_plan_path else ""
        word_url = f"/outputs/docs/{word_filename}" # 假设教案存在 docs 目录下
        
        # 更新版本号游标
        all_versions = db.query(CoursewareVersion).filter_by(session_id=session_id).order_by(asc(CoursewareVersion.created_at)).all()
        version_ids = [v.version_id for v in all_versions]
        try:
            idx = version_ids.index(target_version_id)
            has_prev, has_next = idx > 0, idx < (len(version_ids) - 1)
        except: has_prev, has_next = False, False

        db.commit()

        # --- 🌟 步骤 D: 返回全量还原数据 ---
        return RollbackResponse(data={
            "version_control": {
                "current_version_id": target_version_id, 
                "has_prev": has_prev, 
                "has_next": has_next
            },
            "courseware_data": {
                "outline_content": session_context.baidu_outline_str,
                "lesson_plan_str": session_context.lesson_plan_str, # 还原 Word 教案 Tab 里的 Markdown 内容
                "ppt_preview_html": ppt_preview_html,           # 还原 PPT 预览 Tab 里的视觉效果
                "docx_filepath": session_context.lesson_plan_path, # 提供给“打包下载”的最新路径
                "ppt_filepath": session_context.ppt_path,
                "games": session_context.game_path,
                "images": [
                    {
                        "image_id": img.image_id, 
                        "url": img.url, 
                        "position_code": img.position_code, 
                        "target_page": img.target_page
                    } for img in current_images if img.position_code
                ]
            }
        })
    except Exception as e:
        db.rollback()
        logger.error(f"❌ 回滚引擎崩溃: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
