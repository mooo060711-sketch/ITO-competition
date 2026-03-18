from sqlalchemy.orm import Session
from typing import Dict, Optional

# 🌟 引入 ORM 模型
from src.tools.SQL import TempImage

def execute_bind_and_check_next(
    session_id: str, 
    image_id: str, 
    is_discarded: bool, 
    target_page: Optional[int], 
    sys_coordinate: Optional[str], 
    db: Session
) -> Dict:
    """
    执行图片坐标落库或废弃，并检测是否还有下一张待定图片。
    """
    
    # ==========================================
    # 1. 更新当前图片的状态 (使用 ORM 方式)
    # ==========================================
    img_record = db.query(TempImage).filter(
        TempImage.image_id == image_id, 
        TempImage.session_id == session_id
    ).first()
    
    if img_record:
        if is_discarded:
            img_record.target = 0 # 废弃
        else:
            img_record.target_page = target_page
            img_record.position_code = sys_coordinate
            
    db.commit()

    # ==========================================
    # 2. While 循环检测：寻找下一个待填槽图片
    # ==========================================
    # 找出一张 target=1 且 position_code 为空的图片
    next_pending_img = db.query(TempImage).filter(
        TempImage.session_id == session_id,
        TempImage.target == 1,
        TempImage.position_code.is_(None)
    ).first()

    # 统计剩余待定总数
    pending_count = db.query(TempImage).filter(
        TempImage.session_id == session_id,
        TempImage.target == 1,
        TempImage.position_code.is_(None)
    ).count()

    if next_pending_img:
        # 还有空坐标图片，因为是 ORM 对象，直接点取属性绝对安全
        return {
            "has_next": True,
            "next_image": {
                "image_id": next_pending_img.image_id,
                "url": next_pending_img.url,
                "prompt": next_pending_img.image_prompt
            },
            "pending_count": pending_count
        }
    else:
        # 没有待定图片了，放行流水线
        return {"has_next": False}
