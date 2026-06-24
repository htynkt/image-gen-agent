"""
图片生成 Agent · 阶段 1：Agent Loop 基础骨架
=============================================
学习目标：理解 Agent 的本质 —— 一个 while 循环。

本阶段我们先不真的生成图片，而是先把"骨架"立起来：
  1. 连接大模型（用 openai 库的兼容接口）
  2. 告诉 LLM "你有一个 generate_image 工具"
  3. 写一个 while 循环：LLM 想调工具 → 执行 → 把结果喂回去 → 再问 LLM
     直到 LLM 不再调工具（给出最终回答）就停

跑通这个，你就掌握了 Agent 最核心的运行机制。
（阶段 2 我们再把"假工具"换成真的拼豆 / AIGC / 人像生图）

【安全】API Key 通过 .env 文件读取，不写死在代码里。
"""

import json
import os
from openai import OpenAI
from dotenv import load_dotenv

# 读取项目根目录的 .env 文件，把里面的变量加载到环境变量
load_dotenv()


# ============================================================
# 1. 连接大模型
# ============================================================
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")

# 防呆检查：如果 .env 没配好，提前给友好提示，而不是等到调用时才抛一堆看不懂的错
if not API_KEY or not BASE_URL:
    raise SystemExit(
        "❌ 没从 .env 读到 API_KEY 或 BASE_URL。\n"
        "请检查 .env 文件，确保里面有这两行（变量名要完全一致）：\n"
        "  API_KEY=你的key\n"
        "  BASE_URL=https://你的接口地址"
    )

client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)

# 模型名：必须和 BASE_URL 指向的服务匹配！
#   - BASE_URL 指向 OpenAI 官方/兼容服务 → 用 gpt-4o 等
#   - BASE_URL 指向智谱(bigmodel) → 用 glm-4.5 / glm-4-plus 等
#   （建议把 MODEL 也放进 .env，切换模型就不用改代码）
MODEL = "gpt-4o"


# ============================================================
# 2. 定义工具（阶段 1 先用一个"假"的生图工具）
# ============================================================
# 这段是"工具说明书"，告诉 LLM：你有个工具叫 generate_image，
# 什么时候该用、要传什么参数。
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "generate_image",
            "description": "根据描述生成一张图片。用户想要图片/画作/拼豆图/卡通形象时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": "想生成的图片内容描述，例如：一只戴红围巾的柴犬",
                    }
                },
                "required": ["prompt"],
            },
        },
    }
]


# 工具真正执行的地方（阶段 1 是假的，假装生成了一下）
def generate_image(prompt: str) -> str:
    print(f"   🔧 [工具执行] generate_image('{prompt}')")
    return f"图片已生成：{prompt}（这是阶段1的假结果，阶段2换成真的）"


# "工具名 → 函数"的映射表。执行工具时，靠它找到对应的函数。
TOOL_FUNCTIONS = {
    "generate_image": generate_image,
}


# ============================================================
# 3. Agent Loop —— 整个 Agent 的灵魂（重点理解这一段！）
# ============================================================
def agent_loop(user_input: str) -> str:
    # messages 是 Agent 的"记忆本"，循环里不断往里记新内容
    messages = [
        {"role": "system", "content": "你是一个图片生成助手。用户想要图片时，请调用 generate_image 工具，然后告诉用户图片已生成。"},
        {"role": "user", "content": user_input},
    ]

    max_steps = 10  # 安全护栏：最多循环 10 轮，防止 LLM 一直调工具导致死循环
    step = 0
    while step < max_steps:  # ← "有上限"的循环
        step += 1
        print(f"\n——— 第 {step} 轮：调用 LLM ———")

        # （1）把"记忆 + 工具清单"一起交给 LLM，让它决定下一步
        resp = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=TOOLS,
        )
        msg = resp.choices[0].message

        # （2）判断 LLM 的决定：要调工具？还是直接回答？
        if msg.tool_calls:
            # —— 它要调工具 ——
            messages.append(msg.model_dump())  # 记下"它要调工具"这个决定

            # 逐个执行它想调的工具
            for call in msg.tool_calls:
                name = call.function.name
                # ⭐ 关键改进：工具执行包一层 try-except
                # 工具报错时，不让整个 Agent 崩掉，而是把"错误信息"当成结果返回给 LLM，
                # 让 LLM 自己看到错误、决定怎么办（换参数重试 / 换别的方式 / 告诉用户）。
                try:
                    args = json.loads(call.function.arguments)  # 参数是字符串，转成字典
                    result = TOOL_FUNCTIONS[name](**args)  # 执行真正的函数
                except Exception as e:
                    result = f"[工具执行出错] {type(e).__name__}: {e}"
                    print(f"   ⚠️ [工具报错] {name} → {type(e).__name__}: {e}")
                # 不管成功还是报错，都把结果（或错误信息）喂回给 LLM
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": call.id,
                        "content": result,
                    }
                )
            # 工具执行完了，回到 while 顶部，再问 LLM 下一步
            continue
        else:
            # —— 停止条件①：它不再调工具，给出最终答案（正常结束）——
            print(f"\n✅ 最终回答：\n{msg.content}")
            return msg.content

    # —— 停止条件②：跑满 max_steps 还没收敛 ——
    # 关键改进：不只是干巴巴说"已停止"，而是做一次"收尾调用"——
    # 带着已有全部记忆、但【不带 tools】再问一次，强制它基于已有信息给出结论。
    # 这样不管是"调太多了"还是"中途出过错"，用户都能拿到一个结果。
    print(f"\n⚠️ 已达到最大轮数 {max_steps}，进行收尾（让模型基于已有信息总结）")
    resp = client.chat.completions.create(
        model=MODEL,
        messages=messages,
        # 故意不传 tools：这一轮禁止再调工具，必须直接给文字结论
    )
    final = resp.choices[0].message.content or "（收尾时模型未返回内容）"
    print(f"\n📋 收尾输出：\n{final}")
    return final


# ============================================================
# 4. 跑起来
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("图片生成 Agent · 阶段1 启动")
    print("=" * 50)
    agent_loop("帮我画一只戴着红围巾的柴犬")
    # 跑通后可以换成别的试试，例如：
    # agent_loop("做个拼豆版的小柴犬")
