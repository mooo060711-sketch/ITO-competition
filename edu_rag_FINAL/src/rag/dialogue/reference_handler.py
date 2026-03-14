"""
参考资料处理器 — 支持 PDF/Word/PPT/图片/视频上传与解析

对应 A04 要求:
  - 2c) 提供参考资料上传功能（支持PDF, Word, PPT, 图片, 视频等）
  - 3b) 对上传的参考资料进行内容解析（文本提取、视频关键帧分析或摘要生成）
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional


class ReferenceHandler:
    """
    参考资料解析器。

    支持格式: PDF, Word(.docx), PPT(.pptx), 图片(png/jpg), 视频(mp4/avi)
    复用现有 parsers 模块的解析能力。

    Example:
        handler = ReferenceHandler(config_path="config.yaml")
        result = handler.parse_file("/path/to/doc.pdf", teacher_note="参照第3章的格式")
        print(result["text"][:500])
    """

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self._cfg = None

    @property
    def cfg(self) -> Dict[str, Any]:
        if self._cfg is None:
            from ..config import load_config
            self._cfg = load_config(self.config_path)
        return self._cfg

    def parse_file(
        self,
        file_path: str,
        teacher_note: str = "",
    ) -> Dict[str, Any]:
        """
        解析单个参考资料文件。

        Args:
            file_path: 文件路径
            teacher_note: 教师对此文件的说明

        Returns:
            {
                "file_name": str,
                "file_type": str,
                "text": str,           # 提取的文本内容
                "metadata": dict,      # 元信息
                "teacher_note": str,
                "parse_method": str,   # 使用的解析方法
            }
        """
        fp = Path(file_path)
        if not fp.exists():
            return {
                "file_name": fp.name,
                "file_type": "unknown",
                "text": f"文件不存在: {file_path}",
                "metadata": {},
                "teacher_note": teacher_note,
                "parse_method": "none",
            }

        ext = fp.suffix.lower()
        file_type = self._detect_type(ext)

        try:
            if file_type == "pdf":
                text, meta, method = self._parse_pdf(fp)
            elif file_type == "word":
                text, meta, method = self._parse_word(fp)
            elif file_type == "pptx":
                text, meta, method = self._parse_pptx(fp)
            elif file_type == "image":
                text, meta, method = self._parse_image(fp)
            elif file_type == "video":
                text, meta, method = self._parse_video(fp)
            elif file_type == "text":
                text = fp.read_text(encoding="utf-8", errors="ignore")
                meta = {"chars": len(text)}
                method = "direct_read"
            else:
                text = f"不支持的文件格式: {ext}"
                meta = {}
                method = "unsupported"
        except Exception as e:
            text = f"解析失败: {e}"
            meta = {"error": str(e)}
            method = "error"

        return {
            "file_name": fp.name,
            "file_type": file_type,
            "text": text,
            "metadata": meta,
            "teacher_note": teacher_note,
            "parse_method": method,
        }

    def parse_files(
        self,
        file_paths: List[str],
        teacher_notes: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """批量解析多个参考资料"""
        notes = teacher_notes or [""] * len(file_paths)
        return [
            self.parse_file(fp, note)
            for fp, note in zip(file_paths, notes)
        ]

    def get_combined_text(self, results: List[Dict[str, Any]], max_chars: int = 10000) -> str:
        """将多个解析结果合并为一段文本（用于LLM输入）"""
        parts = []
        total = 0
        for r in results:
            header = f"[参考资料: {r['file_name']} ({r['file_type']})]"
            if r.get("teacher_note"):
                header += f"\n教师说明: {r['teacher_note']}"
            text = r.get("text", "")[:max_chars - total]
            parts.append(f"{header}\n{text}")
            total += len(text) + len(header)
            if total >= max_chars:
                break
        return "\n\n---\n\n".join(parts)

    # ─────────────────────────────────────────
    # 内部解析方法
    # ─────────────────────────────────────────

    @staticmethod
    def _detect_type(ext: str) -> str:
        mapping = {
            ".pdf": "pdf",
            ".doc": "word", ".docx": "word",
            ".ppt": "pptx", ".pptx": "pptx",
            ".png": "image", ".jpg": "image", ".jpeg": "image",
            ".gif": "image", ".bmp": "image", ".webp": "image",
            ".mp4": "video", ".avi": "video", ".mkv": "video",
            ".mov": "video", ".flv": "video",
            ".mp3": "audio", ".wav": "audio",
            ".txt": "text", ".md": "text", ".csv": "text",
        }
        return mapping.get(ext, "unknown")

    def _parse_pdf(self, fp: Path):
        """PDF解析 — 优先用 pdfplumber，退化到 PyPDF2"""
        try:
            import pdfplumber
            texts = []
            with pdfplumber.open(str(fp)) as pdf:
                for i, page in enumerate(pdf.pages):
                    t = page.extract_text() or ""
                    if t.strip():
                        texts.append(f"[第{i+1}页]\n{t}")
            text = "\n\n".join(texts)
            meta = {"pages": len(texts)}
            return text, meta, "pdfplumber"
        except ImportError:
            pass

        try:
            from PyPDF2 import PdfReader
            reader = PdfReader(str(fp))
            texts = []
            for i, page in enumerate(reader.pages):
                t = page.extract_text() or ""
                if t.strip():
                    texts.append(f"[第{i+1}页]\n{t}")
            return "\n\n".join(texts), {"pages": len(texts)}, "PyPDF2"
        except ImportError:
            return "需要安装 pdfplumber 或 PyPDF2", {}, "missing_lib"

    def _parse_word(self, fp: Path):
        """Word解析"""
        try:
            import docx
            doc = docx.Document(str(fp))
            paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
            text = "\n".join(paragraphs)
            meta = {"paragraphs": len(paragraphs)}
            return text, meta, "python-docx"
        except ImportError:
            return "需要安装 python-docx", {}, "missing_lib"

    def _parse_pptx(self, fp: Path):
        """PPT解析"""
        try:
            from pptx import Presentation
            prs = Presentation(str(fp))
            texts = []
            for i, slide in enumerate(prs.slides):
                slide_texts = []
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_texts.append(shape.text)
                if slide_texts:
                    texts.append(f"[幻灯片{i+1}]\n" + "\n".join(slide_texts))
            text = "\n\n".join(texts)
            meta = {"slides": len(prs.slides)}
            return text, meta, "python-pptx"
        except ImportError:
            return "需要安装 python-pptx", {}, "missing_lib"

    def _parse_image(self, fp: Path):
        """图片解析 — 优先OCR，退化到VLM描述"""
        # 尝试使用项目已有的 OCR 工具
        try:
            from ..tools.ocr import extract_text_from_image
            text = extract_text_from_image(str(fp))
            if text and len(text.strip()) > 20:
                return text, {"method": "ocr"}, "ocr"
        except (ImportError, Exception):
            pass

        # 尝试 VLM
        try:
            from ..tools.vlm import describe_image
            vlm_cfg = self.cfg.get("vlm", {})
            if vlm_cfg.get("enabled"):
                text = describe_image(str(fp), vlm_cfg)
                return text, {"method": "vlm"}, "vlm"
        except (ImportError, Exception):
            pass

        return f"图片文件: {fp.name}（需要OCR或VLM服务来提取内容）", {}, "placeholder"

    def _parse_video(self, fp: Path):
        """视频解析 — 使用ASR提取字幕"""
        try:
            from ..tools.asr import transcribe_audio
            text = transcribe_audio(str(fp))
            return text, {"method": "asr"}, "whisper_asr"
        except (ImportError, Exception) as e:
            return f"视频文件: {fp.name}（ASR未就绪: {e}）", {}, "placeholder"
