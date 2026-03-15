"""
多轮对话管理器 — 需求收集状态机

对应 A04 要求:
  - 2a) 提供语音/文字输入
  - 2b) 智能对话：主动提问、多轮对话、总结确认需求
  - 2c) 参考资料上传功能
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from .intent_extractor import IntentExtractor, TeachingIntent
from .prompts import DIALOGUE_SYSTEM_PROMPT, DIALOGUE_TURN_PROMPT
from .reference_handler import ReferenceHandler


class DialogueState(str, Enum):
    """对话阶段"""
    GREETING    = "greeting"     # 初始问候
    COLLECTING  = "collecting"   # 需求收集中
    CONFIRMING  = "confirming"   # 需求确认中
    READY       = "ready"        # 需求已确认，准备生成
    GENERATING  = "generating"   # 正在生成课件
    ITERATING   = "iterating"    # 迭代修改中


@dataclass
class CollectedInfo:
    """已收集的教学需求信息"""
    subject: str = ""
    topic: str = ""
    teaching_goal: str = ""
    target_audience: str = ""
    duration_minutes: int = 0
    output_types: List[str] = field(default_factory=list)
    key_points: List[str] = field(default_factory=list)
    difficulties: List[str] = field(default_factory=list)
    style: str = ""
    special_requirements: str = ""
    reference_files: List[Dict[str, Any]] = field(default_factory=list)

    def to_text(self) -> str:
        lines = []
        if self.subject: lines.append(f"学科: {self.subject}")
        if self.topic: lines.append(f"知识点: {self.topic}")
        if self.teaching_goal: lines.append(f"教学目标: {self.teaching_goal}")
        if self.target_audience: lines.append(f"教学对象: {self.target_audience}")
        if self.duration_minutes: lines.append(f"课时: {self.duration_minutes}分钟")
        if self.output_types: lines.append(f"输出类型: {', '.join(self.output_types)}")
        if self.key_points: lines.append(f"重点: {', '.join(self.key_points)}")
        if self.difficulties: lines.append(f"难点: {', '.join(self.difficulties)}")
        if self.style: lines.append(f"风格: {self.style}")
        if self.special_requirements: lines.append(f"特殊要求: {self.special_requirements}")
        if self.reference_files:
            refs = [f"  - {r.get('file_name', '未知')} ({r.get('teacher_note', '')})" for r in self.reference_files]
            lines.append("参考资料:\n" + "\n".join(refs))
        return "\n".join(lines) if lines else "（尚未收集到信息）"

    def missing_fields(self) -> List[str]:
        missing = []
        if not self.subject: missing.append("学科")
        if not self.topic: missing.append("知识点/章节")
        if not self.teaching_goal: missing.append("教学目标")
        if not self.target_audience: missing.append("教学对象")
        if not self.output_types: missing.append("课件类型")
        return missing

    def is_complete(self) -> bool:
        return len(self.missing_fields()) == 0


class DialogueManager:
    """
    多轮对话管理器。

    管理教师与AI之间的多轮对话，收集需求、追问补充信息、
    确认最终需求、触发课件生成。

    Example:
        dm = DialogueManager(config_path="config.yaml")
        reply, state = dm.chat("我想做一个关于中心法则的PPT")
        print(reply)  # AI会追问缺失信息
        reply, state = dm.chat("面向高二学生，45分钟")
        ...
    """

    def __init__(self, config_path: str = "config.yaml"):
        self.config_path = config_path
        self.state = DialogueState.GREETING
        self.history: List[Dict[str, str]] = []  # [{"role": "user/assistant", "content": ...}]
        self.collected = CollectedInfo()
        self.intent: Optional[TeachingIntent] = None

        self._generator = None
        self._intent_extractor = None
        self._ref_handler = None

    @property
    def generator(self):
        if self._generator is None:
            from ..config import load_config
            from ..generator import GeneratorConfig, QwenGenerator
            cfg = load_config(self.config_path)
            g_cfg = cfg.get("generator", {}) or {}
            self._generator = QwenGenerator(GeneratorConfig(
                mode=str(g_cfg.get("mode", "api")),
                api_model=str(g_cfg.get("api_model", "qwen-plus-latest")),
                api_base_url_env=str(g_cfg.get("api_base_url_env", "OPENAI_BASE_URL")),
                api_key_env=str(g_cfg.get("api_key_env", "OPENAI_API_KEY")),
                timeout_sec=float(g_cfg.get("timeout_sec", 120.0)),
                local_model_path=str(g_cfg.get("local_model_path", "")),
                device=str(g_cfg.get("device", "cpu")),
                max_new_tokens=int(g_cfg.get("max_new_tokens", 2048)),
                temperature=float(g_cfg.get("temperature", 0.4)),
            ))
        return self._generator

    @property
    def intent_extractor(self) -> IntentExtractor:
        if self._intent_extractor is None:
            self._intent_extractor = IntentExtractor(self.config_path)
        return self._intent_extractor

    @property
    def ref_handler(self) -> ReferenceHandler:
        if self._ref_handler is None:
            self._ref_handler = ReferenceHandler(self.config_path)
        return self._ref_handler

    # ─────────────────────────────────────────
    # 核心对话接口
    # ─────────────────────────────────────────

    def chat(
        self,
        user_input: str,
        uploaded_files: Optional[List[str]] = None,
        file_notes: Optional[List[str]] = None,
    ) -> Tuple[str, DialogueState]:
        """
        处理一轮对话。

        Args:
            user_input: 教师输入的文字
            uploaded_files: 本轮上传的文件路径列表
            file_notes: 对应的文件说明

        Returns:
            (assistant_reply, current_state)
        """
        # 处理上传的文件
        if uploaded_files:
            notes = file_notes or [""] * len(uploaded_files)
            for fp, note in zip(uploaded_files, notes):
                parsed = self.ref_handler.parse_file(fp, teacher_note=note)
                self.collected.reference_files.append(parsed)

        # 记录用户输入
        self.history.append({"role": "user", "content": user_input})

        # 根据状态处理
        if self.state == DialogueState.GREETING:
            self.state = DialogueState.COLLECTING

        # 尝试从用户输入中提取信息并更新 collected
        self._update_collected_from_input(user_input)

        # 检查是否教师发了确认指令
        if self._is_confirm_signal(user_input):
            if self.collected.is_complete():
                self.state = DialogueState.READY
                reply = self._generate_final_summary()
                self.history.append({"role": "assistant", "content": reply})
                return reply, self.state

        # 检查信息是否完整
        if self.collected.is_complete() and self.state == DialogueState.COLLECTING:
            self.state = DialogueState.CONFIRMING

        # 生成AI回复
        reply = self._generate_reply(user_input)
        self.history.append({"role": "assistant", "content": reply})

        # 检测回复中是否包含 [READY]
        if "[READY]" in reply:
            self.state = DialogueState.CONFIRMING

        return reply, self.state

    def confirm_and_extract(self) -> TeachingIntent:
        """确认需求并提取结构化教学意图"""
        history_text = self._format_history()
        ref_text = self._format_references()

        self.intent = self.intent_extractor.extract_intent(
            dialogue_text=history_text,
            reference_content=ref_text,
        )
        self.state = DialogueState.READY
        return self.intent

    def reset(self):
        """重置对话"""
        self.state = DialogueState.GREETING
        self.history = []
        self.collected = CollectedInfo()
        self.intent = None

    # ─────────────────────────────────────────
    # 内部方法
    # ─────────────────────────────────────────

    def _generate_reply(self, user_input: str) -> str:
        """调用LLM生成对话回复"""
        history_text = self._format_history()
        ref_summary = self._format_references_brief()

        prompt = DIALOGUE_TURN_PROMPT.format(
            history=history_text,
            user_input=user_input,
            collected_info=self.collected.to_text(),
            reference_summary=ref_summary or "无",
        )

        # 构造完整的消息（system + prompt）
        full_prompt = f"{DIALOGUE_SYSTEM_PROMPT}\n\n{prompt}"
        return self.generator.generate(full_prompt)

    def _generate_final_summary(self) -> str:
        """生成最终的需求确认总结"""
        summary = self.collected.to_text()
        ref_text = self._format_references_brief()
        reply = (
            "✅ **需求确认完毕！** 以下是您的教学课件需求总结：\n\n"
            f"{summary}\n\n"
        )
        if ref_text:
            reply += f"**参考资料：**\n{ref_text}\n\n"
        reply += (
            "如果以上信息无误，您可以：\n"
            "- 点击「生成课件」开始制作\n"
            "- 继续补充或修改需求\n"
        )
        return reply

    def _update_collected_from_input(self, text: str):
        """从用户输入中提取并更新已收集信息（简单关键词匹配）"""
        t = text.lower()

        # 学科检测
        subjects = {
            "生物": "生物", "物理": "物理", "化学": "化学",
            "数学": "数学", "语文": "语文", "英语": "英语",
            "历史": "历史", "地理": "地理", "政治": "政治",
        }
        for kw, subj in subjects.items():
            if kw in t and not self.collected.subject:
                self.collected.subject = subj

        # 教学对象
        import re
        grade_match = re.search(r'(高[一二三]|初[一二三]|[一二三四五六]年级|大[一二三四])', text)
        if grade_match and not self.collected.target_audience:
            self.collected.target_audience = grade_match.group(1)

        # 时长
        duration_match = re.search(r'(\d+)\s*分钟', text)
        if duration_match and not self.collected.duration_minutes:
            self.collected.duration_minutes = int(duration_match.group(1))

        # 课件类型
        if "ppt" in t or "演示" in t or "幻灯片" in t:
            if "ppt" not in self.collected.output_types:
                self.collected.output_types.append("ppt")
        if "教案" in t or "word" in t:
            if "docx" not in self.collected.output_types:
                self.collected.output_types.append("docx")
        if "游戏" in t or "互动" in t:
            if "game" not in self.collected.output_types:
                self.collected.output_types.append("game")

    @staticmethod
    def _is_confirm_signal(text: str) -> bool:
        signals = ["确认", "没问题", "可以了", "就这样", "开始生成", "生成课件", "ok", "好的开始"]
        return any(s in text.lower() for s in signals)

    def _format_history(self, max_turns: int = 20) -> str:
        recent = self.history[-max_turns * 2:]
        lines = []
        for msg in recent:
            role = "教师" if msg["role"] == "user" else "AI助手"
            lines.append(f"{role}: {msg['content']}")
        return "\n".join(lines)

    def _format_references(self) -> str:
        if not self.collected.reference_files:
            return ""
        parts = []
        for r in self.collected.reference_files:
            parts.append(f"[{r['file_name']}] ({r['file_type']})\n{r.get('text', '')[:2000]}")
        return "\n\n---\n\n".join(parts)

    def _format_references_brief(self) -> str:
        if not self.collected.reference_files:
            return ""
        return "\n".join(
            f"- {r['file_name']} ({r['file_type']}): {r.get('teacher_note', '无说明')}"
            for r in self.collected.reference_files
        )
