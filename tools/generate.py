import os
import time
import requests
import re
import json
import logging
from typing import Dict, Any, Optional
from dotenv import load_dotenv

# 优先加载 .env 文件配置
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("slidesgpt_generator")

# 百度千帆配置
BAIDU_QIANFAN_API_KEY = os.getenv("BAIDU_QIANFAN_API_KEY", "bce-v3/ALTAK-KUl4VMpILphl49LTlAM3I/aeed82ca9256762829780b33a3f39ed7e2e3529d")
BAIDU_PPT_API_URL = os.getenv("BAIDU_PPT_API_URL", "https://qianfan.baidubce.com/v2/tools/ai_ppt/generate_ppt_by_outline")

def generate_ppt(
    outline_data: Dict[str, Any],
    query_id: int,
    chat_id: int,
    query: str,
    style_id: int = 0,
    tpl_id: int = 102322,  # 默认模板ID
    save_filename: Optional[str] = None,
    resource_url: Optional[str] = None,
    custom_tpl_url: Optional[str] = None,
    gen_mode: int = 1,
    ai_info: bool = False
) -> Dict[str, Any]:
    """
    调用百度千帆 AI PPT 接口生成PPT（支持 SSE 流式响应）
    """
    if not BAIDU_QIANFAN_API_KEY or BAIDU_QIANFAN_API_KEY.strip() == "":
        raise ValueError("❌ 未配置 BAIDU_QIANFAN_API_KEY")
    
    baidu_outline_str = outline_data.get("baidu_outline_str", "")
    if not baidu_outline_str:
        raise ValueError("❌ 未找到百度接口格式的大纲字符串")
    
    title = outline_data.get("theme", "教学课件")
    
    # 🌟 核心修复：优先从 outline_data 中获取 tpl_id，否则使用函数参数默认值
    final_tpl_id = outline_data.get("tpl_id", tpl_id)
    logger.info(f"💡 最终选定的模板 ID: {final_tpl_id}")

    # 构建请求头
    headers = {
        "Authorization": f"Bearer {BAIDU_QIANFAN_API_KEY.strip()}",
        "Content-Type": "application/json",
        "Accept": "text/event-stream"
    }

    # 构建请求体
    payload = {
        "query_id": query_id,
        "chat_id": chat_id,
        "outline": baidu_outline_str,
        "query": query,
        "title": title,
        "style_id": style_id,
        "tpl_id": final_tpl_id,  # 使用修复后的 final_tpl_id
        "gen_mode": gen_mode,
        "ai_info": ai_info
    }

    if resource_url and resource_url.strip() != "":
        payload["resource_url"] = resource_url.strip()
    if custom_tpl_url and custom_tpl_url.strip() != "":
        payload["custom_tpl_url"] = custom_tpl_url.strip()

    try:
        logger.info(f"📤 正在提交生成请求 (tpl_id={final_tpl_id})...")
        
        response = requests.post(
            BAIDU_PPT_API_URL,
            json=payload,
            headers=headers,
            timeout=180, 
            stream=True
        )
        response.raise_for_status()

        pptx_url = None
        for line in response.iter_lines():
            if not line: continue
            line_str = line.decode('utf-8').strip()
            if not line_str.startswith("data:"): continue
                
            data_str = line_str[5:].strip()
            try:
                event_data = json.loads(data_str)
                if "data" in event_data and isinstance(event_data["data"], dict):
                    if "pptx_url" in event_data["data"]:
                        pptx_url = event_data["data"]["pptx_url"]
                        logger.info("✅ 捕捉到 pptx_url!")
                        break
            except: continue

        if not pptx_url:
            raise Exception("未能获取到 pptx 下载地址")

        if not save_filename:
            safe_title = re.sub(r'[\\/*?:"<>|]', "", title)
            save_filename = f"{safe_title}_{int(time.time())}.pptx"
        
        logger.info(f"⬇️ 下载 PPT 中...")
        ppt_response = requests.get(pptx_url, stream=True, timeout=60)
        ppt_response.raise_for_status()
        
        with open(save_filename, 'wb') as f:
            for chunk in ppt_response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        return {"local_file": save_filename, "status": "success", "message": "生成成功"}

    except Exception as e:
        logger.error(f"❌ PPT生成流程异常: {e}")
        raise e
