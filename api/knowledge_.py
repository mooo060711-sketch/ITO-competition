import os
import logging
import asyncio
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.rag.service import RAGService  # Ensure src/rag/service.py exists

# 🌟 新增引入数据库组件，用于执行真正的“追加(+=)”记录
from src.tools.SQL import SessionContext
from src.tools.database import SessionLocal

router = APIRouter(prefix="/api/v1/knowledge")
logger = logging.getLogger("knowledge_api")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CONFIG_PATH = os.path.join(BASE_DIR, "config.yaml")

try:
    svc = RAGService(CONFIG_PATH)
except Exception as e:
    logger.error(f"RAG 服务初始化失败: {e}")
    svc = None

@router.post("/upload")
async def upload_and_ingest(
    session_id: str = Form(..., description="用于隔离资料的 Session ID"),
    file: UploadFile = File(..., description="支持 PDF/Word/PPT/图片/视频/音频")
):
    if not svc:
        raise HTTPException(status_code=500, detail="RAG 服务未就绪")

    upload_dir = os.path.join("uploads", session_id)
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, file.filename)
    
    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        logger.error(f"文件保存失败: {e}")
        raise HTTPException(status_code=500, detail="文件写入失败")

    try:
        sanitized_id = session_id.replace("-", "_")
        
        # 1. 触发底层向量库解析 (它会自动读取目录下所有文件，不丢失旧特征)
        result = await asyncio.to_thread(
            svc.engine.ingest_dir,
            dir_path=upload_dir,
            index=f"ref_{sanitized_id}", 
            source_type="uploads",
            session_id=session_id
        )
        
        # ==========================================
        # 🌟 核心修复：在这里实现你没找到的 “+=” 追加逻辑！
        # 强制将每次上传的文件名追加记录到数据库的要素池中，防遗忘
        # ==========================================
        db = SessionLocal()
        try:
            session_record = db.query(SessionContext).filter_by(session_id=session_id).first()
            if session_record:
                slots = session_record.extracted_slots or {}
                
                # 🌟 执行字符串的追加 += 
                old_materials = slots.get("reference_material_purpose", "")
                if old_materials and file.filename not in old_materials:
                    slots["reference_material_purpose"] = f"{old_materials} ；另外新增：{file.filename}"
                else:
                    slots["reference_material_purpose"] = f"已上传资料：{file.filename}"
                    
                # SQLAlchemy JSON 需要重新赋值其副本才能触发更新
                session_record.extracted_slots = slots.copy()
                db.commit()
        except Exception as db_e:
            logger.error(f"数据库追加状态失败: {db_e}")
        finally:
            db.close()

        return {
            "code": 200,
            "msg": "上传并解析成功",
            "data": {
                "session_id": session_id,
                "file_name": file.filename,
                "processed_files": result.get("files", 1),
                "total_chunks": result.get("chunks", 0)
            }
        }
    except Exception as e:
        logger.error(f"解析入库失败: {e}")
        raise HTTPException(status_code=500, detail=f"多模态解析异常: {str(e)}")
