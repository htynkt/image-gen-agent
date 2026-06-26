"""
阶段6：FastAPI 后端
==================
把 agent_loop 包一层 HTTP，供前端 Vue 调用。
核心思想：通过 sys.path + os.chdir 复用根目录的 agent_loop，**不改它内部一行**。

启动（必须在【项目根目录】执行，保证 data/ 相对路径写对位置）：
    uvicorn backend.main:app --reload --port 8000
"""
import os
import sys
import re
import uuid
import base64
from pathlib import Path

# ============================================================
# 关键：让后端能 import 根目录的 agent，并保证相对路径写对位置
# ============================================================
# backend/main.py 往上一级就是项目根
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)
# agent / core / skills 全用 data/... 相对路径，cwd 必须是项目根，否则历史/输出写错地方
os.chdir(PROJECT_ROOT)

# 这一句会触发 agent.py 里的 load_dotenv() 和建 OpenAI client
from agent import agent_loop

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="图片生成 Agent API")

# ---- 开发期 CORS 双保险（vite proxy 已经免跨域，这里再放行 5173）----
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_DIR = Path("data").resolve()
UPLOAD_DIR = DATA_DIR / "uploads"   # 用户上传图落盘处
OUTPUT_DIR = DATA_DIR / "outputs"   # Agent 生成的图
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# ---- 静态挂载：前端用 /files/outputs/xxx.png 直接取图 ----
app.mount("/files/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")
app.mount("/files/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")


@app.get("/api/health")
def health():
    """探活 + 验证 import 链是否通"""
    return {"status": "ok"}


class ChatRequest(BaseModel):
    text: str = ""
    image: str | None = None  # data URL（data:image/...;base64,...）或纯 base64


# 从 reply 文本里抠出图片【绝对路径】（Windows 反斜杠 / 正斜杠都兼容）
# 工具返回形如 "...已生成：D:\\...\\data\\outputs\\bead_pattern_3.png"
_PATH_RE = re.compile(r"[A-Za-z]:[\\\/][^\s：:，,。、）)]+\.(?:png|jpg|jpeg|webp)", re.I)


def _abs_to_url(abs_path: str) -> str | None:
    """把绝对路径转成前端可访问的 /files/... URL；不在 data/ 下返回 None"""
    try:
        rel = Path(abs_path).resolve().relative_to(DATA_DIR)
    except ValueError:
        return None
    return "/files/" + rel.as_posix()


@app.post("/api/chat")
def chat(req: ChatRequest):
    """主接口：收文字+可选图片 → 调 agent_loop → 返回 {reply, images}"""
    if not req.text and not req.image:
        raise HTTPException(400, "text 和 image 至少给一个")

    # 1. 图片 base64 落盘到 data/uploads/
    image_path = None
    if req.image:
        b64 = req.image.split(",", 1)[-1]  # 去掉 data:image/...;base64, 前缀
        ext = "jpg" if "jpeg" in req.image[:30].lower() else "png"
        fname = f"{uuid.uuid4().hex}.{ext}"
        image_path = str(UPLOAD_DIR / fname)
        with open(image_path, "wb") as f:
            f.write(base64.b64decode(b64))

    # 2. 复用 agent_loop（不改它内部）
    try:
        reply = agent_loop(req.text, user_image=image_path)
    except Exception as e:
        raise HTTPException(500, f"agent 执行失败: {e}")

    # 3. 从 reply 抽出图片绝对路径 → 转 /files URL（结构化返回，方便前端显示）
    images = []
    for m in _PATH_RE.findall(reply or ""):
        url = _abs_to_url(m)
        if url and url not in images:
            images.append(url)

    return {"reply": reply, "images": images}
