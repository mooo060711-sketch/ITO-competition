import os
import zipfile
import io
import logging
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from urllib.parse import quote

# 引入你的 SQL 模型
import sys; sys.path.insert(0, '.')  # 强制把当前目录加入搜索路径
from src.tools.SQL import SessionContext
from src.tools.database import get_db

logger = logging.getLogger("export_engine")
router = APIRouter(prefix="/api/v1")

@router.get("/export/bundle")
def export_courseware_bundle(session_id: str, db: Session = Depends(get_db)):
    """
    一键打包下载接口：
    基于 SessionContext 直接获取当前最新的物理资产路径进行打包。
    """
    # 1. 获取会话实时上下文
    session = db.query(SessionContext).filter_by(session_id=session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="会话不存在")

    # 2. 创建内存 ZIP 流
    zip_buffer = io.BytesIO()
    
    try:
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
            
            # --- A. 打包 PPT 课件 ---
            # 直接使用 SessionContext 中的 ppt_path
            if session.ppt_path and os.path.exists(session.ppt_path):
                zip_file.write(session.ppt_path, arcname="1_教学课件_演示版.pptx")
            else:
                logger.warning(f"PPT 物理文件不存在: {session.ppt_path}")
                
            # --- B. 打包 Word 教案 ---
            # 直接使用 SessionContext 中的 lesson_plan_path
            if session.lesson_plan_path and os.path.exists(session.lesson_plan_path):
                zip_file.write(session.lesson_plan_path, arcname="2_教学设计_精修版.docx")
            else:
                logger.warning(f"教案物理文件不存在: {session.lesson_plan_path}")
                
            # --- C. 打包互动小游戏 ---
            # 直接使用 SessionContext 中的 game_path (List[Dict])
            game_list = session.game_path if isinstance(session.game_path, list) else []
            for i, game_item in enumerate(game_list):
                if isinstance(game_item, dict):
                    g_path = game_item.get("path")
                    # 确保路径存在
                    if g_path and os.path.exists(g_path):
                        filename = os.path.basename(g_path)
                        zip_file.write(g_path, arcname=f"3_互动小游戏/{filename}")

        # 3. 指针重置回开头准备读取
        zip_buffer.seek(0)
        
        # 4. 返回响应
        safe_filename = quote(f"智能教研资料包_{session_id}.zip")
        
        return StreamingResponse(
            zip_buffer,
            media_type="application/zip",
            headers={
                "Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename}"
            }
        )

    except Exception as e:
        logger.error(f"打包导出失败: {str(e)}")
        raise HTTPException(status_code=500, detail="打包过程中出现异常")
