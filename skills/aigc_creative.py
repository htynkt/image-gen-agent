"""
技能：AIGC 创意图像生成
======================
输入一段提示语（prompt），调用文生图大模型，生成对应风格的图像。
和拼豆图不同：拼豆是本地算法（零成本），AIGC 创意图是调云端 API（按次计费）。

输入：提示语 prompt（+ 可选 style 风格词）
输出：图片存到 data/outputs/aigc_<提示语>.png，返回路径
"""
import os        # 读环境变量、创建目录
import re        # 从提示语提取安全文件名
import time      # 重试时等待（sleep）
import base64    # 解码接口返回的 b64_json 图片
import requests  # 下载接口返回的 url 形式图片
from openai import (           # OpenAI SDK + 多个异常类
    OpenAI,
    APIConnectionError,        # 连接错误（网络层）
    APITimeoutError,           # 请求超时
    InternalServerError,       # 5xx 服务端错误（如 502）
    RateLimitError,            # 429 限流
)
from dotenv import load_dotenv      # 读 .env
from core.logger import setup_logger  # 日志

load_dotenv()                  # 把 .env 的变量加载进环境
log = setup_logger("aigc")     # 创建日志器（名字 "aigc"，和 agent 共用同一个 agent.log 文件）

# 复用 .env 的 API 配置（和 agent.py 一致）
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
IMAGE_MODEL = "gpt-4o-image"   # 文生图模型名（按你聚合平台的模型列表填）
IMAGE_SIZE = "1024x1024"       # 出图尺寸

if API_KEY and BASE_URL:                              # 配置齐全
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)  # 建客户端
else:                                                  # 没配好
    client = None  # 先不报错，等真正调用时再提示（延迟报错，避免 import 阶段就崩）


def _safe_name(text: str, n: int = 12) -> str:
    """从提示语里提取安全文件名片段（只保留中文/字母数字，去掉空格标点）"""
    s = re.sub(r"[^\w一-龥]", "", text)[:n]  # \w=字母数字下划线，一-龥=中文区间；取前 n 个字符
    return s or "img"                         # 如果提取完是空的（比如纯标点），就用 "img"


def _generate_with_retry(**kwargs):
    """
    文生图调用带重试：遇到 502/429/网络抖动时自动等几秒重连，最多 3 次。
    3 次都失败才抛出（交给外层 try-except 优雅处理，不会让 Agent 崩）。
    每次重试/失败都记日志，事后能在 data/agent.log 查到。
    """
    for attempt in range(1, 4):  # attempt = 1,2,3（最多 3 次）
        try:
            return client.images.generate(**kwargs)  # 真正调文生图接口；成功就返回
        except (InternalServerError, RateLimitError, APIConnectionError, APITimeoutError) as e:  # 这些异常才重试
            if attempt == 3:                         # 已经是第 3 次了还失败
                log.error(f"文生图 3 次重试全失败: {type(e).__name__}: {e}")
                raise                                # 抛出异常，交给外层兜底
            wait = attempt * 5                       # 等待秒数：5s、10s
            print(f"   ⚠️ 文生图服务异常（{type(e).__name__}），{wait}s 后第 {attempt + 1} 次重试...")
            log.warning(f"文生图异常 第{attempt}/3次: {type(e).__name__}（{wait}s 后重试）")
            time.sleep(wait)                         # 等待后重试


def generate_aigc(prompt: str, style: str = "") -> str:
    """
    用文生图 API 生成一张创意图。
    prompt: 画面描述，例如「一只戴墨镜的柴犬坐在街头」
    style:  可选风格词，例如「赛博朋克」「水彩」，会拼进 prompt
    返回：图片路径 + 说明文字
    """
    if client is None:  # API 没配好
        return "❌ 还没配置 API_KEY / BASE_URL，请先在 .env 里填好。"

    full_prompt = f"{prompt}，{style}" if style else prompt  # 有风格词就拼进去，没有就只用 prompt
    print(f"   🔧 [工具执行] generate_aigc(prompt='{prompt}', style='{style}')")  # 控制台打印进度
    log.info(f"调用文生图 | model={IMAGE_MODEL} | prompt={full_prompt[:60]}")     # 记日志（截断 60 字符）

    # 1. 调用文生图接口（带重试，扛住平台偶发 502/429）
    resp = _generate_with_retry(
        model=IMAGE_MODEL,
        prompt=full_prompt,
        n=1,                # 生成 1 张
        size=IMAGE_SIZE,    # 尺寸
    )
    item = resp.data[0]     # 取第 1 张（也是唯一一张）

    # 2. 保存图片（接口可能返回 url 或 b64_json，两种格式都处理）
    os.makedirs("data/outputs", exist_ok=True)  # 确保 outputs 目录存在
    out_path = os.path.abspath(f"data/outputs/aigc_{_safe_name(prompt)}.png")  # 输出路径（文件名含提示语片段）

    if getattr(item, "b64_json", None):     # 接口直接返回 base64
        with open(out_path, "wb") as f:     # 二进制写
            f.write(base64.b64decode(item.b64_json))  # base64 解码后写入文件
    else:                                    # 接口返回的是图片 URL
        url = item.url
        r = requests.get(url, timeout=60)   # 下载这张图（最多等 60 秒）
        r.raise_for_status()                # 下载失败（4xx/5xx）就抛异常
        with open(out_path, "wb") as f:
            f.write(r.content)              # 把下载内容写入文件

    log.info(f"文生图成功: {out_path}")      # 记成功日志
    return (                                 # 返回路径 + 说明（给 LLM 转述给用户）
        f"AIGC 创意图已生成：{out_path}\n"
        f"提示语：{full_prompt}\n"
        f"模型：{IMAGE_MODEL}，尺寸：{IMAGE_SIZE}"
    )


# ---------- 工具说明书（给 LLM 看）----------
AIGC_TOOL = {
    "type": "function",       # 工具类型：函数
    "function": {
        "name": "generate_aigc",  # 工具名（LLM 用这个名字调用）
        "description": (            # 告诉 LLM 何时用这个工具
            "根据一段提示语生成一张创意图（调用文生图大模型）。"
            "用户描述想要的画面或风格、想让 AI 画一张图时调用。"
            "注意：和拼豆图不同，这个是从文字直接生成全新图片。"
        ),
        "parameters": {             # 参数定义
            "type": "object",
            "properties": {
                "prompt": {         # 必填：画面描述
                    "type": "string",
                    "description": "画面描述，例如：一只戴墨镜的柴犬坐在霓虹街头",
                },
                "style": {          # 可选：风格词
                    "type": "string",
                    "description": "可选风格词，例如：赛博朋克、水彩、油画、吉卜力风",
                    "default": "",
                },
            },
            "required": ["prompt"],  # 只有 prompt 必填
        },
    },
}


# ---------- 直接运行：测试 AIGC 出图 ----------
if __name__ == "__main__":  # 只有直接运行本文件时才执行
    print(generate_aigc("一只戴墨镜的柴犬坐在街头", style="赛博朋克"))  # 测试出一张图
