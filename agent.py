"""
图片生成 Agent · 阶段 3：记忆系统
=============================================
步骤1：个性化档案 profile（称呼/语气/风格注入 system 提示词）
步骤2：对话持久化（存/加载历史，重启还记得聊过什么）
步骤3：上下文压缩（历史太长时自动总结成摘要，省 context、防撑爆）

（保留阶段2：拼豆图 + AIGC 两个工具，对话连接重试）

【安全】API Key 通过 .env 读取。
"""

import json
import os
import time
from openai import OpenAI, APIConnectionError, APITimeoutError
from dotenv import load_dotenv

from skills.bead_art import generate_bead_art, BEAD_TOOL
from skills.aigc_creative import generate_aigc, AIGC_TOOL
from core.memory import (
    load_profile, build_system_prompt,      # 步骤1
    load_history, save_history,             # 步骤2
    compress_history_if_needed,             # 步骤3：上下文压缩
)

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
MODEL = "gpt-4o"  # 对话模型，要和 BASE_URL 匹配


# 带连接重试的对话调用：网络不稳时自动重连
def chat_with_retry(**kwargs):
    last_err = None
    for attempt in range(1, 5):  # 最多重试 4 次
        try:
            return client.chat.completions.create(**kwargs)
        except (APIConnectionError, APITimeoutError) as e:
            last_err = e
            if attempt < 4:
                wait = attempt * 3
                print(f"   ⚠️ 网络连接失败（{type(e).__name__}），{wait}s 后第 {attempt + 1} 次重试...")
                time.sleep(wait)
    raise last_err


# ============================================================
# 2. 工具注册
# ============================================================
TOOLS = [
    BEAD_TOOL,     # 拼豆图工具
    AIGC_TOOL,     # AIGC 创意图工具
]
TOOL_FUNCTIONS = {
    "generate_bead_art": generate_bead_art,
    "generate_aigc": generate_aigc,
}


# ============================================================
# 3. Agent Loop（带记忆 + 上下文压缩）
# ============================================================
def agent_loop(user_input: str) -> str:
    # 步骤1：读个性化档案 → system 提示词
    profile = load_profile()
    # 步骤2：加载历史对话
    history = load_history()
    # 步骤3：历史太长时，自动压缩成摘要（省 context；平台不稳压缩失败也不丢数据）
    history = compress_history_if_needed(history, client, MODEL)
    # 拼成完整 messages：system +（压缩后的）历史 + 新输入
    messages = [
        {"role": "system", "content": build_system_prompt(profile)},
    ] + history + [
        {"role": "user", "content": user_input},
    ]

    reply = ""
    try:
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
                print(f"\n🤖 Agent：\n{msg.content}")
                reply = msg.content
                break
        else:
            print(f"\n⚠️ 达到最大轮数 {max_steps}，进行收尾")
            resp = chat_with_retry(model=MODEL, messages=messages)
            reply = resp.choices[0].message.content or "（收尾时未返回内容）"
            print(f"\n🤖 Agent：\n{reply}")
    finally:
        # 步骤2：无论正常结束还是出错，都把本轮对话存下来（下次就记得了）
        save_history(messages)
    return reply


# ============================================================
# 4. 跑起来（连续对话模式）
# ============================================================
if __name__ == "__main__":                       # 只有「直接运行 agent.py」时才执行下面这段；被别的文件 import 时跳过
    print("=" * 50)                              # 打印一行分隔线（50 个等号拼成）
    print("图片生成 Agent · 阶段3（个性化档案 + 对话记忆 + 上下文压缩）")  # 启动横幅
    print("输入 quit 退出。关掉重开，Agent 还记得你们聊过什么～")           # 告诉用户怎么退出
    print("=" * 50)                              # 再打一行分隔线，把横幅包起来
    while True:                                  # 无限循环：一直等你说话，直到你说 quit 或按 Ctrl+C
        try:
            user_input = input("\n你：").strip()  # 阻塞等待输入（提示符是「你：」），strip 去掉首尾空白
        except (EOFError, KeyboardInterrupt):    # 捕获两种「打断」：EOFError=输入流结束，KeyboardInterrupt=你按了 Ctrl+C
            print("\n再见～")                     # 打印告别语
            break                                # 跳出 while 循环 → 程序结束
        if user_input.lower() in ("quit", "exit", "q"):  # 统一转小写判断是不是退出命令（quit/exit/q，大小写都认）
            print("再见～下次见！")               # 打印告别语
            break                                # 跳出循环 → 正常退出
        if not user_input:                       # 如果输入是空的（只敲了回车）
            continue                             # 跳过本轮，重新等输入（不拿空话去打扰 Agent）
        agent_loop(user_input)                   # 把这句话交给 agent_loop：Agent 思考 → 调工具 → 回复 → 顺便存进记忆
