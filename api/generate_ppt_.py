import os
import time
import tempfile
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Dict, Any

import pathlib
import sys; sys.path.insert(0, '.')  # 强制把当前目录加入搜索路径
from src.tools.SQL import SessionContext, CoursewareVersion 
from src.tools.database import get_db
from src.tools.generate import generate_ppt 
from src.tools.note import parse_markdown_for_notes, inject_speaker_notes 

BASE_OUTPUT_DIR = pathlib.Path(__file__).parent.parent / "outputs"
PPT_OUTPUT_DIR = os.path.join(BASE_OUTPUT_DIR, "ppts")

logger = logging.getLogger("ppt_assembly_hub")
router = APIRouter()

class GeneratePPTRequest(BaseModel):
    session_id: str
    theme: str = "默认课题标题"
    tpl_id: int 

class GeneratePPTResponse(BaseModel):
    code: int = 200
    msg: str = "success"
    data: Dict[str, Any]

# ==========================================
# 🌟 新增：后台静默 PPT 转 PDF 引擎 (Windows 专用)
# ==========================================
def pptx_to_pdf_windows(ppt_path: str, pdf_path: str) -> bool:
    """
    利用 comtypes 在后台调用 PowerPoint 将 .pptx 文件转换为 .pdf。
    要求运行环境中已安装 Microsoft Office 或 WPS。
    """
    # 确保文件路径是绝对路径
    ppt_path = os.path.abspath(ppt_path)
    pdf_path = os.path.abspath(pdf_path)
    
    try:
        import comtypes.client
        # 在 FastAPI 的异步/多线程环境中，必须为每个线程初始化 COM
        comtypes.CoInitialize() 
        
        powerpoint = comtypes.client.CreateObject("Powerpoint.Application")
        # 隐藏 PowerPoint 窗口，实现真正的“静默”后台执行
        presentation = powerpoint.Presentations.Open(ppt_path, WithWindow=False)
        
        # 使用 PowerPoint 的原生常量来指定 PDF 格式 (32)
        presentation.SaveAs(pdf_path, 32) 
        presentation.Close()
        logger.info(f"✅ PPT 已成功转换为 PDF: {pdf_path}")
        return True
    except Exception as e:
        logger.error(f"⚠️ PPT 转 PDF 失败，可能是未安装 Office/WPS，或文件被占用: {e}")
        return False
    finally:
        # 确保 COM 接口被正确释放
        try:
            powerpoint.Quit()
            del powerpoint
        except:
            pass
        try:
            comtypes.CoUninitialize()
        except:
            pass

@router.post("/api/v1/ppt", response_model=GeneratePPTResponse)
def assemble_ppt(request: GeneratePPTRequest, db: Session = Depends(get_db)):
    session_id = request.session_id
    try:
        session_context = db.query(SessionContext).filter_by(session_id=session_id).first()
        if not session_context:
            raise HTTPException(status_code=404, detail="未找到会话记录")
            
        db.refresh(session_context) 
        
        logger.info(f"DEBUG: 接收到的模板ID -> {request.tpl_id}, 类型 -> {type(request.tpl_id)}")
        try:
            safe_tpl_id = int(request.tpl_id)
        except (ValueError, TypeError):
            logger.warning("模板ID转换失败，回退至默认模板 0")
            safe_tpl_id = 0

        real_theme = request.theme
        if (real_theme == "默认课题标题" or not real_theme) and session_context.extracted_slots:
            real_theme = session_context.extracted_slots.get("theme", real_theme)

        baidu_outline = session_context.baidu_outline_str
        if not baidu_outline:
            raise HTTPException(status_code=400, detail="大纲数据为空，无法生成 PPT")

        if not os.path.exists(PPT_OUTPUT_DIR): 
            os.makedirs(PPT_OUTPUT_DIR, exist_ok=True)
            
        ppt_filename = f"课件_{session_id}_{int(time.time())}.pptx"
        raw_ppt_path = os.path.join(PPT_OUTPUT_DIR, ppt_filename)
        
        outline_data = {
            "baidu_outline_str": baidu_outline,
            "theme": real_theme,
            "tpl_id": safe_tpl_id 
        }
        
        logger.info(f"🚀 正在使用模板 {safe_tpl_id} 渲染《{real_theme}》...")
        gen_result = generate_ppt(
            outline_data=outline_data,
            query_id=int(time.time()),
            chat_id=int(time.time()),
            query=f"生成关于《{real_theme}》的课件",
            save_filename=raw_ppt_path
        )
        
        if gen_result.get("status") != "success":
            raise Exception(f"底层渲染引擎报错: {gen_result.get('message')}")
            
        final_ppt_path = gen_result.get("local_file", raw_ppt_path)
        
        with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', delete=False, suffix=".md") as temp_md:
            temp_md.write(baidu_outline)
            temp_md_path = temp_md.name
        try:
            notes_mapping = parse_markdown_for_notes(temp_md_path) 
            inject_speaker_notes(ppt_path=final_ppt_path, notes_mapping=notes_mapping, output_path=final_ppt_path)
        finally:
            if os.path.exists(temp_md_path): os.remove(temp_md_path)

        filename = os.path.basename(final_ppt_path)
        ppt_web_url = f"/outputs/ppts/{filename}?t={int(time.time())}"

        # ==========================================
        # 🌟 核心渲染：尝试生成 PDF 供网页完美内嵌预览
        # ==========================================
        pdf_filename = filename.replace(".pptx", ".pdf")
        pdf_path = os.path.join(PPT_OUTPUT_DIR, pdf_filename)
        
        logger.info("⏳ 正在后台转换 PDF 以供网页预览...")
        is_pdf_ready = pptx_to_pdf_windows(final_ppt_path, pdf_path)

        if is_pdf_ready:
            pdf_web_url = f"/outputs/ppts/{pdf_filename}?t={int(time.time())}"
            # 成功则显示沉浸式 PDF 阅读器，带下载 PPT 源文件的顶栏
            preview_html = f"""
            <div style="display:flex; flex-direction:column; width:100%; height:100%; min-height:550px; border-radius:12px; overflow:hidden; border:1px solid #e2e8f0; background:white;">
                <div style="display:flex; justify-content:space-between; align-items:center; padding:12px 20px; background:#f8fafc; border-bottom:1px solid #e2e8f0; flex-shrink:0;">
                    <div style="display:flex; align-items:center; gap:10px;">
                        <span style="font-size:20px;">📊</span>
                        <span style="font-weight:600; color:#1e293b; font-size:15px;">《{real_theme}》</span>
                    </div>
                    <a href="{ppt_web_url}" target="_blank" style="text-decoration:none; display:flex; align-items:center; gap:6px; padding:8px 16px; background:linear-gradient(135deg, #6366f1, #4f46e5); color:white; border-radius:8px; font-weight:500; font-size:13px; box-shadow:0 4px 10px rgba(99,102,241,0.2); transition:all 0.2s;">
                        ⬇️ 下载 .pptx 源文件
                    </a>
                </div>
                <iframe src="{pdf_web_url}#toolbar=0" style="width:100%; flex-grow:1; border:none; min-height:500px;"></iframe>
            </div>
            """
        else:
            # 失败则自动降级为美观的下载提示卡片
            preview_html = f"""
            <div style="display:flex; flex-direction:column; align-items:center; justify-content:center; height:100%; min-height:480px; background:linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%); border-radius:16px; border: 1px solid #e2e8f0; text-align:center; padding: 40px;">
                <div style="font-size:64px; margin-bottom:20px;">📊</div>
                <h3 style="color:#1e293b; font-size:22px; font-weight:700; margin:0 0 12px 0;">《{real_theme}》</h3>
                <p style="color:#10b981; font-weight:600; font-size:16px; margin:0 0 16px 0;">✨ 课件渲染已完成 (Template ID: {safe_tpl_id}) ✨</p>
                <p style="color:#f59e0b; font-size:13px; max-width:320px; margin-bottom:20px;">(PDF 预览转换失败，请直接下载源文件)</p>
                <a href="{ppt_web_url}" target="_blank" style="padding:14px 32px; background:linear-gradient(135deg, #6366f1, #4f46e5); color:white; border-radius:12px; font-weight:600; text-decoration:none;">立即下载演示课件</a>
            </div>
            """

        session_context.ppt_path = final_ppt_path
        
        new_version = CoursewareVersion(
            session_id=session_id,
            version_note=f"应用模板[{safe_tpl_id}]渲染《{real_theme}》",
            ppt_path=final_ppt_path,
            outline_snapshot=baidu_outline
        )
        db.add(new_version)
        db.commit() 

        return GeneratePPTResponse(
            data={
                "session_id": session_id,
                "ppt_path": final_ppt_path,
                "preview_html": preview_html,
                "message": f"《{real_theme}》PPT 渲染成功"
            }
        )

    except Exception as e:
        db.rollback()
        logger.error(f"❌ PPT 装配崩溃: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
