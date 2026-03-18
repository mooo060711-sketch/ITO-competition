import os
import time
import requests
import base64
import io
import yaml
from PIL import Image
from typing import Dict, Any
import pathlib

# 🌟 核心修改 1：动态精确定位项目根目录下的 config.yaml
# __file__ 是 src/tools/image.py
# .parent               -> src/tools
# .parent.parent        -> src
# .parent.parent.parent -> 项目根目录 (服务外包)
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
CONFIG_PATH = PROJECT_ROOT / "config.yaml"

def load_image_config() -> Dict[str, Any]:
    """加载 config.yaml 图像配置"""
    try:
        # 打印调试信息，确保路径正确
        # print(f"正在尝试加载配置: {CONFIG_PATH}")
        
        with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        providers = config.get('image_providers', {})
        default_provider = config.get('default_image_provider', 'qwen')
        
        selected = providers.get(default_provider, providers.get('qwen', {}))
        
        api_key = os.getenv("OPENAI_API_KEY") or os.getenv("openkey")
        selected['api_key'] = api_key
        
        return selected
    except Exception as e:
        # 只有在真正找不到文件或解析失败时才报错
        print(f"⚠️ 图像配置加载失败: {e} (路径: {CONFIG_PATH})")
        return {
            'api_key': os.getenv("OPENAI_API_KEY"),
            'api_url': "https://dashscope.aliyuncs.com/api/v1/services/aigc/image-generation/generation",
            'model': 'qwen-vl-max'
        }

# 全局配置缓存
_image_config = load_image_config()

# 🌟 核心修改 2：输出目录也锁定到项目根目录
BASE_OUTPUT_PATH = PROJECT_ROOT / "outputs"
AI_GEN_DIR = BASE_OUTPUT_PATH / "images"
AI_GEN_DIR.mkdir(parents=True, exist_ok=True)

# 静态资源 URL 保持不变
BASE_STATIC_URL = os.getenv("FRONTEND_URL", "http://127.0.0.1:9527") + "/outputs/images"

def call_qwen_image_api(prompt: str, save_path: str, aspect_ratio: str = "16:9") -> bool:
    """调用千问图像生成 API (配置驱动)"""
    if not _image_config.get('api_key'):
        print("❌ 错误: 未检测到 API Key，请检查 .env 或 config.yaml")
        return False

    headers = {
        "Authorization": f"Bearer {_image_config['api_key']}",
        "Content-Type": "application/json"
    }
    
    # 动态尺寸映射
    size_map = {
        "1:1": "1024x1024",
        "16:9": "1792x1024",
        "4:3": "1152x864"
    }
    size = size_map.get(aspect_ratio, _image_config.get('default_size', "1792x1024"))
    
    payload = {
        "model": _image_config.get('model', 'qwen-vl-max'),
        "prompt": prompt,
        "n": 1,
        "size": size,
        "response_format": "b64_json"
    }
    
    try:
        response = requests.post(
            _image_config['api_url'], 
            headers=headers, 
            json=payload, 
            timeout=120
        )
        response.raise_for_status()
        
        result = response.json()
        # 注意：阿里百炼的返回结构可能在 output 或 data 字段中，根据实际 API 调整
        # 下面是通用的 b64 处理逻辑
        output = result.get("output", result.get("data", {}))
        images = output.get("images", []) if isinstance(output, dict) else output
        
        if images:
            img_b64 = images[0].get("b64_json") or images[0].get("b64")
            if img_b64:
                img_data = base64.b64decode(img_b64)
                img = Image.open(io.BytesIO(img_data))
                
                # PPT 兼容处理：去除透明通道
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                img.save(save_path, "JPEG", quality=95)
                print(f"✅ {_image_config['model']} 图像生成成功: {os.path.basename(save_path)}")
                return True
                
    except Exception as e:
        print(f"❌ 图像生成 API 请求失败: {e}")
        return False

def generate_image_by_desc(
    description: str, 
    theme: str = "教学场景", 
    style: str = "写实插画", 
    aspect_ratio: str = "16:9"
) -> str:
    """
    配置驱动图像生成：教育 PPT 专用
    """
    img_filename = f"gen_{int(time.time())}.jpg"
    save_path = str(AI_GEN_DIR / img_filename)
    
    # 教育专用 Prompt 模板
    final_prompt = (
        f"高清教育PPT插图，主题：[{theme}]，内容：[{description}]，"
        f"风格：[{style}]，比例：[{aspect_ratio}]，"
        f"科学准确，矢量感，无文字水印，专业教材质感，构图简洁"
    )
    
    if call_qwen_image_api(final_prompt, save_path, aspect_ratio):
        return f"{BASE_STATIC_URL}/{img_filename}"
    
    return ""  # 失败返回空 URL