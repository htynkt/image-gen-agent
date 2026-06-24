"""
图片生成 Agent · 阶段 2：Tool Use 工具系统
=============================================
阶段1 搭好了 Agent Loop 骨架，但用的是"假工具"。
阶段2 把假工具换成"真工具"——目前已接入两个：
  - 拼豆图生成器（generate_bead_art）：本地算法，图片→拼豆图纸
  - AIGC 创意图（generate_aigc）：调文生图 API，提示语→全新图片

阶段2 核心知识点（Tool Use 工具系统）：
  - 一个工具 = 函数（真正干活） + 说明书（告诉 LLM 何时用、怎么传参）
  - 工具独立成模块（skills/），在 agent.py 里"注册"上岗
  - 加新工具 = 写一个 skill + 注册一行，Agent Loop 不用改

【安全】API Key 通过 .env 文件读取。
【健壮】对话调用带连接重试，网络不稳时自动重连。
"""

import json
import os
import time
from openai import OpenAI, APIConnectionError, APITimeoutError
from dotenv import load_dotenv

# 导入阶段2 的真工具：拼豆图 + AIGC 创意图（函数 + 说明书）
from skills.bead_art import generate_bead_art, BEAD_TOOL
from skills.aigc_creative import generate_aigc, AIGC_TOOL

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
MODEL = "gpt-4o"  # 对话模型，要和 BASE_URL 匹配（OpenAI 用 gpt-4o；智谱用 glm-4.5 等）


# 带连接重试的对话调用：网络不稳（WinError 10054 等）时自动重连，不用手动重跑
def chat_with_retry(**kwargs):
    last_err = None
    for attempt in range(1, 5):  # 最多重试 4 次
        try:
            return client.chat.completions.create(**kwargs)
        except (APIConnectionError, APITimeoutError) as e:
            last_err = e
            if attempt < 4:
                wait = attempt * 3  # 3s、6s、9s 递增
                print(f"   ⚠️ 网络连接失败（{type(e).__name__}），{wait}s 后第 {attempt + 1} 次重试...")
                time.sleep(wait)
    raise last_err


# ============================================================
# 2. 工具注册（Tool Use 的核心：工具在这里"登记上岗"）
# ============================================================
TOOLS = [
    BEAD_TOOL,     # 拼豆图工具（已有图片 → 拼豆图纸）
    AIGC_TOOL,     # AIGC 创意图工具（提示语 → 全新图片）
]
TOOL_FUNCTIONS = {
    "generate_bead_art": generate_bead_art,
    "generate_aigc": generate_aigc,
}


# ============================================================
# 3. Agent Loop（和阶段1 一样，只是挂上了真工具）
# ============================================================
def agent_loop(user_input: str) -> str:
    messages = [
        {
            "role": "system",
            "content": (
                "你是一个图片生成助手，有两个工具：\n"
                "1. generate_bead_art：把【已有的图片】转成拼豆图纸（用户说'拼豆/做成拼豆'，"
                "或给了图片路径时调用，必须传 image_path）。\n"
                "2. generate_aigc：根据【一段提示语】生成全新的创意图（用户描述画面/风格，"
                "想让 AI 画一张图时调用，必须传 prompt）。\n"
                "判断依据：用户给的是'已有图片'→拼豆；用户给的是'文字描述/想画一张'→AIGC。"
                "工具返回后，告诉用户图片已生成、保存在哪里。"
            ),
        },
        {"role": "user", "content": user_input},
    ]

    max_steps = 10
    step = 0
    while step < max_steps:
        step += 1
        print(f"\n——— 第 {step} 轮：调用 LLM ———")

        resp = chat_with_retry(model=MODEL, messages=messages, tools=TOOLS)
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
    resp = chat_with_retry(model=MODEL, messages=messages)
    final = resp.choices[0].message.content or "（收尾时未返回内容）"
    print(f"\n📋 收尾输出：\n{final}")
    return final


# ============================================================
# 4. 跑起来
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("图片生成 Agent · 阶段2 启动（工具：拼豆图 + AIGC 创意图）")
    print("=" * 50)
    # —— 测 AIGC 创意图：用提示语生成一张新图 ——
    agent_loop("画一只戴墨镜的柴犬坐在霓虹街头，赛博朋克风格")
    # —— 或测拼豆图（取消注释，换成你的图片）：——
    # agent_loop("把 data/3.jpg 做成拼豆图")
