import os
import json
from dotenv import load_dotenv
load_dotenv()  # 加载 .env 中的 OPENAI_API_KEY

from langchain_core.tools import tool
from src.rag.service import RAGService  # 保持原样
from src.llm_config import load_llm_config  # 新增：使用千问配置

# 获取千问配置（qwen provider）
config = load_llm_config()  # 返回 {'api_key': '...', 'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1', 'models': {...}}

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(CURRENT_DIR, "config.yaml")
svc = RAGService(CONFIG_PATH)  # RAG独立，不受LLM影响

# 工具定义保持不变，ChatOpenAI会自动使用千问（通过 llm_config.py）
@tool("search_official_curriculum_skill")
def search_official_curriculum_skill(query: str) -> str:
    """
    当老师询问通用的教学大纲、标准定义或基础学科知识时调用。
    检索范围仅限于官方权威教材库（kb）。
    """
    if not svc:
        return "官方知识库引擎暂不可用。"
        
    try:
        # 强制锁定 indexes=["kb"]
        res = svc.query(question=query, indexes=["kb"], top_k=5)
        
        # 利用 human_view 提供的结构化 Markdown 增强 Agent 的回答质量
        hv = res.get("human_view", {})
        return json.dumps({
            "source": "官方教材库 (kb)",
            "answer": res.get("answer"),
            "evidence_md": hv.get("evidence_md", ""), # 包含来源和摘要的表格
            "evidence_raw": res.get("evidence_raw", []) 
        }, ensure_ascii=False)
        
    except Exception as e:
        return f"检索官方库出错: {str(e)}"

@tool("search_uploaded_materials_skill")
def search_uploaded_materials_skill(query: str, session_id: str) -> str:
    """
    当用户提到‘根据我上传的资料’时调用。支持检索视频、图片内容。
    必须传入 query 和 session_id。
    """
    if not svc:
        return "个人资料检索引擎暂不可用。"
        
    try:
        # 动态拼接专属索引名称：ref:<session_id>
        user_index = f"ref:{session_id}"
        
        # 执行检索
        res = svc.query(question=query, indexes=[user_index], top_k=5)
        
        hv = res.get("human_view", {})
        
        return json.dumps({
            "source": f"个人上传资料 ({user_index})",
            "answer": res.get("answer"),
            "source_details": hv.get("sources_md", ""), 
            "evidence_table": hv.get("evidence_md", ""),  
            "evidence_raw": res.get("evidence_raw", [])
        }, ensure_ascii=False)
        
    except Exception as e:
        return f"检索个人资料出错: {str(e)}"
