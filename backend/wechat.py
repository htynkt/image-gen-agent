"""
微信公众号适配层（公众号接入）
============================
给 agent_loop 套一个"微信输入输出壳"，和网页版并列成为第二个渠道：
  GET  /wechat  —— 微信首次配置时的【签名校验】（原样返回 echostr）
  POST /wechat  —— 接收用户消息（XML）→ 调 agent_loop → 回复（XML）

【阶段1】先跑通纯文本对话（同步调用；简单问候能压在 5 秒内返回）。
【阶段2】再解决 5 秒超时（个人订阅号没有客服消息，需用「重试去重」或「引导网页」）。
"""
import hashlib                       # 微信签名校验：sha1
import time                          # 生成回复的 CreateTime
import xml.etree.ElementTree as ET   # 解析/构造 XML

from fastapi import APIRouter, Request, HTTPException, Response
from fastapi.concurrency import run_in_threadpool   # 把同步阻塞调用丢进线程池，避免卡住事件循环

from agent import agent_loop, chat_once   # agent_loop：生图等重活（网页版）；chat_once：公众号对话框轻量对话

WECHAT_TOKEN = "huiling2026"         # ← 改成你自己的 Token（公众号后台填的必须和这里【完全一致】）

router = APIRouter()


def _check_signature(signature: str, timestamp: str, nonce: str) -> bool:
    """微信签名校验：token+timestamp+nonce 排序拼接后 sha1，与微信传来的 signature 比对。"""
    parts = sorted([WECHAT_TOKEN, timestamp, nonce])                  # 三个值按字典序排序
    digest = hashlib.sha1("".join(parts).encode("utf-8")).hexdigest()  # 拼一起做 sha1
    return digest == signature                                        # 一致 = 请求确实来自微信


@router.get("/wechat")
def wechat_verify(signature: str, timestamp: str, nonce: str, echostr: str):
    """GET：微信后台点「提交」时会请求这里验证服务器归属；通过则原样返回 echostr。"""
    if _check_signature(signature, timestamp, nonce):
        # 必须返回【纯文本】的 echostr，不能用默认 JSON（会被加引号，微信不认）
        return Response(content=echostr, media_type="text/plain")
    raise HTTPException(403, "签名校验失败")


def _parse_msg(xml_bytes: bytes) -> dict:
    """把微信发来的 XML 解析成字典：{MsgType, Content, FromUserName, ToUserName, ...}"""
    root = ET.fromstring(xml_bytes)
    return {child.tag: child.text for child in root}


def _text_reply(to_user: str, from_user: str, content: str) -> str:
    """构造一条【文本】回复 XML。注意：回复时 To/From 要【对调】（这条消息是发给用户的）。"""
    return (
        "<xml>"
        f"<ToUserName><![CDATA[{to_user}]]></ToUserName>"
        f"<FromUserName><![CDATA[{from_user}]]></FromUserName>"
        f"<CreateTime>{int(time.time())}</CreateTime>"
        "<MsgType><![CDATA[text]]></MsgType>"
        f"<Content><![CDATA[{content}]]></Content>"
        "</xml>"
    )


# 明确的「生成图片/拼豆」意图关键词（命中 → 引导去菜单，零 token，不调模型）
_GENERATE_KEYWORDS = (
    "生成图片", "生成一张", "生成图", "画一张", "画一个图", "画个图", "画一张图",
    "帮我画", "出图", "出一张", "拼豆", "做拼豆", "生成拼豆", "aigc图", "画图",
)


def _is_generate_intent(text: str) -> bool:
    """用户是否明确想【生成/产出一张图】（而非写描述/咨询）。命中则引导去菜单。"""
    return any(k in text for k in _GENERATE_KEYWORDS)


@router.post("/wechat")
async def wechat_message(request: Request):
    """POST：用户发来的消息/事件。解析 → 调 agent_loop → 回 XML。"""
    msg = _parse_msg(await request.body())   # 读 body 并解析 XML
    from_user = msg.get("FromUserName", "")  # 用户 openid（多用户隔离 + 配额的 key）
    to_user = msg.get("ToUserName", "")      # 公众号

    # —— 关注事件：被关注自动回复欢迎语（一进来就告诉用户能做什么）——
    if msg.get("MsgType") == "event" and msg.get("Event") == "subscribe":
        welcome = ("欢迎来到画灵屋～🐾 我是画灵，你可以：\n"
                   "💬 和我聊天 / 提问\n"
                   "✍️ 让我帮你写文案、构思画面、优化「生图提示词」\n"
                   "📱 问 PS / 修图 / 设计技巧\n"
                   "🎨 想生成图片 / 拼豆图 → 点底部菜单【创作】入口\n"
                   "今日有免费体验额度，先发句话试试吧～")
        return Response(content=_text_reply(from_user, to_user, welcome), media_type="application/xml")

    # —— 非文本（图片/语音等）：暂不支持，引导去网页版 ——
    if msg.get("MsgType") != "text":
        tip = "暂时只在对话框支持文字哦～\n发图/生图请点底部菜单【创作】入口 🎨"
        return Response(content=_text_reply(from_user, to_user, tip), media_type="application/xml")

    user_text = msg.get("Content", "") or ""
    # ② 关键词导航：明确的「生成图片/拼豆」意图 → 固定话术引导去菜单（零 token，不调模型）
    if _is_generate_intent(user_text):
        guide = ("好的～生成图片 / 拼豆请点底部菜单【创作】入口哦 🎨\n"
                 "网页版体验更好、可直接下载～")
        return Response(content=_text_reply(from_user, to_user, guide), media_type="application/xml")
    # ③ 其他文字需求（聊天/问答/写描述/文案/咨询）→ 轻量单轮对话
    reply = await run_in_threadpool(chat_once, user_text, from_user)

    return Response(content=_text_reply(from_user, to_user, reply), media_type="application/xml")
