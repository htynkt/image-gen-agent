"""
记忆系统（阶段3）
================
步骤1：个性化档案 profile（称呼/语气/风格）
步骤2：对话持久化（存/加载历史）
步骤3：上下文压缩（历史太长时，自动总结成摘要，省 context、防撑爆）
"""
import os     # 判断文件是否存在、创建目录
import json   # 读写对话历史（JSON 文件）
import yaml   # 读 profile.yaml（个性化档案）

HISTORY_PATH = "data/chat_history.json"  # 对话历史的存放路径
SUMMARY_THRESHOLD = 4000   # 历史总字符数超过这个 → 触发压缩（可调，越小压得越勤）
KEEP_RECENT = 8            # 压缩时保留最近几条原文（可调）


# ============ 步骤1：个性化档案 ============
def load_profile(path: str = "config/profile.yaml") -> dict:
    """读取个性化档案。文件不存在则返回空字典（用默认值）。"""
    if not os.path.exists(path):  # 档案文件不存在
        return {}                  # 返回空字典（让调用方用代码里的默认称呼/语气）
    with open(path, "r", encoding="utf-8") as f:  # 以 utf-8 打开 yaml
        return yaml.safe_load(f) or {}            # 解析成字典；空文件/None 时返回 {}


def build_system_prompt(profile: dict) -> str:
    """根据个性化档案，拼出 Agent 的 system 提示词（人设 + 工具说明）。"""
    nickname = profile.get("nickname", "你")  # 称呼（档案里没写就用默认"你"）
    tone = profile.get("tone", "友好")        # 语气（默认"友好"）
    style = profile.get("style") or {}        # 风格偏好（是个字典，可能为空）
    # 把 style 字典拼成一段文字，如 "palette：马卡龙；vibe：治愈"；为空则写"无特别偏好"
    style_str = "；".join(f"{k}：{v}" for k, v in style.items()) if style else "无特别偏好"

    return (  # 拼出完整的 system 提示词（告诉 LLM：你是谁、怎么说话、有哪些工具、何时用哪个）
        f"你是「{nickname}」的专属图片生成助手，称呼 ta 为「{nickname}」。\n"
        f"说话语气：{tone}。\n"
        f"出图默认风格偏好：{style_str}。\n\n"
        f"你有两个工具：\n"
        f"1. generate_bead_art：把【已有的图片】转成拼豆图纸（用户说'拼豆/做成拼豆'，"
        f"或给了图片路径时调用，必须传 image_path）。\n"
        f"2. generate_aigc：根据【一段提示语】生成全新的创意图（用户描述画面/风格，"
        f"想让 AI 画一张图时调用，必须传 prompt）。\n"
        f"判断依据：用户给的是'已有图片'→拼豆；用户给的是'文字描述/想画一张'→AIGC。"
        f"工具返回后，用你的语气告诉用户图片已生成、保存在哪里。"
    )


# ============ 步骤2：对话持久化 ============
def load_history(path: str = HISTORY_PATH) -> list:
    """加载历史对话消息。文件不存在/损坏则返回空列表。"""
    if not os.path.exists(path):  # 历史文件不存在
        return []                  # 没有历史，返回空列表
    try:
        with open(path, "r", encoding="utf-8") as f:  # 读 JSON 文件
            return json.load(f)                        # 解析成消息列表返回
    except (json.JSONDecodeError, OSError):  # 文件损坏或读不了
        return []                            # 当作没历史，返回空（不让程序崩）


def save_history(messages: list, path: str = HISTORY_PATH) -> None:
    """
    保存对话历史：去掉第一条「主 system 提示」（它每次由 profile 重新生成），
    其余全存。多模态消息（含图片）只留文字部分——丢掉图片 base64，避免撑爆历史。
    """
    # 第一条是主 system 提示，去掉（它每次重新生成，存了会过时）；其余保留
    raw = messages[1:] if (messages and messages[0].get("role") == "system") else messages
    convo = []                       # 用来存清理后的消息列表
    for m in raw:                    # 遍历每条消息
        c = m.get("content")         # 取它的 content
        if isinstance(c, list):      # 多模态消息的 content 是个数组（含图片段）
            texts = [p.get("text", "") for p in c if p.get("type") == "text"]  # 只把文字段挑出来
            m = {**m, "content": "\n".join(t for t in texts if t)}             # 把 content 换成纯文字（丢掉图片）
        convo.append(m)              # 加入结果列表
    os.makedirs(os.path.dirname(path), exist_ok=True)  # 确保目录存在
    with open(path, "w", encoding="utf-8") as f:       # 写文件
        json.dump(convo, f, ensure_ascii=False, indent=2)  # ensure_ascii=False 保留中文，indent=2 缩进美化


# ============ 步骤3：上下文压缩 ============
def _msg_text(m: dict) -> str:
    """估算一条消息占多少字符（content + tool_calls 都算上）"""
    text = m.get("content") or ""            # 取 content（可能是字符串或 None）
    if m.get("tool_calls"):                  # 如果这条消息带工具调用
        text += json.dumps(m["tool_calls"], ensure_ascii=False)  # 把 tool_calls 也算进长度
    return text


def _summarize(messages: list, client, model: str) -> str:
    """让 LLM 把一段历史对话总结成简短摘要。"""
    text = "\n".join(f"[{m.get('role')}] {_msg_text(m)}" for m in messages)  # 把消息列表拼成一段纯文本
    resp = client.chat.completions.create(          # 调 LLM
        model=model,
        messages=[
            {"role": "system", "content":           # 系统提示：要求它做摘要
             "你是对话总结助手。把下面的历史对话压缩成简短摘要，"
             "保留关键信息：用户是谁、明确说过的偏好、请求过什么图、重要结论。"
             "用三五句话讲清楚，不要编造没有的内容。"},
            {"role": "user", "content": text},       # 把拼接的历史文本作为输入
        ],
    )
    return resp.choices[0].message.content          # 返回 LLM 生成的摘要文字


def compress_history_if_needed(history: list, client, model: str,
                               threshold: int = SUMMARY_THRESHOLD,
                               keep_recent: int = KEEP_RECENT) -> list:
    """
    历史太长时压缩：把较早的消息交给 LLM 总结成一条【摘要】，
    替换掉那一大堆旧消息，只保留最近 keep_recent 条原文。
    - 不够长 → 原样返回（不压缩）
    - 压缩失败（如网络/平台不稳）→ 原样返回（绝不丢数据）
    """
    total_chars = sum(len(_msg_text(m)) for m in history)  # 统计所有消息的总字符数
    if total_chars <= threshold or len(history) <= keep_recent:  # 总长度没超阈值，或消息条数太少
        return history  # 不需要压缩，原样返回

    older = history[:-keep_recent]   # 较早的（列表前面那部分）：要被总结掉
    recent = history[-keep_recent:]  # 最近的（列表后面那部分）：保留原文
    print(f"   🗜️ 历史较长（约 {total_chars} 字符），把较早的 {len(older)} 条压缩成摘要...")
    try:
        summary = _summarize(older, client, model)  # 让 LLM 把较早的部分总结成摘要
    except Exception as e:                          # 压缩过程出错（网络/平台问题）
        print(f"   ⚠️ 压缩失败（{type(e).__name__}），本次保留原文，不丢数据")
        return history                              # 失败就保留原文，绝不丢数据
    print(f"   ✅ 已压缩为摘要（{len(summary)} 字符），保留最近 {len(recent)} 条原文")
    # 返回：一条【摘要 system 消息】 + 保留的最近原文
    return [{"role": "system", "content": f"【过往对话摘要】\n{summary}"}] + recent
