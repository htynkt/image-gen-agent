"""
图片生成 Agent · 阶段 2：Tool Use 工具系统
=============================================
阶段1 搭好了 Agent Loop 骨架，但用的是"假工具"。
阶段2 把假工具换成"真工具"——第一个：拼豆图生成器。

阶段2 核心知识点（Tool Use 工具系统）：
  - 一个工具 = 函数（真正干活） + 说明书（告诉 LLM 何时用、怎么传参）
  - 工具独立成模块（skills/），在 agent.py 里"注册"上岗
  - 加新工具 = 写一个 skill + 注册一行，Agent Loop 不用改

【安全】API Key 通过 .env 文件读取。
"""

import json
import os
from openai import OpenAI
from dotenv import load_dotenv

# 导入阶段2 的真工具：拼豆图（函数 + 说明书）
from skills.bead_art import generate_bead_art, BEAD_TOOL

load_dotenv()


# ============================================================
# 1. 连接大模型
# ============================================================
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
if not API_KEY or not BASE_URL:
    raise SystemExit(
        "❌ 没从 .env 读到 API_KEY 或 BASE_URL，请检查 .env 文件。\n"
        "  API_KEY=你的key\n  BASE_URL=https://你的接口地址"
    )

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
MODEL = "gpt-4o"  # 要和 BASE_URL 匹配（OpenAI 用 gpt-4o；智谱用 glm-4.5 等）


# ============================================================
# 2. 工具注册（Tool Use 的核心：工具在这里"登记上岗"）
# ============================================================
# TOOLS：工具"说明书"列表（给 LLM 看，决定何时调用哪个工具）
# TOOL_FUNCTIONS：工具名 → 真正执行的函数（执行时靠它找到函数）
#
# ⭐ 重点：以后加新工具（AIGC、人像转卡通）只要：
#   1) 在 skills/ 下写一个新文件，导出「函数 + 说明书」
#   2) 在这里 import 进来，加进这两个列表/字典
#   Agent Loop 一行都不用改！这就是好的工具系统设计。
TOOLS = [
    BEAD_TOOL,  # 拼豆图工具
]
TOOL_FUNCTIONS = {
    "generate_bead_art": generate_bead_art,
}


# ============================================================
# 3. Agent Loop（和阶段1 一样，只是挂上了真工具）
# ============================================================
def agent_loop(user_input: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "你是一个图片生成助手。用户想把某张图片做成拼豆图时，"
                "请调用 generate_bead_art 工具（必须传 image_path 图片路径参数）。"
                "工具返回结果后，告诉用户拼豆图已生成、保存在哪里、用了哪些颜色。"
            ),
        },
        {"role": "user", "content": user_input},
    ]

    max_steps = 10
    step = 0
    while step < max_steps:
        step += 1
        print(f"\n——— 第 {step} 轮：调用 LLM ———")

        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
        )
        msg = resp.choices[0].message

        if msg.tool_calls:
            messages.append(msg.model_dump())
            for call in msg.tool_calls:
                name = call.function.name
                # 工具执行包 try-except：报错也不崩，错误信息返回给 LLM
                try:
                    args = json.loads(call.function.arguments)
                    result = TOOL_FUNCTIONS[name](**args)
                except Exception as e:
                    result = f"[工具执行出错] {type(e).__name__}: {e}"
                    print(f"   ⚠️ [工具报错] {name} → {type(e).__name__}: {e}")
                messages.append(
                    {"role": "tool", "tool_call_id": call.id, "content": result}
                )
            continue
        else:
            # 停止条件①：LLM 给出最终答案
            print(f"\n✅ 最终回答：\n{msg.content}")
            return msg.content

    # 停止条件②：达到最大轮数，收尾输出
    print(f"\n⚠️ 达到最大轮数 {max_steps}，进行收尾")
    resp = client.chat.completions.create(model=MODEL, messages=messages)
    final = resp.choices[0].message.content or "（收尾时未返回内容）"
    print(f"\n📋 收尾输出：\n{final}")
    return final


# ============================================================
# 4. 跑起来
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("图片生成 Agent · 阶段2 启动（真工具：拼豆图）")
    print("=" * 50)
    # 直接用你准备好的真实图片生成拼豆图（改成自己的图片路径即可）
    data_url = "data/3.jpg"
    agent_loop(f"把 {data_url} 做成 52×52 的拼豆图")
