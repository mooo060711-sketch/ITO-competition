import json
from langchain_core.tools import tool
from pydantic import BaseModel, Field
from typing import Optional, Literal
from sqlalchemy.orm import Session
from sqlalchemy import and_

# 🌟 引入数据库依赖与模型逻辑
from src.tools.database import SessionLocal
from src.tools.SQL import TempImage, SessionContext
from src.tools.image_servise import handle_image_business_logic # 执行物理生图或初始落库
from src.tools.image_check import execute_bind_and_check_next # 执行坐标绑定与队列探测

class UnifiedImageIntentInput(BaseModel):
    session_id: str = Field(description="当前的会话 ID", default="default")
    
    action_type: Literal["ai_generate", "use_uploaded_image", "bind_only"] = Field(
        description="动作类型：'ai_generate' (生成新图), 'use_uploaded_image' (复用图), 'bind_only' (仅绑定现有待定图)。"
    )
    content: Optional[str] = Field(description="对图片的描述或生图 Prompt。", default=None)
    
    # 🌟 第一层：生图要素与确认机制
    style: Optional[str] = Field(description="美术风格：写实插画、卡通、3D渲染、水彩等", default="写实插画")
    aspect_ratio: Optional[str] = Field(description="比例：16:9, 4:3, 1:1", default="16:9")
    is_confirmed: bool = Field(description="用户是否已确认生图方案。", default=False)
    clarifying_question: Optional[str] = Field(description="确认话术，引导用户补充细节。", default=None)
    
    # 🌟 第二层：资产位置与消消乐管理
    image_id: Optional[str] = Field(description="当前正在操作的图片 ID。", default=None)
    is_discarded: bool = Field(description="用户是否明确表示‘不要这张图了’。", default=False)
    target_page: Optional[int] = Field(description="目标 PPT 页码。", default=None)
    image_index: Optional[int] = Field(description="位置序号(1-左上, 2-右上, 3-左下, 4-右下)。", default=None)

    # 🌟 第三层：免打扰逻辑（延迟处理）
    defer_placement: bool = Field(description="用户是否明确表示'稍后再放'、'以后再说'或'先跳过排版'。", default=False)

@tool("process_image_intelligence", args_schema=UnifiedImageIntentInput)
def process_image_intelligence(**kwargs) -> str:
    """
    智能视觉资产管理技能：
    1. 负责生图要素拦截：描述模糊或风格缺失时主动追问，确保对齐 UnifiedImageIntentInput。
    2. 支持“稍后处理”意图，开启屏蔽探针的免打扰模式。
    3. 实现视觉资产审计（消消乐）：安放完当前图片后自动扫描数据库，强制追问剩余 target=1 且无坐标的图片。
    4. 资产闭环确认：队列清空后反问老师是否还有其他图，确认后执行 PPT 批量写入逻辑。
    """
    db = SessionLocal()
    session_id = kwargs.get("session_id")
    action_type = kwargs.get("action_type")
    is_confirmed = kwargs.get("is_confirmed", False)
    content = kwargs.get("content")
    image_id = kwargs.get("image_id")
    defer_placement = kwargs.get("defer_placement", False)
    
    try:
        # ==========================================
        # 0. 场景 0：免打扰/延迟排版逻辑
        # ==========================================
        if defer_placement:
            session = db.query(SessionContext).filter(SessionContext.session_id == session_id).first()
            if session:
                session.is_image_placement_deferred = True 
                db.commit()
            return json.dumps({
                "event": "CHAT_TEXT",
                "data": {
                    "chunk": "好的老师，我已经把当前画廊中的图片存入待定资产区，等您处理完大纲后我再提醒您安放。",
                    "is_done": True
                }
            }, ensure_ascii=False)

        # ==========================================
        # 1. 场景 A：生图要素拦截 (确保内容、风格、比例齐全)
        # ==========================================
        if action_type == "ai_generate":
            # 🌟 核心拦截：描述太短或要素缺失
            if not content or len(content.strip()) < 8:
                return json.dumps({
                    "event": "CHAT_TEXT",
                    "data": {
                        "chunk": "老师，为了生图更精准，请您描述一下具体的画面内容（例如：一个正在观察豌豆生长情况的小学生）？",
                        "is_done": True
                    }
                }, ensure_ascii=False)
            
            if not is_confirmed:
                return json.dumps({
                    "event": "CHAT_TEXT",
                    "data": {
                        "chunk": kwargs.get("clarifying_question") or f"已为您构思方案：内容【{content}】，风格【{kwargs.get('style')}】，比例【{kwargs.get('aspect_ratio')}】。可以生成吗？",
                        "is_done": True
                    }
                }, ensure_ascii=False)

        # ==========================================
        # 2. 场景 B：执行物理操作 (生图或坐标更新)
        # ==========================================
        current_op_id = image_id
        # 如果是确认生图，先执行生图逻辑并拿到新 ID
        if action_type == "ai_generate" and is_confirmed:
            gen_res = handle_image_business_logic(**kwargs) 
            current_op_id = json.loads(gen_res).get("data", {}).get("image_id")

        # 构造系统坐标码 (如 p3_2)
        pos_code = None
        if kwargs.get("target_page") and kwargs.get("image_index"):
            pos_code = f"p{kwargs.get('target_page')}_{kwargs.get('image_index')}"

        # 更新当前图片的位置或丢弃状态
        if current_op_id:
            img_record = db.query(TempImage).filter_by(image_id=current_op_id, session_id=session_id).first()
            if img_record:
                if kwargs.get("is_discarded", False):
                    img_record.target = 0 # 软删除
                else:
                    img_record.target_page = kwargs.get("target_page")
                    img_record.position_code = pos_code
                db.commit()

        # ==========================================
        # 3. 🌟 场景 C：视觉资产审计扫描 (消消乐模式核心)
        # ==========================================
        # 扫描数据库：是否存在 target=1 且坐标为空的图片
        pending_assets = db.query(TempImage).filter(
            and_(
                TempImage.session_id == session_id,
                TempImage.target == 1,
                TempImage.position_code == None
            )
        ).order_by(TempImage.id.asc()).all()

        if pending_assets:
            # 还有图没安放，取第一张继续追问
            next_img = pending_assets[0]
            return json.dumps({
                "event": "IMAGE_PLACEMENT_CONTINUE",
                "data": {
                    "image_id": next_img.image_id,
                    "url": next_img.url, # 🌟 回传 URL 供前端画廊和对话框展示
                    "message": f"老师，图片（{next_img.image_prompt}）已就绪。目前还有 {len(pending_assets)} 张待处理，请问这张放在第几页的哪个位置？"
                }
            }, ensure_ascii=False)
        else:
            # 🌟 资产闭环：全部坐标已填满
            return json.dumps({
                "event": "CHAT_TEXT",
                "data": {
                    "chunk": "✅ 画廊中的所有图片已按您的指令在 PPT 中分配完毕。老师，请问还有其他要插入的图片吗？如果没有了，我就开始为您执行批量 PPT 写入。",
                    "is_done": True
                }
            }, ensure_ascii=False)

    except Exception as e:
        db.rollback()
        return json.dumps({"event": "ERROR", "data": {"message": f"视觉调度异常: {str(e)}"}})
    finally:
        db.close()
