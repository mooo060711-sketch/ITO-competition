"""
互动小游戏生成 — Gradio UI

启动方式:
    python -m src.rag.game.ui_game

浏览器打开: http://127.0.0.1:7861
"""

from __future__ import annotations

import json
import os
import traceback
from pathlib import Path
from typing import List, Optional, Tuple

import gradio as gr

from .game_engine import GameEngine, GameType
from .game_prompts import GAME_DESCRIPTIONS


def _try_load_rag_service(cfg_path: str = "config.yaml"):
    """Try to load RAGService; return None if unavailable (e.g., Milvus not running)."""
    try:
        from ..service import RAGService
        svc = RAGService(cfg_path)
        _ = svc.list_indexes()
        return svc
    except Exception:
        return None


def build_game_ui(cfg_path: str = "config.yaml") -> gr.Blocks:
    engine = GameEngine(cfg_path)
    rag_svc = _try_load_rag_service(cfg_path)

    game_type_choices = [(desc, key) for key, desc in GAME_DESCRIPTIONS.items()]
    rag_available = rag_svc is not None

    try:
        idxs = rag_svc.list_indexes() if rag_svc else ["kb"]
    except Exception:
        idxs = ["kb"]

    def generate_game(
        knowledge_topic: str,
        game_type_val: str,
        teacher_req: str,
        count: int,
        use_rag: bool,
        selected_indexes: List[str],
        raw_text: str,
    ) -> Tuple[str, str, str, str]:
        """
        Returns: (status_msg, html_preview, html_raw, file_path)
        """
        try:
            output_dir = "outputs/games"

            if use_rag and rag_svc and knowledge_topic.strip():
                result = engine.generate_with_rag(
                    question=knowledge_topic,
                    game_type=game_type_val,
                    rag_service=rag_svc,
                    indexes=selected_indexes or ["kb"],
                    teacher_requirement=teacher_req,
                    count=int(count),
                    output_dir=output_dir,
                )
            elif raw_text.strip():
                result = engine.generate_from_text(
                    text=raw_text,
                    game_type=game_type_val,
                    teacher_requirement=teacher_req,
                    count=int(count),
                    output_dir=output_dir,
                )
            elif knowledge_topic.strip():
                result = engine.generate(
                    knowledge_topic=knowledge_topic,
                    game_type=game_type_val,
                    teacher_requirement=teacher_req,
                    count=int(count),
                    output_dir=output_dir,
                )
            else:
                return "❌ 请输入知识点主题或粘贴教材文本", "", "", ""

            status = (
                f"✅ 游戏生成成功!\n"
                f"- 类型: {GAME_DESCRIPTIONS.get(game_type_val, game_type_val)}\n"
                f"- 标题: {result['title']}\n"
                f"- 耗时: {result['generation_time']}s\n"
                f"- 文件: {result['html_path']}"
            )

            html_preview = result["html"]
            html_raw = result["html"]
            file_path = result["html_path"]

            return status, html_preview, html_raw, file_path

        except Exception as e:
            err = f"❌ 生成失败: {e}\n\n{traceback.format_exc()}"
            return err, "", "", ""

    # ────── UI Layout ──────
    with gr.Blocks(
        title="互动小游戏生成器",
        theme=gr.themes.Soft(primary_hue="blue"),
    ) as demo:

        gr.Markdown(
            "# 🎮 互动小游戏生成器\n"
            "根据知识点自动生成 HTML5 互动小游戏 · 支持选择题/连线/排序/填空/判断/翻卡/流程补全\n\n"
            + ("✅ RAG 知识库已连接" if rag_available else "⚠️ RAG 知识库未连接（Milvus 未启动？），仅支持直接输入模式")
        )

        with gr.Row():
            with gr.Column(scale=1):
                knowledge_topic = gr.Textbox(
                    label="📚 知识点主题",
                    placeholder="例如：中心法则中的转录过程",
                    lines=2,
                )
                game_type_dd = gr.Dropdown(
                    choices=game_type_choices,
                    value="quiz",
                    label="🎯 游戏类型",
                )
                teacher_req = gr.Textbox(
                    label="📝 教师补充要求（可选）",
                    placeholder="例如：侧重于RNA聚合酶的作用，难度中等",
                    lines=2,
                )
                count = gr.Slider(
                    minimum=3, maximum=15, value=5, step=1,
                    label="📊 题目/卡片数量",
                )

                with gr.Accordion("🔍 RAG 设置", open=False):
                    use_rag = gr.Checkbox(
                        value=rag_available,
                        label="使用 RAG 知识库检索",
                        interactive=rag_available,
                    )
                    index_sel = gr.Dropdown(
                        choices=idxs,
                        value=["kb"] if "kb" in idxs else [],
                        multiselect=True,
                        label="选择索引",
                        interactive=rag_available,
                    )

                with gr.Accordion("📄 直接输入教材文本（不使用 RAG）", open=False):
                    raw_text = gr.Textbox(
                        label="教材/知识文本",
                        placeholder="在此粘贴教材内容，游戏将基于此文本生成...",
                        lines=8,
                    )

                gen_btn = gr.Button("🚀 生成游戏", variant="primary", size="lg")

            with gr.Column(scale=2):
                status_out = gr.Textbox(label="状态", lines=6, interactive=False)

                with gr.Tab("🎮 游戏预览"):
                    html_preview = gr.HTML(label="游戏预览")

                with gr.Tab("📝 HTML 源码"):
                    html_raw = gr.Code(label="HTML 源码", language="html")

                with gr.Tab("💾 下载"):
                    file_path = gr.Textbox(label="文件路径", interactive=False)
                    gr.Markdown("生成后可在上方路径找到 HTML 文件，用浏览器打开即可游玩。")

        gen_btn.click(
            fn=generate_game,
            inputs=[knowledge_topic, game_type_dd, teacher_req, count, use_rag, index_sel, raw_text],
            outputs=[status_out, html_preview, html_raw, file_path],
        )

        # ── 示例 ──
        gr.Examples(
            examples=[
                ["中心法则 - 转录过程", "quiz", "侧重RNA聚合酶的识别与结合", 5],
                ["DNA复制的步骤", "sorting", "按照正确的生物学顺序", 5],
                ["减数分裂的特点", "true_false", "包含常见错误概念", 6],
                ["分子生物学核心概念", "matching", "概念与定义配对", 6],
                ["翻译过程中的关键术语", "flashcard", "", 8],
                ["转录过程的详细步骤", "flow_fill", "从DNA解旋到mRNA成熟", 5],
            ],
            inputs=[knowledge_topic, game_type_dd, teacher_req, count],
        )

    return demo


def main():
    demo = build_game_ui("config.yaml")
    demo.queue()
    demo.launch(server_name="0.0.0.0", server_port=7861, share=False)


if __name__ == "__main__":
    main()
