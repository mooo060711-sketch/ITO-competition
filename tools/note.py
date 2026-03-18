import os
import re
import logging
from pptx import Presentation

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("PPT_NOTES_INJECTOR")

def normalize_text(text: str) -> str:
    """
    极致清洗：只保留中文、字母、数字。
    """
    if not text: return ""
    return re.sub(r'[^\u4e00-\u9fa5a-zA-Z0-9]', '', text).lower()

def parse_markdown_for_notes(md_file_path: str) -> dict:
    """
    智能解析：确保只抓取真正带有备注的标题。
    """
    notes_mapping = {}
    current_title = ""
    
    try:
        with open(md_file_path, "r", encoding="utf-8") as f:
            for line in f:
                raw_line = line # 保留原始缩进判断
                line_content = line.strip()
                
                # 匹配标题行 (支持 #, *, -)
                title_match = re.match(r'^(?:#+|\*|-|\d+\.)\s+(.+)', line_content)
                if title_match:
                    title_text = title_match.group(1).strip()
                    # 只有当标题不太长时才作为潜在 Key
                    if len(title_text) < 40:
                        current_title = title_text
                
                # 匹配备注
                elif re.match(r'^>\s*备注[:：]', line_content):
                    note_text = re.sub(r'^>\s*备注[:：]', '', line_content).strip()
                    if current_title:
                        # 存储清洗后的 Key，方便后续模糊匹配
                        clean_key = normalize_text(current_title)
                        notes_mapping[clean_key] = note_text
            
        logger.info(f"✅ 成功提取 {len(notes_mapping)} 条干货备注。")
        return notes_mapping
    except Exception as e:
        logger.error(f"❌ MD 解析失败: {e}")
        return {}

def inject_speaker_notes(ppt_path: str, notes_mapping: dict, output_path: str = None) -> bool:
    """
    模糊匹配注射器：对百度 API 生成的标题进行暴力包含检查。
    """
    if not os.path.exists(ppt_path) or not notes_mapping:
        logger.warning("⚠️ 文件不存在或无备注可注射。")
        return False

    def get_all_text(slide):
        """递归获取幻灯片所有文本块"""
        texts = []
        for shape in slide.shapes:
            if shape.has_text_frame:
                texts.append(shape.text)
            elif hasattr(shape, "shapes"): # 处理组合形状
                for s in shape.shapes:
                    if s.has_text_frame: texts.append(s.text)
        return texts

    try:
        prs = Presentation(ppt_path)
        injected_count = 0
        
        for i, slide in enumerate(prs.slides):
            slide_texts = [normalize_text(t) for t in get_all_text(slide) if t.strip()]
            matched_note = None
            
            # 🌟 核心改进：双向模糊匹配
            for md_title_clean, note_content in notes_mapping.items():
                for st in slide_texts:
                    # 如果 PPT 里的文字包含 MD 标题，或反之
                    if md_title_clean in st or st in md_title_clean:
                        matched_note = note_content
                        break
                if matched_note: break
            
            if matched_note:
                notes_slide = slide.notes_slide
                notes_slide.notes_text_frame.text = f"【教师专属教案】\n{matched_note}"
                injected_count += 1
                logger.info(f"🎯 第 {i+1} 页匹配成功！")
            else:
                logger.warning(f"❓ 第 {i+1} 页未能匹配到备注 (PPT 文本: {slide_texts[:1]})")
                
        save_path = output_path if output_path else ppt_path
        prs.save(save_path)
        logger.info(f"🎉 注射完成！共覆盖 {injected_count} 页。保存至: {save_path}")
        return True
    except Exception as e:
        logger.error(f"❌ 注射崩溃: {e}")
        return False
