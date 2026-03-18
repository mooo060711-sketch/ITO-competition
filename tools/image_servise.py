import uuid
import json
from sqlalchemy import desc
from src.tools.SQL import TempImage
from src.tools.database import SessionLocal
from sqlalchemy import desc
from src.tools.image import generate_image_by_desc

def handle_image_business_logic(**kwargs) -> str:
    db = SessionLocal()
    session_id = kwargs.get("session_id", "default")
    action_type = kwargs.get("action_type")
    image_id = kwargs.get("image_id")
    
    try:
        # --- 动作执行：更新位置或创建新图 ---
        if image_id:
            img_record = db.query(TempImage).filter_by(image_id=image_id, session_id=session_id).first()
            if img_record:
                if kwargs.get("is_discarded", False):
                    img_record.target = 0 # 用户明确不要这张图，设为失效
                else:
                    target_page = kwargs.get("target_page")
                    image_index = kwargs.get("image_index")
                    if target_page and image_index:
                        img_record.position_code = f"p{target_page}_{image_index}"
                        img_record.target_page = target_page
                db.commit()
        
        elif action_type == "ai_generate":
            final_url = generate_image_by_desc(kwargs.get("content"), style=kwargs.get("style"))
            new_record = TempImage(
                image_id=f"img_{uuid.uuid4().hex[:6]}", session_id=session_id, url=final_url,
                image_prompt=kwargs.get("content"), target=1, position_code=None
            )
            db.add(new_record)
            db.commit()

        # --- 🌟 审计扫描 (XiaoXiaoLe) ---
        pending = db.query(TempImage).filter(
            TempImage.session_id == session_id,
            TempImage.target == 1,
            TempImage.position_code == None
        ).all()
        
        if pending:
            # 还有图没放好，取出第一张继续追问
            next_img = pending[0]
            return json.dumps({
                "event": "IMAGE_PLACEMENT_CONTINUE",
                "data": {
                    "image_id": next_img.image_id,
                    "url": next_img.url,
                    "message": f"📷 图片已就绪。老师，请问这张图片（ID:{next_img.image_id}）要放在第几页的哪个位置？（目前还有 {len(pending)} 张待处理）"
                }
            }, ensure_ascii=False)
        else:
            # 队列全空：触发最终确认
            return json.dumps({
                "event": "CHAT_TEXT",
                "data": {"chunk": "✅ 所有待定图片已安放完毕。老师，请问还有其他要插入的图片吗？如果没有了，我就为您执行 PPT 批量写入。", "is_done": True}
            }, ensure_ascii=False)

    except Exception as e:
        db.rollback()
        return json.dumps({"event": "ERROR", "data": {"message": str(e)}})
    finally: db.close()
