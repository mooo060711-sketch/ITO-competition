import os
import logging
import time
import json
from typing import Optional, Dict, Any
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from src.tools.schemas import IntentSlots

# ===================== 配置与初始化 =====================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("blueprint_engine")
load_dotenv()

from src.llm_config import load_llm_config
from langchain_openai import ChatOpenAI

config = load_llm_config()

def init_courseware_llm():
    return ChatOpenAI(
        model=config['models']['outline'],  # deepseek-chat
        api_key=config['api_key'],
        base_url=config['base_url'],
        temperature=0.1,
        timeout=120
    )

parser = StrOutputParser()

# ===================== 核心 Prompt 定义 =====================
SYSTEM_PROMPT = """
你是一名深耕一线、具备深厚教育心理学背景的生物金牌教研专家。
你的任务是根据下述全量输入，生成符合百度千帆API排版逻辑的 PPT 深度大纲。

### 【排版禁忌 - 必须严格遵守】
1. **禁止生成任何导语**：严禁出现“根据您的要求”、“为您构建了大纲”等任何非大纲的寒暄话语。
2. **输出格式**：仅输出 Markdown 格式的大纲内容，严禁包含任何代码块标记(```)之外的文字，甚至连代码块标记也不要，直接输出文本内容即可。
3. **禁止超页**：务必严格按照计算公式控制内容页数量，切勿为了填充内容而生成过多页面。
4. **禁止生成目录具体内容**：目录二字和目录具体内容不用写在大纲里，直接从章节开始写起就行了,只能有1页目录，用来汇总章节。

### 一、 核心输入与执行准则
你必须基于以下变量构建大纲：
- **教学主题**: {theme} | **受众属性**: {audience}
- **教学目标**: {teaching_objectives} | **重点难点**: {key_points}
- **必含知识点**: {required_knowledge} | **特殊要求**: {other_requirements}
- **教师教学思路**: {teaching_logic} (这是PPT的骨架逻辑，必须严格按此顺序组织章节)

### 二、 页数管控与结构逻辑 (红线指令)
1. **强制页数红线**：目标总页数必须控制在 {page_range} 页。
2. **强制计算公式**：
   - 目标内容页数量 (M) = {page_range} - 1(目录) - N(实际章节数)。
   - **你必须在生成内容前计算 M 的值，且严禁输出超过 M 个二级列表 (`  * `)。**
3. **计数检查**：输出结尾必须包含一行：`[页数检查：共{{总页数}}页]`，请务必核实该数字是否等于 {page_range}。
4. **内容结构**：
   - 章节页: `* {{章节名称}}`
   - 内容页: `  * {{页面核心标题}}`
   - 正文要点: `    - {{丰满的要点}}`
   - 备注层: `    > 备注：{{详细深度内容}}`
5. **封面页**：放大纲第一行
    -结构：`# {{主题名字}}`

### 三、 多源资料的“智能融合”与“深度填充”
1. **RAG 知识注入 (参考知识点)**：将 `{local_kb_context}` 中的实验细节、生理机理、精确数据，转化为“现象描述 + 机理分析”的完整句式，作为内容页要点的核心支撑。
2. **用户素材解析 (题目/案例)**：将 `{user_material_context}` 中的题目与案例，结合 `{key_points}` 中的难点，重构为“情境描述 + 关键提问 + 核心解析”的结构，置于对应章节中。
3. **落实教学目标**：每一页内容的撰写，必须围绕 `{teaching_objectives}` 展开，确保所有 `{required_knowledge}` 的知识点在 PPT 中均有对应的页面呈现。
4. **适配受众逻辑**：根据 `{audience}` 的认知水平，调整语言的专业度与引导性；根据 `{other_requirements}` 进行个性化大纲内容调整。

### 四、 格式与深度要求
1. **正文深度**：禁止出现“参考资料所述”等空洞描述，必须直接呈现检索到的具体事实、数值、实验过程。
2. **正文要求**：每张内容页(`  * `)下方包含3-4个要点(`    - `)，每个要点必须采用【核心概念】+ 详细解释的句式（约 50-70 个汉字）。
3. **备注深度**：仅限 `{local_kb_context}` 中不宜外露的原始结论、前沿挑战，或针对 `{key_points}` 预设的“认知陷阱”提示。
4. **案例与习题转化**：严禁直接粘贴题目，必须按照“现象-机理-考点”的逻辑转化为教学叙事。

### 五、 格式示例
# 细胞膜的流动镶嵌模型
* 膜结构的探索历程
  * 欧文顿的脂质透过性实验
    - 实验现象：脂溶性物质更易通过
    - 科学推论：细胞膜是由脂质组成的
    - 科学方法：基于观察的推理事例
    > 备注：1895年欧文顿用500多种化学物质进行实验，发现凡是可以溶于脂质的物质更容易通过。这是人类第一次对膜成分进行推测。


### 六、 执行清单 (生成前自检)
1. 是否完全按照 `{teaching_logic}` 的顺序安排章节？
2. 内容页数量 M 是否精准符合计算公式？
3. `{required_knowledge}` 中的每个点是否都已落实到正文中？
4. 是否已将检索资料从“待用资源”直接转化为了“PPT 核心内容”？
"""
prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", """
    ### 【教学意图输入】
    - 教学主题: {theme}
    - 目标受众: {audience}
    - 目标页数: {page_range}
    - 教学目标: {teaching_objectives}
    - 重点难点: {key_points}
    - 必须包含: {required_knowledge}
    - 教师教学思路: {teaching_logic}
    - 其他特殊要求: {other_requirements}
    
    ### 【参考资料 (双源融合注入)】
    - 本地权威库检索: {local_kb_context}
    - 用户上传素材解析: {user_material_context}
    
    👉 请基于以上极其详尽的信息，严格执行“知识融合”策略，输出最终的 Markdown 大纲：
    """)
])

def generate_direct_outline(
    slots: IntentSlots, 
    local_kb: str = "",
    user_docs: str = ""
) -> Optional[Dict[str, Any]]:
    
    if not slots.is_complete:
        logger.error("❌ 意图槽位未填充完整，操作拦截")
        return None
    
    kb_data = local_kb if local_kb else "未匹配到本地库资料，请按课标常规发挥"
    user_data = user_docs if user_docs else "用户未上传额外解析资料"

    try:
        logger.info(f"🚀 [Blueprint] 正在执行多源融合合成任务...")
        llm_chain = prompt | init_courseware_llm() | parser
        
        baidu_outline_str = llm_chain.invoke({
            "theme": slots.theme,
            "audience": slots.audience or "常规高中生",
            "page_range": slots.page_range or "12-15页",
            "teaching_objectives": slots.teaching_objectives or "落实核心素养",
            "key_points": slots.key_points or "未明确",
            "required_knowledge": slots.required_knowledge or "无",
            "teaching_logic": slots.teaching_logic or "未提供，请根据教学目标自动生成教学思路并利用 RAG 资料填充",
            "other_requirements": slots.other_requirements or "无",
            "local_kb_context": kb_data,
            "user_material_context": user_data
        })
        
  # 1. 结果清洗：处理模型可能返回的 Markdown 代码块标签
        baidu_outline_str = baidu_outline_str.strip()
        if baidu_outline_str.startswith("```"):
            lines = baidu_outline_str.split('\n')
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines[-1].strip() == "```":
                lines = lines[:-1]
            baidu_outline_str = '\n'.join(lines).strip()

        # 2. 精准页数预估统计
        # 章节页统计
        chapter_count = baidu_outline_str.count("\n* ")
        if baidu_outline_str.startswith("* "):
            chapter_count += 1
            
        # 内容页统计
        page_count = baidu_outline_str.count("\n  * ")
        if baidu_outline_str.startswith("  * "):
            page_count += 1
            
        # 基础页：封面(1) + 目录(1)
        total_estimated = chapter_count + page_count + 2
        
        logger.info(f"✅ 大纲合成完毕。视觉主页: {page_count}, 章节数: {chapter_count}, 预估总页数: {total_estimated}")
        
        # 3. 返回结构化结果
        return {
            "theme": slots.theme,
            "total_pages": total_estimated,
            "baidu_outline_str": baidu_outline_str,
            "metadata": {
                "chapters": chapter_count,
                "content_slides": page_count,
                "timestamp": int(time.time())
            }
        }
        
    except Exception as e:
        logger.error(f"❌ 流程异常: {e}")
        return None
    

