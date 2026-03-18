from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

import yaml


def load_config(path: str) -> Dict[str, Any]:
    """Load YAML config.

    - Resolves relative paths relative to the project root directory.
    - Expands environment variables in strings like ${VAR}.
    """
    # 🌟 1. 动态获取项目根目录 (最核心的一步)
    # __file__ 是 src/rag/config.py 的绝对路径
    # .parent 是 src/rag
    # .parent.parent 是 src
    # .parent.parent.parent 是 服务外包 (即项目根目录 C:\Users\moon\Desktop\服务外包)
    base_dir = Path(__file__).resolve().parent.parent.parent
    
    # 🌟 2. 无论外面传入的是 "config.yaml" 还是 "../tools/config.yaml"
    # 我们都只提取文件名，强制在项目根目录下寻找它！
    file_name = Path(path).name
    cfg_path = base_dir / file_name

    if not cfg_path.exists():
        raise FileNotFoundError(f"在项目根目录找不到配置文件: {cfg_path}")

    # 🌟 3. 读取配置文件
    cfg = yaml.safe_load(cfg_path.read_text(encoding="utf-8")) or {}

    def _expand(v):
        if isinstance(v, str):
            v = os.path.expandvars(v)
            # 🌟 4. 如果 YAML 里写了相对路径（比如 ./models 或 ./rag_store）
            # 统统基于项目根目录 (base_dir) 转换为绝对路径！
            if not os.path.isabs(v) and ("/" in v or v.startswith(".")):
                return str((base_dir / v).resolve())
            return v
        if isinstance(v, dict):
            return {k: _expand(val) for k, val in v.items()}
        if isinstance(v, list):
            return [_expand(x) for x in v]
        return v

    return _expand(cfg)


def ensure_dirs(cfg: Dict[str, Any]) -> None:
    """Create required directories."""
    store_dir = Path(cfg.get("store_dir", "./rag_store")).expanduser()
    (store_dir / "assets").mkdir(parents=True, exist_ok=True)
    (store_dir / "indexes").mkdir(parents=True, exist_ok=True)