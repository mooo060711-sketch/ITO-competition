import os
import sys
import json
import logging
import asyncio
import pathlib
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import desc
from typing import List, Optional

# 1. 🌟 绝对路径与环境注入
CONFIG_PATH = pathlib.Path(__file__).parent.parent / "config.yaml"
OUTPUT_BASE = pathlib.Path(__file__).parent.parent / "outputs" / "games"

# 2. 🌟 修正包搜索路径
_api_dir = os.path.dirname(os.path.abspath(__file__))
_root_dir = os.path.dirname(os.path.dirname(_api_dir))
if _root_dir not in sys.path:
    sys.path.insert(0, _root_dir)

# 3. 🌟 直接引入业务组件 (不需要再做任何 monkey patch)
from src.tools.SQL import SessionContext, CoursewareVersion
from src.tools.database import get_db
from src.tools.search import search_official_curriculum_skill, search_uploaded_materials_skill
from src.rag.game.game_engine import GameEngine, GameType

logger = logging.getLogger("game_api")
router = APIRouter(prefix="/api/v1/extensions")

class BatchGameRequest(BaseModel):
    session_id: str
    game_types: Optional[List[str]] = Field(default=None)

@router.post("/game/batch_generate")
async def batch_generate_games(req: BatchGameRequest, db: Session = Depends(get_db)):
    # 1. 会话校验
    session_record = db.query(SessionContext).filter_by(session_id=req.session_id).first()
    if not session_record:
        raise HTTPException(status_code=404, detail="会话不存在")
        
    sanitized_id = req.session_id.replace("-", "_")
    slots = session_record.extracted_slots or {}
    theme = slots.get("theme", "未命名主题")
    key_points = slots.get("key_points", "未明确")
    
    # 2. RAG 检索逻辑
    search_query = f"{theme} {key_points}"
    try:
        official_raw = await asyncio.to_thread(search_official_curriculum_skill.invoke, {"query": search_query})
        user_material_raw = await asyncio.to_thread(search_uploaded_materials_skill.invoke, {
            "query": search_query, 
            "session_id": sanitized_id 
        })
        
        def safe_extract(raw):
            if isinstance(raw, str) and raw.strip().startswith('{'):
                try: return json.loads(raw).get('summary', str(raw))
                except: return raw
            return str(raw)

        combined_context = f"官方：\n{safe_extract(official_raw)}\n\n用户：\n{safe_extract(user_material_raw)}"
    except Exception as e:
        logger.warning(f"RAG 检索失败: {e}")
        combined_context = f"主题：{theme}\n重难点：{key_points}"

    # 3. 引擎初始化
    try:
        engine = GameEngine(config_path=str(CONFIG_PATH)) 
    except Exception as e:
        logger.error(f"引擎加载失败: {e}")
        raise HTTPException(status_code=500, detail=f"配置文件异常: {e}")

    # 4. 安全的枚举转换与过滤
    valid_types = [gt.value for gt in GameType]
    
    if req.game_types and isinstance(req.game_types, list):
        target_types = []
        for t in req.game_types:
            t_clean = str(t).lower().strip()
            if t_clean in valid_types:
                target_types.append(GameType(t_clean))
        
        if not target_types:
            target_types = [GameType.QUIZ, GameType.MATCHING, GameType.SORTING]
    else:
        target_types = [GameType.QUIZ, GameType.MATCHING, GameType.SORTING]

    # 5. 生成逻辑
    session_output_dir = os.path.join(OUTPUT_BASE, req.session_id)
    os.makedirs(session_output_dir, exist_ok=True)

    results_manifest = []

    for gt in target_types:
        try:
            res = await asyncio.to_thread(
                engine.generate,
                knowledge_topic=theme,
                game_type=gt,
                teacher_requirement=f"围绕【{key_points}】设计。",
                count=5,
                context=combined_context,
                output_dir=session_output_dir
            )
            
            html_path = res.get("html_path", "")
            if html_path:
                normalized_path = html_path.replace("\\", "/")
                filename = os.path.basename(normalized_path)
                web_url = f"/outputs/games/{req.session_id}/{filename}"
            else:
                web_url = ""

            results_manifest.append({
                "type": gt.value,
                "title": res.get("title", f"{theme} - {gt.value}"),
                "path": html_path,
                "url": web_url
            })
            
        except Exception as inner_e:
            import traceback
            logger.error(f"单款游戏 ({gt.value}) 失败: {inner_e}\n{traceback.format_exc()}")
            continue

    # 6. 版本管理
    prev_version = db.query(CoursewareVersion).filter_by(session_id=req.session_id).order_by(desc(CoursewareVersion.created_at)).first()
    
    new_version = CoursewareVersion(
        session_id=req.session_id,
        version_note=f"成功生成 {len(results_manifest)} 款互动游戏",
        outline_snapshot=session_record.baidu_outline_str,
        plan_snapshot=session_record.lesson_plan_str,
        ppt_path=session_record.ppt_path, 
        game_path_snapshot=results_manifest,
        image_layout_snapshot=prev_version.image_layout_snapshot if prev_version and hasattr(prev_version, 'image_layout_snapshot') else []
    )
    db.add(new_version)
    db.commit()
    
    return {
        "event": "BATCH_GAME_GENERATED",
        "data": {
            "session_id": req.session_id,
            "games": results_manifest,
            "current_version_id": new_version.version_id
        }
    }