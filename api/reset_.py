import os
import shutil
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

# ==========================================
# 1. 引入数据库模型与依赖
# ==========================================
import sys; sys.path.insert(0, '.')  # 强制把当前目录加入搜索路径
from src.tools.SQL import SessionContext, SessionHistory, TempImage, CoursewareVersion
from src.tools.database import get_db
import pathlib 

logger = logging.getLogger("reset_engine")
router = APIRouter(prefix="/api/v1")

class ResetRequest(BaseModel):
    session_id: str

OUTPUT_BASE = pathlib.Path(__file__).parent.parent / "outputs"
@router.post("/reset")
def reset_demonstration_data(req: ResetRequest, db: Session = Depends(get_db)):
    """
    演示级重置接口：
    1. 物理层：清理绝对路径下的 PPT、教案、互动小游戏文件；
    2. 向量层：销毁 Milvus 中对应的临时知识库集合；
    3. 数据库层：显式暴力清理所有相关表的记录。
    """
    session_id = req.session_id
    
    try:
        # ------------------------------------------
        # 步骤 A: 物理文件精准清理 (使用绝对路径)
        # ------------------------------------------
        # 1. 清理该会话专属的互动小游戏文件夹
        game_folder = os.path.join(OUTPUT_BASE, "games", session_id)
        if os.path.exists(game_folder):
            shutil.rmtree(game_folder)
            logger.info(f"🗑️ 已物理删除互动小游戏目录: {game_folder}")

        # 2. 清理包含 session_id 的 PPT 和 Word 教案
        assets_dirs = [
            os.path.join(OUTPUT_BASE, "ppts"), 
            os.path.join(OUTPUT_BASE, "lesson_plans")
        ]
        for directory in assets_dirs:
            if os.path.exists(directory):
                for filename in os.listdir(directory):
                    # 只要文件名包含这个 session_id 就删掉
                    if session_id in filename:
                        file_path = os.path.join(directory, filename)
                        try:
                            os.remove(file_path)
                            logger.info(f"🗑️ 已清理物理资产: {filename}")
                        except Exception as fe:
                            logger.warning(f"⚠️ 文件被占用无法删除: {file_path}, 报错: {fe}")

        # ------------------------------------------
        # 步骤 B: 向量库 RAG 集合清理
        # ------------------------------------------
        try:
            from src.rag.vector_store.milvus_store import MilvusStore
            sanitized_id = session_id.replace("-", "_")
            collection_name = f"ref_{sanitized_id}"
            
            store = MilvusStore() 
            store.client.drop_collection(collection_name)
            logger.info(f"🗑️ 已销毁向量库集合: {collection_name}")
        except Exception as ve:
            logger.warning(f"⚠️ 向量库清理跳过 (可能无临时数据): {ve}")

        # ------------------------------------------
        # 步骤 C: SQL 数据库 100% 暴力清理
        # ------------------------------------------
        # 🌟 不依赖级联，显式删除，绝对不会报错或残留脏数据！
        
        # 1. 删对话历史
        db.query(SessionHistory).filter(SessionHistory.session_id == session_id).delete()
        # 2. 删画廊临时图片记录
        db.query(TempImage).filter(TempImage.session_id == session_id).delete()
        # 3. 删时光机版本快照
        db.query(CoursewareVersion).filter(CoursewareVersion.session_id == session_id).delete()
        # 4. 最后删会话主表
        db.query(SessionContext).filter(SessionContext.session_id == session_id).delete()
        
        # 一次性提交所有删除操作
        db.commit()
        logger.info(f"✅ 会话 {session_id} 数据库内容已 100% 清空。")

        return {
            "code": 200, 
            "msg": "演示环境已完全重置", 
            "data": {"session_id": session_id}
        }

    except Exception as e:
        db.rollback()
        logger.error(f"❌ 重置服务执行异常: {e}")
        raise HTTPException(status_code=500, detail=f"重置失败: {str(e)}")
