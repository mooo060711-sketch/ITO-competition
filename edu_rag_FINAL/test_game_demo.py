#!/usr/bin/env python3
"""
互动小游戏模块 — 独立测试脚本

本脚本不依赖 Milvus，可直接验证游戏生成功能。
它会调用 LLM API 生成游戏内容，然后渲染为 HTML5 文件。

使用前需要设置环境变量:
    export OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"
    export OPENAI_API_KEY="你的DashScope API Key"

运行:
    python test_game_demo.py
"""

import json
import os
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def test_game_templates_only():
    """测试 1: 仅测试 HTML 渲染（不调用 LLM）— 使用硬编码示例数据"""
    print("=" * 60)
    print("测试 1: HTML5 模板渲染（不需要 API）")
    print("=" * 60)

    from src.rag.game.game_templates import GAME_RENDERERS

    # 示例数据：选择题
    quiz_data = {
        "title": "中心法则基础测验",
        "questions": [
            {
                "id": 1,
                "stem": "中心法则描述了遗传信息的流动方向，以下哪个选项正确描述了这个过程？",
                "options": [
                    "A. DNA → RNA → 蛋白质",
                    "B. RNA → DNA → 蛋白质",
                    "C. 蛋白质 → RNA → DNA",
                    "D. RNA → 蛋白质 → DNA"
                ],
                "answer": "A",
                "explanation": "中心法则指出遗传信息从DNA通过转录传递到RNA，再通过翻译传递到蛋白质。"
            },
            {
                "id": 2,
                "stem": "转录过程中，RNA聚合酶的主要作用是什么？",
                "options": [
                    "A. 解开DNA双螺旋",
                    "B. 催化RNA链的合成",
                    "C. 连接氨基酸形成蛋白质",
                    "D. 复制DNA分子"
                ],
                "answer": "B",
                "explanation": "RNA聚合酶以DNA为模板催化核糖核苷酸的聚合，合成RNA链。"
            },
            {
                "id": 3,
                "stem": "在翻译过程中，携带氨基酸到核糖体的分子是？",
                "options": [
                    "A. mRNA",
                    "B. rRNA",
                    "C. tRNA",
                    "D. snRNA"
                ],
                "answer": "C",
                "explanation": "tRNA（转运RNA）的反密码子与mRNA上的密码子配对，将对应的氨基酸运送到核糖体。"
            },
        ]
    }

    # 示例数据：排序题
    sorting_data = {
        "title": "转录过程排序",
        "tasks": [{
            "id": 1,
            "description": "请将转录过程的步骤按正确顺序排列",
            "correct_order": [
                "RNA聚合酶识别并结合启动子",
                "DNA双链在转录区域解旋",
                "RNA聚合酶沿模板链3'→5'方向移动",
                "核糖核苷酸按互补配对原则连接",
                "RNA聚合酶到达终止子",
                "新合成的mRNA从模板上释放",
            ]
        }]
    }

    # 示例数据：配对题
    matching_data = {
        "title": "分子生物学核心概念配对",
        "pairs": [
            {"left": "mRNA", "right": "携带遗传信息从细胞核到核糖体"},
            {"left": "tRNA", "right": "将氨基酸运送到核糖体"},
            {"left": "rRNA", "right": "构成核糖体的结构和催化组分"},
            {"left": "DNA聚合酶", "right": "催化DNA复制过程中核苷酸的聚合"},
            {"left": "RNA聚合酶", "right": "催化转录过程中RNA链的合成"},
        ]
    }

    # 示例数据：翻卡记忆
    flashcard_data = {
        "title": "中心法则核心术语",
        "cards": [
            {"front": "转录 (Transcription)", "back": "以DNA为模板合成RNA的过程，发生在细胞核中"},
            {"front": "翻译 (Translation)", "back": "以mRNA为模板合成蛋白质的过程，发生在核糖体上"},
            {"front": "密码子 (Codon)", "back": "mRNA上每3个相邻碱基组成的三联体，编码一个氨基酸"},
            {"front": "反密码子 (Anticodon)", "back": "tRNA上与密码子互补配对的三个碱基"},
        ]
    }

    # 示例数据：判断题
    true_false_data = {
        "title": "中心法则判断题",
        "questions": [
            {"id": 1, "statement": "DNA复制是半保留复制", "answer": True, "explanation": "DNA复制时，每条子链各含一条母链和一条新链"},
            {"id": 2, "statement": "转录过程中模板链的阅读方向是5'→3'", "answer": False, "explanation": "RNA聚合酶沿模板链3'→5'方向移动"},
            {"id": 3, "statement": "一个密码子可以编码多个氨基酸", "answer": False, "explanation": "一个密码子只能编码一个氨基酸（密码子的专一性）"},
        ]
    }

    # 示例数据：填空题
    fill_blank_data = {
        "title": "中心法则填空",
        "questions": [
            {
                "id": 1,
                "sentence": "中心法则中，遗传信息从____通过转录传递到____，再通过翻译传递到蛋白质。",
                "blanks": ["DNA", "RNA"],
                "hint": "两种核酸分子"
            },
            {
                "id": 2,
                "sentence": "转录过程中，____酶以DNA的____链为模板合成RNA。",
                "blanks": ["RNA聚合", "模板"],
                "hint": "一种酶和一条链"
            },
        ]
    }

    # 示例数据：流程补全
    flow_fill_data = {
        "title": "转录过程流程补全",
        "description": "补全转录的关键步骤",
        "nodes": [
            {"id": 1, "label": "RNA聚合酶识别启动子", "is_blank": False},
            {"id": 2, "label": "DNA双链解旋", "is_blank": True},
            {"id": 3, "label": "RNA聚合酶沿模板链移动", "is_blank": False},
            {"id": 4, "label": "核糖核苷酸互补配对", "is_blank": True},
            {"id": 5, "label": "到达终止子，转录终止", "is_blank": False},
            {"id": 6, "label": "mRNA释放", "is_blank": True},
        ],
        "arrows": [
            {"from": 1, "to": 2, "label": "起始"},
            {"from": 2, "to": 3, "label": "延伸开始"},
            {"from": 3, "to": 4, "label": "延伸"},
            {"from": 4, "to": 5, "label": "终止"},
            {"from": 5, "to": 6, "label": "释放"},
        ],
        "blank_answers": {
            "2": "DNA双链解旋",
            "4": "核糖核苷酸互补配对",
            "6": "mRNA释放",
        }
    }

    test_cases = {
        "quiz": quiz_data,
        "sorting": sorting_data,
        "matching": matching_data,
        "flashcard": flashcard_data,
        "true_false": true_false_data,
        "fill_blank": fill_blank_data,
        "flow_fill": flow_fill_data,
    }

    output_dir = Path("outputs/games/demo")
    output_dir.mkdir(parents=True, exist_ok=True)

    for game_type, data in test_cases.items():
        renderer = GAME_RENDERERS[game_type]
        html = renderer(data)
        filepath = output_dir / f"demo_{game_type}.html"
        filepath.write_text(html, encoding="utf-8")
        print(f"  ✅ {game_type:12s} -> {filepath}  ({len(html):,} bytes)")

    print(f"\n🎉 所有 {len(test_cases)} 种游戏模板渲染成功!")
    print(f"📁 输出目录: {output_dir.resolve()}")
    print("用浏览器打开任意 .html 文件即可游玩。\n")


def test_llm_game_generation():
    """测试 2: 通过 LLM API 生成游戏内容（需要 API Key）"""
    print("=" * 60)
    print("测试 2: LLM 游戏生成（需要 OPENAI_API_KEY）")
    print("=" * 60)

    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        print("  ⚠️  未设置 OPENAI_API_KEY，跳过 LLM 测试。")
        print("  设置方法:")
        print('    export OPENAI_BASE_URL="https://dashscope.aliyuncs.com/compatible-mode/v1"')
        print('    export OPENAI_API_KEY="你的API Key"')
        return

    from src.rag.game.game_engine import GameEngine

    engine = GameEngine("config.yaml")

    # 测试生成一个选择题游戏
    print("\n  正在生成: 选择题（中心法则）...")
    result = engine.generate(
        knowledge_topic="中心法则 - 遗传信息的传递",
        game_type="quiz",
        teacher_requirement="侧重于转录和翻译的区别，适合高中生",
        count=3,
        output_dir="outputs/games/llm_test",
    )
    print(f"  ✅ 生成成功! 耗时: {result['generation_time']}s")
    print(f"     标题: {result['title']}")
    print(f"     文件: {result['html_path']}")

    # 测试生成一个排序游戏
    print("\n  正在生成: 排序游戏（DNA复制）...")
    result2 = engine.generate(
        knowledge_topic="DNA复制的详细步骤",
        game_type="sorting",
        teacher_requirement="按照时间顺序排列DNA复制的各个阶段",
        count=1,
        output_dir="outputs/games/llm_test",
    )
    print(f"  ✅ 生成成功! 耗时: {result2['generation_time']}s")
    print(f"     文件: {result2['html_path']}")

    print(f"\n🎉 LLM 游戏生成测试通过!")


if __name__ == "__main__":
    print("\n🎮 互动小游戏模块测试\n")

    # 测试 1: 模板渲染（不需要任何外部服务）
    test_game_templates_only()

    # 测试 2: LLM 生成（需要 API Key）
    test_llm_game_generation()

    print("\n✅ 全部测试完成!")
