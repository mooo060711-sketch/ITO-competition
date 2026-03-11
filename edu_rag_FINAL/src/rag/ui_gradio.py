from __future__ import annotations

import json
import traceback
from typing import List, Tuple

import gradio as gr

from .service import RAGService


def build_ui(cfg_path: str = "config.yaml") -> gr.Blocks:
    service = RAGService(cfg_path)

    try:
        idxs = service.list_indexes()
        if not idxs:
            idxs = ["kb"]
    except Exception:
        idxs = ["kb"]

    def query_fn(
        question: str,
        selected_indexes: List[str],
        top_k: int,
        show_trace: bool,
    ) -> Tuple[str, str, str, str, str]:
        """
        Returns:
          answer_md, evidence_md, sources_md, trace_md, machine_json
        """
        try:
            if not selected_indexes:
                selected_indexes = ["kb"]

            res = service.query(
                question=question,
                indexes=selected_indexes,
                top_k=int(top_k),
                evidence_tag="ui",
                enable_trace=True,   # ✅ 强制开启 trace
            )

            hv = res.get("human_view", {}) or {}
            answer_md = hv.get("answer_md", "")
            evidence_md = hv.get("evidence_md", "")
            sources_md = hv.get("sources_md", "")
            trace_md = hv.get("trace_md", "")

            if not show_trace:
                trace_md = "（已隐藏 trace）"

            machine_json = json.dumps(
                {
                    "schema_version": res.get("schema_version"),
                    "question": res.get("question"),
                    "indexes": res.get("indexes"),
                    "subqueries": res.get("subqueries"),
                    "answer": res.get("answer"),
                    "evidence": res.get("evidence"),
                    "citations": res.get("citations"),
                    "trace": res.get("trace") if show_trace else [],
                    "evidence_path": res.get("evidence_path"),
                },
                ensure_ascii=False,
                indent=2,
            )

            return answer_md, evidence_md, sources_md, trace_md, machine_json

        except Exception as e:
            err = f"UI query error: {e}\n\n{traceback.format_exc()}"
            return "", "", "", err, ""

    with gr.Blocks(title="Edu-RAG (Human + Machine)") as demo:
        gr.Markdown("# Edu-RAG\n对外展示：**human_view**；对内对接：**machine JSON**（结构化稳定字段）。")

        question = gr.Textbox(
            label="问题（Question）",
            placeholder="例如：解释中心法则，并给出两个易错点。",
            lines=3,
        )

        with gr.Row():
            index_sel = gr.Dropdown(
                choices=idxs,
                value=["kb"] if "kb" in idxs else ([idxs[0]] if idxs else ["kb"]),
                multiselect=True,
                label="索引（Indexes）",
            )
            top_k = gr.Slider(minimum=1, maximum=20, value=5, step=1, label="Top-K")
            show_trace = gr.Checkbox(value=True, label="显示 trace")

        with gr.Row():
            btn = gr.Button("Query", variant="primary")
            btn_clear = gr.Button("Clear")

        answer_md = gr.Markdown(label="回答（Human View）")

        with gr.Accordion("证据摘要（Human View）", open=True):
            evidence_md = gr.Markdown(label="证据表格")
            sources_md = gr.Markdown(label="证据来源列表")

        with gr.Accordion("Trace（Human View）", open=False):
            trace_md = gr.Markdown(label="检索过程（trace）")

        with gr.Accordion("结构化输出（Machine JSON）", open=False):
            machine_json = gr.Code(label="machine JSON（用于模块对接）", language="json")

        btn.click(
            fn=query_fn,
            inputs=[question, index_sel, top_k, show_trace],
            outputs=[answer_md, evidence_md, sources_md, trace_md, machine_json],
            api_name="query",
        )

        def clear_fn():
            return "", (["kb"] if "kb" in idxs else []), 5, True, "", "", "", "", "{}"

        btn_clear.click(
            fn=clear_fn,
            inputs=[],
            outputs=[question, index_sel, top_k, show_trace, answer_md, evidence_md, sources_md, trace_md, machine_json],
        )

    return demo


def main():
    demo = build_ui("config.yaml")
    demo.queue()
    demo.launch(server_name="0.0.0.0", server_port=7860, share=False)


if __name__ == "__main__":
    main()
