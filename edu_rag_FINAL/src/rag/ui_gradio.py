"""
多模态 AI 互动式教学智能体 — 最终版 UI
"""
from __future__ import annotations
import json, traceback
from pathlib import Path
from typing import List, Optional
import gradio as gr
from .service import RAGService

def build_ui(cfg_path: str = "config.yaml") -> gr.Blocks:
    service = RAGService(cfg_path)
    dialogue_mgr = None
    try:
        from .dialogue.dialogue_manager import DialogueManager
        dialogue_mgr = DialogueManager(cfg_path)
    except Exception: pass
    pipeline = None
    try:
        from .courseware_pipeline import CoursewarePipeline
        pipeline = CoursewarePipeline(cfg_path)
    except Exception: pass
    try: idxs = service.list_indexes() or ["kb"]
    except: idxs = ["kb"]

    def asr_to_text(audio_path) -> str:
        if not audio_path: return ""
        try:
            from .tools.asr import transcribe_audio
            r = transcribe_audio(str(audio_path))
            return str(r) if not isinstance(r, str) else r
        except Exception as e:
            return f"[语音识别需安装faster-whisper: {e}]"

    def pptx_preview(path):
        if not path or not Path(path).exists(): return "<p style='color:#999;text-align:center;padding:40px;'>无PPT</p>"
        try:
            from .ppt_preview import pptx_preview_html
            return pptx_preview_html(path, max_pages=12)
        except:
            try:
                from pptx import Presentation
                prs = Presentation(path)
                lines = [f"<p><b>第{i+1}页:</b> {' | '.join(s.text.strip()[:50] for s in sl.shapes if hasattr(s,'text') and s.text.strip())[:3]}</p>" for i,sl in enumerate(prs.slides)]
                return "<div>" + "\n".join(lines) + "</div>"
            except Exception as e: return f"<p>预览失败: {e}</p>"

    def docx_preview(path):
        if not path or not Path(path).exists(): return "无Word文件"
        try:
            import docx; doc = docx.Document(path)
            lines = []
            for p in doc.paragraphs[:30]:
                t = p.text.strip()
                if not t: continue
                sn = p.style.name if p.style else ""
                if "Heading" in sn: lines.append(f"\n## {t}")
                else: lines.append(t)
            return "\n".join(lines)[:3000]
        except Exception as e: return f"预览失败: {e}"

    # ── 对话 ──
    def chat(user_msg, audio, history, files, note):
        if audio and not user_msg.strip(): user_msg = asr_to_text(audio)
        if not user_msg.strip(): return history or [], "", "请输入文字或语音", None
        if not dialogue_mgr: return (history or [])+[[user_msg,"⚠️ 对话模块未加载"]], "", "未就绪", None
        try:
            fps = [f.name if hasattr(f,'name') else str(f) for f in (files if isinstance(files,list) else [files])] if files else []
            ns = [note]*len(fps) if fps else None
            reply, state = dialogue_mgr.chat(user_input=user_msg, uploaded_files=fps or None, file_notes=ns)
            ch = (history or [])+[[user_msg, reply]]
            info = f"阶段: {state.value}\n已收集:\n{dialogue_mgr.collected.to_text()}\n\n缺失: {', '.join(dialogue_mgr.collected.missing_fields()) or '✅ 信息完整'}"
            return ch, "", info, None
        except Exception as e:
            return (history or [])+[[user_msg,f"❌ {e}"]], "", str(e), None

    def reset():
        if dialogue_mgr: dialogue_mgr.reset()
        return [], "", "已重置", None

    # ── 一键生成 ──
    _empty = "<p style='color:#999;text-align:center;padding:40px;'>等待生成</p>"

    def gen_all(_st):
        if not pipeline:
            return "❌ 流水线未加载", _empty, "未生成", _empty, _empty, None, None, None, None, None
        # 空对话保护
        if dialogue_mgr and not dialogue_mgr.collected.topic and not dialogue_mgr.history:
            return "⚠️ 请先在左侧对话中描述您的教学需求（至少说明课题和知识点），然后再点此按钮。", _empty, "", _empty, _empty, None, None, None, None, None
        try:
            r = pipeline.generate_all(dialogue_mgr=dialogue_mgr, rag_service=service, output_types=["ppt","docx","game"])
            st = r.summary()
            ph = pptx_preview(r.pptx_path) if r.pptx_path else _empty
            dt = docx_preview(r.docx_path) if r.docx_path else "未生成"
            gh = r.game_html or _empty
            ah = r.animation_html or _empty
            pf = r.pptx_path if r.pptx_path and Path(r.pptx_path).exists() else None
            df = r.docx_path if r.docx_path and Path(r.docx_path).exists() else None
            gf = r.game_path if r.game_path and Path(r.game_path).exists() else None
            af = r.animation_path if r.animation_path and Path(r.animation_path).exists() else None
            return st, ph, dt, gh, ah, pf, df, gf, af, r
        except Exception as e:
            return f"❌ {e}\n{traceback.format_exc()}", _empty, "", _empty, _empty, None, None, None, None, None

    # ── 迭代修改 ──
    def regen(fb, rp, rd, rg, prev):
        if not pipeline: return "❌ 未加载", _empty, "", _empty, _empty, None, None, None, None, prev
        if not fb.strip(): return "请输入修改意见", _empty, "", _empty, _empty, None, None, None, None, prev
        if not prev: return "请先生成课件", _empty, "", _empty, _empty, None, None, None, None, None
        rt = []
        if rp: rt.append("ppt")
        if rd: rt.append("docx")
        if rg: rt.append("game")
        if not rt: rt = ["ppt","docx","game"]
        try:
            r = pipeline.regenerate_with_feedback(feedback=fb, previous_result=prev, rag_service=service, regenerate_types=rt)
            st = "🔄 修改完成:\n"+r.summary()
            return st, pptx_preview(r.pptx_path) if r.pptx_path else "", docx_preview(r.docx_path) if r.docx_path else "", r.game_html or "", r.animation_html or prev.animation_html or "", r.pptx_path, r.docx_path, r.game_path, getattr(r,'animation_path',None) or getattr(prev,'animation_path',None), r
        except Exception as e:
            return f"❌ {e}", "", "", "", "", None, None, None, None, prev

    # ── RAG ──
    def query(q, idx, k, tr):
        try:
            res = service.query(question=q, indexes=idx or ["kb"], top_k=int(k), evidence_tag="ui", enable_trace=True)
            hv = res.get("human_view",{}) or {}
            return hv.get("answer_md",""), hv.get("evidence_md",""), hv.get("sources_md",""), hv.get("trace_md","") if tr else "", json.dumps({"answer":res.get("answer")},ensure_ascii=False,indent=2)
        except Exception as e: return "","","",f"错误:{e}",""

    # ═══════════ BUILD ═══════════
    with gr.Blocks(title="多模态AI互动式教学智能体", theme=gr.themes.Soft(primary_hue="blue")) as demo:
        cw = gr.State(None)
        gr.Markdown("# 🎓 多模态 AI 互动式教学智能体\n**A04 锐捷网络** · 对话→一键生成PPT+Word+游戏+动画→预览下载→修改再生成")

        # ──── Tab1: 对话+生成+预览 ────
        with gr.Tab("💬 教学对话 & 课件生成"):
            with gr.Row():
                with gr.Column(scale=1):
                    gr.Markdown("### ① 描述教学需求")
                    chatbot = gr.Chatbot(height=280)
                    with gr.Row():
                        mi = gr.Textbox(placeholder="我要做一节高二生物课，中心法则...", lines=2, scale=4, show_label=False)
                        sb = gr.Button("发送", variant="primary", scale=1)
                    au = gr.Audio(label="🎙️ 语音输入", sources=["microphone"], type="filepath")
                    with gr.Accordion("📎 上传参考资料", open=False):
                        gr.Markdown("*每次上传时请在下方说明此资料的用途，如「参照此PDF第3章格式」「从此视频提取知识点」*")
                        rf = gr.File(label="PDF/Word/PPT/图片/视频", file_count="multiple")
                        rn = gr.Textbox(label="此次上传的资料用途说明", placeholder="如: 参照此PDF第3章的知识点内容和排版格式")
                    si = gr.Textbox(label="已收集信息", lines=5, interactive=False)
                    with gr.Row():
                        rb = gr.Button("🔄 重置")
                        gb = gr.Button("🚀 一键生成全部课件", variant="primary", size="lg")
                    gs = gr.Textbox(label="生成状态", lines=4, interactive=False)

                with gr.Column(scale=1):
                    gr.Markdown("### ② 预览 & 下载")
                    with gr.Tab("📊 PPT"):
                        pp = gr.HTML(value=_empty)
                        pd = gr.File(label="📥 下载PPT")
                    with gr.Tab("📝 教案"):
                        dp = gr.Textbox(label="教案预览", lines=10, interactive=False, value="等待生成")
                        dd = gr.File(label="📥 下载Word")
                    with gr.Tab("🎮 游戏"):
                        gp = gr.HTML(value=_empty)
                        gd = gr.File(label="📥 下载游戏HTML")
                    with gr.Tab("🎬 动画"):
                        ap = gr.HTML(value=_empty)
                        ad = gr.File(label="📥 下载动画HTML")

            sb.click(fn=chat, inputs=[mi,au,chatbot,rf,rn], outputs=[chatbot,mi,si,au])
            mi.submit(fn=chat, inputs=[mi,au,chatbot,rf,rn], outputs=[chatbot,mi,si,au])
            rb.click(fn=reset, outputs=[chatbot,mi,si,au])
            gb.click(fn=gen_all, inputs=[cw], outputs=[gs,pp,dp,gp,ap,pd,dd,gd,ad,cw])

        # ──── Tab2: 迭代修改 ────
        with gr.Tab("✏️ 迭代修改"):
            gr.Markdown("### ③ 修改意见 → 再生成\n输入如「把第3页简化」「游戏改排序题」「教案增加讨论环节」")
            with gr.Row():
                with gr.Column(scale=1):
                    fi = gr.Textbox(label="修改意见", lines=5, placeholder="如: 简化第3页 / 增加案例 / 游戏改排序题")
                    with gr.Row():
                        fp = gr.Checkbox(value=True, label="PPT")
                        fd = gr.Checkbox(value=True, label="Word")
                        fg = gr.Checkbox(value=True, label="游戏")
                    fb = gr.Button("🔄 应用修改", variant="primary", size="lg")
                    fs = gr.Textbox(label="状态", lines=4, interactive=False)
                with gr.Column(scale=1):
                    with gr.Tab("📊 PPT"):
                        rpp = gr.HTML()
                        rpd = gr.File(label="📥 PPT")
                    with gr.Tab("📝 教案"):
                        rdp = gr.Textbox(lines=8, interactive=False)
                        rdd = gr.File(label="📥 Word")
                    with gr.Tab("🎮 游戏"):
                        rgp = gr.HTML()
                        rgd = gr.File(label="📥 游戏")
                    with gr.Tab("🎬 动画"):
                        rap = gr.HTML()
                        rad = gr.File(label="📥 动画")
            fb.click(fn=regen, inputs=[fi,fp,fd,fg,cw], outputs=[fs,rpp,rdp,rgp,rap,rpd,rdd,rgd,rad,cw])

        # ──── Tab3: 知识问答 ────
        with gr.Tab("🔍 知识问答"):
            q = gr.Textbox(label="问题", placeholder="解释中心法则", lines=2)
            with gr.Row():
                qi = gr.Dropdown(choices=idxs, value=["kb"] if "kb" in idxs else idxs[:1], multiselect=True, label="索引")
                qk = gr.Slider(1,20,value=5,step=1,label="K")
                qt = gr.Checkbox(value=False, label="trace")
            qb = gr.Button("查询", variant="primary")
            qa = gr.Markdown()
            with gr.Accordion("证据",open=True):
                qe = gr.Markdown(); qs = gr.Markdown()
            with gr.Accordion("Trace",open=False): qtr = gr.Markdown()
            with gr.Accordion("JSON",open=False): qj = gr.Code(language="json")
            qb.click(fn=query, inputs=[q,qi,qk,qt], outputs=[qa,qe,qs,qtr,qj])

        # ──── Tab4: 知识库管理 ────
        with gr.Tab("📚 知识库"):
            ks = gr.Textbox(label="索引", interactive=False)
            gr.Button("刷新").click(fn=lambda: "\n".join(f"  - {x}" for x in service.list_indexes()), outputs=[ks])
            with gr.Row():
                id_ = gr.Textbox(label="目录", value="knowledge_base")
                ii = gr.Textbox(label="索引", value="kb")
                iis = gr.Textbox(label="Session", value="kb")
                ir = gr.Checkbox(value=True, label="重建")
            ib = gr.Button("入库", variant="primary")
            io = gr.Textbox(label="结果", lines=3, interactive=False)
            def do_ingest(d,i,s,r):
                try:
                    if r: service.engine.reset_index(i)
                    return f"✅ {service.engine.ingest_dir(d,index=i,source_type='knowledge_base',session_id=s or 'kb')}"
                except Exception as e: return f"❌ {e}"
            ib.click(fn=do_ingest, inputs=[id_,ii,iis,ir], outputs=[io])

    return demo

def main():
    demo = build_ui("config.yaml"); demo.queue(); demo.launch(server_name="0.0.0.0", server_port=7860, share=False)

if __name__ == "__main__": main()
