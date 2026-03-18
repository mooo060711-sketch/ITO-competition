import os
import time  # 🌟 新增
import logging
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from sqlalchemy import and_
import sys; sys.path.insert(0, '.')  # 强制把当前目录加入搜索路径
from src.tools.database import get_db
from src.tools.SQL import TempImage, CoursewareVersion
# 🌟 引入你的底层物理注入引擎
from src.tools.insert1 import replace_image_by_coordinate_logic

router = APIRouter(prefix="/api/v1/ppt")
logger = logging.getLogger("replace_media")

# ==========================================
# 🌟 新增：后台静默 PPT 转 PDF 引擎 (Windows 专用)
# ==========================================
def pptx_to_pdf_windows(ppt_path: str, pdf_path: str) -> bool:
    """
    利用 comtypes 在后台调用 PowerPoint 将 .pptx 文件转换为 .pdf。
    """
    ppt_path = os.path.abspath(ppt_path)
    pdf_path = os.path.abspath(pdf_path)
    try:
        import comtypes.client
        comtypes.CoInitialize() 
        powerpoint = comtypes.client.CreateObject("Powerpoint.Application")
        presentation = powerpoint.Presentations.Open(ppt_path, WithWindow=False)
        presentation.SaveAs(pdf_path, 32) 
        presentation.Close()
        logger.info(f"✅ PPT 已成功转换为 PDF: {pdf_path}")
        return True
    except Exception as e:
        logger.error(f"⚠️ PPT 转 PDF 失败: {e}")
        return False
    finally:
        try:
            powerpoint.Quit()
            del powerpoint
        except:
            pass
        try:
            comtypes.CoUninitialize()
        except:
            pass

@router.post("/replace_media")
async def replace_media_handler(req: dict, db: Session = Depends(get_db)):
    try:
        session_id = req.get("session_id")
        image_id = req.get("image_id")
        target_page = req.get("target_page")
        pos_code = req.get("position_code")
        is_bulk_confirm = req.get("is_bulk_confirm", False) 

        # --- 第一部分：如果老师发来了位置信息，执行标记 ---
        if image_id and target_page and pos_code:
            img_record = db.query(TempImage).filter_by(image_id=image_id).first()
            if img_record:
                img_record.target = 1
                img_record.target_page = target_page
                img_record.position_code = pos_code
                db.commit()

        # --- 第二部分：批量物理写入触发器 ---
        pending_images = db.query(TempImage).filter(
            and_(
                TempImage.session_id == session_id,
                TempImage.target == 1,
                TempImage.position_code != None
            )
        ).all()

        if is_bulk_confirm and pending_images:
            latest_version = db.query(CoursewareVersion).filter(
                CoursewareVersion.session_id == session_id
            ).order_by(CoursewareVersion.created_at.desc()).first()

            if not latest_version or not latest_version.ppt_path:
                raise HTTPException(status_code=400, detail="未找到有效课件，请先生成 PPT")

            coordinate_mapping = {}
            for img in pending_images:
                page = str(img.target_page)
                if page not in coordinate_mapping: coordinate_mapping[page] = {}
                coordinate_mapping[page][img.position_code] = os.path.abspath(img.url)
                
                img.target = 0 
                img.position_code = None

            # 物理调用引擎 (仅重绘一次)
            final_ppt_path = replace_image_by_coordinate_logic(
                ppt_filepath=latest_version.ppt_path,
                coordinate_mapping=coordinate_mapping
            )
            
            latest_version.ppt_path = final_ppt_path
            db.commit()
            
            # ==========================================
            # 🌟 新增逻辑：将新生成的 PPT 转换为 PDF 并构造 HTML
            # ==========================================
            filename = os.path.basename(final_ppt_path)
            ppt_web_url = f"/outputs/ppts/{filename}?t={int(time.time())}"
            
            pdf_filename = filename.replace(".pptx", ".pdf")
            pdf_path = os.path.join(os.path.dirname(final_ppt_path), pdf_filename)
            
            logger.info("⏳ 正在后台转换 PDF 以供网页预览...")
            is_pdf_ready = pptx_to_pdf_windows(final_ppt_path, pdf_path)

            if is_pdf_ready:
                pdf_web_url = f"/outputs/ppts/{pdf_filename}?t={int(time.time())}"
                preview_html = f"""
                <div style="display:flex; flex-direction:column; width:100%; height:100%; min-height:550px; border-radius:12px; overflow:hidden; border:1px solid #e2e8f0; background:white;">
                    <div style="display:flex; justify-content:space-between; align-items:center; padding:12px 20px; background:#f8fafc; border-bottom:1px solid #e2e8f0; flex-shrink:0;">
                        <div style="display:flex; align-items:center; gap:10px;">
                            <span style="font-size:20px;">📊</span>
                            <span style="font-weight:600; color:#1e293b; font-size:15px;">已插入图片的最新课件</span>
                        </div>
                        <a href="{ppt_web_url}" target="_blank" style="text-decoration:none; display:flex; align-items:center; gap:6px; padding:8px 16px; background:linear-gradient(135deg, #6366f1, #4f46e5); color:white; border-radius:8px; font-weight:500; font-size:13px; box-shadow:0 4px 10px rgba(99,102,241,0.2); transition:all 0.2s;">
                            ⬇️ 下载最新 .pptx 源文件
                        </a>
                    </div>
                    <iframe src="{pdf_web_url}#toolbar=0" style="width:100%; flex-grow:1; border:none; min-height:500px;"></iframe>
                </div>
                """
            else:
                preview_html = f"""
                <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; min-height:480px; background:linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); border-radius:16px; border: 1px solid #e2e8f0; text-align:center; padding: 40px;">
                    <div style="font-size:64px; margin-bottom:20px;">📊</div>
                    <h3 style="color:#1e293b; font-size:22px; font-weight:700; margin:0 0 12px 0;">图片插入已完成</h3>
                    <p style="color:#f59e0b; font-size:13px; max-width:320px; margin-bottom:20px;">(PDF 预览转换失败，请直接下载源文件)</p>
                    <a href="{ppt_web_url}" target="_blank" style="padding:14px 32px; background:linear-gradient(135deg, #6366f1, #4f46e5); color:white; border-radius:12px; font-weight:600; text-decoration:none;">立即下载最新课件</a>
                </div>
                """
            
            return {
                "event": "MEDIA_INJECTION_COMPLETED", 
                "message": "🎉 所有视觉资产已成功批量安放并写入 PPT！",
                # 🌟 把组装好的 HTML 返回给前端
                "data": {"ppt_preview_html": preview_html}
            }

        # --- 第三部分：消消乐接力逻辑 ---
        next_asset = db.query(TempImage).filter(
            and_(
                TempImage.session_id == session_id,
                TempImage.target == 1,
                TempImage.position_code == None
            )
        ).order_by(TempImage.id.asc()).first()

        if next_asset:
            return {
                "event": "IMAGE_PLACEMENT_CONTINUE",
                "data": {
                    "next_image": {"url": next_asset.url, "image_id": next_asset.image_id},
                    "message": f"✅ 已标记。还有资产 {next_asset.image_id} 待处理。"
                }
            }
        else:
            return {"event": "READY_TO_BULK", "message": "所有图片已标注完毕，请确认插入。"}

    except Exception as e:
        db.rollback()
        logger.error(f"❌ 视觉替换逻辑异常: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/pending_images")
async def get_pending_images(session_id: str, db: Session = Depends(get_db)):
    """供画廊读取未处理图片"""
    pending = db.query(TempImage).filter(
        and_(
            TempImage.session_id == session_id,
            TempImage.target == 1,
            TempImage.position_code == None
        )
    ).all()
    return {"data": [{"url": i.url, "image_id": i.image_id} for i in pending]}
