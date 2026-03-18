import os
import logging
from typing import Dict, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

# ===================== 配置与初始化 =====================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("refine_engine")
load_dotenv()
from src.llm_config import load_llm_config

config = load_llm_config()
def init_refine_llm():
    return ChatOpenAI(
        model=config['models']['refine'],  # qwen2.5-72b-instruct
        api_key=config['api_key'],
        base_url=config['base_url'],
        temperature=0.1,
        timeout=120
    )
parser = StrOutputParser()

def clean_markdown_ticks(text: str) -> str:
    """通用工具函数：清理 LLM 可能带有的 ```markdown 代码块标记"""
    text = text.strip()
    if text.startswith("```markdown"): text = text[11:]
    if text.startswith("```"): text = text[3:]
    if text.endswith("```"): text = text[:-3]
    return text.strip()

# =====================================================================
# 引擎一：PPT 大纲精修引擎 (Outline Refiner)
# =====================================================================
AGENT_REFINE_OUTLINE_PROMPT = """
你是专业的“AI 课件教研助理”。你的任务是根据教师意见，【局部重写】PPT大纲。

【绝对格式禁令 - 违反将导致系统崩溃】：
1. 必须且只能输出纯净的 Markdown 文本。
2. 顶层标题（主题）必须是：`# 课题名称`。
3. 章节标题（一级列表）必须是：`* 章节名称`。
4. 幻灯片页面标题（二级列表）必须是：`  * 页面标题` (开头必须是两个空格，紧跟一个星号)。
5. ❌ 绝对禁止使用 `-` 符号，绝对禁止输出三级列表。
6. ❌ 绝对禁止输出任何“好的”、“已为您修改”等解释性废话。

【精修与镜像逻辑】：
1. 你的修改必须是“手术刀式”的：除了教师明确要求修改的部分，其余所有章节、页面的文字必须【100%原样克隆】原始大纲，一个字符都不能少，格式也不能动。
2. 只有当教师提到“增加”、“删除”或“重写”时，才改变对应行的内容。

面对教师的修改意见，请你严格执行以下底层逻辑：
1. 触发“简化/合并”时：将原有的多个 `  * ` 节点合并为 1 个或更少的节点。合并后的新标题必须包含高度概括的信息。
2. 触发“增加案例/深化某页”时：在对应章节新增一行 `  * ` 节点。新节点的标题必须像一句“排版指令”，把案例的细节写进去。
3. 触发“调整顺序”时：移动对应的 `  * ` 节点位置，保持信息完整。
4. 触发“未提及的部分”时：绝对保持原样，原封不动地复制过来！不要随意删改老师没要求改的地方。

请只输出修改后的完整 Markdown 大纲，不要输出任何解释性的废话，不要带有 ```markdown 标记。
"""

outline_prompt = ChatPromptTemplate.from_messages([
    ("system", AGENT_REFINE_OUTLINE_PROMPT),
    ("human", """
    【当前的课件大纲】：\n{current_content}\n
    【教师修改意见】：\n{teacher_feedback}\n
    👉 请输出调整后的全新大纲：
    """)
])

def agent_refine_courseware(current_outline_str: str, feedback: str) -> Dict[str, Any]:
    """大纲精修函数：重写大纲并重新估算 PPT 页数"""
    logger.info(f"🤖 [大纲引擎] 正在分析教师意见: '{feedback}'...")
    try:
        llm_chain = outline_prompt | init_refine_llm() | parser
        new_outline = llm_chain.invoke({
            "current_content": current_outline_str,
            "teacher_feedback": feedback
        })
        
        new_outline = clean_markdown_ticks(new_outline)
        
        # 提取新标题和估算新页数
        lines = new_outline.split('\n')
        theme = lines[0].replace('#', '').strip() if lines else "未命名课件"
        
        chapter_count = new_outline.count("\n* ") + new_outline.count("\n- ")
        page_count = new_outline.count("\n  * ") + new_outline.count("\n  - ")
        total_pages = chapter_count + page_count + 2
        
        logger.info(f"✅ 大纲重构完成，新页数预估: {total_pages}页")
        return {
            "theme": theme,
            "total_pages": total_pages,
            "baidu_outline_str": new_outline
        }
    except Exception as e:
        logger.error(f"❌ 大纲重构失败: {e}")
        return {}


# =====================================================================
# 引擎二：Word 教案精修引擎 (Lesson Plan Refiner)
# =====================================================================
AGENT_REFINE_LESSON_PROMPT = """
你是专业的“AI 教案精修助理”。你的任务是根据教师的【修改意见】，对当前的【Markdown教案】进行局部精准修改。

【核心铁律】：
1. 只修改教师提及的部分！未提及的章节、段落、格式，必须【原封不动】地复制保留并完整输出。
2. 严格保持原有的标题层级结构（如：# 一、 课题名称，# 四、 教学过程 等）。
3. 如果在特定环节（如“教学过程”）新增了内容，请模仿原有的讲稿语气和格式（如：教师活动、学生活动）进行撰写。
4. 绝对不要输出任何解释性废话（如“好的，这是修改后的教案...”）。
5. 不要带有 ```markdown 标记，直接输出纯净的 Markdown 文本。
"""

lesson_prompt = ChatPromptTemplate.from_messages([
    ("system", AGENT_REFINE_LESSON_PROMPT),
    ("human", """
    【当前的 Word 教案原文】：\n{current_content}\n
    【教师修改意见】：\n{teacher_feedback}\n
    👉 请输出调整后的最新版教案 Markdown：
    """)
])

def agent_refine_lesson_plan(current_lesson_str: str, feedback: str) -> Dict[str, Any]:
    """教案精修函数：仅重写文本内容，无需计算页数"""
    logger.info(f"🤖 [教案引擎] 正在分析教师意见: '{feedback}'...")
    try:
        llm_chain = lesson_prompt | init_refine_llm() | parser
        new_lesson_plan = llm_chain.invoke({
            "current_content": current_lesson_str,
            "teacher_feedback": feedback
        })
        
        new_lesson_plan = clean_markdown_ticks(new_lesson_plan)
        
        logger.info(f"✅ 教案重构完成！")
        return {
            "lesson_plan_str": new_lesson_plan
        }
    except Exception as e:
        logger.error(f"❌ 教案重构失败: {e}")
        return {}
