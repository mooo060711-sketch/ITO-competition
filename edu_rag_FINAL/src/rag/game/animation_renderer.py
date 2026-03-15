"""
HTML5 知识点动画渲染器

对应 A04 4c): "应能根据教师要求生成知识点相关的动画创意"
生成可独立运行的 HTML5 动画页面（流程动画/概念展开动画）
"""

from __future__ import annotations

import html
import json
from typing import Any, Dict, List


def render_process_animation(data: Dict[str, Any]) -> str:
    """
    流程动画：逐步展示一个生物/化学/物理过程。
    点击"下一步"逐帧播放，每帧有标题+描述+图示区域。

    data格式:
    {
      "title": "转录过程动画",
      "steps": [
        {"title": "第1步: 起始", "description": "RNA聚合酶识别并结合...", "icon": "🧬"},
        {"title": "第2步: 延伸", "description": "核糖核苷酸按互补配对...", "icon": "🔗"},
      ]
    }
    """
    title = html.escape(data.get("title", "知识点动画"))
    steps = data.get("steps", [])
    steps_json = json.dumps(steps, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700&display=swap');
  *,*::before,*::after {{ box-sizing:border-box; margin:0; padding:0; }}
  :root {{
    --bg:#0f172a; --surface:#1e293b; --card:#334155;
    --primary:#38bdf8; --secondary:#818cf8; --accent:#f472b6;
    --success:#34d399; --text:#f1f5f9; --dim:#94a3b8;
  }}
  body {{
    font-family:'Noto Sans SC',system-ui,sans-serif;
    background:var(--bg); color:var(--text);
    min-height:100vh; display:flex; align-items:center; justify-content:center;
    background-image:
      radial-gradient(ellipse at 20% 50%, rgba(56,189,248,.08) 0%, transparent 50%),
      radial-gradient(ellipse at 80% 20%, rgba(129,140,248,.08) 0%, transparent 50%);
  }}
  .container {{ max-width:700px; width:100%; padding:24px; }}
  .header {{ text-align:center; margin-bottom:32px; }}
  .header h1 {{
    font-size:28px; font-weight:700;
    background:linear-gradient(135deg, var(--primary), var(--secondary));
    -webkit-background-clip:text; -webkit-text-fill-color:transparent;
  }}
  .progress {{
    display:flex; gap:6px; justify-content:center; margin:20px 0;
  }}
  .dot {{
    width:10px; height:10px; border-radius:50%;
    background:var(--card); transition:all .3s;
  }}
  .dot.active {{ background:var(--primary); transform:scale(1.3); }}
  .dot.done {{ background:var(--success); }}

  .stage {{
    background:var(--surface); border-radius:16px; padding:40px;
    text-align:center; min-height:300px;
    display:flex; flex-direction:column; align-items:center; justify-content:center;
    border:1px solid rgba(255,255,255,.06);
    box-shadow:0 8px 32px rgba(0,0,0,.35);
    animation:fadeScale .5s ease-out;
  }}
  .icon {{ font-size:64px; margin-bottom:16px; animation:float 3s ease-in-out infinite; }}
  .stage-title {{ font-size:22px; font-weight:600; margin-bottom:12px; color:var(--primary); }}
  .stage-desc {{ font-size:15px; line-height:1.8; color:var(--dim); max-width:500px; }}

  .controls {{ display:flex; gap:12px; justify-content:center; margin-top:24px; }}
  .btn {{
    padding:10px 28px; border:none; border-radius:8px;
    font-size:15px; font-weight:500; cursor:pointer;
    transition:all .2s; font-family:inherit;
  }}
  .btn-primary {{
    background:linear-gradient(135deg,var(--primary),var(--secondary));
    color:#fff; box-shadow:0 4px 16px rgba(56,189,248,.3);
  }}
  .btn-primary:hover {{ transform:translateY(-2px); }}
  .btn-outline {{
    background:transparent; border:1.5px solid var(--primary); color:var(--primary);
  }}
  .btn-outline:hover {{ background:rgba(56,189,248,.1); }}
  .btn:disabled {{ opacity:.4; cursor:default; transform:none; }}

  .counter {{ text-align:center; color:var(--dim); font-size:13px; margin-top:12px; }}

  @keyframes fadeScale {{
    from {{ opacity:0; transform:scale(.95); }}
    to {{ opacity:1; transform:scale(1); }}
  }}
  @keyframes float {{
    0%,100% {{ transform:translateY(0); }}
    50% {{ transform:translateY(-8px); }}
  }}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <h1>🎬 {title}</h1>
    <p style="color:var(--dim);font-size:13px;margin-top:6px;">点击"下一步"逐步了解过程</p>
  </div>
  <div class="progress" id="progress"></div>
  <div class="stage" id="stage"></div>
  <div class="controls">
    <button class="btn btn-outline" id="prevBtn" onclick="prev()">← 上一步</button>
    <button class="btn btn-primary" id="nextBtn" onclick="next()">下一步 →</button>
  </div>
  <div class="counter" id="counter"></div>
</div>

<script>
const steps = {steps_json};
let cur = 0;

function render() {{
  const s = steps[cur];
  document.getElementById('stage').innerHTML = `
    <div class="icon">${{s.icon || '📌'}}</div>
    <div class="stage-title">${{s.title}}</div>
    <div class="stage-desc">${{s.description}}</div>
  `;
  document.getElementById('stage').style.animation = 'none';
  setTimeout(() => document.getElementById('stage').style.animation = 'fadeScale .5s ease-out', 10);

  // progress dots
  let dots = '';
  steps.forEach((_, i) => {{
    const cls = i === cur ? 'dot active' : i < cur ? 'dot done' : 'dot';
    dots += `<div class="${{cls}}"></div>`;
  }});
  document.getElementById('progress').innerHTML = dots;
  document.getElementById('counter').textContent = `${{cur+1}} / ${{steps.length}}`;
  document.getElementById('prevBtn').disabled = cur === 0;
  document.getElementById('nextBtn').textContent = cur === steps.length - 1 ? '🎉 完成' : '下一步 →';
}}

function next() {{
  if (cur < steps.length - 1) {{ cur++; render(); }}
  else {{ /* done */ }}
}}
function prev() {{
  if (cur > 0) {{ cur--; render(); }}
}}

render();
</script>
</body>
</html>"""


# 用于 LLM 调用的 Prompt
ANIMATION_PROMPT = """\
你是一位教学设计专家。请根据以下知识点材料，设计一个逐步展示的教学动画脚本。
每一步包含一个标题、详细描述和一个表情图标。

【知识点材料】
{context}

【教师补充要求】
{teacher_requirement}

【步骤数量】约 {count} 步

请严格按以下JSON格式输出：
{{
  "title": "动画标题",
  "steps": [
    {{
      "title": "第1步: 步骤标题",
      "description": "详细描述这一步发生了什么（2-3句话）",
      "icon": "🧬"
    }}
  ]
}}
"""
