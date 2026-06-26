"""
图片生成 Agent · 阶段 6：多模态（支持文字 + 图片一起发给 LLM）
=============================================
在阶段5（日志）基础上，agent_loop 支持「文字 + 图片」多模态输入：
  - 发图片时，转成 base64 按 OpenAI 多模态格式塞进消息，gpt-4o 能看图
  - 例如：发张照片 + "做成拼豆" → LLM 看图 → 调拼豆工具

（保留：拼豆 + AIGC 工具、对话重试、记忆系统、上下文压缩、日志）
命令行模式（__main__）仍只支持文字；图片输入走 app.py 的 Gradio 界面。

【安全】API Key 通过 .env 读取。
"""

import json
import os
import time
import base64
from openai import OpenAI, APIConnectionError, APITimeoutError
from dotenv import load_dotenv

from skills.bead_art import generate_bead_art, BEAD_TOOL
from skills.aigc_creative import generate_aigc, AIGC_TOOL
from core.memory import (
    load_profile, build_system_prompt,
    load_history, save_history,
    compress_history_if_needed,
)
from core.logger import setup_logger

load_dotenv()
log = setup_logger("agent")


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
MODEL = "gpt-4o"  # 多模态模型，能看图


# 带连接重试的对话调用（每次重试都记日志）
def chat_with_retry(**kwargs):
    last_err = None
    for attempt in range(1, 5):
        try:
            return client.chat.completions.create(**kwargs)
        except (APIConnectionError, APITimeoutError) as e:
            last_err = e
            log.warning(f"对话连接失败 第{attempt}/4次: {type(e).__name__}")
            if attempt < 4:
                wait = attempt * 3
                print(f"   ⚠️ 网络连接失败（{type(e).__name__}），{wait}s 后第 {attempt + 1} 次重试...")
                time.sleep(wait)
    log.error(f"对话连接 4 次全失败: {type(last_err).__name__}: {last_err}")
    raise last_err


def _image_to_data_url(path: str) -> str:
    """把本地图片读成 data URL（base64），喂给多模态 LLM。"""
    ext = os.path.splitext(path)[1].lower().lstrip(".") or "png"
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/{mime};base64,{b64}"


# ============================================================
# 2. 工具注册
# ============================================================
TOOLS = [
    BEAD_TOOL,
    AIGC_TOOL,
]
TOOL_FUNCTIONS = {
    "generate_bead_art": generate_bead_art,
    "generate_aigc": generate_aigc,
}


# ============================================================
# 3. Agent Loop（支持文字 + 图片多模态）
# ============================================================
def agent_loop(user_text: str, user_image: str = None) -> str:
    """
    user_text: 用户输入的文字
    user_image: 可选，用户上传的图片路径（多模态）
    """
    log.info(f"收到输入: text={(user_text or '')[:60]} | image={user_image or '无'}")
    profile = load_profile()
    history = load_history()
    history = compress_history_if_needed(history, client, MODEL)

    # 构建本轮 user 消息：有图就多模态，没图就纯文字
    if user_image and os.path.exists(user_image):
        content = []
        if user_text:
            content.append({"type": "text", "text": user_text})
        content.append({"type": "image_url", "image_url": {"url": _image_to_data_url(user_image)}})
        # 告诉 LLM 图片路径，方便它调用拼豆工具时传 image_path
        content.append({"type": "text", "text": f"（用户上传的图片文件路径是 {user_image}。若需做成拼豆，把这个路径作为 image_path 传给 generate_bead_art）"})
        user_msg = {"role": "user", "content": content}
    else:
        user_msg = {"role": "user", "content": user_text}

    messages = [
        {"role": "system", "content": build_system_prompt(profile)},
    ] + history + [user_msg]

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
                        log.info(f"工具 {name} 成功 | 参数: {args}")
                    except Exception as e:
                        result = f"[工具执行出错] {type(e).__name__}: {e}"
                        print(f"   ⚠️ [工具报错] {name} → {type(e).__name__}: {e}")
                        log.error(f"工具 {name} 失败 | {type(e).__name__}: {e}")
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
        save_history(messages)  # 多模态图片会在存储时被清理掉（只留文字）
    return reply


# ============================================================
# 4. 命令行模式（纯文字；要发图片请用 app.py 的网页界面）
# ============================================================
if __name__ == "__main__":
    print("=" * 50)
    print("图片生成 Agent · 命令行模式（纯文字）。要发图片请运行：python app.py")
    print("输入 quit 退出。关掉重开，Agent 还记得你们聊过什么～")
    print("=" * 50)
    while True:
        try:
            user_input = input("\n你：").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见～")
            break
        if user_input.lower() in ("quit", "exit", "q"):
            print("再见～下次见！")
            break
        if not user_input:
            continue
        agent_loop(user_input)
