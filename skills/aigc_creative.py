"""
技能：AIGC 创意图像生成
======================
输入一段提示语（prompt），调用文生图大模型，生成对应风格的图像。
和拼豆图不同：拼豆是本地算法（零成本），AIGC 创意图是调云端 API（按次计费）。

输入：提示语 prompt（+ 可选 style 风格词）
输出：图片存到 data/outputs/aigc_<提示语>.png，返回路径
"""
import os
import re
import time
import base64
import requests
from openai import (
    OpenAI,
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)
from dotenv import load_dotenv

load_dotenv()

# 复用 .env 的 API 配置（和 agent.py 一致）
API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
# 文生图模型名：按你的服务填（OpenAI→dall-e-3 / gpt-image-1；智谱→cogview-3-plus；聚合平台按模型列表填）
IMAGE_MODEL = "gpt-4o-image"
IMAGE_SIZE = "1024x1024"

if API_KEY and BASE_URL:
    client = OpenAI(api_key=API_KEY, base_url=BASE_URL)
else:
    client = None  # 没配好时延迟报错，由调用方提示


def _safe_name(text: str, n: int = 12) -> str:
    """从提示语里提取安全文件名片段（保留中文/字母数字）"""
    s = re.sub(r"[^\w一-龥]", "", text)[:n]
    return s or "img"


def _generate_with_retry(**kwargs):
    """
    文生图调用带重试：遇到 502（服务临时不可用）/ 429（限流）/ 网络抖动时，
    自动等几秒重连，最多 3 次。提高在平台偶发抽风时的出图成功率。
    3 次都失败才抛出（交给外层 try-except 优雅处理，不会让 Agent 崩）。
    """
    for attempt in range(1, 4):  # 最多 3 次
        try:
            return client.images.generate(**kwargs)
        except (InternalServerError, RateLimitError, APIConnectionError, APITimeoutError) as e:
            if attempt == 3:
                raise  # 第 3 次仍失败 → 抛出，由外层兜底
            wait = attempt * 5  # 5s、10s 递增
            print(f"   ⚠️ 文生图服务异常（{type(e).__name__}），{wait}s 后第 {attempt + 1} 次重试...")
            time.sleep(wait)


def generate_aigc(prompt: str, style: str = "") -> str:
    """
    用文生图 API 生成一张创意图。
    prompt: 画面描述，例如「一只戴墨镜的柴犬坐在街头」
    style:  可选风格词，例如「赛博朋克」「水彩」，会拼进 prompt
    返回：图片路径 + 说明文字
    """
    if client is None:
        return "❌ 还没配置 API_KEY / BASE_URL，请先在 .env 里填好。"

    full_prompt = f"{prompt}，{style}" if style else prompt
    print(f"   🔧 [工具执行] generate_aigc(prompt='{prompt}', style='{style}')")

    # 1. 调用文生图接口（带重试，扛住平台偶发 502/429）
    resp = _generate_with_retry(
        model=IMAGE_MODEL,
        prompt=full_prompt,
        n=1,
        size=IMAGE_SIZE,
    )
    item = resp.data[0]

    # 2. 保存图片（接口可能返回 url 或 b64_json，两种都处理）
    os.makedirs("data/outputs", exist_ok=True)
    out_path = os.path.abspath(f"data/outputs/aigc_{_safe_name(prompt)}.png")

    if getattr(item, "b64_json", None):
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(item.b64_json))
    else:
        url = item.url
        r = requests.get(url, timeout=60)
        r.raise_for_status()
        with open(out_path, "wb") as f:
            f.write(r.content)

    return (
        f"AIGC 创意图已生成：{out_path}\n"
        f"提示语：{full_prompt}\n"
        f"模型：{IMAGE_MODEL}，尺寸：{IMAGE_SIZE}"
    )


# ---------- 工具说明书（给 LLM 看）----------
AIGC_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_aigc",
        "description": (
            "根据一段提示语生成一张创意图（调用文生图大模型）。"
            "用户描述想要的画面或风格、想让 AI 画一张图时调用。"
            "注意：和拼豆图不同，这个是从文字直接生成全新图片。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "画面描述，例如：一只戴墨镜的柴犬坐在霓虹街头",
                },
                "style": {
                    "type": "string",
                    "description": "可选风格词，例如：赛博朋克、水彩、油画、吉卜力风",
                    "default": "",
                },
            },
            "required": ["prompt"],
        },
    },
}


# ---------- 直接运行：测试 AIGC 出图 ----------
if __name__ == "__main__":
    print(generate_aigc("一只戴墨镜的柴犬坐在街头", style="赛博朋克"))
