"""
HTML5 Game Template Renderers.

Each renderer takes structured JSON data (from the LLM) and produces
a self-contained HTML5 page with embedded CSS/JS that can:
  - Run in any modern browser
  - Be exported as a standalone .html file
  - Be embedded into PPT via iframe / web-object
"""

from __future__ import annotations

import html
import json
from typing import Any, Dict

# ═══════════════════════════════════════════════════════════════
# Shared CSS / Head fragment
# ═══════════════════════════════════════════════════════════════

_HEAD = """\
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+SC:wght@300;400;500;700&display=swap');
  *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
  :root {{
    --bg: #0f172a; --surface: #1e293b; --card: #334155;
    --primary: #38bdf8; --secondary: #818cf8; --accent: #f472b6;
    --success: #34d399; --danger: #f87171; --warning: #fbbf24;
    --text: #f1f5f9; --text-dim: #94a3b8;
    --radius: 12px; --shadow: 0 8px 32px rgba(0,0,0,.35);
  }}
  body {{
    font-family: 'Noto Sans SC', system-ui, sans-serif;
    background: var(--bg); color: var(--text);
    min-height: 100vh; padding: 24px;
    background-image:
      radial-gradient(ellipse at 20% 50%, rgba(56,189,248,.08) 0%, transparent 50%),
      radial-gradient(ellipse at 80% 20%, rgba(129,140,248,.08) 0%, transparent 50%);
  }}
  .game-container {{
    max-width: 800px; margin: 0 auto;
  }}
  .game-header {{
    text-align: center; margin-bottom: 32px;
    animation: fadeInDown .6s ease-out;
  }}
  .game-header h1 {{
    font-size: 28px; font-weight: 700;
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text;
  }}
  .game-header .subtitle {{
    color: var(--text-dim); font-size: 14px; margin-top: 8px;
  }}
  .score-bar {{
    display: flex; justify-content: center; gap: 24px;
    margin: 16px 0; font-size: 15px; color: var(--text-dim);
  }}
  .score-bar span {{ font-weight: 500; color: var(--primary); }}
  .btn {{
    display: inline-flex; align-items: center; justify-content: center;
    padding: 10px 24px; border: none; border-radius: 8px;
    font-size: 15px; font-weight: 500; cursor: pointer;
    transition: all .2s ease; font-family: inherit;
  }}
  .btn-primary {{
    background: linear-gradient(135deg, var(--primary), var(--secondary));
    color: #fff; box-shadow: 0 4px 16px rgba(56,189,248,.3);
  }}
  .btn-primary:hover {{ transform: translateY(-2px); box-shadow: 0 6px 20px rgba(56,189,248,.4); }}
  .btn-outline {{
    background: transparent; border: 1.5px solid var(--primary);
    color: var(--primary);
  }}
  .btn-outline:hover {{ background: rgba(56,189,248,.1); }}

  .card {{
    background: var(--surface); border-radius: var(--radius);
    padding: 24px; margin-bottom: 16px;
    box-shadow: var(--shadow);
    border: 1px solid rgba(255,255,255,.06);
    animation: fadeInUp .5s ease-out both;
  }}

  .result-overlay {{
    position: fixed; inset: 0; background: rgba(15,23,42,.85);
    display: flex; align-items: center; justify-content: center;
    z-index: 1000; animation: fadeIn .3s;
  }}
  .result-box {{
    background: var(--surface); border-radius: 20px; padding: 40px;
    text-align: center; max-width: 420px; box-shadow: var(--shadow);
    animation: scaleIn .4s ease-out;
  }}
  .result-box h2 {{ font-size: 24px; margin-bottom: 12px; }}
  .result-box .score-display {{
    font-size: 56px; font-weight: 700;
    background: linear-gradient(135deg, var(--success), var(--primary));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    margin: 16px 0;
  }}

  @keyframes fadeIn {{ from {{ opacity: 0; }} to {{ opacity: 1; }} }}
  @keyframes fadeInUp {{ from {{ opacity: 0; transform: translateY(20px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  @keyframes fadeInDown {{ from {{ opacity: 0; transform: translateY(-20px); }} to {{ opacity: 1; transform: translateY(0); }} }}
  @keyframes scaleIn {{ from {{ opacity: 0; transform: scale(.8); }} to {{ opacity: 1; transform: scale(1); }} }}
  @keyframes shake {{ 0%,100% {{ transform: translateX(0); }} 25% {{ transform: translateX(-8px); }} 75% {{ transform: translateX(8px); }} }}
  @keyframes pulse {{ 0%,100% {{ transform: scale(1); }} 50% {{ transform: scale(1.05); }} }}
</style>
</head>
<body>
<div class="game-container">
"""

_FOOTER = """
</div>
</body>
</html>"""


# ═══════════════════════════════════════════════════════════════
# 1. Quiz (选择题)
# ═══════════════════════════════════════════════════════════════

def render_quiz(data: Dict[str, Any]) -> str:
    title = html.escape(data.get("title", "知识测验"))
    questions = data.get("questions", [])
    q_json = json.dumps(questions, ensure_ascii=False)

    return _HEAD.format(title=title) + f"""
<div class="game-header">
  <h1>📝 {title}</h1>
  <div class="subtitle">共 {len(questions)} 题 · 选择正确答案</div>
</div>
<div class="score-bar">
  <div>得分: <span id="score">0</span> / <span id="total">{len(questions)}</span></div>
  <div>进度: <span id="progress">1</span> / {len(questions)}</div>
</div>
<div id="quiz-area"></div>
<div id="nav-bar" style="display:flex;justify-content:center;gap:12px;margin-top:24px;"></div>

<script>
const questions = {q_json};
let current = 0, score = 0, answered = new Array(questions.length).fill(null);

function renderQ() {{
  const q = questions[current];
  const area = document.getElementById('quiz-area');
  const isAns = answered[current] !== null;
  let html = `<div class="card" style="animation-delay:${{current*0.05}}s">
    <div style="color:var(--primary);font-size:13px;margin-bottom:8px;">第 ${{current+1}} 题</div>
    <div style="font-size:17px;font-weight:500;margin-bottom:20px;line-height:1.7">${{q.stem}}</div>
    <div style="display:flex;flex-direction:column;gap:10px;">`;
  q.options.forEach((opt, i) => {{
    const letter = opt.charAt(0);
    let cls = 'opt-btn';
    if (isAns) {{
      if (letter === q.answer) cls += ' correct';
      else if (letter === answered[current]) cls += ' wrong';
    }}
    const disabled = isAns ? 'pointer-events:none;' : '';
    html += `<div class="opt-btn-wrap ${{cls}}" style="${{disabled}}" onclick="choose('${{letter}}')">
      <div class="opt-letter">${{letter}}</div>
      <div class="opt-text">${{opt.substring(2).trim()}}</div>
    </div>`;
  }});
  html += '</div>';
  if (isAns && q.explanation) {{
    const isCorrect = answered[current] === q.answer;
    html += `<div class="explanation ${{isCorrect?'exp-correct':'exp-wrong'}}">
      <strong>${{isCorrect?'✓ 正确':'✗ 错误'}}</strong> — ${{q.explanation}}
    </div>`;
  }}
  html += '</div>';
  area.innerHTML = html;
  document.getElementById('progress').textContent = current + 1;

  const nav = document.getElementById('nav-bar');
  nav.innerHTML = '';
  if (current > 0) nav.innerHTML += '<button class="btn btn-outline" onclick="prev()">← 上一题</button>';
  if (current < questions.length - 1) nav.innerHTML += '<button class="btn btn-primary" onclick="next()">下一题 →</button>';
  else if (isAns) nav.innerHTML += '<button class="btn btn-primary" onclick="showResult()">查看结果</button>';
}}

function choose(letter) {{
  if (answered[current] !== null) return;
  answered[current] = letter;
  if (letter === questions[current].answer) score++;
  document.getElementById('score').textContent = score;
  renderQ();
}}

function next() {{ if (current < questions.length - 1) {{ current++; renderQ(); }} }}
function prev() {{ if (current > 0) {{ current--; renderQ(); }} }}

function showResult() {{
  const pct = Math.round(score / questions.length * 100);
  let emoji = pct >= 90 ? '🏆' : pct >= 70 ? '🌟' : pct >= 50 ? '💪' : '📚';
  document.body.insertAdjacentHTML('beforeend', `
    <div class="result-overlay" onclick="this.remove()">
      <div class="result-box">
        <div style="font-size:48px;">${{emoji}}</div>
        <h2>测验完成!</h2>
        <div class="score-display">${{pct}}%</div>
        <div style="color:var(--text-dim);margin-bottom:20px;">答对 ${{score}} / ${{questions.length}} 题</div>
        <button class="btn btn-primary" onclick="location.reload()">重新开始</button>
      </div>
    </div>`);
}}

renderQ();
</script>

<style>
.opt-btn-wrap {{
  display: flex; align-items: center; gap: 14px;
  padding: 14px 18px; border-radius: 10px; cursor: pointer;
  background: var(--card); border: 2px solid transparent;
  transition: all .2s;
}}
.opt-btn-wrap:hover {{ border-color: var(--primary); transform: translateX(4px); }}
.opt-letter {{
  width: 32px; height: 32px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: rgba(56,189,248,.15); color: var(--primary);
  font-weight: 700; font-size: 14px; flex-shrink: 0;
}}
.opt-text {{ font-size: 15px; line-height: 1.5; }}
.correct {{ border-color: var(--success) !important; background: rgba(52,211,153,.1) !important; }}
.correct .opt-letter {{ background: var(--success); color: #fff; }}
.wrong {{ border-color: var(--danger) !important; background: rgba(248,113,113,.1) !important; animation: shake .4s; }}
.wrong .opt-letter {{ background: var(--danger); color: #fff; }}
.explanation {{
  margin-top: 16px; padding: 14px 18px; border-radius: 10px;
  font-size: 14px; line-height: 1.6; animation: fadeIn .3s;
}}
.exp-correct {{ background: rgba(52,211,153,.12); border-left: 3px solid var(--success); }}
.exp-wrong {{ background: rgba(248,113,113,.12); border-left: 3px solid var(--danger); }}
</style>
""" + _FOOTER


# ═══════════════════════════════════════════════════════════════
# 2. Matching (连线配对)
# ═══════════════════════════════════════════════════════════════

def render_matching(data: Dict[str, Any]) -> str:
    title = html.escape(data.get("title", "连线配对"))
    pairs = data.get("pairs", [])
    pairs_json = json.dumps(pairs, ensure_ascii=False)

    return _HEAD.format(title=title) + f"""
<div class="game-header">
  <h1>🔗 {title}</h1>
  <div class="subtitle">将左侧概念与右侧定义正确配对 · 点击选中后点击配对项</div>
</div>
<div class="score-bar">
  <div>已配对: <span id="matched">0</span> / <span>{len(pairs)}</span></div>
</div>
<div id="match-area" style="display:flex;gap:24px;justify-content:center;flex-wrap:wrap;"></div>
<div style="text-align:center;margin-top:24px;">
  <button class="btn btn-outline" onclick="resetGame()">重新开始</button>
</div>

<script>
const pairs = {pairs_json};
let selectedLeft = null, selectedRight = null, matchedCount = 0;
const leftItems = pairs.map((p,i) => ({{id: i, text: p.left, matched: false}}));
const rightItems = [...pairs.map((p,i) => ({{id: i, text: p.right, matched: false}}))];
// shuffle right
for (let i = rightItems.length - 1; i > 0; i--) {{
  const j = Math.floor(Math.random() * (i + 1));
  [rightItems[i], rightItems[j]] = [rightItems[j], rightItems[i]];
}}

function render() {{
  const area = document.getElementById('match-area');
  let lhtml = '<div class="match-col">';
  leftItems.forEach(it => {{
    const cls = it.matched ? 'match-item matched' : (selectedLeft === it.id ? 'match-item selected-left' : 'match-item');
    lhtml += `<div class="${{cls}}" data-side="left" data-id="${{it.id}}" onclick="selectItem('left',${{it.id}})">${{it.text}}</div>`;
  }});
  lhtml += '</div>';

  let rhtml = '<div class="match-col">';
  rightItems.forEach(it => {{
    const cls = it.matched ? 'match-item matched' : (selectedRight === it.id ? 'match-item selected-right' : 'match-item');
    rhtml += `<div class="${{cls}}" data-side="right" data-id="${{it.id}}" onclick="selectItem('right',${{it.id}})">${{it.text}}</div>`;
  }});
  rhtml += '</div>';

  area.innerHTML = lhtml + '<div class="match-divider"></div>' + rhtml;
  document.getElementById('matched').textContent = matchedCount;
}}

function selectItem(side, id) {{
  if (side === 'left') {{
    if (leftItems[id].matched) return;
    selectedLeft = (selectedLeft === id) ? null : id;
  }} else {{
    if (rightItems.find(r => r.id === id).matched) return;
    selectedRight = (selectedRight === id) ? null : id;
  }}
  if (selectedLeft !== null && selectedRight !== null) {{
    checkMatch();
  }} else {{
    render();
  }}
}}

function checkMatch() {{
  const rItem = rightItems.find(r => r.id === selectedRight);
  if (selectedLeft === rItem.id) {{
    leftItems[selectedLeft].matched = true;
    rItem.matched = true;
    matchedCount++;
    if (matchedCount === pairs.length) setTimeout(showComplete, 500);
  }}
  selectedLeft = null;
  selectedRight = null;
  render();
}}

function showComplete() {{
  document.body.insertAdjacentHTML('beforeend', `
    <div class="result-overlay" onclick="this.remove()">
      <div class="result-box">
        <div style="font-size:48px;">🎉</div>
        <h2>全部配对完成!</h2>
        <div style="color:var(--text-dim);margin:16px 0;">你成功匹配了所有 ${{pairs.length}} 组概念</div>
        <button class="btn btn-primary" onclick="location.reload()">再玩一次</button>
      </div>
    </div>`);
}}

function resetGame() {{
  matchedCount = 0; selectedLeft = null; selectedRight = null;
  leftItems.forEach(it => it.matched = false);
  rightItems.forEach(it => it.matched = false);
  for (let i = rightItems.length - 1; i > 0; i--) {{
    const j = Math.floor(Math.random() * (i + 1));
    [rightItems[i], rightItems[j]] = [rightItems[j], rightItems[i]];
  }}
  render();
}}

render();
</script>

<style>
.match-col {{ display: flex; flex-direction: column; gap: 12px; flex: 1; max-width: 340px; }}
.match-divider {{ width: 2px; background: linear-gradient(to bottom, transparent, var(--primary), transparent); flex-shrink: 0; }}
.match-item {{
  padding: 16px 20px; border-radius: 10px; cursor: pointer;
  background: var(--surface); border: 2px solid rgba(255,255,255,.08);
  font-size: 14px; line-height: 1.5; transition: all .2s;
}}
.match-item:hover {{ border-color: var(--primary); transform: scale(1.02); }}
.selected-left {{ border-color: var(--primary) !important; background: rgba(56,189,248,.12) !important; box-shadow: 0 0 20px rgba(56,189,248,.2); }}
.selected-right {{ border-color: var(--secondary) !important; background: rgba(129,140,248,.12) !important; box-shadow: 0 0 20px rgba(129,140,248,.2); }}
.matched {{
  border-color: var(--success) !important; background: rgba(52,211,153,.1) !important;
  opacity: .7; pointer-events: none;
}}
</style>
""" + _FOOTER


# ═══════════════════════════════════════════════════════════════
# 3. Sorting (排序游戏)
# ═══════════════════════════════════════════════════════════════

def render_sorting(data: Dict[str, Any]) -> str:
    title = html.escape(data.get("title", "排序游戏"))
    tasks = data.get("tasks", [])
    tasks_json = json.dumps(tasks, ensure_ascii=False)

    return _HEAD.format(title=title) + f"""
<div class="game-header">
  <h1>📋 {title}</h1>
  <div class="subtitle">拖拽或点击箭头将步骤排列为正确顺序</div>
</div>
<div id="sort-area"></div>

<script>
const tasks = {tasks_json};
let currentTask = 0;

function shuffle(arr) {{
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {{
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }}
  return a;
}}

let items = [];
let dragIdx = null;

function renderTask() {{
  const task = tasks[currentTask];
  items = shuffle(task.correct_order);
  renderItems(task);
}}

function renderItems(task) {{
  const area = document.getElementById('sort-area');
  let html = `<div class="card">
    <div style="font-size:15px;margin-bottom:20px;color:var(--text-dim);">${{task.description}}</div>
    <div id="sort-list">`;
  items.forEach((item, i) => {{
    html += `<div class="sort-item" draggable="true"
      ondragstart="onDragStart(event,${{i}})"
      ondragover="event.preventDefault()"
      ondrop="onDrop(event,${{i}})">
      <span class="sort-num">${{i+1}}</span>
      <span class="sort-text">${{item}}</span>
      <span class="sort-arrows">
        <button class="arrow-btn" onclick="moveUp(${{i}})">▲</button>
        <button class="arrow-btn" onclick="moveDown(${{i}})">▼</button>
      </span>
    </div>`;
  }});
  html += `</div>
    <div style="display:flex;gap:12px;justify-content:center;margin-top:20px;">
      <button class="btn btn-primary" onclick="checkOrder()">提交答案</button>
      <button class="btn btn-outline" onclick="renderTask()">重新打乱</button>
    </div>
    <div id="sort-feedback"></div>
  </div>`;
  area.innerHTML = html;
}}

function onDragStart(e, i) {{ dragIdx = i; e.dataTransfer.effectAllowed = 'move'; }}
function onDrop(e, i) {{
  e.preventDefault();
  if (dragIdx === null || dragIdx === i) return;
  const item = items.splice(dragIdx, 1)[0];
  items.splice(i, 0, item);
  dragIdx = null;
  renderItems(tasks[currentTask]);
}}
function moveUp(i) {{ if (i > 0) {{ [items[i-1], items[i]] = [items[i], items[i-1]]; renderItems(tasks[currentTask]); }} }}
function moveDown(i) {{ if (i < items.length-1) {{ [items[i], items[i+1]] = [items[i+1], items[i]]; renderItems(tasks[currentTask]); }} }}

function checkOrder() {{
  const correct = tasks[currentTask].correct_order;
  const isCorrect = items.every((item, i) => item === correct[i]);
  const fb = document.getElementById('sort-feedback');
  if (isCorrect) {{
    fb.innerHTML = '<div class="sort-success">🎉 完全正确! 排列顺序无误!</div>';
    if (currentTask < tasks.length - 1) {{
      fb.innerHTML += `<button class="btn btn-primary" style="margin-top:12px;" onclick="nextTask()">下一题 →</button>`;
    }}
  }} else {{
    let wrongCount = items.filter((item, i) => item !== correct[i]).length;
    fb.innerHTML = `<div class="sort-wrong">❌ 还有 ${{wrongCount}} 个位置不正确，再试试!</div>`;
    // highlight wrong items
    document.querySelectorAll('.sort-item').forEach((el, i) => {{
      if (items[i] !== correct[i]) el.style.borderColor = 'var(--danger)';
      else el.style.borderColor = 'var(--success)';
    }});
  }}
}}

function nextTask() {{ currentTask++; renderTask(); }}
renderTask();
</script>

<style>
.sort-item {{
  display: flex; align-items: center; gap: 14px;
  padding: 14px 18px; margin-bottom: 8px; border-radius: 10px;
  background: var(--card); border: 2px solid transparent;
  cursor: grab; transition: all .2s; user-select: none;
}}
.sort-item:hover {{ border-color: var(--primary); }}
.sort-item:active {{ cursor: grabbing; }}
.sort-num {{
  width: 28px; height: 28px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  background: rgba(56,189,248,.2); color: var(--primary);
  font-weight: 700; font-size: 13px; flex-shrink: 0;
}}
.sort-text {{ flex: 1; font-size: 14px; }}
.sort-arrows {{ display: flex; flex-direction: column; gap: 2px; }}
.arrow-btn {{
  background: none; border: none; color: var(--text-dim);
  cursor: pointer; font-size: 10px; padding: 2px 6px; border-radius: 4px;
}}
.arrow-btn:hover {{ background: rgba(255,255,255,.1); color: var(--text); }}
.sort-success {{
  margin-top: 16px; padding: 14px 18px; border-radius: 10px;
  background: rgba(52,211,153,.12); border-left: 3px solid var(--success);
  font-size: 15px; animation: fadeIn .3s;
}}
.sort-wrong {{
  margin-top: 16px; padding: 14px 18px; border-radius: 10px;
  background: rgba(248,113,113,.12); border-left: 3px solid var(--danger);
  font-size: 15px; animation: shake .4s;
}}
</style>
""" + _FOOTER


# ═══════════════════════════════════════════════════════════════
# 4. Fill-in-the-Blank (填空题)
# ═══════════════════════════════════════════════════════════════

def render_fill_blank(data: Dict[str, Any]) -> str:
    title = html.escape(data.get("title", "填空题"))
    questions = data.get("questions", [])
    q_json = json.dumps(questions, ensure_ascii=False)

    return _HEAD.format(title=title) + f"""
<div class="game-header">
  <h1>✏️ {title}</h1>
  <div class="subtitle">在空白处填入正确答案</div>
</div>
<div class="score-bar">
  <div>得分: <span id="score">0</span> / <span id="total">{len(questions)}</span></div>
</div>
<div id="fill-area"></div>
<div style="text-align:center;margin-top:24px;">
  <button class="btn btn-primary" onclick="submitAll()">全部提交</button>
  <button class="btn btn-outline" onclick="location.reload()">重新开始</button>
</div>

<script>
const questions = {q_json};
let score = 0, submitted = false;

function render() {{
  const area = document.getElementById('fill-area');
  let html = '';
  questions.forEach((q, qi) => {{
    html += `<div class="card" style="animation-delay:${{qi*0.08}}s">
      <div style="color:var(--primary);font-size:13px;margin-bottom:8px;">第 ${{qi+1}} 题</div>`;
    // Replace ____ with input fields
    let parts = q.sentence.split('____');
    let sentence = '';
    parts.forEach((part, pi) => {{
      sentence += `<span>${{part}}</span>`;
      if (pi < parts.length - 1) {{
        sentence += `<input type="text" class="fill-input" id="fill-${{qi}}-${{pi}}"
          placeholder="填写答案" ${{submitted?'disabled':''}}>`;
      }}
    }});
    html += `<div class="fill-sentence">${{sentence}}</div>`;
    if (q.hint) html += `<div class="fill-hint">💡 提示: ${{q.hint}}</div>`;
    html += `<div id="fill-fb-${{qi}}" class="fill-feedback"></div></div>`;
  }});
  area.innerHTML = html;
}}

function submitAll() {{
  if (submitted) return;
  submitted = true;
  score = 0;
  questions.forEach((q, qi) => {{
    const fb = document.getElementById('fill-fb-' + qi);
    let allCorrect = true;
    q.blanks.forEach((ans, bi) => {{
      const input = document.getElementById(`fill-${{qi}}-${{bi}}`);
      input.disabled = true;
      const userAns = (input.value || '').trim();
      // Flexible matching: contains the key answer
      if (userAns && (userAns === ans || ans.includes(userAns) || userAns.includes(ans))) {{
        input.style.borderColor = 'var(--success)';
        input.style.background = 'rgba(52,211,153,.1)';
      }} else {{
        input.style.borderColor = 'var(--danger)';
        input.style.background = 'rgba(248,113,113,.1)';
        allCorrect = false;
      }}
    }});
    if (allCorrect) {{
      score++;
      fb.innerHTML = '<div class="exp-correct" style="margin-top:12px;padding:10px 14px;border-radius:8px;font-size:13px;">✓ 正确</div>';
    }} else {{
      fb.innerHTML = `<div class="exp-wrong" style="margin-top:12px;padding:10px 14px;border-radius:8px;font-size:13px;">✗ 参考答案: ${{q.blanks.join(' / ')}}</div>`;
    }}
  }});
  document.getElementById('score').textContent = score;
}}

render();
</script>

<style>
.fill-sentence {{ font-size: 16px; line-height: 2.2; }}
.fill-input {{
  display: inline-block; width: 140px; padding: 4px 10px;
  border: 2px solid var(--card); border-radius: 6px;
  background: var(--card); color: var(--text);
  font-size: 14px; font-family: inherit;
  text-align: center; transition: all .2s;
  margin: 0 4px;
}}
.fill-input:focus {{ border-color: var(--primary); outline: none; box-shadow: 0 0 12px rgba(56,189,248,.2); }}
.fill-hint {{ color: var(--text-dim); font-size: 13px; margin-top: 8px; }}
</style>
""" + _FOOTER


# ═══════════════════════════════════════════════════════════════
# 5. True/False (判断题)
# ═══════════════════════════════════════════════════════════════

def render_true_false(data: Dict[str, Any]) -> str:
    title = html.escape(data.get("title", "判断题"))
    questions = data.get("questions", [])
    q_json = json.dumps(questions, ensure_ascii=False)

    return _HEAD.format(title=title) + f"""
<div class="game-header">
  <h1>⚖️ {title}</h1>
  <div class="subtitle">判断以下陈述的正误</div>
</div>
<div class="score-bar">
  <div>得分: <span id="score">0</span> / {len(questions)}</div>
  <div>进度: <span id="prog">1</span> / {len(questions)}</div>
</div>
<div id="tf-area"></div>

<script>
const questions = {q_json};
let cur = 0, score = 0, answered = new Array(questions.length).fill(null);

function render() {{
  const q = questions[cur];
  const isAns = answered[cur] !== null;
  let html = `<div class="card">
    <div style="color:var(--primary);font-size:13px;margin-bottom:8px;">第 ${{cur+1}} 题</div>
    <div style="font-size:17px;font-weight:500;margin-bottom:24px;line-height:1.7">${{q.statement}}</div>
    <div style="display:flex;gap:16px;justify-content:center;">`;
  // True button
  let tCls = 'tf-btn', fCls = 'tf-btn';
  if (isAns) {{
    if (q.answer === true) tCls += ' tf-correct'; else tCls += ' tf-dim';
    if (q.answer === false) fCls += ' tf-correct'; else fCls += ' tf-dim';
    if (answered[cur] === true && q.answer !== true) tCls += ' tf-wrong';
    if (answered[cur] === false && q.answer !== false) fCls += ' tf-wrong';
  }}
  html += `<div class="${{tCls}}" onclick="answer(true)" ${{isAns?'style="pointer-events:none"':''}}>
    <span style="font-size:28px;">✓</span><span>正确</span>
  </div>`;
  html += `<div class="${{fCls}}" onclick="answer(false)" ${{isAns?'style="pointer-events:none"':''}}>
    <span style="font-size:28px;">✗</span><span>错误</span>
  </div></div>`;
  if (isAns && q.explanation) {{
    const ok = answered[cur] === q.answer;
    html += `<div class="${{ok?'exp-correct':'exp-wrong'}}" style="margin-top:20px;padding:14px;border-radius:10px;font-size:14px;line-height:1.6;">
      <strong>${{ok?'✓ 回答正确':'✗ 回答错误'}}</strong> — ${{q.explanation}}</div>`;
  }}
  html += '</div>';
  // Nav
  html += '<div style="display:flex;justify-content:center;gap:12px;margin-top:16px;">';
  if (cur > 0) html += '<button class="btn btn-outline" onclick="cur--;render();">← 上一题</button>';
  if (cur < questions.length-1 && isAns) html += '<button class="btn btn-primary" onclick="cur++;render();">下一题 →</button>';
  else if (cur === questions.length-1 && isAns) html += '<button class="btn btn-primary" onclick="showResult()">查看结果</button>';
  html += '</div>';

  document.getElementById('tf-area').innerHTML = html;
  document.getElementById('prog').textContent = cur + 1;
}}

function answer(val) {{
  if (answered[cur] !== null) return;
  answered[cur] = val;
  if (val === questions[cur].answer) score++;
  document.getElementById('score').textContent = score;
  render();
}}

function showResult() {{
  const pct = Math.round(score / questions.length * 100);
  document.body.insertAdjacentHTML('beforeend', `
    <div class="result-overlay" onclick="this.remove()">
      <div class="result-box">
        <div style="font-size:48px;">${{pct >= 80 ? '🏆' : '💪'}}</div>
        <h2>判断题完成!</h2>
        <div class="score-display">${{pct}}%</div>
        <div style="color:var(--text-dim);margin-bottom:20px;">答对 ${{score}} / ${{questions.length}} 题</div>
        <button class="btn btn-primary" onclick="location.reload()">重新开始</button>
      </div>
    </div>`);
}}

render();
</script>

<style>
.tf-btn {{
  display: flex; flex-direction: column; align-items: center;
  gap: 8px; padding: 24px 40px; border-radius: 16px;
  background: var(--card); border: 2px solid transparent;
  cursor: pointer; transition: all .2s; font-size: 16px; font-weight: 500;
}}
.tf-btn:hover {{ border-color: var(--primary); transform: scale(1.05); }}
.tf-correct {{ border-color: var(--success) !important; background: rgba(52,211,153,.15) !important; }}
.tf-wrong {{ border-color: var(--danger) !important; background: rgba(248,113,113,.15) !important; animation: shake .4s; }}
.tf-dim {{ opacity: .5; }}
</style>
""" + _FOOTER


# ═══════════════════════════════════════════════════════════════
# 6. Flashcard (翻卡记忆)
# ═══════════════════════════════════════════════════════════════

def render_flashcard(data: Dict[str, Any]) -> str:
    title = html.escape(data.get("title", "翻卡记忆"))
    cards = data.get("cards", [])
    cards_json = json.dumps(cards, ensure_ascii=False)

    return _HEAD.format(title=title) + f"""
<div class="game-header">
  <h1>🃏 {title}</h1>
  <div class="subtitle">点击卡片翻转，记忆概念与定义</div>
</div>
<div class="score-bar">
  <div>卡片: <span id="cur">1</span> / {len(cards)}</div>
  <div>已掌握: <span id="mastered">0</span></div>
</div>
<div id="fc-area" style="display:flex;justify-content:center;"></div>
<div style="display:flex;justify-content:center;gap:12px;margin-top:24px;">
  <button class="btn btn-outline" onclick="prevCard()">← 上一张</button>
  <button class="btn btn-outline" style="border-color:var(--danger);color:var(--danger);" onclick="markCard(false)">还不熟</button>
  <button class="btn btn-outline" style="border-color:var(--success);color:var(--success);" onclick="markCard(true)">已掌握</button>
  <button class="btn btn-primary" onclick="nextCard()">下一张 →</button>
</div>

<script>
const cards = {cards_json};
let cur = 0, flipped = false, mastered = new Set();

function render() {{
  const c = cards[cur];
  const fc = document.getElementById('fc-area');
  const flipCls = flipped ? 'flipped' : '';
  fc.innerHTML = `<div class="flashcard ${{flipCls}}" onclick="flipCard()">
    <div class="fc-inner">
      <div class="fc-front">
        <div class="fc-label">概念</div>
        <div class="fc-content">${{c.front}}</div>
        <div class="fc-tip">点击翻转 →</div>
      </div>
      <div class="fc-back">
        <div class="fc-label">释义</div>
        <div class="fc-content">${{c.back}}</div>
      </div>
    </div>
  </div>`;
  document.getElementById('cur').textContent = cur + 1;
  document.getElementById('mastered').textContent = mastered.size;
}}

function flipCard() {{ flipped = !flipped; render(); }}
function nextCard() {{ if (cur < cards.length - 1) {{ cur++; flipped = false; render(); }} }}
function prevCard() {{ if (cur > 0) {{ cur--; flipped = false; render(); }} }}
function markCard(ok) {{
  if (ok) mastered.add(cur); else mastered.delete(cur);
  document.getElementById('mastered').textContent = mastered.size;
  if (mastered.size === cards.length) {{
    document.body.insertAdjacentHTML('beforeend', `
      <div class="result-overlay" onclick="this.remove()">
        <div class="result-box">
          <div style="font-size:48px;">🧠</div>
          <h2>全部掌握!</h2>
          <div style="color:var(--text-dim);margin:16px 0;">你已掌握所有 ${{cards.length}} 张卡片</div>
          <button class="btn btn-primary" onclick="location.reload()">再复习一次</button>
        </div>
      </div>`);
  }}
  nextCard();
}}

render();
</script>

<style>
.flashcard {{
  width: 420px; height: 280px; perspective: 800px; cursor: pointer;
}}
.fc-inner {{
  position: relative; width: 100%; height: 100%;
  transition: transform .6s; transform-style: preserve-3d;
}}
.flashcard.flipped .fc-inner {{ transform: rotateY(180deg); }}
.fc-front, .fc-back {{
  position: absolute; inset: 0; backface-visibility: hidden;
  border-radius: 16px; padding: 32px;
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  text-align: center;
}}
.fc-front {{
  background: linear-gradient(135deg, var(--surface), var(--card));
  border: 2px solid rgba(56,189,248,.3);
}}
.fc-back {{
  background: linear-gradient(135deg, rgba(56,189,248,.15), rgba(129,140,248,.15));
  border: 2px solid rgba(129,140,248,.3);
  transform: rotateY(180deg);
}}
.fc-label {{ font-size: 12px; color: var(--text-dim); text-transform: uppercase; letter-spacing: 2px; margin-bottom: 12px; }}
.fc-content {{ font-size: 18px; font-weight: 500; line-height: 1.6; }}
.fc-tip {{ font-size: 12px; color: var(--text-dim); margin-top: 16px; }}
</style>
""" + _FOOTER


# ═══════════════════════════════════════════════════════════════
# 7. Flow Fill (流程补全)
# ═══════════════════════════════════════════════════════════════

def render_flow_fill(data: Dict[str, Any]) -> str:
    title = html.escape(data.get("title", "流程补全"))
    desc = html.escape(data.get("description", ""))
    nodes = data.get("nodes", [])
    arrows = data.get("arrows", [])
    blanks = data.get("blank_answers", {})
    data_json = json.dumps({"nodes": nodes, "arrows": arrows, "blank_answers": blanks}, ensure_ascii=False)

    return _HEAD.format(title=title) + f"""
<div class="game-header">
  <h1>🔬 {title}</h1>
  <div class="subtitle">{desc} · 从选项中拖入正确内容补全流程</div>
</div>
<div id="flow-area"></div>

<script>
const data = {data_json};
const blanks = data.blank_answers;
const blankIds = Object.keys(blanks);
let userAnswers = {{}};

function shuffle(arr) {{
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {{
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }}
  return a;
}}

const options = shuffle(Object.values(blanks));

function render() {{
  let html = '<div class="card">';
  // Options bank
  html += '<div class="flow-bank"><div style="font-size:13px;color:var(--text-dim);margin-bottom:8px;">📦 选项库 (点击选项，再点击空白节点)</div><div class="flow-opts">';
  options.forEach((opt, i) => {{
    const used = Object.values(userAnswers).includes(opt);
    html += `<div class="flow-opt ${{used?'flow-opt-used':''}}" onclick="selectOpt('${{opt.replace(/'/g,"\\\\'")}}')">${{opt}}</div>`;
  }});
  html += '</div></div>';
  // Flow nodes
  html += '<div class="flow-nodes">';
  data.nodes.forEach((node, i) => {{
    const isBlank = node.is_blank;
    const filled = userAnswers[node.id];
    if (isBlank) {{
      html += `<div class="flow-node flow-blank" onclick="fillBlank(${{node.id}})">
        ${{filled || '<span style=\\"color:var(--text-dim)\\">点击填入</span>'}}
      </div>`;
    }} else {{
      html += `<div class="flow-node">${{node.label}}</div>`;
    }}
    if (i < data.nodes.length - 1) {{
      const arrow = data.arrows.find(a => a.from === data.nodes[i].id && a.to === data.nodes[i+1].id);
      html += `<div class="flow-arrow">↓ ${{arrow ? '<span style="font-size:11px;color:var(--text-dim)">' + arrow.label + '</span>' : ''}}</div>`;
    }}
  }});
  html += '</div>';
  html += `<div style="text-align:center;margin-top:20px;">
    <button class="btn btn-primary" onclick="checkFlow()">检查答案</button>
    <button class="btn btn-outline" onclick="resetFlow()">重置</button>
  </div>`;
  html += '<div id="flow-fb"></div></div>';
  document.getElementById('flow-area').innerHTML = html;
}}

let selectedOpt = null;
function selectOpt(opt) {{ selectedOpt = opt; }}
function fillBlank(nodeId) {{
  if (selectedOpt) {{
    userAnswers[nodeId] = selectedOpt;
    selectedOpt = null;
    render();
  }}
}}

function checkFlow() {{
  let correct = 0;
  blankIds.forEach(id => {{
    if (userAnswers[id] === blanks[id]) correct++;
  }});
  const fb = document.getElementById('flow-fb');
  if (correct === blankIds.length) {{
    fb.innerHTML = '<div class="sort-success" style="margin-top:16px;">🎉 完全正确! 流程补全无误!</div>';
  }} else {{
    fb.innerHTML = `<div class="sort-wrong" style="margin-top:16px;">还有 ${{blankIds.length - correct}} 处错误，再试试!</div>`;
  }}
}}

function resetFlow() {{ userAnswers = {{}}; selectedOpt = null; render(); }}
render();
</script>

<style>
.flow-bank {{ margin-bottom: 24px; }}
.flow-opts {{ display: flex; flex-wrap: wrap; gap: 8px; }}
.flow-opt {{
  padding: 8px 16px; border-radius: 8px; font-size: 13px;
  background: var(--card); border: 1.5px solid rgba(56,189,248,.3);
  cursor: pointer; transition: all .2s;
}}
.flow-opt:hover {{ border-color: var(--primary); background: rgba(56,189,248,.1); }}
.flow-opt-used {{ opacity: .35; pointer-events: none; text-decoration: line-through; }}
.flow-nodes {{ display: flex; flex-direction: column; align-items: center; gap: 4px; }}
.flow-node {{
  padding: 14px 28px; border-radius: 12px; font-size: 14px;
  background: var(--card); border: 2px solid rgba(255,255,255,.1);
  min-width: 220px; text-align: center; transition: all .2s;
}}
.flow-blank {{
  border-style: dashed; border-color: var(--primary);
  cursor: pointer; min-height: 48px;
}}
.flow-blank:hover {{ background: rgba(56,189,248,.08); }}
.flow-arrow {{ color: var(--primary); font-size: 18px; display: flex; flex-direction: column; align-items: center; }}
</style>
""" + _FOOTER


# ═══════════════════════════════════════════════════════════════
# Renderer registry
# ═══════════════════════════════════════════════════════════════

GAME_RENDERERS = {
    "quiz":       render_quiz,
    "matching":   render_matching,
    "sorting":    render_sorting,
    "fill_blank": render_fill_blank,
    "true_false": render_true_false,
    "flashcard":  render_flashcard,
    "flow_fill":  render_flow_fill,
}
