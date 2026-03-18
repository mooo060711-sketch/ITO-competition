import json
import logging
from typing import Literal
from sqlalchemy import asc
from langchain_core.tools import tool

# 🌟 引入数据库配置与 SQL 模型
from src.tools.database import SessionLocal
from src.tools.SQL import SessionContext, CoursewareVersion

# 配置日志
logger = logging.getLogger("timeline_recall")

@tool("timeline_recall")
def timeline_recall(session_id: str, direction: Literal["prev", "next"]) -> str:
    """
    时光机检索工具：
    当用户发出“撤销”、“重做”、“回到上一步”、“回退”等指令时触发。
    通过对比当前大纲与历史快照，计算出目标版本的 ID，并下发回滚信令。
    """
    db = SessionLocal()
    try:
        # 1. 加载当前会话上下文
        session_context = db.query(SessionContext).filter(
            SessionContext.session_id == session_id
        ).first()
        
        if not session_context:
            return f"错误：未找到会话 {session_id} 的上下文记录。"

        # 2. 获取该会话的所有历史版本（按时间升序排列）
        versions = db.query(CoursewareVersion).filter(
            CoursewareVersion.session_id == session_id
        ).order_by(asc(CoursewareVersion.created_at)).all()

        if not versions:
            return "当前没有任何历史版本记录，无法执行撤销或重做。"

        # 3. 🌟 核心逻辑：定位当前指针
        # 通过对比当前会话的大纲文本与快照文本，确定当前处于第几个版本
        current_ver_index = -1
        current_outline = session_context.baidu_outline_str or ""
        
        for i, v in enumerate(versions):
            if v.outline_snapshot == current_outline:
                current_ver_index = i
                # 如果有多个相同大纲的版本（虽然罕见），我们取最近匹配的一个，
                # 但由于是顺序遍历，匹配到第一个即锁定。
                break

        # 4. 计算目标索引
        # 如果当前内容不匹配任何版本（例如用户刚做完修改还未生成快照），
        # “回退”默认回到版本列表的最后一个。
        if current_ver_index == -1:
            if direction == "prev":
                target_index = len(versions) - 1
            else:
                return "当前已是最新修改内容，无法重做。"
        else:
            if direction == "prev":
                target_index = current_ver_index - 1
            else:
                target_index = current_ver_index + 1

        # 5. 边界判定
        if target_index < 0:
            return "已经是最早的版本了，无法再撤销。"
        if target_index >= len(versions):
            return "已经是最新版本了，无法再重做。"

        # 6. 提取目标版本信息
        target_version = versions[target_index]
        
        # 7. 构建信令分发
        # 这里不直接执行物理回滚，而是下发信令由前端调度 /api/v1/version/rollback 接口
        # 这样可以保持前端 UI 状态与后端物理数据的一致性
        result_payload = {
            "event": "TIMELINE_ROLLBACK_TRIGGER",
            "data": {
                "target_version_id": target_version.version_id,
                "note": target_version.version_note,
                "message": f"正在为您调取历史快照：{target_version.version_note}"
            }
        }
        
        logger.info(f"会话 {session_id} 时光机跳转: {direction} -> {target_version.version_id}")
        return json.dumps(result_payload, ensure_ascii=False)

    except Exception as e:
        logger.error(f"时光机检索失败: {str(e)}")
        return f"系统繁忙，时光机暂时无法启动: {str(e)}"
    finally:
        db.close()
