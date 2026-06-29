"""
图片生成 Agent · 核心入口（agent_loop）
=============================================
这是整个项目的「大脑」。前端/命令行都通过调用 agent_loop() 来和 AI 对话。
核心 = 一个 while 循环（Agent Loop）：反复问 LLM，它要调工具就执行，直到给出最终回复。

能力：拼豆图 + AIGC 创意图（工具）、多模态看图、个性化、记忆、重试、日志。
【安全】API Key 通过 .env 读取，不写死在代码里。
"""

# ===== 标准库导入 =====
import json              # 解析 LLM 返回的工具参数（JSON 字符串 → 字典）
import os                # 读环境变量、判断文件存在、处理路径
import time              # 重试时等待（sleep）
import base64            # 把本地图片编码成 base64（多模态需要）

# ===== 第三方库导入 =====
from openai import OpenAI, APIConnectionError, APITimeoutError  # OpenAI 兼容 SDK + 两个网络异常类
from dotenv import load_dotenv   # 从 .env 文件加载环境变量

# ===== 项目内模块导入 =====
from skills.bead_art import generate_bead_art, BEAD_TOOL        # 拼豆图：函数 + 工具说明书
from skills.aigc_creative import generate_aigc, AIGC_TOOL       # AIGC 创意图：函数 + 工具说明书
from core.memory import (                                        # 记忆系统
    load_profile, build_system_prompt,                           #   —— 个性化档案
    load_history, save_history,                                  #   —— 对话历史
    compress_history_if_needed,                                  #   —— 上下文压缩
)
from core.logger import setup_logger   # 日志
from core.quota import check_and_consume   # 配额限流（商业化·第二步）

load_dotenv()                  # 把 .env 里的 API_KEY / BASE_URL 加载进环境变量
log = setup_logger("agent")    # 创建一个写文件的日志器（名字 "agent"，写到 data/agent.log）


# ============================================================
# 1. 连接大模型
# ============================================================
API_KEY = os.getenv("API_KEY")    # 从环境变量读 API 密钥
BASE_URL = os.getenv("BASE_URL")  # 从环境变量读接口地址
if not API_KEY or not BASE_URL:   # 没配好的话，立刻报错退出（别等运行到一半才崩）
    raise SystemExit(
        "❌ 没从 .env 读到 API_KEY 或 BASE_URL，请检查 .env 文件。\n"
        "  API_KEY=你的key\n  BASE_URL=https://你的接口地址"
    )

client = OpenAI(api_key=API_KEY, base_url=BASE_URL)  # 建一个 OpenAI 客户端（指向聚合平台地址）
MODEL = "gpt-4o"            # 主力模型：多模态（能看图）+ 强推理；贵，只在【需要看图/复杂决策】时用
CHEAP_MODEL = "gpt-4o-mini"  # 轻量模型：纯文字对话 + 文生图工具调用；价格约为 gpt-4o 的 1/15，走量大用它


# 带连接重试的对话调用（网络不稳时自动重连）
def chat_with_retry(**kwargs):
    """包装 client.chat.completions.create：网络类异常时自动重试最多 4 次。"""
    last_err = None                                   # 记录最后一次异常
    for attempt in range(1, 5):                       # attempt = 1,2,3,4（最多试 4 次）
        try:
            resp = client.chat.completions.create(**kwargs)  # 真正调 LLM
            # —— 成本可观测：打印 token 用量 + 缓存命中情况（prompt caching 省了多少）——
            usage = resp.usage
            if usage:
                pd = getattr(usage, "prompt_tokens_details", None)
                cached = getattr(pd, "cached_tokens", 0) if pd else 0
                print(f"   💰 token | 输入 {usage.prompt_tokens}（缓存命中 {cached}） 输出 {usage.completion_tokens}")
            return resp                                       # 成功就返回结果
        except (APIConnectionError, APITimeoutError) as e:   # 只在网络类异常时才重试
            last_err = e                              # 记下这次异常
            log.warning(f"对话连接失败 第{attempt}/4次: {type(e).__name__}")  # 记日志
            if attempt < 4:                           # 还没到第 4 次，等一会儿再试
                wait = attempt * 3                    # 等待秒数：3s、6s、9s（递增退避）
                print(f"   ⚠️ 网络连接失败（{type(e).__name__}），{wait}s 后第 {attempt + 1} 次重试...")
                time.sleep(wait)                      # 等待
    log.error(f"对话连接 4 次全失败: {type(last_err).__name__}: {last_err}")  # 4 次都失败，记错误
    raise last_err                                    # 把最后一次异常抛出，交给调用方


def _image_to_data_url(path: str) -> str:
    """把本地图片读成 data URL（base64），喂给多模态 LLM。"""
    ext = os.path.splitext(path)[1].lower().lstrip(".") or "png"  # 取扩展名（去点），如 "jpg"；无则默认 png
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext              # jpg 的 MIME 类型实际是 jpeg，其余直接用扩展名
    with open(path, "rb") as f:                                   # 二进制方式打开图片
        b64 = base64.b64encode(f.read()).decode()                # 整个文件编码成 base64 字符串
    return f"data:image/{mime};base64,{b64}"                      # 拼成标准 data URL 返回


# ============================================================
# 2. 工具注册（Tool Use 的核心：工具在这里「登记上岗」）
# ============================================================
TOOLS = [                # 工具「说明书」列表，会传给 LLM，告诉它有哪些工具可用
    BEAD_TOOL,           # 拼豆图工具的说明书
    AIGC_TOOL,           # AIGC 创意图工具的说明书
]
TOOL_FUNCTIONS = {       # 「工具名 → 真正执行的函数」映射表（执行时靠它找到对应函数）
    "generate_bead_art": generate_bead_art,
    "generate_aigc": generate_aigc,
}


# 引用历史的关键词：用户说这些词时，才把过往对话加载进上下文
_HISTORY_KEYWORDS = ("上次", "上一次", "之前", "刚才", "刚刚", "上一个", "上一张", "前一次", "记得吗", "历史")


def _mentions_history(text: str) -> bool:
    """用户是否在引用之前的对话（如「上次那个」「之前那张图」）"""
    return any(k in (text or "") for k in _HISTORY_KEYWORDS)  # text 含任一关键词就返回 True


# ============================================================
# 3. Agent Loop（核心：一个 while 循环，支持文字 + 图片多模态）
# ============================================================
def agent_loop(user_text: str, user_image: str = None, user_id: str = "default") -> str:
    """
    user_text:  用户输入的文字
    user_image: 可选，用户上传的图片在本地的路径（多模态）
    user_id:    用户标识（公众号=openid，网页版="web"）；用于隔离历史 + 配额限流
    返回: LLM 的最终文字回复
    """
    log.info(f"收到输入: user={user_id} text={(user_text or '')[:60]} | image={user_image or '无'}")
    # —— 配额限流（入口拦截，超额不调模型，省 token）——
    allowed, used, limit = check_and_consume(user_id)
    if not allowed:
        print(f"   🚫 [{user_id}] 今日额度已满（{limit} 次），拦截，不调模型")
        return f"今日免费体验额度（{limit} 次）已用完，明天再来吧～"
    profile = load_profile()  # 读个性化档案（称呼/语气/风格）

    # —— 记忆策略 ——
    # 默认不把历史塞进上下文（避免回复混乱，AI 只聚焦当前这句话）；
    # 只有用户【引用了之前】（说"上次/之前/刚才..."）时，才加载历史，让 AI 能看懂"上次那个"
    if _mentions_history(user_text):                                            # 用户引用了历史
        history = compress_history_if_needed(load_history(user_id), client, MODEL)    # 加载【该用户】历史，必要时压缩
        log.info("检测到引用历史，已加载过往对话供参考")
    else:                                                                       # 平时对话
        history = []                                                            # 不加载历史，回复保持干净

    # —— 构建本轮 user 消息：有图就多模态，没图就纯文字 ——
    if user_image and os.path.exists(user_image):  # 有图片路径且文件确实存在
        content = []                               # 多模态消息的 content 是一个「数组」（可含多段内容）
        if user_text:                              # 有文字就先加一段文字
            content.append({"type": "text", "text": user_text})
        content.append({"type": "image_url", "image_url": {"url": _image_to_data_url(user_image)}})  # 加图片段（base64）
        # 再用文字告诉 LLM 这张图的本地路径，方便它调用拼豆工具时把路径传进去
        content.append({"type": "text", "text": f"（用户上传的图片文件路径是 {user_image}。若需做成拼豆，把这个路径作为 image_path 传给 generate_bead_art）"})
        user_msg = {"role": "user", "content": content}  # 组成多模态 user 消息
    else:                                                 # 没有图片
        user_msg = {"role": "user", "content": user_text}  # 纯文字 user 消息

    # —— 拼出完整消息列表：系统提示 + 历史 + 本轮输入 ——
    messages = [
        {"role": "system", "content": build_system_prompt(profile)},  # system：人设 + 工具说明（由 profile 生成）
    ] + history + [user_msg]                                          # 再接上历史对话，最后是本轮 user 消息

    # —— 模型分层（商业化降本，最大杠杆）：带图需多模态看图 → gpt-4o；纯文字 → 便宜的 gpt-4o-mini ——
    use_model = MODEL if user_image else CHEAP_MODEL
    print(f"   🎚️ 本轮模型：{use_model}{'（带图→多模态主力）' if user_image else '（纯文字→轻量省钱）'}")

    reply = ""                          # 用来存最终回复
    try:
        max_steps = 10                  # 安全护栏：最多循环 10 轮，防止死循环
        step = 0                        # 当前轮数计数
        while step < max_steps:         # ← 这就是 Agent Loop：一个 while 循环
            step += 1
            print(f"\n——— 第 {step} 轮：调用 LLM ———")  # 控制台打印进度（给开发者看）

            resp = chat_with_retry(model=use_model, messages=messages, tools=TOOLS)  # 调 LLM（带重试），按分层选模型
            msg = resp.choices[0].message                                        # 取出返回的 message 对象

            if msg.tool_calls:                    # LLM 决定要调工具
                messages.append(msg.model_dump())  # 把「它要调工具」这个决定记进 messages（model_dump 转成字典）
                for call in msg.tool_calls:        # 一次可能要调多个工具，逐个执行
                    name = call.function.name      # 工具名，如 "generate_bead_art"
                    try:
                        args = json.loads(call.function.arguments)  # 参数是 JSON 字符串，转成字典
                        result = TOOL_FUNCTIONS[name](**args)        # 从映射表找到函数并执行，得到结果
                        log.info(f"工具 {name} 成功 | 参数: {args}")  # 记成功日志
                    except Exception as e:                          # 工具执行报错（不让整个 Agent 崩）
                        result = f"[工具执行出错] {type(e).__name__}: {e}"  # 把错误信息当成「结果」
                        print(f"   ⚠️ [工具报错] {name} → {type(e).__name__}: {e}")
                        log.error(f"工具 {name} 失败 | {type(e).__name__}: {e}")
                    messages.append(                                # 把工具结果作为 role=tool 的消息喂回去
                        {"role": "tool", "tool_call_id": call.id, "content": result}
                    )
                continue                            # 工具执行完，回到 while 顶部，再问 LLM 下一步
            else:                                   # LLM 没要调工具 → 它给出最终答案了
                print(f"\n🤖 Agent：\n{msg.content}")
                reply = msg.content                 # 记下回复
                break                               # 跳出循环（正常结束）
        else:                                       # while 跑满 max_steps 仍没 break（达到上限）
            print(f"\n⚠️ 达到最大轮数 {max_steps}，进行收尾")
            resp = chat_with_retry(model=use_model, messages=messages)  # 不带 tools 再调一次，强制它收尾输出
            reply = resp.choices[0].message.content or "（收尾时未返回内容）"
            print(f"\n🤖 Agent：\n{reply}")
    finally:
        save_history(messages, user_id)  # 按 user_id 存（多用户隔离）；图片在存储时会被清理
    return reply                # 返回最终回复文字


# ============================================================
# 3.5 轻量单轮对话（公众号对话框专用：不走 Agent Loop，不生图，快且省 token）
# ============================================================
def chat_once(user_text: str, user_id: str = "default") -> str:
    """
    轻量单轮对话（公众号对话框用）：不走 Agent Loop、不带工具、不生图。
    适合：聊天 / 问答咨询 / 写文案 / 构思·优化「生图提示词」/ 技巧解答。
    特点：快、省 token、5 秒内稳。生图等重活由菜单引导去网页版。
    """
    # 配额限流（和 agent_loop 共用同一套，统一计数）
    allowed, used, limit = check_and_consume(user_id)
    if not allowed:
        print(f"   🚫 [{user_id}] 轻量对话额度已满，拦截")
        return f"今日免费体验额度（{limit} 次）已用完，明天再来吧～"

    system = (
        "你是「画灵屋」公众号的助手画灵，语气友好、简洁。\n"
        "你的能力：① 陪聊、问答咨询；② 写文案；③ 帮用户构思/优化「生图提示词」，"
        "让 ta 能生成更好的图；④ 解答 PS/修图/设计等技巧问题。\n"
        "【重要】你【不能】直接生成图片或拼豆图。若用户想「生成图片 / 拼豆 / 出图 / 画一张图」，"
        "请引导：「请点击公众号底部菜单【创作】入口，在网页版生成，体验更好、可直接下载 🎨」。\n"
        "回复控制在三五句话内，不啰嗦。"
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user_text},
    ]
    # 单次直调便宜模型（不带 tools，不进 Agent Loop）→ 快、省、5 秒内稳
    resp = chat_with_retry(model=CHEAP_MODEL, messages=messages)
    reply = resp.choices[0].message.content or "（没听清，再说一次试试？）"
    print(f"   💬 轻量对话 [{user_id}]：{user_text[:20]} → {reply[:30]}…")
    return reply


# ============================================================
# 4. 命令行模式（纯文字；要发图片请用网页界面 backend + frontend）
# ============================================================
if __name__ == "__main__":                       # 只有「直接运行 agent.py」时才执行下面；被 import 时跳过
    print("=" * 50)                              # 打印一行分隔线（50 个等号）
    print("图片生成 Agent · 命令行模式（纯文字）。要发图片请启动 backend + frontend")  # 启动横幅
    print("输入 quit 退出。关掉重开，Agent 还记得你们聊过什么～")           # 提示怎么退出
    print("=" * 50)                              # 分隔线收尾
    while True:                                  # 无限循环：一直等用户输入
        try:
            user_input = input("\n你：").strip()  # 阻塞等待输入（提示符「你：」），strip 去首尾空白
        except (EOFError, KeyboardInterrupt):    # 输入流结束 / 按 Ctrl+C
            print("\n再见～")                     # 告别
            break                                # 退出循环
        if user_input.lower() in ("quit", "exit", "q"):  # 是退出命令（大小写都认）
            print("再见～下次见！")               # 告别
            break                                # 退出
        if not user_input:                       # 空输入（只敲回车）
            continue                             # 跳过，重新等输入
        agent_loop(user_input)                   # 把这句话交给 agent_loop 处理
