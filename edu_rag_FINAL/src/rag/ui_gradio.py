"""
多模态 AI 互动式教学智能体 — 主界面 (完整版)

Tabs:
  1. 教学对话     — A04 2a-2c) 多轮对话 + 资料上传 + 需求收集
  2. 知识问答     — A04 1) RAG 知识库检索
  3. 互动小游戏   — A04 4c) 游戏生成
  4. 知识库管理   — 入库/列表/重建

启动: python -m src.rag.ui_gradio
"""

from __future__ import annotations

import json
import traceback
from pathlib import Path
from typing import List, Tuple

import gradio as gr

from .service import RAGService
from .game.game_engine import GameEngine
from .game.game_prompts import GAME_DESCRIPTIONS


def build_ui(cfg_path: str = "config.yaml") -> gr.Blocks:
    service = RAGService(cfg_path)
    game_engine = GameEngine(cfg_path)

    dialogue_mgr = None
    try:
        from .dialogue.dialogue_manager import DialogueManager
        dialogue_mgr = DialogueManager(cfg_path)
    except Exception:
        pass

    try:
        idxs = service.list_indexes()
        if not idxs:
            idxs = ["kb"]
    except Exception:
        idxs = ["kb"]

    # ══════════════════════════════════════════
    # Tab 1: 教学对话
    # ══════════════════════════════════════════

    def dialogue_chat(user_msg, chat_history, uploaded_files, file_note):
        if dialogue_mgr is None:
            chat_history = chat_history or []
            chat_history.append([user_msg, "⚠️ 对话模块加载失败，请检查依赖。"])
            return chat_history, "", "未就绪"
        try:
            file_paths = []
            if uploaded_files:
                if isinstance(uploaded_files, list):
                    file_paths = [f.name if hasattr(f, 'name') else str(f) for f in uploaded_files]
                elif hasattr(uploaded_files, 'name'):
                    file_paths = [uploaded_files.name]
            notes = [file_note] * len(file_paths) if file_paths else None
            reply, state = dialogue_mgr.chat(
                user_input=user_msg,
                uploaded_files=file_paths if file_paths else None,
                file_notes=notes,
            )
            chat_history = chat_history or []
            chat_history.append([user_msg, reply])
            state_text = (
                f"状态: {state.value}\n"
                f"已收集信息:\n{dialogue_mgr.collected.to_text()}\n\n"
                f"缺失字段: {', '.join(dialogue_mgr.collected.missing_fields()) or '无（信息完整）'}"
            )
            return chat_history, "", state_text
        except Exception as e:
            chat_history = chat_history or []
            chat_history.append([user_msg, f"❌ 错误: {e}"])
            return chat_history, "", f"Error: {e}"

    def dialogue_reset():
        if dialogue_mgr:
            dialogue_mgr.reset()
        return [], "", "已重置"

    def dialogue_extract_intent():
        if dialogue_mgr is None:
            return "对话模块未加载"
        try:
            intent = dialogue_mgr.confirm_and_extract()
            return intent.summary_text() + "\n\n" + json.dumps(intent.raw_json, ensure_ascii=False, indent=2)
        except Exception as e:
            return f"提取失败: {e}\n{traceback.format_exc()}"

    # ══════════════════════════════════════════
    # Tab 2: RAG 知识问答
    # ══════════════════════════════════════════

    def query_fn(question, selected_indexes, top_k, show_trace):
        try:
            if not selected_indexes:
                selected_indexes = ["kb"]
            res = service.query(question=question, indexes=selected_indexes, top_k=int(top_k), evidence_tag="ui", enable_trace=True)
            hv = res.get("human_view", {}) or {}
            answer_md = hv.get("answer_md", "")
            evidence_md = hv.get("evidence_md", "")
            sources_md = hv.get("sources_md", "")
            trace_md = hv.get("trace_md", "") if show_trace else "（已隐藏 trace）"
            machine_json = json.dumps({"schema_version": res.get("schema_version"), "question": res.get("question"), "answer": res.get("answer"), "evidence": res.get("evidence"), "trace": res.get("trace") if show_trace else []}, ensure_ascii=False, indent=2)
            return answer_md, evidence_md, sources_md, trace_md, machine_json
        except Exception as e:
            return "", "", "", f"UI query error: {e}\n{traceback.format_exc()}", ""

    # ══════════════════════════════════════════
    # Tab 3: 互动小游戏
    # ══════════════════════════════════════════

    game_type_choices = [(desc, key) for key, desc in GAME_DESCRIPTIONS.items()]

    def game_gen_fn(knowledge_topic, game_type_val, teacher_req, count, use_rag, selected_indexes, raw_text):
        try:
            output_dir = "outputs/games"
            if use_rag and knowledge_topic.strip():
                result = game_engine.generate_with_rag(question=knowledge_topic, game_type=game_type_val, rag_service=service, indexes=selected_indexes or ["kb"], teacher_requirement=teacher_req, count=int(count), output_dir=output_dir)
            elif raw_text.strip():
                result = game_engine.generate_from_text(text=raw_text, game_type=game_type_val, teacher_requirement=teacher_req, count=int(count), output_dir=output_dir)
            elif knowledge_topic.strip():
                result = game_engine.generate(knowledge_topic=knowledge_topic, game_type=game_type_val, teacher_requirement=teacher_req, count=int(count), output_dir=output_dir)
            else:
                return "请输入知识点主题或教材文本", "", "", ""
            status = f"✅ 游戏生成成功!\n类型: {GAME_DESCRIPTIONS.get(game_type_val, game_type_val)}\n标题: {result['title']}\n耗时: {result['generation_time']}s\n文件: {result['html_path']}"
            return status, result["html"], result["html"], result["html_path"]
        except Exception as e:
            return f"❌ 生成失败: {e}\n{traceback.format_exc()}", "", "", ""

    # ══════════════════════════════════════════
    # Tab 4: 知识库管理
    # ══════════════════════════════════════════

    def list_indexes_fn():
        try:
            return "当前索引:\n" + "\n".join(f"  - {x}" for x in service.list_indexes())
        except Exception as e:
            return f"Error: {e}"

    def ingest_fn(dir_path, index_name, session_id, do_reset):
        try:
            eng = service.engine
            if do_reset:
                eng.reset_index(index_name)
            result = eng.ingest_dir(dir_path, index=index_name, source_type="knowledge_base", session_id=session_id or "kb")
            return f"✅ 入库完成: {result}"
        except Exception as e:
            return f"❌ 入库失败: {e}\n{traceback.format_exc()}"

    # ══════════════════════════════════════════
    # Build Blocks
    # ══════════════════════════════════════════

    with gr.Blocks(title="多模态AI互动式教学智能体", theme=gr.themes.Soft(primary_hue="blue")) as demo:

        gr.Markdown("# 🎓 多模态 AI 互动式教学智能体\n本地知识库 RAG · 多轮教学对话 · 互动小游戏生成 · 教学课件辅助\n\n**A04 — 锐捷网络赛题**")

        # ── Tab 1: 教学对话 ──
        with gr.Tab("💬 教学对话"):
            d_status = "✅ 对话模块已就绪" if dialogue_mgr else "⚠️ 对话模块未加载"
            gr.Markdown(f"### 与AI助手对话，描述您的教学课件需求\n支持语音/文字输入 · 上传参考资料 · 智能追问 · 需求确认\n\n{d_status}")
            with gr.Row():
                with gr.Column(scale=2):
                    chatbot = gr.Chatbot(label="对话", height=450)
                    with gr.Row():
                        msg_input = gr.Textbox(label="输入消息", placeholder="例如：我想做一节高二生物课，关于中心法则...", lines=2, scale=4)
                        send_btn = gr.Button("发送", variant="primary", scale=1)
                    with gr.Row():
                        audio_input = gr.Audio(label="语音输入（可选）", sources=["microphone"], type="filepath")
                    with gr.Accordion("📎 上传参考资料", open=False):
                        ref_files = gr.File(label="参考资料（PDF/Word/PPT/图片/视频）", file_count="multiple")
                        ref_note = gr.Textbox(label="资料说明", placeholder="例如：参照这个PDF第3章的格式")
                with gr.Column(scale=1):
                    state_display = gr.Textbox(label="对话状态 & 已收集信息", lines=15, interactive=False, value="等待开始对话...")
                    with gr.Row():
                        reset_btn = gr.Button("🔄 重置对话")
                        extract_btn = gr.Button("📋 提取教学意图", variant="primary")
                    intent_output = gr.Textbox(label="结构化教学意图", lines=10, interactive=False)

            send_btn.click(fn=dialogue_chat, inputs=[msg_input, chatbot, ref_files, ref_note], outputs=[chatbot, msg_input, state_display])
            msg_input.submit(fn=dialogue_chat, inputs=[msg_input, chatbot, ref_files, ref_note], outputs=[chatbot, msg_input, state_display])
            reset_btn.click(fn=dialogue_reset, outputs=[chatbot, msg_input, state_display])
            extract_btn.click(fn=dialogue_extract_intent, outputs=[intent_output])

        # ── Tab 2: 知识问答 ──
        with gr.Tab("🔍 知识问答"):
            gr.Markdown("### RAG 知识库检索问答")
            question = gr.Textbox(label="问题", placeholder="例如：解释中心法则", lines=3)
            with gr.Row():
                index_sel = gr.Dropdown(choices=idxs, value=["kb"] if "kb" in idxs else ([idxs[0]] if idxs else ["kb"]), multiselect=True, label="索引")
                top_k = gr.Slider(1, 20, value=5, step=1, label="Top-K")
                show_trace = gr.Checkbox(value=False, label="显示 trace")
            with gr.Row():
                btn_query = gr.Button("查询", variant="primary")
                btn_clear = gr.Button("清空")
            answer_md = gr.Markdown(label="回答")
            with gr.Accordion("证据", open=True):
                evidence_md = gr.Markdown()
                sources_md = gr.Markdown()
            with gr.Accordion("Trace", open=False):
                trace_md = gr.Markdown()
            with gr.Accordion("Machine JSON", open=False):
                machine_json = gr.Code(language="json")
            btn_query.click(fn=query_fn, inputs=[question, index_sel, top_k, show_trace], outputs=[answer_md, evidence_md, sources_md, trace_md, machine_json])
            btn_clear.click(fn=lambda: ("", ["kb"], 5, False, "", "", "", "", "{}"), inputs=[], outputs=[question, index_sel, top_k, show_trace, answer_md, evidence_md, sources_md, trace_md, machine_json])

        # ── Tab 3: 互动小游戏 ──
        with gr.Tab("🎮 互动小游戏"):
            gr.Markdown("### 根据知识点生成 HTML5 互动小游戏\n支持 7 种游戏类型：选择题 / 连线配对 / 排序 / 填空 / 判断 / 翻卡记忆 / 流程补全")
            with gr.Row():
                with gr.Column(scale=1):
                    g_topic = gr.Textbox(label="知识点主题", placeholder="例如：中心法则的转录过程", lines=2)
                    g_type = gr.Dropdown(choices=game_type_choices, value="quiz", label="游戏类型")
                    g_req = gr.Textbox(label="教师补充要求", placeholder="（可选）", lines=2)
                    g_count = gr.Slider(3, 15, value=5, step=1, label="题目数量")
                    g_use_rag = gr.Checkbox(value=True, label="使用 RAG 知识库")
                    g_idx = gr.Dropdown(choices=idxs, value=["kb"], multiselect=True, label="索引")
                    with gr.Accordion("直接输入文本", open=False):
                        g_text = gr.Textbox(label="教材文本", lines=6, placeholder="粘贴教材内容...")
                    g_btn = gr.Button("🚀 生成游戏", variant="primary", size="lg")
                with gr.Column(scale=2):
                    g_status = gr.Textbox(label="状态", lines=5, interactive=False)
                    with gr.Tab("🎮 预览"):
                        g_preview = gr.HTML()
                    with gr.Tab("📝 源码"):
                        g_code = gr.Code(language="html")
                    with gr.Tab("💾 下载"):
                        g_path = gr.Textbox(label="文件路径", interactive=False)
                        gr.Markdown("在上方路径找到 HTML 文件，用浏览器打开即可游玩。可嵌入到 PPT 中作为互动环节。")
            g_btn.click(fn=game_gen_fn, inputs=[g_topic, g_type, g_req, g_count, g_use_rag, g_idx, g_text], outputs=[g_status, g_preview, g_code, g_path])

        # ── Tab 4: 知识库管理 ──
        with gr.Tab("📚 知识库管理"):
            gr.Markdown("### 知识库入库与管理")
            kb_status = gr.Textbox(label="索引列表", interactive=False)
            btn_list = gr.Button("刷新索引列表")
            btn_list.click(fn=list_indexes_fn, outputs=[kb_status])
            gr.Markdown("---\n### 入库操作")
            with gr.Row():
                ig_dir = gr.Textbox(label="资料目录", value="knowledge_base", placeholder="knowledge_base")
                ig_index = gr.Textbox(label="索引名", value="kb")
                ig_session = gr.Textbox(label="Session ID", value="kb")
                ig_reset = gr.Checkbox(value=True, label="重建索引")
            ig_btn = gr.Button("开始入库", variant="primary")
            ig_result = gr.Textbox(label="入库结果", lines=5, interactive=False)
            ig_btn.click(fn=ingest_fn, inputs=[ig_dir, ig_index, ig_session, ig_reset], outputs=[ig_result])

    return demo


def main():
    demo = build_ui("config.yaml")
    demo.queue()
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)


if __name__ == "__main__":
    main()
